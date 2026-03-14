import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import sys
import csv

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hq.tick_storage import TickData
from .tushare_data_provider import TushareDataProvider

from utils.logger import get_core_logger
logger = get_core_logger('real_trading_provider')

class RealDataProvider:
    """真实数据提供器 - 使用您的逐笔行情数据"""
    
    def __init__(self, config, data_dir: str = "tick_data"):
        self.config = config
        self.current_ticks = {}  # 当前各股票的最新tick
        self.historical_data = {}  # 缓存的历史数据
        self.current_date = datetime.now().strftime('%Y%m%d')
        self.tushare_provider = TushareDataProvider(
            token=config.tushare_token,
            cache_dir=config.cache_dir,
            use_historical_cache=config.use_historical_cache
        )
        self.realtime_cache = {}
        self.last_update_time = {}
    
    def set_current_date(self, date_str: str):
        """设置当前回放日期"""
        self.current_date = date_str
        logger.info(f"设置回放日期: {date_str}")
    
    def load_historical_data(self, stock_code: str, days: int = 30) -> pd.DataFrame:
        """加载历史数据（优先使用Tushare真实数据）"""
        cache_key = f"{stock_code}_{days}"
        if cache_key in self.historical_data:
            return self.historical_data[cache_key]
        
        try:
            # 1. 优先使用Tushare获取真实历史数据
            tushare_data = self.tushare_provider.get_last_n_days(stock_code, days, use_cache=self.config.use_historical_cache)
            if not tushare_data.empty and len(tushare_data) >= 10:
                logger.info(f"使用Tushare历史数据: {stock_code}, 天数: {len(tushare_data)}")
                data = self._calculate_technical_indicators(tushare_data)
                if self.config.use_historical_cache:
                    self.historical_data[cache_key] = data
                return data
            
            # 2. 最后使用模拟数据
            logger.warning(f"真实数据不足，使用模拟数据: {stock_code}")
            simulated_data = self._generate_simulated_data(stock_code, days)
            data = self._calculate_technical_indicators(simulated_data)
            self.historical_data[cache_key] = data
            return data
            
        except Exception as e:
            logger.error(f"加载历史数据失败 {stock_code}: {e}")
            return self._generate_simulated_data(stock_code, days)

    def clear_cache(self):
        """清理缓存"""
        self.tushare_provider.clear_cache()
        self.historical_data.clear()  # 清空内存缓存
        logger.info("数据缓存已清理")
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        stats = self.tushare_provider.get_cache_stats()
        stats['memory_cache_count'] = len(self.historical_data)
        return stats

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标（修复fillna警告）"""
        if len(df) == 0:
            return df
            
        try:
            # 基础移动平均线
            df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
            df['ma10'] = df['close'].rolling(window=10, min_periods=1).mean()
            df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
            df['ma30'] = df['close'].rolling(window=30, min_periods=1).mean()
            
            # 成交量移动平均
            df['volume_ma5'] = df['volume'].rolling(window=5, min_periods=1).mean()
            df['volume_ma10'] = df['volume'].rolling(window=10, min_periods=1).mean()
            df['volume_ma20'] = df['volume'].rolling(window=20, min_periods=1).mean()
            
            # 价格变化和波动率
            df['price_change'] = df['close'].pct_change()
            df['volatility'] = df['close'].rolling(window=10, min_periods=2).std()
            
            # 相对强弱指标RSI
            df['rsi'] = self._calculate_rsi(df['close'])
            
            # MACD
            exp1 = df['close'].ewm(span=12).mean()
            exp2 = df['close'].ewm(span=26).mean()
            df['macd'] = exp1 - exp2
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
            
            # 布林带
            df['boll_mid'] = df['close'].rolling(window=20).mean()
            df['boll_std'] = df['close'].rolling(window=20).std()
            df['boll_upper'] = df['boll_mid'] + 2 * df['boll_std']
            df['boll_lower'] = df['boll_mid'] - 2 * df['boll_std']
            
            # 修复：使用新的fillna方法
            df = self._safe_fillna(df)
            
            logger.debug(f"技术指标计算完成: 数据长度{len(df)}, 最新MA5: {df['ma5'].iloc[-1]:.2f}")
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            # 设置基础指标作为兜底
            df['ma5'] = df['close']
            df['ma20'] = df['close']
            df['volume_ma5'] = df['volume']
            df = self._safe_fillna(df)
            
        return df

    def _safe_fillna(self, df: pd.DataFrame) -> pd.DataFrame:
        """安全的NaN填充（兼容新版本pandas）"""
        try:
            # 方法1：使用ffill()和bfill()方法（推荐）
            df = df.ffill().bfill()
            
            # 方法2：如果还有NaN，用0填充
            df = df.fillna(0)
            
            return df
            
        except Exception as e:
            logger.error(f"填充NaN失败: {e}")
            return df.fillna(0)  # 最终兜底

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except:
            return pd.Series([50] * len(prices), index=prices.index)  # 默认值

    def _generate_simulated_data(self, stock_code: str, days: int) -> pd.DataFrame:
        """生成模拟历史数据（改进版）"""
        try:
            # 使用股票代码作为随机种子，保持一致性
            seed = abs(hash(stock_code)) % 10000
            np.random.seed(seed)
            
            # 尝试获取当前价格作为基准
            base_price = 50.0  # 默认基准价格
            try:
                realtime_data = self.get_realtime_data(stock_code)
                if realtime_data and realtime_data.get('price', 0) > 0:
                    base_price = realtime_data['price']
                    logger.debug(f"使用实时价格作为基准: {stock_code} {base_price}")
            except:
                pass
            
            dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
            
            # 生成更真实的价格序列（带趋势和波动）
            returns = np.random.normal(0.0005, 0.015, days)  # 更小的波动
            prices = [base_price]
            
            for ret in returns[1:]:
                new_price = prices[-1] * (1 + ret)
                # 确保价格不会变成负数
                prices.append(max(new_price, 0.01))
            
            # 生成OHLC数据
            data = pd.DataFrame({
                'date': dates,
                'open': [p * (1 + np.random.uniform(-0.005, 0.005)) for p in prices],
                'high': [p * (1 + np.random.uniform(0.01, 0.03)) for p in prices],
                'low': [p * (1 + np.random.uniform(-0.03, -0.01)) for p in prices],
                'close': prices,
                'volume': np.random.randint(500000, 2000000, days)
            })
            
            # 确保高价>低价
            data['high'] = data[['high', 'open', 'close']].max(axis=1)
            data['low'] = data[['low', 'open', 'close']].min(axis=1)
            
            # 计算技术指标
            data = self._calculate_technical_indicators(data)
            
            logger.info(f"为 {stock_code} 生成模拟历史数据，基准价格: {base_price}")
            return data
            
        except Exception as e:
            logger.error(f"生成模拟数据失败 {stock_code}: {e}")
            # 返回一个最小的有效DataFrame
            return pd.DataFrame({
                'date': [datetime.now()],
                'open': [50.0],
                'high': [52.0],
                'low': [48.0],
                'close': [51.0],
                'volume': [1000000],
                'ma5': [51.0],
                'ma20': [51.0],
                'volume_ma5': [1000000]
            })
    
    def get_realtime_data(self, stock_code: str) -> Dict:
        """获取实时数据 - 从当前tick数据中获取"""
        if stock_code in self.current_ticks:
            tick = self.current_ticks[stock_code]
            return self._tick_to_realtime_data(tick)
        else:
            # 如果没有当前tick，返回模拟数据
            raise ValueError(f"没有实时tick数据: {stock_code}")
            # return self._get_simulated_data(stock_code)
    
    def update_tick_data(self, tick_data: TickData):
        """更新tick数据"""
        self.current_ticks[tick_data.code] = tick_data
        logger.debug(f"更新 {tick_data.code} 数据: 价格 {tick_data.price}")
    
    def _tick_to_realtime_data(self, tick: TickData) -> Dict:
        """将TickData转换为实时数据格式"""
        return {
            'price': tick.price,
            'volume': tick.volume,
            'timestamp': tick.timestamp,
            'bid_price': tick.bid_price,
            'ask_price': tick.ask_price,
            'bid_volume': tick.bid_volume,
            'ask_volume': tick.ask_volume,
            'change_rate': tick.change_percent / 100.0,  # 转换为小数
            'high': tick.price * 1.02,  # 模拟最高价
            'low': tick.price * 0.98    # 模拟最低价
        }
    
    def _get_simulated_data(self, stock_code: str) -> Dict:
        """获取模拟数据（当没有真实数据时）"""
        base_price = 50.0
        price_change = np.random.normal(0, 0.01)
        
        return {
            'price': base_price * (1 + price_change),
            'volume': np.random.randint(100000, 500000),
            'timestamp': datetime.now(),
            'bid_price': base_price * 0.999,
            'ask_price': base_price * 1.001,
            'bid_volume': np.random.randint(1000, 10000),
            'ask_volume': np.random.randint(1000, 10000),
            'change_rate': price_change,
            'high': base_price * 1.02,
            'low': base_price * 0.98
        }
    
    def get_multiple_stocks_data(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """获取多只股票的实时数据"""
        result = {}
        for code in stock_codes:
            result[code] = self.get_realtime_data(code)
        return result
    