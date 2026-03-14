import pandas as pd
from datetime import datetime, timedelta, time as dt_time 
from typing import Dict, List, Tuple, Optional
import os
import sys
import json

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies import create_strategy, get_available_strategies
from .real_data_provider import RealDataProvider
from .position_manager import PositionManager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hq.tick_storage import TickStorage, TickData

from .k_minute_data_manager import MinuteDataManager

from utils.logger import get_core_logger
logger = get_core_logger('real_trading_engine')

def append_advice(advise_data_dir: str, message: str):
    """向建议文件追加内容"""
    # 确保目录存在
    os.makedirs(advise_data_dir, exist_ok=True)
    
    # 生成文件名
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"advice_{today}.txt"
    filepath = os.path.join(advise_data_dir, filename)
    
    try:
        # 以追加模式打开文件
        with open(filepath, 'a', encoding='utf-8') as f:
            # 如果是新文件，写入文件头
            if f.tell() == 0:
                f.write(f"=== 交易建议记录 {today} ===\n\n")
            
            # 写入带时间戳的消息
            timestamp = datetime.now().strftime("%H:%M:%S")
            full_message = f"[{timestamp}] {message}\n"
            f.write(full_message)
        
        print(f"建议已记录到: {filepath}")
        
    except Exception as e:
        print(f"写入建议失败: {e}")

