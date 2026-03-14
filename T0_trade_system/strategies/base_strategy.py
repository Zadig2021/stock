from abc import ABC, abstractmethod
from typing import Dict, Tuple
import pandas as pd

class BaseStrategy(ABC):
    """交易策略基类"""
    
    def __init__(self, config):
        self.config = config
        self.strategy_params = config.get_strategy_params(self.__class__.__name__)
    
    @abstractmethod
    def generate_signal(self, stock_code: str, historical_data: pd.DataFrame, 
                       realtime_data: Dict) -> Tuple[str, float, int, float]:
        """
        生成交易信号
        
        Returns:
            tuple: (signal, price, quantity, confidence)
            - signal: BUY/SELL/HOLD
            - price: 建议价格
            - quantity: 建议数量
            - confidence: 信号置信度 [0-1]
        """
        pass
    
    def calculate_position_size(self, price: float, signal_type: str) -> int:
        """计算仓位大小"""
        if signal_type == "BUY":
            base_amount = self.config.initial_capital * 0.1  # 基础仓位10%
        else:  # SELL
            base_amount = self.config.initial_capital * 0.1
        
        # 根据策略类型调整仓位
        if self.__class__.__name__ == "TrendFollowingStrategy":
            base_amount = self.config.initial_capital * 0.15
        elif self.__class__.__name__ == "BreakoutStrategy":
            base_amount = self.config.initial_capital * 0.12
        elif self.__class__.__name__ == "ScalpingStrategy":
            base_amount = self.config.initial_capital * 0.08
        
        quantity = int(base_amount / price)
        
        # 确保最小交易金额
        min_quantity = int(self.config.min_trade_amount / price)
        quantity = max(quantity, min_quantity)
        
        return quantity
    
    def calculate_confidence(self, factors: Dict[str, float]) -> float:
        """计算信号置信度"""
        confidence = 0.0
        weight_sum = 0.0
        
        for factor, (value, weight) in factors.items():
            confidence += value * weight
            weight_sum += weight
        
        return min(1.0, confidence / weight_sum) if weight_sum > 0 else 0.0

    def set_initial_position(self, stock_code: str, position: int):
        pass

    def update_position(self, stock_code: str, position_change: int):
        pass