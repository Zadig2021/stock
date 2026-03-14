import pandas as pd
from typing import Dict, Tuple
from .base_strategy import BaseStrategy
import logging

from utils.logger import get_strategy_logger
logger = get_strategy_logger('mean_reversion')

class MeanReversionStrategy(BaseStrategy):
    """均值回归策略"""
    def generate_signal(self, stock_code: str, historical_data: pd.DataFrame, realtime_data: Dict):
        """均值回归策略（带详细调试）"""
        try:
            logger.debug(f"策略输入 - 股票: {stock_code}, 实时价格: {realtime_data.get('price')}")
            
            # 检查数据完整性
            if historical_data is None or len(historical_data) < 20:
                logger.warning(f"历史数据不足: {stock_code}, 长度: {len(historical_data) if historical_data is not None else 0}")
                return "HOLD", 0, 0, 0.0
            
            current_price = realtime_data.get('price', 0)
            if current_price <= 0:
                logger.warning(f"当前价格无效: {stock_code}, 价格: {current_price}")
                return "HOLD", 0, 0, 0.0
            
            # 计算技术指标
            ma5 = historical_data['ma5'].iloc[-1] if 'ma5' in historical_data.columns else current_price
            ma20 = historical_data['ma20'].iloc[-1] if 'ma20' in historical_data.columns else current_price
            volume_ma5 = historical_data['volume_ma5'].iloc[-1] if 'volume_ma5' in historical_data.columns else 1
            
            logger.debug(f"技术指标 - MA5: {ma5}, MA20: {ma20}, 成交量MA5: {volume_ma5}")
            
            # 计算偏离度
            deviation_from_ma5 = (current_price - ma5) / ma5
            deviation_from_ma20 = (current_price - ma20) / ma20
            
            # 成交量确认
            current_volume = realtime_data.get('volume', 0)
            volume_ratio = current_volume / volume_ma5 if volume_ma5 > 0 else 1
            
            logger.debug(f"偏离度 - MA5: {deviation_from_ma5:.3f}, MA20: {deviation_from_ma20:.3f}, 成交量比率: {volume_ratio:.2f}")
            
            # 获取策略参数
            deviation_threshold = self.strategy_params.get('deviation_threshold', 0.03)
            volume_threshold = self.config.volume_threshold
            
            logger.debug(f"策略参数 - 偏离阈值: {deviation_threshold}, 成交量阈值: {volume_threshold}")
            
            # 买卖逻辑
            signal = "HOLD"
            confidence = 0.0

            if deviation_from_ma5 < -deviation_threshold and volume_ratio > volume_threshold:
                # 价格显著低于5日均线，且成交量放大，买入
                signal = "BUY"
                confidence = min(0.9, abs(deviation_from_ma5) * 10)  # 基于偏离度计算置信度
                logger.info(f"生成买入信号: {stock_code}, 偏离度: {deviation_from_ma5:.3f}")
                
            elif deviation_from_ma5 > deviation_threshold and volume_ratio > volume_threshold:
                # 价格显著高于5日均线，且成交量放大，卖出
                signal = "SELL" 
                confidence = min(0.9, abs(deviation_from_ma5) * 10)
                logger.info(f"生成卖出信号: {stock_code}, 偏离度: {deviation_from_ma5:.3f}")
            
            # 计算仓位
            if signal != "HOLD":
                quantity = self.calculate_position_size(current_price, signal)
                logger.debug(f"交易信号 - {signal}, 价格: {current_price}, 数量: {quantity}, 置信度: {confidence:.3f}")
                return signal, current_price, quantity, confidence
            else:
                logger.debug(f"无交易信号 - 偏离度: {deviation_from_ma5:.3f}, 成交量比率: {volume_ratio:.2f}")
                return "HOLD", 0, 0, 0.0
                
        except Exception as e:
            logger.error(f"策略执行错误 {stock_code}: {str(e)}", exc_info=True)
            return "HOLD", 0, 0, 0.0