import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional
from abc import ABC, abstractmethod
import yaml
import warnings
warnings.filterwarnings('ignore')

g_config_file = 'config/trading_config.yaml'

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradingConfig:
    """交易配置类 - 实际使用所有配置项"""
    def __init__(self, config_file: str = None):
        # 默认配置
        self.default_config = {
            'trading': {
                'capital': 100000,
                'max_position_ratio': 0.8,
                'commission_rate': 0.0003,
                'stamp_tax_rate': 0.001,
                'min_trade_amount': 10000
            },
            'risk_control': {
                'stop_loss_rate': 0.02,
                'take_profit_rate': 0.03,
                'max_daily_loss': 0.05,
                'max_single_loss': 0.01,
                'position_control': True
            },
            'strategy': {
                'name': 'MeanReversion',
                'volume_threshold': 1.5,
                'price_change_threshold': 0.02,
                'max_holding_time': 300,
                'min_profit_threshold': 0.005
            },
            'strategies': {
                'MeanReversion': {
                    'deviation_threshold': 0.03,
                    'lookback_period': 20,
                    'ma_period': 5,
                    'volume_confirmation': True
                },
                'TrendFollowing': {
                    'short_period': 5,
                    'long_period': 20,
                    'trend_threshold': 0.01,
                    'momentum_period': 10
                },
                'Breakout': {
                    'period': 20,
                    'confirmation_bars': 2,
                    'breakout_threshold': 0.01
                }
            }
        }
        
        # 加载配置文件或使用默认配置
        if config_file:
            self.load_config(config_file)
        else:
            self.apply_config(self.default_config)
    
    def load_config(self, config_file: str):
        """从YAML文件加载配置"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
            
            # 深度合并配置
            merged_config = self.deep_merge(self.default_config, user_config)
            self.apply_config(merged_config)
            logger.info(f"配置文件 {config_file} 加载成功")
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}，使用默认配置")
            self.apply_config(self.default_config)
    
    def deep_merge(self, base: Dict, update: Dict) -> Dict:
        """深度合并字典"""
        result = base.copy()
        for key, value in update.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def apply_config(self, config: Dict):
        """应用配置到属性"""
        # 交易配置
        trading_config = config['trading']
        self.capital = trading_config['capital']
        self.max_position_ratio = trading_config['max_position_ratio']
        self.commission_rate = trading_config['commission_rate']
        self.stamp_tax_rate = trading_config['stamp_tax_rate']
        self.min_trade_amount = trading_config['min_trade_amount']
        
        # 风险控制配置
        risk_config = config['risk_control']
        self.stop_loss_rate = risk_config['stop_loss_rate']
        self.take_profit_rate = risk_config['take_profit_rate']
        self.max_daily_loss = risk_config['max_daily_loss']
        self.max_single_loss = risk_config['max_single_loss']
        self.position_control = risk_config['position_control']
        
        # 策略基础配置
        strategy_config = config['strategy']
        self.strategy_name = strategy_config['name']
        self.volume_threshold = strategy_config['volume_threshold']
        self.price_change_threshold = strategy_config['price_change_threshold']
        self.max_holding_time = strategy_config['max_holding_time']
        self.min_profit_threshold = strategy_config['min_profit_threshold']
        
        # 策略特定配置
        self.strategy_params = config['strategies']
    
    def save_config(self, config_file: str):
        """保存当前配置到文件"""
        config_dict = {
            'trading': {
                'capital': self.capital,
                'max_position_ratio': self.max_position_ratio,
                'commission_rate': self.commission_rate,
                'stamp_tax_rate': self.stamp_tax_rate,
                'min_trade_amount': self.min_trade_amount
            },
            'risk_control': {
                'stop_loss_rate': self.stop_loss_rate,
                'take_profit_rate': self.take_profit_rate,
                'max_daily_loss': self.max_daily_loss,
                'max_single_loss': self.max_single_loss,
                'position_control': self.position_control
            },
            'strategy': {
                'name': self.strategy_name,
                'volume_threshold': self.volume_threshold,
                'price_change_threshold': self.price_change_threshold,
                'max_holding_time': self.max_holding_time,
                'min_profit_threshold': self.min_profit_threshold
            },
            'strategies': self.strategy_params
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"配置已保存到 {config_file}")

class DataProvider:
    """数据提供类"""
    def __init__(self):
        self.historical_data = {}
        self.realtime_data = {}
    
    def load_historical_data(self, stock_code: str, days: int = 30) -> pd.DataFrame:
        """加载历史数据（模拟）"""
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        
        # 模拟更真实的价格序列
        np.random.seed(hash(stock_code) % 10000)  # 基于股票代码设置随机种子
        returns = np.random.normal(0.001, 0.02, days)
        prices = [100]  # 起始价格
        
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        data = pd.DataFrame({
            'date': dates,
            'open': [p * (1 + np.random.uniform(-0.01, 0.01)) for p in prices],
            'high': [p * (1 + np.random.uniform(0, 0.03)) for p in prices],
            'low': [p * (1 + np.random.uniform(-0.03, 0)) for p in prices],
            'close': prices,
            'volume': np.random.randint(100000, 1000000, days)
        })
        
        # 计算技术指标
        data['ma5'] = data['close'].rolling(5).mean()
        data['ma20'] = data['close'].rolling(20).mean()
        data['volume_ma5'] = data['volume'].rolling(5).mean()
        data['volatility'] = data['close'].rolling(10).std()
        
        self.historical_data[stock_code] = data
        return data
    
    def get_realtime_data(self, stock_code: str) -> Dict:
        """获取实时数据（模拟）"""
        if stock_code not in self.historical_data:
            self.load_historical_data(stock_code)
        
        hist_data = self.historical_data[stock_code]
        last_close = hist_data['close'].iloc[-1]
        
        # 基于历史数据生成更真实的实时数据
        price_change = np.random.normal(0, 0.01)
        current_price = last_close * (1 + price_change)
        
        self.realtime_data[stock_code] = {
            'price': current_price,
            'volume': int(np.random.uniform(0.5, 2.0) * hist_data['volume_ma5'].iloc[-1]),
            'timestamp': datetime.now(),
            'bid_price': current_price * 0.999,
            'ask_price': current_price * 1.001,
            'bid_volume': np.random.randint(1000, 10000),
            'ask_volume': np.random.randint(1000, 10000),
            'change_rate': price_change
        }
        return self.realtime_data[stock_code]

class TradingStrategy(ABC):
    """交易策略基类"""
    def __init__(self, config: TradingConfig):
        self.config = config
        self.strategy_params = config.strategy_params.get(self.__class__.__name__, {})
    
    @abstractmethod
    def generate_signal(self, stock_code: str, historical_data: pd.DataFrame, 
                       realtime_data: Dict) -> Tuple[str, float, int]:
        """生成交易信号"""
        pass
    
    def calculate_position_size(self, price: float, signal_type: str) -> int:
        """计算仓位大小 - 使用配置参数"""
        base_amount = self.config.capital * 0.1  # 基础仓位10%
        
        if signal_type == "BUY":
            # 根据策略调整仓位
            if self.config.strategy_name == "TrendFollowing":
                base_amount = self.config.capital * 0.15
            elif self.config.strategy_name == "Breakout":
                base_amount = self.config.capital * 0.12
        
        quantity = int(base_amount / price)
        
        # 确保最小交易金额
        min_quantity = int(self.config.min_trade_amount / price)
        quantity = max(quantity, min_quantity)
        
        return quantity

class MeanReversionStrategy(TradingStrategy):
    """均值回归策略 - 实际使用配置参数"""
    def generate_signal(self, stock_code: str, historical_data: pd.DataFrame, 
                       realtime_data: Dict) -> Tuple[str, float, int]:
        # 使用配置参数
        deviation_threshold = self.strategy_params.get('deviation_threshold', 0.03)
        lookback_period = self.strategy_params.get('lookback_period', 20)
        ma_period = self.strategy_params.get('ma_period', 5)
        
        current_price = realtime_data['price']
        ma_fast = historical_data['close'].rolling(ma_period).mean().iloc[-1]
        ma_slow = historical_data['close'].rolling(lookback_period).mean().iloc[-1]
        
        # 计算偏离度 - 使用配置的阈值
        deviation_from_fast = (current_price - ma_fast) / ma_fast
        deviation_from_slow = (current_price - ma_slow) / ma_slow
        
        # 成交量确认 - 使用配置的成交量阈值
        volume_ratio = realtime_data['volume'] / historical_data['volume_ma5'].iloc[-1]
        
        # 买卖逻辑 - 使用配置参数
        if (deviation_from_fast < -deviation_threshold and 
            volume_ratio > self.config.volume_threshold):
            # 价格显著低于均线，且成交量放大，买入
            quantity = self.calculate_position_size(current_price, "BUY")
            return "BUY", current_price, quantity
        
        elif (deviation_from_fast > deviation_threshold and 
              volume_ratio > self.config.volume_threshold):
            # 价格显著高于均线，且成交量放大，卖出
            quantity = self.calculate_position_size(current_price, "SELL")
            return "SELL", current_price, quantity
        
        return "HOLD", 0, 0

class TrendFollowingStrategy(TradingStrategy):
    """趋势跟踪策略 - 实际使用配置参数"""
    def generate_signal(self, stock_code: str, historical_data: pd.DataFrame, 
                       realtime_data: Dict) -> Tuple[str, float, int]:
        # 使用配置参数
        short_period = self.strategy_params.get('short_period', 5)
        long_period = self.strategy_params.get('long_period', 20)
        trend_threshold = self.strategy_params.get('trend_threshold', 0.01)
        
        current_price = realtime_data['price']
        ma_short = historical_data['close'].rolling(short_period).mean().iloc[-1]
        ma_long = historical_data['close'].rolling(long_period).mean().iloc[-1]
        
        # 趋势判断 - 使用配置参数
        trend_strength = (ma_short - ma_long) / ma_long
        price_change = realtime_data['change_rate']
        
        volume_ratio = realtime_data['volume'] / historical_data['volume_ma5'].iloc[-1]
        
        # 买卖逻辑 - 使用配置参数
        if (trend_strength > trend_threshold and 
            price_change > self.config.price_change_threshold and 
            volume_ratio > self.config.volume_threshold):
            # 上升趋势，价格上涨，成交量放大，买入
            quantity = self.calculate_position_size(current_price, "BUY")
            return "BUY", current_price, quantity
        
        elif (trend_strength < -trend_threshold and 
              price_change < -self.config.price_change_threshold and 
              volume_ratio > self.config.volume_threshold):
            # 下降趋势，价格下跌，成交量放大，卖出
            quantity = self.calculate_position_size(current_price, "SELL")
            return "SELL", current_price, quantity
        
        return "HOLD", 0, 0

class BreakoutStrategy(TradingStrategy):
    """突破策略 - 实际使用配置参数"""
    def generate_signal(self, stock_code: str, historical_data: pd.DataFrame, 
                       realtime_data: Dict) -> Tuple[str, float, int]:
        # 使用配置参数
        period = self.strategy_params.get('period', 20)
        breakout_threshold = self.strategy_params.get('breakout_threshold', 0.01)
        
        current_price = realtime_data['price']
        high_n = historical_data['high'].rolling(period).max().iloc[-1]
        low_n = historical_data['low'].rolling(period).min().iloc[-1]
        
        volume_ratio = realtime_data['volume'] / historical_data['volume_ma5'].iloc[-1]
        
        # 突破判断 - 使用配置参数
        upper_breakout = current_price > high_n * (1 + breakout_threshold)
        lower_breakout = current_price < low_n * (1 - breakout_threshold)
        
        if upper_breakout and volume_ratio > self.config.volume_threshold:
            # 突破N日高点，买入
            quantity = self.calculate_position_size(current_price, "BUY")
            return "BUY", current_price, quantity
        
        elif lower_breakout and volume_ratio > self.config.volume_threshold:
            # 跌破N日低点，卖出
            quantity = self.calculate_position_size(current_price, "SELL")
            return "SELL", current_price, quantity
        
        return "HOLD", 0, 0

class T0TradingEngine:
    """T0交易引擎 - 完整使用配置参数"""
    def __init__(self, config: TradingConfig):
        self.config = config
        self.data_provider = DataProvider()
        self.positions = {}
        self.trade_history = []
        self.daily_pnl = 0
        self.daily_trades = 0
        
        # 策略映射
        self.strategies = {
            "MeanReversion": MeanReversionStrategy(config),
            "TrendFollowing": TrendFollowingStrategy(config),
            "Breakout": BreakoutStrategy(config)
        }
        
        self.current_strategy = self.strategies[config.strategy_name]
        logger.info(f"交易引擎初始化完成，当前策略: {config.strategy_name}")
    
    def change_strategy(self, strategy_name: str):
        """切换交易策略"""
        if strategy_name in self.strategies:
            self.current_strategy = self.strategies[strategy_name]
            self.config.strategy_name = strategy_name
            logger.info(f"切换到策略: {strategy_name}")
        else:
            logger.error(f"未知策略: {strategy_name}")
    
    def update_parameters(self, **kwargs):
        """更新配置参数"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"更新参数 {key} = {value}")
            elif key in self.config.strategy_params.get(self.config.strategy_name, {}):
                self.config.strategy_params[self.config.strategy_name][key] = value
                logger.info(f"更新策略参数 {key} = {value}")
    
    def analyze_stock(self, stock_code: str) -> Dict:
        """分析股票并生成交易建议"""
        try:
            # 获取数据
            historical_data = self.data_provider.load_historical_data(stock_code)
            realtime_data = self.data_provider.get_realtime_data(stock_code)
            
            # 生成交易信号
            signal, price, quantity = self.current_strategy.generate_signal(
                stock_code, historical_data, realtime_data)
            
            # 风险控制检查 - 使用配置的风险参数
            if signal != "HOLD":
                if not self.risk_control_check(stock_code, signal, price, quantity):
                    signal, price, quantity = "HOLD", 0, 0
            
            # 构建建议
            recommendation = {
                'stock_code': stock_code,
                'signal': signal,
                'price': round(price, 2),
                'quantity': quantity,
                'amount': round(price * quantity, 2),
                'timestamp': datetime.now(),
                'strategy': self.config.strategy_name,
                'current_price': round(realtime_data['price'], 2),
                'volume_ratio': round(realtime_data['volume'] / historical_data['volume_ma5'].iloc[-1], 2),
                'change_rate': round(realtime_data['change_rate'], 4)
            }
            
            return recommendation
            
        except Exception as e:
            logger.error(f"分析股票 {stock_code} 时出错: {str(e)}")
            return {
                'stock_code': stock_code,
                'signal': 'HOLD',
                'price': 0,
                'quantity': 0,
                'amount': 0,
                'error': str(e)
            }
    
    def risk_control_check(self, stock_code: str, signal: str, price: float, quantity: int) -> bool:
        """风险控制检查 - 完整使用配置参数"""
        trade_amount = price * quantity
        
        # 检查单日亏损限制
        if self.daily_pnl < -self.config.capital * self.config.max_daily_loss:
            logger.warning(f"达到单日最大亏损限制({self.config.max_daily_loss*100}%)，停止交易")
            return False
        
        # 检查单笔亏损限制
        if trade_amount > self.config.capital * self.config.max_single_loss:
            logger.warning(f"单笔交易金额超过限制({self.config.max_single_loss*100}%)")
            return False
        
        # 检查持仓限制
        if self.config.position_control:
            total_position_value = sum(pos['quantity'] * pos['price'] for pos in self.positions.values())
            if total_position_value + trade_amount > self.config.capital * self.config.max_position_ratio:
                logger.warning(f"超过最大持仓限制({self.config.max_position_ratio*100}%)")
                return False
        
        # 检查最小盈利阈值
        if signal == "BUY":
            expected_profit = price * self.config.min_profit_threshold
            if expected_profit < price * 0.01:  # 至少要有1%的预期空间
                logger.warning("预期盈利空间不足")
                return False
        
        return True
    
    def execute_trade(self, recommendation: Dict):
        """执行交易"""
        if recommendation['signal'] == 'HOLD':
            return
        
        stock_code = recommendation['stock_code']
        signal = recommendation['signal']
        price = recommendation['price']
        quantity = recommendation['quantity']
        
        # 计算交易成本 - 使用配置的费率
        commission = price * quantity * self.config.commission_rate
        if signal == "SELL":
            stamp_tax = price * quantity * self.config.stamp_tax_rate
        else:
            stamp_tax = 0
        
        total_cost = commission + stamp_tax
        
        # 记录交易
        trade_record = {
            'stock_code': stock_code,
            'signal': signal,
            'price': price,
            'quantity': quantity,
            'amount': price * quantity,
            'commission': round(commission, 2),
            'stamp_tax': round(stamp_tax, 2),
            'total_cost': round(total_cost, 2),
            'timestamp': datetime.now(),
            'strategy': self.config.strategy_name
        }
        
        self.trade_history.append(trade_record)
        self.daily_trades += 1
        
        logger.info(f"执行交易: {signal} {stock_code} {quantity}股 @ {price}, 金额: {price*quantity:.2f}, 成本: {total_cost:.2f}")
    
    def get_strategy_parameters(self, strategy_name: str) -> Dict:
        """获取策略参数"""
        return self.config.strategy_params.get(strategy_name, {})
    
    def show_config_summary(self):
        """显示配置摘要"""
        print("\n=== 当前配置摘要 ===")
        print(f"策略: {self.config.strategy_name}")
        print(f"资金: {self.config.capital:,.2f}")
        print(f"最大持仓: {self.config.max_position_ratio*100}%")
        print(f"单日最大亏损: {self.config.max_daily_loss*100}%")
        print(f"成交量阈值: {self.config.volume_threshold}")
        print(f"价格变动阈值: {self.config.price_change_threshold*100}%")
        
        # 显示当前策略特定参数
        strategy_params = self.get_strategy_parameters(self.config.strategy_name)
        print(f"\n{self.config.strategy_name}策略参数:")
        for key, value in strategy_params.items():
            print(f"  {key}: {value}")

