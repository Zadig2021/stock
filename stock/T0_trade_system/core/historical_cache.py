# historical_cache.py
import pandas as pd
import pickle
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import hashlib

from utils.logger import get_core_logger
logger = get_core_logger('historical_cache')

class HistoricalCache:
    """历史数据缓存管理器"""
    
    def __init__(self, cache_dir: str = "historical_cache", expiry_days: int = 1):
        self.cache_dir = cache_dir
        self.expiry_days = expiry_days
        self.memory_cache: Dict[str, pd.DataFrame] = {}  # 内存缓存
        self.ensure_cache_dir()
    
    def ensure_cache_dir(self):
        """确保缓存目录存在"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            logger.info(f"创建历史数据缓存目录: {self.cache_dir}")
    
    def get_cache_key(self, stock_code: str, days: int) -> str:
        """生成缓存键"""
        key_str = f"{stock_code}_{days}_{datetime.now().strftime('%Y%m%d')}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get_cache_filepath(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.pkl")
    
    def is_cache_valid(self, filepath: str) -> bool:
        """检查缓存是否有效"""
        if not os.path.exists(filepath):
            return False
        
        # 检查文件修改时间
        file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        cache_age = datetime.now() - file_mtime
        
        return cache_age.days < self.expiry_days
    
    def save_to_cache(self, stock_code: str, days: int, data: pd.DataFrame):
        """保存数据到缓存"""
        try:
            cache_key = self.get_cache_key(stock_code, days)
            filepath = self.get_cache_filepath(cache_key)
            
            # 保存到内存缓存
            self.memory_cache[cache_key] = data.copy()
            
            # 保存到磁盘缓存
            cache_data = {
                'stock_code': stock_code,
                'days': days,
                'data': data,
                'cached_time': datetime.now(),
                'data_hash': hashlib.md5(pickle.dumps(data)).hexdigest()
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(cache_data, f)
            
            logger.debug(f"历史数据缓存已保存: {stock_code} {days}天")
            
        except Exception as e:
            logger.error(f"保存缓存失败 {stock_code}: {e}")
    
    def load_from_cache(self, stock_code: str, days: int) -> Optional[pd.DataFrame]:
        """从缓存加载数据"""
        try:
            cache_key = self.get_cache_key(stock_code, days)
            
            # 首先检查内存缓存
            if cache_key in self.memory_cache:
                logger.debug(f"从内存缓存加载: {stock_code}")
                return self.memory_cache[cache_key].copy()
            
            # 检查磁盘缓存
            filepath = self.get_cache_filepath(cache_key)
            if self.is_cache_valid(filepath):
                with open(filepath, 'rb') as f:
                    cache_data = pickle.load(f)
                
                # 验证数据完整性
                current_hash = hashlib.md5(pickle.dumps(cache_data['data'])).hexdigest()
                if current_hash == cache_data['data_hash']:
                    # 同时更新内存缓存
                    self.memory_cache[cache_key] = cache_data['data'].copy()
                    logger.debug(f"从磁盘缓存加载: {stock_code} {days}天")
                    return cache_data['data'].copy()
                else:
                    logger.warning(f"缓存数据损坏: {stock_code}")
                    os.remove(filepath)  # 删除损坏的缓存文件
            
        except Exception as e:
            logger.debug(f"加载缓存失败 {stock_code}: {e}")
        
        return None
    
    def clear_expired_cache(self):
        """清理过期缓存"""
        try:
            cleared_count = 0
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.pkl'):
                    filepath = os.path.join(self.cache_dir, filename)
                    if not self.is_cache_valid(filepath):
                        os.remove(filepath)
                        cleared_count += 1
            
            if cleared_count > 0:
                logger.info(f"清理了 {cleared_count} 个过期缓存文件")
                
            # 清理内存缓存（保留最近100个）
            if len(self.memory_cache) > 100:
                # 简单的LRU策略：删除最早的100个以外的缓存
                keys_to_remove = list(self.memory_cache.keys())[:-100]
                for key in keys_to_remove:
                    del self.memory_cache[key]
                logger.debug(f"清理了 {len(keys_to_remove)} 个内存缓存")
                
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        try:
            disk_files = [f for f in os.listdir(self.cache_dir) if f.endswith('.pkl')]
            memory_keys = list(self.memory_cache.keys())
            
            return {
                'disk_cache_count': len(disk_files),
                'memory_cache_count': len(memory_keys),
                'cache_dir': self.cache_dir,
                'total_size_mb': self._get_cache_size_mb()
            }
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {}
    
    def _get_cache_size_mb(self) -> float:
        """获取缓存目录大小（MB）"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.cache_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
        return total_size / (1024 * 1024)