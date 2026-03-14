import pandas as pd
from typing import Dict, Tuple
from .base_strategy import BaseStrategy

class ScalpingStrategy(BaseStrategy):
    """日内刷单策略"""
    
    def generate_signal(self, stock_code: str, historical_data: pd.DataFrame, 
                       realtime_data: Dict) -> Tuple[str, float, int, float]:
        
        price_spread_threshold = self.strategy_params.get('price_spread_threshold', 0.005)
        quick_profit_target = self.strategy_params.get('quick_profit_target', 0.008)
        stop_loss_rate = self.strategy_params.get('stop_loss', 0.004)  # 新增止损参数
        
        current_price = realtime_data['price']
        bid_price = realtime_data.get('bid_price', current_price * 0.999)
        ask_price = realtime_data.get('ask_price', current_price * 1.001)
        
        # 计算买卖价差
        price_spread = (ask_price - bid_price) / current_price
        
        # 计算短期动量
        short_momentum = self._calculate_momentum(historical_data, period=5)
        
        # 成交量确认
        volume_ratio = realtime_data['volume'] / historical_data['volume_ma5'].iloc[-1]
        
        # 计算置信度因子
        factors = {
            'price_spread': (max(0, 1 - price_spread / price_spread_threshold), 0.3),
            'momentum_strength': (abs(short_momentum) / 0.02, 0.4),
            'volume_confirmation': (min(volume_ratio / 1.2, 1.0), 0.3)
        }
        
        confidence = self.calculate_confidence(factors)
        
        # 刷单逻辑 - 寻找小的价格波动机会
        if (price_spread < price_spread_threshold and 
            short_momentum > 0.005 and 
            volume_ratio > 1.0 and
            confidence > self.config.signal_confidence_threshold):
            
            quantity = self.calculate_position_size(current_price, "BUY")
            stop_loss_price = current_price * (1 - stop_loss_rate)  # 买入止损价
            return "BUY", current_price, quantity, confidence, stop_loss_price
        
        elif (price_spread < price_spread_threshold and 
              short_momentum < -0.005 and 
              volume_ratio > 1.0 and
              confidence > self.config.signal_confidence_threshold):
            
            quantity = self.calculate_position_size(current_price, "SELL")
            stop_loss_price = current_price * (1 + stop_loss_rate)  # 卖出止损价
            return "SELL", current_price, quantity, confidence, stop_loss_price
        
        return "HOLD", 0, 0, confidence, 0
    
    def _calculate_momentum(self, data: pd.DataFrame, period: int = 5) -> float:
        """计算短期动量"""
        if len(data) < period:
            return 0.0
        return (data['close'].iloc[-1] - data['close'].iloc[-period]) / data['close'].iloc[-period]
    
    def check_stop_loss(self, position: Dict, current_price: float) -> bool:
        """检查是否触发止损"""
        if not position:
            return False
            
        stop_loss_price = position.get('stop_loss_price', 0)
        position_type = position.get('type', '')
        
        if position_type == "BUY" and current_price <= stop_loss_price:
            return True
        elif position_type == "SELL" and current_price >= stop_loss_price:
            return True
            
        return False
    
    def calculate_dynamic_stop_loss(self, entry_price: float, position_type: str, 
                                  volatility: float) -> float:
        """计算动态止损价格"""
        base_stop_loss = self.strategy_params.get('stop_loss', 0.004)
        
        # 根据波动率调整止损
        volatility_adjustment = min(volatility * 1.5, base_stop_loss * 2)
        adjusted_stop_loss = base_stop_loss + volatility_adjustment
        
        if position_type == "BUY":
            return entry_price * (1 - adjusted_stop_loss)
        else:  # SELL
            return entry_price * (1 + adjusted_stop_loss)