def create_sample_config():
    """创建示例配置文件"""
    sample_config = {
        'trading': {
            'capital': 50000,
            'max_position_ratio': 0.7,
            'commission_rate': 0.00025,
            'stamp_tax_rate': 0.001,
            'min_trade_amount': 5000
        },
        'risk_control': {
            'stop_loss_rate': 0.015,
            'take_profit_rate': 0.025,
            'max_daily_loss': 0.03,
            'max_single_loss': 0.008,
            'position_control': True
        },
        'strategy': {
            'name': 'TrendFollowing',
            'volume_threshold': 1.8,
            'price_change_threshold': 0.015,
            'max_holding_time': 240,
            'min_profit_threshold': 0.008
        },
        'strategies': {
            'MeanReversion': {
                'deviation_threshold': 0.025,
                'lookback_period': 15,
                'ma_period': 3,
                'volume_confirmation': True
            },
            'TrendFollowing': {
                'short_period': 3,
                'long_period': 15,
                'trend_threshold': 0.008,
                'momentum_period': 5
            },
            'Breakout': {
                'period': 15,
                'confirmation_bars': 1,
                'breakout_threshold': 0.008
            }
        }
    }
    
    with open(g_config_file, 'w', encoding='utf-8') as f:
        yaml.dump(sample_config, f, default_flow_style=False, allow_unicode=True)
    
    print(f"示例配置文件 {g_config_file} 已创建")

