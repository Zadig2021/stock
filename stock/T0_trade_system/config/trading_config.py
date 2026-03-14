import yaml
import os
from typing import Dict, Any, List
import logging

from utils.logger import get_config_logger
logger = get_config_logger('trading_config')

class TradingConfig:
    """交易配置类"""
    
    def __init__(self, config_file: str = None):
        self.default_config_path = os.path.join(os.path.dirname(__file__), 'default_config.yaml')
        self.config_file = config_file
        
        # 加载默认配置
        self.default_config = self._load_default_config()
        
        # 加载用户配置
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
        else:
            self.apply_config(self.default_config)
            logger.info("使用默认配置")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        try:
            with open(self.default_config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载默认配置失败: {str(e)}")
            return self._create_fallback_config()
    
    def _create_fallback_config(self) -> Dict[str, Any]:
        """创建备用配置"""
        return {
            'trading': {
                'initial_capital': 100000,
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
                'position_risk_check': True
            },
            'monitoring': {
                'scan_interval': 5,
                'trading_hours_start': '09:30',
                'trading_hours_end': '15:00',
                'max_stocks_monitor': 10
            },
            'strategy': {
                'name': 'MeanReversion',
                'volume_threshold': 1.5,
                'price_change_threshold': 0.02,
                'max_holding_time': 300,
                'min_profit_threshold': 0.005,
                'signal_confidence_threshold': 0.7
            },
            'position': {
                'enable_position_persistence': True,
                'position_data_dir': 'position_data',
                'auto_save_interval': 60,
                'max_history_days': 30,
                'recover_positions_on_startup': True
            },
            'strategies': {
                'MeanReversion': {
                    'deviation_threshold': 0.03,
                    'lookback_period': 20,
                    'ma_period': 5,
                    'volume_confirmation': True
                }
            }
        }
    
    def load_config(self, config_file: str):
        """从YAML文件加载配置"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
            
            # 深度合并配置
            merged_config = self.deep_merge(self.default_config, user_config)
            self.apply_config(merged_config)
            self.config_file = config_file
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
        self.initial_capital = trading_config['initial_capital']
        self.max_position_ratio = trading_config['max_position_ratio']
        self.commission_rate = trading_config['commission_rate']
        self.stamp_tax_rate = trading_config['stamp_tax_rate']
        self.min_trade_amount = trading_config['min_trade_amount']
        self.trade_flag = trading_config['trade_flag']
        self.advise_data_dir = trading_config['advise_data_dir']
        
        # 风险控制配置
        risk_config = config['risk_control']
        self.stop_loss_rate = risk_config['stop_loss_rate']
        self.take_profit_rate = risk_config['take_profit_rate']
        self.max_daily_loss = risk_config['max_daily_loss']
        self.max_single_loss = risk_config['max_single_loss']
        self.position_risk_check = risk_config['position_risk_check']
        
        # 监控配置
        monitoring_config = config['monitoring']
        self.scan_interval = monitoring_config['scan_interval']
        self.trading_hours_start = monitoring_config['trading_hours_start']
        self.trading_hours_end = monitoring_config['trading_hours_end']
        self.max_stocks_monitor = monitoring_config['max_stocks_monitor']
        
        # 持仓配置
        position_config = config.get('position', {})
        self.initial_position_file = position_config.get('initial_position_file')
        self.enable_position_persistence = position_config.get('enable_position_persistence', False)
        self.position_data_dir = position_config.get('position_data_dir', 'position_data')
        self.auto_save_interval = position_config.get('auto_save_interval', 300)  # 5分钟
        self.max_history_days = position_config.get('max_history_days', 30)
        self.recover_positions_on_startup = position_config.get('recover_positions_on_startup', False)

        # 历史日线数据配置
        historical_data_config = config.get('historical_data', {})
        self.tushare_token = historical_data_config.get('tushare_token', '')
        self.historical_days = historical_data_config.get('historical_days', 30)
        self.use_historical_cache = historical_data_config.get('use_historical_cache', False)
        self.cache_expiry_days = historical_data_config.get('cache_expiry_days', 7)
        self.cache_dir = historical_data_config.get('cache_dir', 'historical_cache')

        # 成交数据
        deal_data = config.get('deal_data', {})
        self.deal_data_dir = deal_data.get('deal_data_dir', '')
        self.load_deal = deal_data.get('load_deal', True)

        # 行情设置
        tick_config = config.get('tick', {})
        self.tick_data_dir = tick_config.get('tick_data_dir', 'tick_data')
        self.tick_data_source = tick_config.get('tick_data_source', 'replayer')
        self.monitor_stocks = tick_config.get('monitor_stocks', [])
        self.collection_interval = tick_config.get('collection_interval', 3)
        self.replay_speed = tick_config.get('replay_speed', 1.0)
        self.replay_date = tick_config.get('replay_date', '')
        
        # 策略基础配置
        strategy_config = config['strategy']
        self.strategy_name = strategy_config['name']
        self.volume_threshold = strategy_config['volume_threshold']
        self.price_change_threshold = strategy_config['price_change_threshold']
        self.max_holding_time = strategy_config['max_holding_time']
        self.min_profit_threshold = strategy_config['min_profit_threshold']
        self.signal_confidence_threshold = strategy_config['signal_confidence_threshold']
        
        # 策略特定配置
        self.strategy_params = config['strategies']
    
    def save_config(self, config_file: str = None):
        """保存当前配置到文件"""
        if config_file is None:
            config_file = self.config_file
        
        config_dict = {
            'trading': {
                'initial_capital': self.initial_capital,
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
                'position_risk_check': self.position_risk_check
            },
            'monitoring': {
                'scan_interval': self.scan_interval,
                'trading_hours_start': self.trading_hours_start,
                'trading_hours_end': self.trading_hours_end,
                'max_stocks_monitor': self.max_stocks_monitor,
                'signal_confidence_threshold': self.signal_confidence_threshold
            },
            'position': {
                'enable_position_persistence': self.enable_position_persistence,
                'position_data_dir': self.position_data_dir,
                'auto_save_interval': self.auto_save_interval,
                'max_history_days': self.max_history_days,
                'recover_positions_on_startup': self.recover_positions_on_startup,
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
    
    def get_strategy_params(self, strategy_name: str) -> Dict:
        """获取指定策略的参数"""
        return self.strategy_params.get(strategy_name, {})
    
    def update_position_config(self, **kwargs):
        """更新持仓配置"""
        valid_keys = [
            'enable_position_persistence',
            'position_data_dir', 
            'auto_save_interval',
            'max_history_days',
            'recover_positions_on_startup'
        ]
        
        for key, value in kwargs.items():
            if key in valid_keys and hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"更新持仓配置 {key} = {value}")
    
    def get_position_config_summary(self) -> Dict:
        """获取持仓配置摘要"""
        return {
            'enable_position_persistence': self.enable_position_persistence,
            'position_data_dir': self.position_data_dir,
            'auto_save_interval': self.auto_save_interval,
            'max_history_days': self.max_history_days,
            'recover_positions_on_startup': self.recover_positions_on_startup
        }