# tushare_data_provider.py
import tushare as ts
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from .historical_cache import HistoricalCache

from utils.logger import get_core_logger
logger = get_core_logger('tushare_data_provider')
class TushareDataProvider:
    """Tushare数据提供器 - 集成缓存"""
    
    def __init__(self, token: str = None, cache_dir: str = "historical_cache", use_historical_cache: bool = True):
        self.token = token or os.getenv('TUSHARE_TOKEN')
        if self.token:
            ts.set_token(self.token)
        self.pro = ts.pro_api()
        self.cache = HistoricalCache(cache_dir=cache_dir)
        self.use_historical_cache = use_historical_cache
        
    def get_daily_data(self, stock_code: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame:
        """获取日线数据（支持缓存）"""
        cache_key_suffix = f"{start_date}_{end_date}"
        
        try:
            # 首先尝试从缓存加载
            if use_cache:
                cached_data = self.cache.load_from_cache(stock_code, cache_key_suffix)
                if cached_data is not None:
                    logger.debug(f"使用缓存数据: {stock_code}")
                    return cached_data
            
            df = self.pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
            
            if df is None or df.empty:
                logger.warning(f"未获取到数据: {stock_code} {start_date}~{end_date}")
                return pd.DataFrame()
            
            # 数据清洗和转换
            df = self._process_dataframe(df)
            
            # 保存到缓存
            if use_cache and not df.empty:
                self.cache.save_to_cache(stock_code, cache_key_suffix, df)
            
            logger.info(f"获取Tushare数据成功: {stock_code}, 数据量: {len(df)}")
            return df
            
        except Exception as e:
            logger.error(f"获取Tushare数据失败 {stock_code}: {e}")
            return pd.DataFrame()
    
    def get_last_n_days(self, stock_code: str, days: int = 30, use_cache: bool = True) -> pd.DataFrame:
        """获取最近N天的数据（支持缓存）"""
        try:
            # 缓存未命中，从Tushare获取
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')
            
            df = self.get_daily_data(stock_code, start_date, end_date, use_cache=use_cache)
            
            if not df.empty:
                # 取最近days天
                df = df.tail(days).reset_index(drop=True)
                
                # 保存到缓存
                if use_cache:
                    self.cache.save_to_cache(stock_code, days, df)
            
            return df
            
        except Exception as e:
            logger.error(f"获取最近{days}天数据失败 {stock_code}: {e}")
            return pd.DataFrame()
    
    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理DataFrame数据"""
        df = df.sort_values('trade_date').reset_index(drop=True)
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.rename(columns={
            'trade_date': 'date',
            'open': 'open',
            'high': 'high', 
            'low': 'low',
            'close': 'close',
            'vol': 'volume'
        })
        
        # 选择需要的列
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
        return df
    
    def clear_cache(self):
        """清理缓存"""
        self.cache.clear_expired_cache()
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return self.cache.get_cache_stats()