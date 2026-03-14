import pandas as pd
from typing import Dict, Tuple, Optional
from .base_strategy import BaseStrategy
from datetime import datetime, time

from .index_calculation import IndexCalculation
from utils.logger import get_strategy_logger
logger = get_strategy_logger('t0_reversion')

class T0ReversionStrategy(BaseStrategy):
    """T0日内回转交易策略"""
    
    def __init__(self, config):
        super().__init__(config)
        self.index_calculation = IndexCalculation(self.strategy_params)
        self.current_positions = {}
        self.initial_positions = {}
        self.daily_turnovers_sell = {}
        self.daily_turnovers_buy = {}
        self.max_daily_turnover_rate = self.strategy_params.get('max_daily_turnover_rate', 1.0)
        self.trade_lots_rate = self.strategy_params.get('trade_lots_rate', 0.1)
        # 新增交易阶段管理
        self.trading_phase = "waiting"
        self.phase_start_time = None
        self.trade_unit = 100  # 每手100股
        self.last_signal_times = {}  # 记录每只股票上次信号时间
        self.last_signal_prices = {} # 记录每只股票信号价格
        
    def generate_signal(self, stock_code: str, historical_data: pd.DataFrame, 
                   realtime_data: Dict) -> Tuple[str, float, int, float]:
        """生成T0交易信号 - 简化逻辑"""
        # 更新交易阶段
        current_time = realtime_data.get('timestamp', '')
        self._update_trading_phase(current_time)
        
        # 检查历史数据格式和完整性
        self._validate_historical_data(historical_data)
        
        current_price = realtime_data['price']
        
        # 根据交易阶段调整数据长度要求
        min_data_required = self._get_min_data_required()
        if len(historical_data) < min_data_required:
            logger.info(f"历史数据不足: 需要 {min_data_required} 条，当前 {len(historical_data)} 条")
            return "HOLD", 0, 0, 0.0
        
        try:
            # 计算技术指标
            macd_line, macd_signal_value, macd_histogram = self.index_calculation.calculate_macd(historical_data)
            rsi = self.index_calculation.calculate_rsi(historical_data)
            
            # 计算额外指标
            extra_indicators = {}
            if len(historical_data) >= 15:
                extra_indicators['mfi'] = self.index_calculation.calculate_mfi(historical_data)
                extra_indicators['cci'] = self.index_calculation.calculate_cci(historical_data)
                extra_indicators['bb_position'], extra_indicators['bb_width'], _ = self.index_calculation.calculate_bollinger_bands(historical_data)
                extra_indicators['obv_trend'] = self.index_calculation.calculate_obv(historical_data)
            else:
                extra_indicators = {'mfi': 50.0, 'cci': 0.0, 'bb_position': 0.5, 'bb_width': 0.0, 'obv_trend': 0.0}
            
            volume_analysis = self.index_calculation.analyze_volume(historical_data, realtime_data)
            price_trend = self.index_calculation.analyze_price_trend(historical_data)
            
            # 检查收盘平仓
            if self._is_near_market_close(current_time):
                signal = self._generate_close_signal(stock_code, current_price)
            else:
                # 检查信号冷却时间和价格变化限制
                if not self._check_signal_cooldown(stock_code, current_time, current_price):
                    return "HOLD", 0, 0, 0.0
                # 直接计算交易信号，不再分开计算置信度和买卖分数
                signal = self._calculate_trading_signal(
                    stock_code, macd_line, macd_signal_value, macd_histogram, 
                    rsi, volume_analysis, price_trend, extra_indicators,
                    current_price, current_time
                )
                if signal[0] != "HOLD":
                    self._update_signal_cooldown(stock_code, current_time, current_price)
            
            if signal[0] != "HOLD":
                logger.info(
                    f"生成交易信号: {stock_code} {signal[0]} "
                    f"价格: {signal[1]:.2f} 数量: {signal[2]} "
                    f"置信度: {signal[3]:.3f} "
                    f"(阶段: {self.trading_phase}, RSI: {rsi:.1f}, MFI: {extra_indicators.get('mfi', 50):.1f})"
                )

            return signal
        except Exception as e:
            logger.error(f"信号生成错误 {stock_code}: {e}")
            return "HOLD", 0, 0, 0.0

    def _check_signal_cooldown(self, stock_code: str, current_time: datetime, current_price: float) -> bool:
        """检查信号冷却时间和价格变化限制"""
        phase_params = self._get_phase_trading_params()
        cooldown_minutes = phase_params.get('signal_cooldown', 1)
        min_price_change = phase_params.get('min_price_change', 0.01)
        
        last_time = self.last_signal_times.get(stock_code)
        last_price = self.last_signal_prices.get(stock_code)

        if last_price and last_time:
            price_diff = abs(current_price - last_price) / last_price
            time_diff = (current_time - last_time).total_seconds() / 60.0
            if price_diff < min_price_change and time_diff < cooldown_minutes:
                logger.info(f"价格变化不足: 股票={stock_code}, 价格变化={price_diff:.4f}, 需变化={min_price_change}"
                            f"或冷却中: 时间差={time_diff:.2f}分钟, 需冷却={cooldown_minutes}分钟")
                return False
            del self.last_signal_prices[stock_code]  # 清除记录，避免占用内存
            del self.last_signal_times[stock_code]  # 清除记录，避免占用内存

        return True

    def _update_signal_cooldown(self, stock_code: str, current_time: datetime, current_price: float):
        """更新信号冷却时间记录"""
        self.last_signal_times[stock_code] = current_time
        self.last_signal_prices[stock_code] = current_price

    def _calculate_trading_signal(self, stock_code: str, macd_line: float, macd_signal: float, macd_hist: float, 
                                rsi: float, volume_analysis: float, price_trend: float, extra_indicators: Dict,
                                current_price: float, current_time: str) -> Tuple[str, float, int, float]:
        """统一计算交易信号和置信度"""
        
        # 获取交易阶段参数
        phase_params = self._get_phase_trading_params()
        desired_quantity = phase_params.get('base_lots', 2) * self.trade_lots_rate * self.initial_positions.get(stock_code, 0)
        confidence_threshold = self.config.signal_confidence_threshold * phase_params['confidence_multiplier']

        
        # 统一计算买入和卖出信号强度
        buy_strength, sell_strength = self._calculate_signal_strength(
            macd_line, macd_signal, macd_hist, rsi, volume_analysis, 
            price_trend, extra_indicators
        )
        
        logger.info(f"{current_time} 信号强度:{stock_code} 买入={buy_strength:.3f}, 卖出={sell_strength:.3f} 阈值={confidence_threshold:.3f}")
        
        # 决策逻辑
        if buy_strength > confidence_threshold:
            # 检查交易限制
            if self._check_trading_buy_limits(stock_code):
                logger.info(f"已达到当日最大买入数量 股票: {stock_code}")
            else :
                actual_quantity = self._calculate_trade_quantity(stock_code, "BUY", desired_quantity)
                if actual_quantity >= 100:
                    return "BUY", current_price, actual_quantity, buy_strength
                else:
                    logger.info(f"买入数量不足最小交易单位: 股票={stock_code}, 数量={actual_quantity}")
        
        elif sell_strength > confidence_threshold:
            if self._check_trading_sell_limits(stock_code):
                logger.info(f"已达到当日最大买出数量 股票: {stock_code}")
            else :
                actual_quantity = self._calculate_trade_quantity(stock_code, "SELL", desired_quantity)
                if actual_quantity >= 100:
                    return "SELL", current_price, actual_quantity, sell_strength
                else:
                    logger.info(f"卖出数量不足最小交易单位: 股票={stock_code}, 数量={actual_quantity}")
        
        return "HOLD", 0, 0, 0.0

    def _calculate_signal_strength(self, macd_line: float, macd_signal: float, macd_hist: float, 
                                rsi: float, volume_analysis: float, price_trend: float, 
                                extra_indicators: Dict) -> Tuple[float, float]:
        """统一计算买入和卖出信号强度"""
        
        mfi = extra_indicators.get('mfi', 50.0)
        cci = extra_indicators.get('cci', 0.0)
        bb_position = extra_indicators.get('bb_position', 0.5)
        obv_trend = extra_indicators.get('obv_trend', 0.0)
        
        # 根据交易阶段设置权重
        if self.trading_phase == "morning_opening":
            weights = self._get_opening_weights()
        elif self.trading_phase == "morning_main":
            weights = self._get_morning_weights()
        else:  # afternoon_trading and others
            weights = self._get_afternoon_weights()
        
        # 计算买入信号强度
        buy_factors = {
            'macd': self._normalize_macd_buy_signal(macd_line, macd_hist),
            'rsi': self._normalize_rsi_buy_signal(rsi),
            'mfi': self._normalize_mfi_buy_signal(mfi),
            'volume': volume_analysis,
            'trend': max(0, price_trend),  # 只取正趋势
            'cci': self._normalize_cci_buy_signal(cci),
            'bb': self._normalize_bb_buy_signal(bb_position),
            'obv': max(0, obv_trend)  # 只取正OBV趋势
        }
        
        # 计算卖出信号强度
        sell_factors = {
            'macd': self._normalize_macd_sell_signal(macd_line, macd_hist),
            'rsi': self._normalize_rsi_sell_signal(rsi),
            'mfi': self._normalize_mfi_sell_signal(mfi),
            'volume': volume_analysis,
            'trend': max(0, -price_trend),  # 只取负趋势的绝对值
            'cci': self._normalize_cci_sell_signal(cci),
            'bb': self._normalize_bb_sell_signal(bb_position),
            'obv': max(0, -obv_trend)  # 只取负OBV趋势的绝对值
        }
        
        # 加权计算信号强度
        buy_strength = sum(buy_factors[key] * weights[key] for key in weights)
        sell_strength = sum(sell_factors[key] * weights[key] for key in weights)
        
        # 确保在0-1范围内
        buy_strength = max(0, min(1, buy_strength))
        sell_strength = max(0, min(1, sell_strength))
        
        return buy_strength, sell_strength

    def _get_opening_weights(self) -> Dict[str, float]:
        """开盘阶段权重"""
        return {
            'macd': 0.15,
            'rsi': 0.15,
            'mfi': 0.10,
            'volume': 0.20,
            'trend': 0.20,
            'cci': 0.05,
            'bb': 0.10,
            'obv': 0.05
        }

    def _get_morning_weights(self) -> Dict[str, float]:
        """上午主要交易阶段权重"""
        return {
            'macd': 0.20,
            'rsi': 0.15,
            'mfi': 0.10,
            'volume': 0.15,
            'trend': 0.15,
            'cci': 0.10,
            'bb': 0.10,
            'obv': 0.05
        }

    def _get_afternoon_weights(self) -> Dict[str, float]:
        """下午交易阶段权重"""
        return {
            'macd': 0.25,
            'rsi': 0.15,
            'mfi': 0.10,
            'volume': 0.15,
            'trend': 0.15,
            'cci': 0.10,
            'bb': 0.05,
            'obv': 0.05
        }

    # 专门的信号归一化方法
    def _normalize_macd_buy_signal(self, macd_line: float, macd_hist: float) -> float:
        """MACD买入信号归一化"""
        if macd_line > 0.001 and macd_hist > 0.001:
            return 1.0
        elif macd_line > -0.001 and macd_hist > -0.001:
            return 0.5
        else:
            return 0.0

    def _normalize_macd_sell_signal(self, macd_line: float, macd_hist: float) -> float:
        """MACD卖出信号归一化"""
        if macd_line < -0.001 and macd_hist < -0.001:
            return 1.0
        elif macd_line < 0.001 and macd_hist < 0.001:
            return 0.5
        else:
            return 0.0

    def _normalize_rsi_buy_signal(self, rsi: float) -> float:
        """RSI买入信号归一化"""
        if rsi < 30:
            return 1.0
        elif rsi < 40:
            return 0.7
        elif rsi < 50:
            return 0.3
        else:
            return 0.0

    def _normalize_rsi_sell_signal(self, rsi: float) -> float:
        """RSI卖出信号归一化"""
        if rsi > 70:
            return 1.0
        elif rsi > 60:
            return 0.7
        elif rsi > 50:
            return 0.3
        else:
            return 0.0

    def _normalize_mfi_buy_signal(self, mfi: float) -> float:
        """MFI买入信号归一化"""
        if mfi < 20:
            return 1.0
        elif mfi < 30:
            return 0.7
        elif mfi < 40:
            return 0.3
        else:
            return 0.0

    def _normalize_mfi_sell_signal(self, mfi: float) -> float:
        """MFI卖出信号归一化"""
        if mfi > 80:
            return 1.0
        elif mfi > 70:
            return 0.7
        elif mfi > 60:
            return 0.3
        else:
            return 0.0

    def _normalize_cci_buy_signal(self, cci: float) -> float:
        """CCI买入信号归一化"""
        if cci < -100:
            return 1.0
        elif cci < -50:
            return 0.5
        else:
            return 0.0

    def _normalize_cci_sell_signal(self, cci: float) -> float:
        """CCI卖出信号归一化"""
        if cci > 100:
            return 1.0
        elif cci > 50:
            return 0.5
        else:
            return 0.0

    def _normalize_bb_buy_signal(self, bb_position: float) -> float:
        """布林带买入信号归一化"""
        if bb_position < 0.2:
            return 1.0
        elif bb_position < 0.3:
            return 0.5
        else:
            return 0.0

    def _normalize_bb_sell_signal(self, bb_position: float) -> float:
        """布林带卖出信号归一化"""
        if bb_position > 0.8:
            return 1.0
        elif bb_position > 0.7:
            return 0.5
        else:
            return 0.0

    def _update_trading_phase(self, current_time: datetime):
        """更新交易阶段 - 针对datetime对象"""
        try:
            hour = current_time.hour
            minute = current_time.minute
            
            if hour == 9 and minute >= 30:
                new_phase = "morning_opening"
            elif hour == 10 and minute < 30:
                new_phase = "morning_main" 
            elif (hour == 10 and minute >= 30) or hour == 11:
                new_phase = "morning_main"
            elif 13 <= hour < 15:
                new_phase = "afternoon_trading"
            else:
                new_phase = "waiting"
            
            if new_phase != self.trading_phase:
                logger.info(f"交易阶段切换: {self.trading_phase} -> {new_phase}")
                self.trading_phase = new_phase
                self.phase_start_time = current_time
                
        except Exception as e:
            logger.warning(f"更新交易阶段错误: {e}")
    
    def _get_min_data_required(self) -> int:
        """根据交易阶段返回最小数据要求"""
        phase_requirements = {
            "morning_opening": 5,   # 只需要5分钟数据
            "morning_main": 30,     # 需要30分钟数据
            "afternoon_trading": 10, # 需要10分钟数据（结合上午数据）
            "waiting": 60
        }
        return phase_requirements.get(self.trading_phase, 60)
    
    def _get_phase_trading_params(self) -> Dict:
        """获取各阶段的交易参数 - 修正基础数量"""
        base_params = {
            "morning_opening": {
                'confidence_multiplier': 1.2,   # 提高置信度要求
                'base_lots': 0.5,               # 0.5倍最小单位
                'min_price_change': 0.03,       # 最小价格变化
                'signal_cooldown': 1            # 信号冷却时间(分钟)
            },
            "morning_main": {
                'confidence_multiplier': 1.14,
                'base_lots': 1,                 # 1倍最小单位
                'min_price_change': 0.02,       # 最小价格变化
                'signal_cooldown': 2            # 信号冷却时间(分钟)
            },
            "afternoon_trading": {
                'confidence_multiplier': 1.17,
                'base_lots': 0.8,               # 0.8倍最小单位
                'min_price_change': 0.25,       # 最小价格变化
                'signal_cooldown': 3            # 信号冷却时间(分钟)
            },
            "waiting": {
                'confidence_multiplier': 2.0,
                'base_lots': 0,              # 0手
                'min_price_change': 1,   # 最小价格变化(5‰)
                'signal_cooldown': 60         # 信号冷却时间(分钟)
            }
        }
        return base_params.get(self.trading_phase, {"position_ratio": 1.0, "confidence_multiplier": 1.0, "base_lots": 2})

    def _calculate_trade_quantity(self, stock_code: str, signal_type: str, desired_quantity: int) -> int:
        """计算实际交易数量，考虑T+1制度限制"""
        if desired_quantity <= 0:
            return 0
        
        if signal_type == "BUY":
            # 获取已买入的当日交易额
            daily_turnover_buy = self.daily_turnovers_buy.get(stock_code, 0)
            total_can_buy = self.initial_positions.get(stock_code, 0) * self.max_daily_turnover_rate
            # T+1制度下：买入不受限制，但需要考虑资金和交易额度
            # 主要限制：交易额度限制
            remaining_turnover = max(0, total_can_buy - daily_turnover_buy)
            
            # 取较小值作为最大买入数量
            should_buy = min(remaining_turnover, desired_quantity)
            
            # 确保是100的整数倍
            actual_quantity = (should_buy // self.trade_unit) * self.trade_unit

            if should_buy > 0 and actual_quantity < self.trade_unit and self.trade_unit < remaining_turnover:
                logger.info(f"买入数量不足最小单位，调整为一手: 股票={stock_code}, 计算数量={actual_quantity}")
                actual_quantity = self.trade_unit  # 至少买入一手
            
            logger.info(f"买入数量计算: 股票={stock_code}, 期望={desired_quantity}, "
                        f"剩余额度={remaining_turnover}, 实际={actual_quantity}")
            
            return actual_quantity
            
        elif signal_type == "SELL":
            daily_turnover_sell = self.daily_turnovers_sell.get(stock_code, 0)
            total_can_sell = self.initial_positions.get(stock_code, 0) * self.max_daily_turnover_rate

            # T+1制度下：只能卖出昨日持仓（初始持仓），不能卖出当日买入的股票
            # 考虑交易额度限制
            remaining_turnover = max(0, total_can_sell - daily_turnover_sell)
            
            # 实际可卖出数量
            should_sell = min(remaining_turnover, desired_quantity)
            
            # 确保是100的整数倍
            actual_quantity = (should_sell // self.trade_unit) * self.trade_unit

            if should_sell > 0 and actual_quantity < self.trade_unit and self.trade_unit < remaining_turnover:
                logger.info(f"买出数量不足最小单位，调整为一手: 股票={stock_code}, 计算数量={actual_quantity}")
                actual_quantity = self.trade_unit  # 至少卖出一手
            
            logger.info(f"卖出数量计算: 股票={stock_code}, 期望={desired_quantity}, "
                        f"剩余额度={remaining_turnover}, 实际={actual_quantity}")
            
            return actual_quantity
        
        return 0
    
    def _validate_historical_data(self, historical_data: pd.DataFrame):
        """验证历史数据格式"""
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in historical_data.columns]
        if missing_columns:
            raise ValueError(f"历史数据缺少必要列: {missing_columns}")
    
    def _is_near_market_close(self, current_time: datetime) -> bool:
        """检查是否接近收盘时间 - 通过配置获取"""
        try:
            # 从配置获取收盘时间参数
            close_start_str = self.strategy_params.get("close_position_start_time", "14:50:00")
            market_close_str = self.strategy_params.get("market_close_time", "15:00:00")
            
            # 解析配置中的时间字符串
            close_start = datetime.strptime(close_start_str, '%H:%M:%S').time()
            market_close = datetime.strptime(market_close_str, '%H:%M:%S').time()
            
            current_time_only = current_time.time()
            return close_start <= current_time_only <= market_close
            
        except Exception as e:
            logger.warning(f"收盘时间判断错误: {e}")
            return False

    def _is_near_market_close_(self, current_time: datetime) -> bool:
        """检查是否接近收盘集合竞价时间 - 通过配置获取"""
        try:
            # 从配置获取收盘时间参数
            close_start_str = self.strategy_params.get("close_position_start_time", "14:56:30")
            market_close_str = self.strategy_params.get("market_close_time", "14:57:00")
            
            # 解析配置中的时间字符串
            close_start = datetime.strptime(close_start_str, '%H:%M:%S').time()
            market_close = datetime.strptime(market_close_str, '%H:%M:%S').time()
            
            current_time_only = current_time.time()
            return close_start <= current_time_only <= market_close
            
        except Exception as e:
            logger.warning(f"收盘时间判断错误: {e}")
            return False
    
    # 生成收盘平仓信号,用于清理当日持仓敞口
    def _generate_close_signal(self, stock_code: str, current_price: float) -> Tuple[str, float, int, float]:
        current_position = self.current_positions.get(stock_code, 0)
        initial_position = self.initial_positions.get(stock_code, 0)
        position_diff = current_position - initial_position
        
        if position_diff > 0:
            return "SELL", current_price, position_diff, 1
        elif position_diff < 0:
            return "BUY", current_price, abs(position_diff), 1
        
        return "HOLD", 0, 0, 0.0
    
    # 检查每日交易额度限制
    def _check_trading_buy_limits(self, stock_code: str) -> bool:
        daily_turnover_buy = self.daily_turnovers_buy.get(stock_code, 0)
        # 检查剩余交易额度是否小于最小买卖单位
        return self.max_daily_turnover_rate * self.initial_positions.get(stock_code, 0) - daily_turnover_buy < self.trade_unit
    
    def _check_trading_sell_limits(self, stock_code: str) -> bool:
        daily_turnover_sell = self.daily_turnovers_sell.get(stock_code, 0)
        # 检查剩余交易额度是否小于最小买卖单位
        return self.max_daily_turnover_rate * self.initial_positions.get(stock_code, 0) - daily_turnover_sell < self.trade_unit
    
    def set_initial_position(self, stock_code: str, position: int):
        self.initial_positions[stock_code] = position
        self.current_positions[stock_code] = position
        self.daily_turnovers_buy[stock_code] = 0
        self.daily_turnovers_sell[stock_code] = 0

    # 更新当前持仓和当日交易额
    def update_position(self, stock_code: str, position_change: int):
        if stock_code not in self.current_positions:
            self.current_positions[stock_code] = 0
        self.current_positions[stock_code] += position_change
        # 更新当日买入交易额
        if position_change > 0:
            if stock_code not in self.daily_turnovers_buy:
                self.daily_turnovers_buy[stock_code] = 0
            self.daily_turnovers_buy[stock_code] += position_change
        # 更新当日卖出交易额
        elif position_change < 0:
            if stock_code not in self.daily_turnovers_sell:
                self.daily_turnovers_sell[stock_code] = 0
            self.daily_turnovers_sell[stock_code] += abs(position_change)