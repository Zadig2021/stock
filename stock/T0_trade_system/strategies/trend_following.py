import pandas as pd
from typing import Dict, Tuple
from .base_strategy import BaseStrategy

class TrendFollowingStrategy(BaseStrategy):
    """趋势跟踪策略"""
    
    def generate_signal(self, stock_code: str, historical_data: pd.DataFrame, 
                       realtime_data: Dict) -> Tuple[str, float, int, float]:
        
        short_period = self.strategy_params.get('short_period', 5)
        long_period = self.strategy_params.get('long_period', 20)
        trend_threshold = self.strategy_params.get('trend_threshold', 0.01)
        
        current_price = realtime_data['price']
        ma_short = historical_data['close'].rolling(short_period).mean().iloc[-1]
        ma_long = historical_data['close'].rolling(long_period).mean().iloc[-1]
        
        # 趋势判断
        trend_strength = (ma_short - ma_long) / ma_long
        price_change = realtime_data.get('change_rate', 0)
        
        volume_ratio = realtime_data['volume'] / historical_data['volume_ma5'].iloc[-1]
        
        # 计算置信度因子
        factors = {
            'trend_strength': (abs(trend_strength) / trend_threshold, 0.4),
            'price_momentum': (abs(price_change) / self.config.price_change_threshold, 0.3),
            'volume_confirmation': (min(volume_ratio / self.config.volume_threshold, 1.0), 0.3)
        }
        
        confidence = self.calculate_confidence(factors)
        
        # 买卖逻辑
        if (trend_strength > trend_threshold and 
            price_change > self.config.price_change_threshold and 
            volume_ratio > self.config.volume_threshold and
            confidence > self.config.signal_confidence_threshold):
            
            quantity = self.calculate_position_size(current_price, "BUY")
            return "BUY", current_price, quantity, confidence
        
        elif (trend_strength < -trend_threshold and 
              price_change < -self.config.price_change_threshold and 
              volume_ratio > self.config.volume_threshold and
              confidence > self.config.signal_confidence_threshold):
            
            quantity = self.calculate_position_size(current_price, "SELL")
            return "SELL", current_price, quantity, confidence
        
        return "HOLD", 0, 0, confidence