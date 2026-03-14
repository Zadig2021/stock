import pandas as pd
import numpy as np
import talib
from typing import Tuple, Dict
from utils.logger import get_strategy_logger
logger = get_strategy_logger('index_calculation')

class IndexCalculation():
    """策略指标计算基类"""
    def __init__(self, strategy_params):
        self.strategy_params = strategy_params

    def calculate_macd(self, data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[float, float, float]:
        """基于分钟K线计算MACD指标 - 返回三个值"""
        closes = data['close'].values
        
        # 使用最近的有效数据，避免过多历史数据
        required_length = slow + signal + 10
        if len(closes) < required_length:
            recent_closes = closes
        else:
            recent_closes = closes[-required_length:]
        
        if len(recent_closes) < slow + signal:
            return 0.0, 0.0, 0.0
            
        macd, macd_signal, macd_hist = talib.MACD(recent_closes, fastperiod=fast, 
                                                slowperiod=slow, signalperiod=signal)
        
        if np.isnan(macd[-1]) or np.isnan(macd_signal[-1]) or np.isnan(macd_hist[-1]):
            return 0.0, 0.0, 0.0
            
        # 返回：MACD线, 信号线, 柱状图
        return macd[-1], macd_signal[-1], macd_hist[-1]

    def calculate_rsi(self, data: pd.DataFrame, period: int = None) -> float:
        """计算RSI指标"""
        if period is None:
            period = self.strategy_params.get('rsi_period', 14)

        if len(data) < period:
            return 50.0
            
        closes = data['close'].values
        rsi = talib.RSI(closes, timeperiod=period)
        
        return rsi[-1] if not np.isnan(rsi[-1]) else 50.0

    def calculate_mfi(self, data: pd.DataFrame, period: int = None) -> float:
        """计算MFI（资金流量指数）"""
        if period is None:
            period = self.strategy_params.get('mfi_period', 14)
        
        if len(data) < period + 1:
            return 50.0
        
        # 确保有足够的数据列
        required_cols = ['high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_cols):
            return 50.0
            
        try:
            # 转换为double类型
            high = data['high'].values.astype(np.float64)
            low = data['low'].values.astype(np.float64)
            close = data['close'].values.astype(np.float64)
            volume = data['volume'].values.astype(np.float64)
            
            if len(high) < period + 1:
                return 50.0
                
            mfi = talib.MFI(high, low, close, volume, timeperiod=period)
            
            return mfi[-1] if not np.isnan(mfi[-1]) else 50.0
        except Exception as e:
            logger.warning(f"MFI计算错误: {e}")
            return 50.0

    def calculate_cci(self, data: pd.DataFrame, period: int = None) -> float:
        """计算CCI（商品通道指数）"""
        if period is None:
            period = self.strategy_params.get('cci_period', 14)
        
        if len(data) < period:
            return 0.0
            
        try:
            # 转换为double类型
            high = data['high'].values.astype(np.float64)
            low = data['low'].values.astype(np.float64)
            close = data['close'].values.astype(np.float64)
            
            cci = talib.CCI(high, low, close, timeperiod=period)
            
            return cci[-1] if not np.isnan(cci[-1]) else 0.0
        except Exception as e:
            logger.warning(f"CCI计算错误: {e}")
            return 0.0

    def calculate_bollinger_bands(self, data: pd.DataFrame, period: int = None) -> Tuple[float, float, float]:
        """计算布林带位置"""
        if period is None:
            period = self.strategy_params.get('bb_period', 20)
        
        if len(data) < period:
            return 0.5, 0.0, 0.5
            
        try:
            # 转换为double类型
            closes = data['close'].values.astype(np.float64)
            upper, middle, lower = talib.BBANDS(closes, timeperiod=period, nbdevup=2, nbdevdn=2)
            
            if np.isnan(upper[-1]) or np.isnan(lower[-1]):
                return 0.5, 0.0, 0.5
            
            # 计算价格在布林带中的相对位置
            current_price = closes[-1]
            if upper[-1] != lower[-1]:
                bb_position = (current_price - lower[-1]) / (upper[-1] - lower[-1])
                bb_position = max(0.0, min(1.0, bb_position))
            else:
                bb_position = 0.5
            
            # 计算布林带宽度（波动性）
            bb_width = (upper[-1] - lower[-1]) / middle[-1] if middle[-1] > 0 else 0.0
            
            return bb_position, bb_width, current_price
        except Exception as e:
            logger.warning(f"布林带计算错误: {e}")
            return 0.5, 0.0, 0.5

    def calculate_atr(self, data: pd.DataFrame, period: int = None) -> float:
        """计算ATR（平均真实波幅）"""
        if period is None:
            period = self.strategy_params.get('atr_period', 14)
        
        if len(data) < period:
            return 0.0
            
        try:
            # 转换为double类型
            high = data['high'].values.astype(np.float64)
            low = data['low'].values.astype(np.float64)
            close = data['close'].values.astype(np.float64)
            
            atr = talib.ATR(high, low, close, timeperiod=period)
            
            return atr[-1] if not np.isnan(atr[-1]) else 0.0
        except Exception as e:
            logger.warning(f"ATR计算错误: {e}")
            return 0.0

    def calculate_obv(self, data: pd.DataFrame) -> float:
        """计算OBV（能量潮）趋势"""
        if len(data) < 10:
            return 0.0
            
        try:
            # 转换为double类型
            closes = data['close'].values.astype(np.float64)
            volumes = data['volume'].values.astype(np.float64)
            
            obv = talib.OBV(closes, volumes)
            
            if len(obv) < 5 or np.isnan(obv[-1]):
                return 0.0
                
            # 计算OBV的短期趋势
            obv_ma5 = np.mean(obv[-5:])
            obv_ma10 = np.mean(obv[-10:]) if len(obv) >= 10 else obv_ma5
            
            if obv_ma10 != 0:
                obv_trend = (obv_ma5 - obv_ma10) / abs(obv_ma10)
                return min(max(obv_trend, -1.0), 1.0)
            else:
                return 0.0
        except Exception as e:
            logger.warning(f"OBV计算错误: {e}")
            return 0.0
    
    def analyze_volume(self, historical_data: pd.DataFrame, realtime_data: Dict) -> float:
        """综合分析成交量和成交额"""
        if len(historical_data) < 15:
            return 0.0
        
        df = historical_data.copy()
        
        # 确保有成交额数据
        if 'amount' not in df.columns:
            # 如果没有成交额，估算：成交额 ≈ 成交量 * 平均价格
            avg_price = (df['high'] + df['low'] + df['close']) / 3
            df['amount'] = df['volume'] * avg_price
        
        # 计算量价关系指标
        current_volume = df['volume'].iloc[-1]
        current_amount = df['amount'].iloc[-1]
        
        # 1. 成交量相对强度
        volume_ma5 = df['volume'].tail(5).mean()
        volume_ma20 = df['volume'].tail(20).mean()
        
        if volume_ma20 > 0:
            volume_strength = min(current_volume / volume_ma20, 3.0) / 3.0
        else:
            volume_strength = 0.0
        
        # 2. 成交额相对强度
        amount_ma5 = df['amount'].tail(5).mean()
        amount_ma20 = df['amount'].tail(20).mean()
        
        if amount_ma20 > 0:
            amount_strength = min(current_amount / amount_ma20, 3.0) / 3.0
        else:
            amount_strength = 0.0
        
        # 3. 量价配合度
        price_change = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
        volume_change = (current_volume - df['volume'].iloc[-2]) / df['volume'].iloc[-2] if df['volume'].iloc[-2] > 0 else 0
        
        if abs(price_change) > 0.001:  # 价格有变动
            if (price_change > 0 and volume_change > 0) or (price_change < 0 and volume_change > 0):
                price_volume_confirmation = 1.0  # 量价配合
            else:
                price_volume_confirmation = 0.3  # 量价背离
        else:
            price_volume_confirmation = 0.5  # 价格平稳
        
        # 综合评分
        confidence = (volume_strength * 0.4 + 
                    amount_strength * 0.3 + 
                    price_volume_confirmation * 0.3)
        
        return min(confidence, 1.0)
    
    def analyze_price_trend(self, historical_data: pd.DataFrame) -> float:
        """分析价格趋势强度"""
        if len(historical_data) < 10:
            return 0.0
            
        # 计算短期和中期趋势
        short_trend = (historical_data['close'].iloc[-1] - historical_data['close'].iloc[-5]) / historical_data['close'].iloc[-5]
        medium_trend = (historical_data['close'].iloc[-1] - historical_data['close'].iloc[-10]) / historical_data['close'].iloc[-10]
        
        # 趋势一致性
        trend_strength = (abs(short_trend) + abs(medium_trend)) / 2
        return min(trend_strength / 0.02, 1.0)  # 归一化
    
    def _normalize_rsi_signal(self, rsi: float) -> float:
        """归一化RSI信号"""
        rsi_overbought = self.strategy_params.get('rsi_overbought', 70)
        rsi_oversold = self.strategy_params.get('rsi_oversold', 30)
        
        # 确保RSI在合理范围内
        rsi = max(0, min(100, rsi))
        
        if rsi > rsi_overbought:  # 超买区域
            return min(1.0, (rsi - rsi_overbought) / (100 - rsi_overbought))
        elif rsi < rsi_oversold:  # 超卖区域
            return min(1.0, (rsi_oversold - rsi) / rsi_oversold)
        else:
            return 0.0