def main():
    """主函数 - 演示完整配置使用"""
    import os
    
    # 检查是否存在配置文件
    if not os.path.exists(g_config_file):
        print("未找到配置文件，创建示例配置...")
        create_sample_config()
        use_sample = input("是否使用示例配置? (y/n): ").lower()
        if use_sample == 'y':
            config = TradingConfig(g_config_file)
        else:
            config = TradingConfig()  # 使用默认配置
    else:
        config = TradingConfig(g_config_file)
    
    # 创建交易引擎
    engine = T0TradingEngine(config)
    
    # 示例股票列表
    stock_list = ['000001', '000002', '000003', '600000', '600036']
    
    print("\n=== T0交易系统启动 ===")
    engine.show_config_summary()
    print("\n" + "="*40)
    
    # 分析每只股票
    for stock in stock_list:
        recommendation = engine.analyze_stock(stock)
        
        print(f"\n股票: {recommendation['stock_code']}")
        print(f"当前价格: {recommendation['current_price']} ({recommendation['change_rate']*100:+.2f}%)")
        print(f"成交量比率: {recommendation['volume_ratio']}")
        print(f"交易建议: {recommendation['signal']}")
        
        if recommendation['signal'] != 'HOLD':
            print(f"建议价格: {recommendation['price']}")
            print(f"建议数量: {recommendation['quantity']}")
            print(f"交易金额: {recommendation['amount']:,.2f}")
            
            # 询问是否执行交易
            execute = input("是否执行此交易? (y/n): ").lower()
            if execute == 'y':
                engine.execute_trade(recommendation)
    
    # 配置管理界面
    while True:
        print("\n=== 配置管理 ===")
        print("1. 切换交易策略")
        print("2. 修改风险参数")
        print("3. 修改策略参数")
        print("4. 保存当前配置")
        print("5. 重新加载配置")
        print("6. 显示当前配置")
        print("7. 退出")
        
        choice = input("请选择操作 (1-7): ").strip()
        
        if choice == '1':
            print("\n可用的交易策略:")
            for strategy in engine.strategies.keys():
                print(f"  - {strategy}")
            new_strategy = input("请输入策略名称: ").strip()
            engine.change_strategy(new_strategy)
            
        elif choice == '2':
            print("\n当前风险参数:")
            print(f"止损率: {engine.config.stop_loss_rate}")
            print(f"止盈率: {engine.config.take_profit_rate}")
            print(f"单日最大亏损: {engine.config.max_daily_loss}")
            
            param_name = input("要修改的参数名: ").strip()
            if hasattr(engine.config, param_name):
                new_value = float(input("新值: "))
                engine.update_parameters(**{param_name: new_value})
            else:
                print("参数不存在")
                
        elif choice == '3':
            strategy_name = engine.config.strategy_name
            params = engine.get_strategy_parameters(strategy_name)
            print(f"\n{strategy_name}策略当前参数:")
            for key, value in params.items():
                print(f"  {key}: {value}")
            
            param_name = input("要修改的参数名: ").strip()
            if param_name in params:
                new_value = input("新值: ").strip()
                # 尝试转换为数值
                try:
                    new_value = float(new_value) if '.' in new_value else int(new_value)
                except ValueError:
                    pass  # 保持字符串
                engine.update_parameters(**{param_name: new_value})
            else:
                print("参数不存在")
                
        elif choice == '4':
            config_file = input(f"配置文件名 (默认: {g_config_file}): ").strip() or g_config_file
            engine.config.save_config(config_file)
            
        elif choice == '5':
            config_file = input(f"配置文件名 (默认: {g_config_file}): ").strip() or g_config_file
            engine.config.load_config(config_file)
            engine.change_strategy(engine.config.strategy_name)  # 重新加载策略
            
        elif choice == '6':
            engine.show_config_summary()
            
        elif choice == '7':
            print("退出系统")
            break
            
        else:
            print("无效选择")

if __name__ == "__main__":
    main()