class RealTradingEngine:
    """真实数据交易引擎"""
    
    def __init__(self, config, data_dir: str = "tick_data"):
        self.config = config
        self.data_provider = RealDataProvider(config, data_dir)
        self.position_manager = PositionManager(config)
        self.current_strategy = None
        self.is_running = False
        self.monitor_stocks = []
        self.current_date = datetime.now().strftime('%Y%m%d')
        self.minute_data_manager = MinuteDataManager(config)
        # 历史数据缓存
        self._historical_cache = {}
        self._historical_cache_date = None
        self._cache_initialized = False
        
        # 初始化策略
        self._init_strategy()
    
    def _init_strategy(self):
        """初始化策略"""
        try:
            self.current_strategy = create_strategy(self.config.strategy_name, self.config)
            logger.info(f"策略初始化完成: {self.config.strategy_name}")
        except ValueError as e:
            logger.error(f"策略初始化失败: {str(e)}")
            # 尝试使用默认策略
            try:
                self.current_strategy = create_strategy("MeanReversion", self.config)
                self.config.strategy_name = "MeanReversion"
                logger.info(f"已切换到默认策略: MeanReversion")
            except Exception as fallback_error:
                logger.error(f"默认策略也初始化失败: {str(fallback_error)}")
                raise
        except Exception as e:
            logger.error(f"策略初始化意外错误: {str(e)}")
            raise
    
    def set_current_date(self, date_str: str):
        """设置当前回放日期"""
        self.current_date = date_str
        self.data_provider.set_current_date(date_str)
    
    def set_monitor_stocks(self, stock_codes: List[str]):
        """设置监控股票列表"""
        if stock_codes is None:
            stock_codes = []
        self.monitor_stocks = stock_codes[:self.config.max_stocks_monitor]
        logger.info(f"预先加载监控股票K线历史数据: {self.monitor_stocks}")
        for stock_code in self.monitor_stocks:
            # t0策略需要加载当日分钟k线数据
            if self.config.strategy_name == "T0Reversion":
                if self.position_manager.get_position(stock_code) == None:
                    quantity = 0
                else:
                    quantity = self.position_manager.get_position(stock_code).quantity
                self.current_strategy.set_initial_position(stock_code, quantity)
                if self.config.tick_data_source != "replayer":
                    self.minute_data_manager.load_historical_minute_data(stock_code, self.current_date)
                    # self.minute_data_manager.plot_minute_chart(stock_code, self.current_date, f"plog/{stock_code}_initial_minute_chart.png")
            else :
                historical_data = self.data_provider.load_historical_data(stock_code, days=30)
    
    def update_with_tick_data(self, tick_data: TickData):
        """使用tick数据更新引擎状态"""
        try:
            # 跳过无效数据
            if tick_data.volume <= 0 or tick_data.price <= 0:
                logger.debug(f"跳过无效tick数据: {tick_data.code} 价格: {tick_data.price} 成交量: {tick_data.volume}")
                return
            
            # 更新数据提供器
            self.data_provider.update_tick_data(tick_data)

            # 更新分钟K线数据
            self.minute_data_manager.update_with_tick_data(tick_data)
            
            # 更新持仓价格
            price_data = {tick_data.code: tick_data.price}
            self.position_manager.update_position_prices(price_data)
            
            # 检查持仓风险
            if self.config.position_risk_check and tick_data.code in self.position_manager.positions:
                self.position_manager.check_risk_limits(tick_data.code, tick_data.price)
        except Exception as e:
            logger.error(f"处理tick数据失败: {e}")
    
    def analyze_with_tick_data(self, tick_data: TickData) -> Dict:
        """基于tick数据进行分析（带调试信息）"""
        try:
            # 调试：检查tick数据
            logger.debug(f"分析tick数据: {tick_data.code}, 价格: {tick_data.price}, 成交量: {tick_data.volume}")
            
            if tick_data.price <= 0:
                logger.warning(f"股票 {tick_data.code} 价格异常: {tick_data.price}")
                return self._create_hold_recommendation(tick_data.code, "价格异常", tick_data.timestamp)
            
            # 根据策略类型获取不同的历史数据
            if self.config.strategy_name == "T0Reversion":
                # T0策略使用分钟K线数据
                historical_data = self.minute_data_manager.get_historical_data_df(tick_data.code)
                data_type = "minute"
                if historical_data is None or len(historical_data) == 0:
                    logger.debug(f"股票 {tick_data.code} 分钟K线数据为空")
                    return self._create_hold_recommendation(tick_data.code, "分钟K线数据为空", tick_data.timestamp)
            else:
                # 其他策略使用日K线数据
                cache_key = f"{tick_data.code}_historical"
                current_date = tick_data.timestamp.date() if tick_data.timestamp else datetime.now().date()
                
                if (cache_key not in self._historical_cache or 
                    self._historical_cache_date != current_date):
                    historical_data = self.data_provider.load_historical_data(tick_data.code, days=30)
                    self._historical_cache[cache_key] = historical_data
                    self._historical_cache_date = current_date
                    logger.debug(f"更新日K线数据缓存: {tick_data.code}, 数据长度: {len(historical_data)}")
                else:
                    historical_data = self._historical_cache[cache_key]
                
                data_type = "daily"

                # 调试：检查历史数据
                if historical_data is None or len(historical_data) == 0:
                    logger.warning(f"股票 {tick_data.code} 日K线数据为空")
                    return self._create_hold_recommendation(tick_data.code, "日K线数据为空", tick_data.timestamp)
            
            # 获取实时数据
            realtime_data = self.data_provider.get_realtime_data(tick_data.code)
            logger.debug(f"实时数据: {realtime_data}")
            
            # 生成交易信号
            signal, price, quantity, confidence = self.current_strategy.generate_signal(
                tick_data.code, historical_data, realtime_data)[:4]
            
            # logger.info(f"{tick_data.timestamp} 策略信号: {signal}, 价格: {price}, 数量: {quantity}, 置信度: {confidence}")
            
            # 风险控制检查
            if signal != "HOLD":
                if self.config.position_risk_check and not self._risk_control_check(tick_data.code, signal, price, quantity, confidence):
                    signal, price, quantity, confidence = "HOLD", 0, 0, 0
                    logger.warning("风险控制拒绝交易")
            
            # 根据数据类型构建建议
            if data_type == "minute":
                # 分钟K线数据的建议构建
                recommendation = self._build_minute_recommendation(
                    tick_data, signal, price, quantity, confidence, historical_data
                )
            else:
                # 日K线数据的建议构建
                recommendation = self._build_daily_recommendation(
                    tick_data, signal, price, quantity, confidence, historical_data
                )
            
            logger.debug(f"生成推荐: {recommendation}")
            return recommendation
            
        except Exception as e:
            logger.error(f"分析股票 {tick_data.code} 时出错: {str(e)}", exc_info=True)
            return self._create_hold_recommendation(tick_data.code, str(e), tick_data.timestamp)

    def _build_minute_recommendation(self, tick_data: TickData, signal: str, price: float, 
                               quantity: int, confidence: float, 
                               historical_data: pd.DataFrame) -> Dict:
        """构建基于分钟K线的交易建议"""
        
        # 计算分钟级别的技术指标
        volume_ratio = self._calculate_minute_volume_ratio(tick_data, historical_data)
        price_trend = self._calculate_minute_price_trend(historical_data)
        volatility = self._calculate_minute_volatility(historical_data)
        
        # 获取当前分钟K线的买卖盘信息
        current_bar = self.minute_data_manager.get_current_minute_bar(tick_data.code)
        if current_bar:
            bid_ask_spread = current_bar.ask_price - current_bar.bid_price if current_bar.ask_price > current_bar.bid_price else 0
            bid_ask_ratio = current_bar.bid_volume / current_bar.ask_volume if current_bar.ask_volume > 0 else 1.0
        else:
            bid_ask_spread = 0
            bid_ask_ratio = 1.0
        
        change_rate = tick_data.change_percent / 100.0 if tick_data.change_percent is not None else 0.0
        recommendation = {
            'stock_code': tick_data.code,
            'stock_name': tick_data.name,
            'signal': signal,
            'price': round(price, 2) if price > 0 else 0,
            'quantity': quantity,
            'amount': round(price * quantity, 2) if price > 0 and quantity > 0 else 0,
            'confidence': round(confidence, 3),
            'timestamp': tick_data.timestamp.isoformat(),
            'strategy': self.config.strategy_name,
            'data_type': 'minute',
            'current_price': round(tick_data.price, 2),
            'volume_ratio': round(volume_ratio, 2),
            'change_rate': round(change_rate, 4),
            'price_trend': round(price_trend, 4),
            'volatility': round(volatility, 4),
            'bid_ask_spread': round(bid_ask_spread, 3),
            'bid_ask_ratio': round(bid_ask_ratio, 2),
            'time_frame': 'intraday'
        }
    
        # 添加分钟级别的额外信息
        if len(historical_data) > 0:
            recommendation.update({
                'minute_high': round(historical_data['high'].iloc[-1], 2),
                'minute_low': round(historical_data['low'].iloc[-1], 2),
                'minute_volume': int(historical_data['volume'].iloc[-1]),
                'minutes_count': len(historical_data)
            })

        return recommendation

    def _calculate_minute_volume_ratio(self, tick_data: TickData, historical_data: pd.DataFrame) -> float:
        """计算分钟成交量比率"""
        if len(historical_data) < 5:
            return 1.0
        
        # 获取当前分钟成交量（从正在构建的K线）
        current_bar = self.minute_data_manager.get_current_minute_bar(tick_data.code)
        if current_bar:
            current_volume = current_bar.volume
        else:
            current_volume = 0
        
        # 计算过去N分钟的平均成交量
        avg_volume = historical_data['volume'].tail(30).mean()
        
        if avg_volume == 0:
            return 1.0
        
        return current_volume / avg_volume if current_volume > 0 else 0

    def _calculate_minute_price_trend(self, historical_data: pd.DataFrame) -> float:
        """计算分钟价格趋势"""
        if len(historical_data) < 10:
            return 0.0
        
        # 短期趋势（最近5分钟）
        short_trend = (historical_data['close'].iloc[-1] - historical_data['close'].iloc[-5]) / historical_data['close'].iloc[-5]
        
        # 中期趋势（最近15分钟）
        if len(historical_data) >= 15:
            medium_trend = (historical_data['close'].iloc[-1] - historical_data['close'].iloc[-15]) / historical_data['close'].iloc[-15]
        else:
            medium_trend = short_trend
        
        return (short_trend + medium_trend) / 2

    def _calculate_minute_volatility(self, historical_data: pd.DataFrame) -> float:
        """计算分钟波动率"""
        if len(historical_data) < 5:
            return 0.0
        
        # 计算最近N根K线的价格范围百分比
        recent_data = historical_data.tail(10)
        price_ranges = (recent_data['high'] - recent_data['low']) / recent_data['close']
        return price_ranges.mean()

    def _build_daily_recommendation(self, tick_data: TickData, signal: str, price: float, 
                              quantity: int, confidence: float, 
                              historical_data: pd.DataFrame) -> Dict:
        """构建基于日K线的交易建议"""
        
        # 计算日线级别的技术指标
        volume_ratio = self._calculate_daily_volume_ratio(tick_data, historical_data)
        price_trend = self._calculate_daily_price_trend(historical_data)
        volatility = self._calculate_daily_volatility(historical_data)
        
        change_rate = tick_data.change_percent / 100.0 if tick_data.change_percent is not None else 0.0
        
        recommendation = {
            'stock_code': tick_data.code,
            'stock_name': tick_data.name,
            'signal': signal,
            'price': round(price, 2) if price > 0 else 0,
            'quantity': quantity,
            'amount': round(price * quantity, 2) if price > 0 and quantity > 0 else 0,
            'confidence': round(confidence, 3),
            'timestamp': tick_data.timestamp,
            'strategy': self.config.strategy_name,
            'data_type': 'daily',
            'current_price': round(tick_data.price, 2),
            'volume_ratio': round(volume_ratio, 2),
            'change_rate': round(change_rate, 4),
            'price_trend': round(price_trend, 4),
            'volatility': round(volatility, 4),
            'time_frame': 'daily'
        }
        
        # 添加日线级别的额外信息
        if len(historical_data) > 0:
            recommendation.update({
                'daily_high': round(historical_data['high'].iloc[-1], 2),
                'daily_low': round(historical_data['low'].iloc[-1], 2),
                'daily_volume': int(historical_data['volume'].iloc[-1]),
                'days_count': len(historical_data),
                'ma5': round(historical_data['close'].tail(5).mean(), 2) if len(historical_data) >= 5 else 0,
                'ma10': round(historical_data['close'].tail(10).mean(), 2) if len(historical_data) >= 10 else 0
            })
        
        return recommendation

    def _calculate_daily_volume_ratio(self, tick_data: TickData, historical_data: pd.DataFrame) -> float:
        """计算日成交量比率"""
        if len(historical_data) < 5:
            return 1.0
        
        # 使用当日实时成交量与历史平均成交量比较
        current_volume = tick_data.volume
        avg_volume = historical_data['volume'].tail(20).mean()
        
        if avg_volume == 0:
            return 1.0
        
        return current_volume / avg_volume

    def _calculate_daily_price_trend(self, historical_data: pd.DataFrame) -> float:
        """计算日价格趋势"""
        if len(historical_data) < 10:
            return 0.0
        
        # 短期趋势（最近5天）
        short_trend = (historical_data['close'].iloc[-1] - historical_data['close'].iloc[-5]) / historical_data['close'].iloc[-5]
        
        # 中期趋势（最近20天）
        if len(historical_data) >= 20:
            medium_trend = (historical_data['close'].iloc[-1] - historical_data['close'].iloc[-20]) / historical_data['close'].iloc[-20]
        else:
            medium_trend = short_trend
        
        return (short_trend + medium_trend) / 2

    def _calculate_daily_volatility(self, historical_data: pd.DataFrame) -> float:
        """计算日波动率"""
        if len(historical_data) < 10:
            return 0.0
        
        # 计算最近N天的价格范围百分比
        recent_data = historical_data.tail(10)
        price_ranges = (recent_data['high'] - recent_data['low']) / recent_data['close']
        return price_ranges.mean()
        
    def _calculate_volume_ratio(self, tick_data: TickData, historical_data: pd.DataFrame) -> float:
        """计算成交量比率（增强版）"""
        try:
            if (historical_data is None or len(historical_data) == 0 or 
                'volume_ma5' not in historical_data.columns):
                return 1.0
            
            current_volume_ma5 = historical_data['volume_ma5'].iloc[-1]
            if current_volume_ma5 <= 0:
                return 1.0
            
            # 确保tick_data.volume是有效值
            if tick_data.volume <= 0:
                return 1.0
                
            volume_ratio = tick_data.volume / current_volume_ma5
            return round(float(volume_ratio), 2)  # 确保返回Python float而不是numpy类型
            
        except Exception as e:
            logger.debug(f"计算成交量比率失败: {e}")
            return 1.0
    
    def _create_hold_recommendation(self, stock_code: str, error_msg: str = "", timestamp: datetime = datetime.now()) -> Dict:
        """创建HOLD建议"""
        return {
            'stock_code': stock_code,
            'signal': 'HOLD',
            'price': 0,
            'quantity': 0,
            'amount': 0,
            'confidence': 0,
            'timestamp': timestamp,
            'strategy': self.config.strategy_name,
            'current_price': 0,
            'volume_ratio': 0,
            'change_rate': 0,
            'error': error_msg
        }
    
    def _risk_control_check(self, stock_code: str, signal: str, price: float, quantity: int, confidence: float) -> bool:
        """风险控制检查 - 修正逻辑"""
        trade_amount = price * quantity
        
        # 1. 检查单日亏损限制 - 通过position_manager获取
        daily_trade_pnl = self.position_manager.daily_trade_pnl
        if daily_trade_pnl < -self.config.initial_capital * self.config.max_daily_loss:
            logger.warning(f"达到单日最大亏损限制({self.config.max_daily_loss*100}%)，当前亏损: {daily_trade_pnl:.2f}，停止交易")
            return False
        
        # 2. 检查持仓限制 - 通过position_manager检查
        if not self.position_manager.check_position_limit(stock_code, signal, price, quantity):
            logger.warning(f"超过持仓限制: {stock_code}")
            return False
        
        # 3. 检查单只股票风险暴露
        current_position = self.position_manager.positions.get(stock_code)
        current_position_value = current_position.market_value if current_position else 0
        new_position_value = current_position_value + trade_amount
        
        # 单只股票持仓不能超过资金的一定比例（防止过度集中）
        single_stock_exposure = new_position_value / self.config.initial_capital
        max_single_exposure = self.config.max_single_loss * 3  # 例如止损2%，最大暴露6%
        
        if single_stock_exposure > max_single_exposure:
            logger.warning(
                f"单只股票风险暴露过高: {stock_code} 暴露={single_stock_exposure*100:.2f}% > "
                f"限制={max_single_exposure*100}%"
            )
            return False
        
        # 4. 检查交易金额合理性（基于最小交易金额配置）
        if trade_amount < self.config.min_trade_amount:
            logger.warning(f"交易金额过小: {trade_amount:.2f} < 最小要求={self.config.min_trade_amount}")
            return False
        
        # 5. 检查信号置信度
        if confidence < 0.6:  # 置信度阈值
            logger.warning(f"信号置信度过低: {confidence:.3f} < 0.6")
            return False
        
        # 6. 检查预期盈利空间
        if signal == "BUY":
            expected_profit_ratio = self._calculate_expected_profit(stock_code, price)
            if expected_profit_ratio < self.config.min_profit_threshold:
                logger.warning(
                    f"预期盈利空间不足: {expected_profit_ratio*100:.2f}% < "
                    f"要求={self.config.min_profit_threshold*100}%"
                )
                return False
        
        return True

    def _calculate_expected_profit(self, stock_code: str, current_price: float) -> float:
        """计算预期盈利比例"""
        try:
            # 基于当前策略计算预期盈利
            if self.config.strategy_name == "MeanReversion":
                # 均值回归策略：预期回归到均线
                hist_data = self.data_provider.historical_data.get(stock_code)
                if hist_data is not None and len(hist_data) > 0:
                    ma5 = hist_data['ma5'].iloc[-1]
                    deviation = (ma5 - current_price) / current_price
                    return abs(deviation) * 0.8  # 假设能捕获80%的回归空间
            
            elif self.config.strategy_name == "TrendFollowing":
                # 趋势跟踪策略：预期延续趋势
                return self.config.min_profit_threshold * 1.5  # 预期1.5倍最小要求
            
            elif self.config.strategy_name == "Breakout":
                # 突破策略：预期突破后有一定空间
                return self.config.min_profit_threshold * 2.0  # 预期2倍最小要求
            
            # 默认返回最小要求
            return self.config.min_profit_threshold
            
        except Exception as e:
            logger.warning(f"计算预期盈利失败: {e}")
            return self.config.min_profit_threshold

    def _calculate_position_size(self, price: float, signal_type: str, stock_code: str = None) -> int:
        """计算仓位大小 - 基于风险管理的正确逻辑"""
        
        # 方法1: 基于单只股票最大风险计算
        if stock_code:
            current_position = self.position_manager.positions.get(stock_code, {})
            current_value = current_position.market_value
            
            # 剩余可投入金额 = 最大风险暴露 - 当前持仓
            max_single_value = self.config.initial_capital * self.config.max_single_loss * 3
            available_amount = max(0, max_single_value - current_value)
            
            # 取可用金额和基础仓位的较小值
            base_amount = min(available_amount, self.config.initial_capital * 0.1)
        else:
            # 方法2: 基础仓位计算
            base_amount = self.config.initial_capital * 0.1
        
        # 根据策略调整
        strategy_factors = {
            "MeanReversion": 1.0,
            "TrendFollowing": 1.2, 
            "Breakout": 1.5
        }
        strategy_factor = strategy_factors.get(self.config.strategy_name, 1.0)
        adjusted_amount = base_amount * strategy_factor
        
        # 确保不低于最小交易金额
        final_amount = max(adjusted_amount, self.config.min_trade_amount)
        
        # 计算股数（按100股取整）
        quantity = int(final_amount / price / 100) * 100
        quantity = max(quantity, 100)  # 至少100股
        
        # 最终金额验证
        final_trade_amount = quantity * price
        if final_trade_amount > self.config.initial_capital * 0.15:  # 单笔不超过15%
            quantity = int(self.config.initial_capital * 0.15 / price / 100) * 100
        
        return quantity

    def _calculate_stop_loss_price(self, entry_price: float, signal: str) -> float:
        """计算止损价格 - 这才是max_single_loss的正确应用"""
        if signal == "BUY":
            stop_loss_price = entry_price * (1 - self.config.max_single_loss)
        else:  # SELL (做空)
            stop_loss_price = entry_price * (1 + self.config.max_single_loss)
        
        return stop_loss_price

    def _check_stop_loss(self, stock_code: str, current_price: float) -> bool:
        """检查是否触发止损"""
        position = self.position_manager.positions.get(stock_code)
        if position:
            stop_loss_price = position.get('stop_loss_price')
            
            if stop_loss_price is not None:
                if (position['signal'] == "BUY" and current_price <= stop_loss_price) or \
                   (position['signal'] == "SELL" and current_price >= stop_loss_price):
                    logger.warning(
                        f"触发止损: {stock_code} 当前价={current_price:.2f} "
                        f"止损价={stop_loss_price:.2f}"
                    )
                    return True
        return False
    
    def execute_trade(self, recommendation: Dict) -> bool:
        """执行交易"""
        if recommendation is None or recommendation['signal'] == 'HOLD':
            return False
        
        stock_code = recommendation['stock_code']
        stock_name = recommendation['stock_name']
        signal = recommendation['signal']
        price = recommendation['price']
        quantity = recommendation['quantity']
        current_amount = recommendation.get('timestamp', datetime.now())
   
        # 验证参数
        if price <= 0 or quantity <= 0:
            logger.warning(f"交易参数无效: {stock_code} 价格={price}, 数量={quantity}")
            return False

        # 查看交易执行标记，如果不允许执行交易，则以建议的方式显示
        if not self.config.trade_flag:
            logger.info(f"建议{signal} {stock_code}({stock_name}) @{price} {quantity}股 止损价:{stop_loss_price}")
            return False
        
        # 计算止损价格
        stop_loss_price = self._calculate_stop_loss_price(price, signal)
        append_advice(self.config.advise_data_dir, f"建议{signal} {stock_code}({stock_name}) @{price} {quantity}股 止损价:{stop_loss_price}")
        # 执行交易逻辑
        if signal == "BUY":
            success = self.position_manager.buy_position(stock_code, stock_name, signal, price, quantity, stop_loss_price, current_amount)
        else:
            success = self.position_manager.sell_position(stock_code, stock_name, signal, price, quantity, current_amount)

        # 买则增加持仓，卖则减少持仓
        position_change = quantity if signal == "BUY" else -quantity
        # 更新策略持仓状态
        self.current_strategy.update_position(stock_code, position_change)
        success = True  # 模拟成功

        if success:
            logger.info(f"执行交易: {signal} {stock_code} {quantity}股 @ {price}, 止损价: {stop_loss_price:.2f}")
            return True
        else:
            logger.warning(f"交易执行失败: {signal} {stock_code}")
            return False
    
    def is_trading_time(self) -> bool:
        """判断是否为交易时间"""
        now = datetime.now()
        current_time = now.time()
        current_weekday = now.weekday()
        
        if current_weekday >= 5:
            return False
        
        morning_start = dt_time(9, 25)
        morning_end = dt_time(11, 30)
        afternoon_start = dt_time(12, 59)
        afternoon_end = dt_time(15, 0)
        
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)

    def get_trading_summary(self) -> Dict:
        """获取交易摘要"""
        try:
            position_summary = self.position_manager.get_position_summary()
            
            return {
                'strategy': self.config.strategy_name,
                'initial_capital': self.config.initial_capital,
                'monitor_stocks': self.monitor_stocks,
                'current_date': self.current_date,
                'is_trading_hours': True if self.config.tick_data_source == 'replayer' else self.is_trading_time(),  # 回放模式下总是交易时间
                **position_summary
            }
        except Exception as e:
            logger.error(f"获取交易摘要失败: {str(e)}")
            return {
                'strategy': self.config.strategy_name,
                'initial_capital': self.config.initial_capital,
                'monitor_stocks': self.monitor_stocks,
                'current_date': self.current_date,
                'is_trading_hours': True,
                'total_positions': 0,
                'total_value': 0,
                'total_pnl': 0,
                'daily_trade_pnl': 0,
                'daily_position_pnl': 0,
                'daily_trades': 0,
                'positions': []
            }
    
    def get_available_strategies(self) -> List[str]:
        """获取可用策略列表"""
        return get_available_strategies()
    
    def change_strategy(self, strategy_name: str):
        """切换交易策略"""
        try:
            self.current_strategy = create_strategy(strategy_name, self.config)
            self.config.strategy_name = strategy_name
            logger.info(f"切换到策略: {strategy_name}")
            return True
        except ValueError as e:
            logger.error(f"切换策略失败: {str(e)}")
            return False
    
    def update_parameters(self, **kwargs):
        """更新配置参数"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"更新参数 {key} = {value}")
            elif key in self.config.strategy_params.get(self.config.strategy_name, {}):
                self.config.strategy_params[self.config.strategy_name][key] = value
                logger.info(f"更新策略参数 {key} = {value}")
    
    def cleanup(self):
        """清理资源"""
        self.data_provider.cleanup()
        logger.info("交易引擎资源清理完成")

    def close_all_positions(self, price_data: Dict[str, float]):
        """平掉所有持仓"""
        positions_to_close = list(self.position_manager.positions.keys())
        
        for stock_code in positions_to_close:
            if stock_code in price_data:
                self.position_manager.close_position(stock_code, price_data[stock_code])
                logger.info(f"平仓: {stock_code} @ {price_data[stock_code]}")
    
    def close_position(self, stock_code: str, price: float):
        """平掉指定持仓"""
        if stock_code in self.position_manager.positions:
            self.position_manager.close_position(stock_code, price)
            logger.info(f"平仓: {stock_code} @ {price}")
        else:
            logger.warning(f"没有找到 {stock_code} 的持仓")

    import os
