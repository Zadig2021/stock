import pandas as pd
from typing import Dict, Tuple
from .base_strategy import BaseStrategy

class BreakoutStrategy(BaseStrategy):
    """突破策略"""
    
    def generate_signal(self, stock_code: str, historical_data: pd.DataFrame, 
                       realtime_data: Dict) -> Tuple[str, float, int, float]:
        
        period = self.strategy_params.get('period', 20)
        breakout_threshold = self.strategy_params.get('breakout_threshold', 0.01)
        
        current_price = realtime_data['price']
        high_n = historical_data['high'].rolling(period).max().iloc[-1]
        low_n = historical_data['low'].rolling(period).min().iloc[-1]
        
        volume_ratio = realtime_data['volume'] / historical_data['volume_ma5'].iloc[-1]
        
        # 突破判断
        upper_breakout = current_price > high_n * (1 + breakout_threshold)
        lower_breakout = current_price < low_n * (1 - breakout_threshold)
        
        # 计算置信度因子
        factors = {
            'breakout_strength': (
                max(
                    (current_price - high_n) / high_n if upper_breakout else 0,
                    (low_n - current_price) / low_n if lower_breakout else 0
                ) / breakout_threshold, 0.5
            ),
            'volume_confirmation': (min(volume_ratio / self.config.volume_threshold, 1.0), 0.5)
        }
        
        confidence = self.calculate_confidence(factors)
        
        if (upper_breakout and 
            volume_ratio > self.config.volume_threshold and
            confidence > self.config.signal_confidence_threshold):
            
            quantity = self.calculate_position_size(current_price, "BUY")
            return "BUY", current_price, quantity, confidence
        
        elif (lower_breakout and 
              volume_ratio > self.config.volume_threshold and
              confidence > self.config.signal_confidence_threshold):
            
            quantity = self.calculate_position_size(current_price, "SELL")
            return "SELL", current_price, quantity, confidence
        
        return "HOLD", 0, 0, confidence