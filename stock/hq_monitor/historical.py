import os
import threading
import yaml
import logging
from datetime import datetime, timedelta
from typing import Optional, List
import akshare as ak
import time

from .models import HistoricalVolumeConfig


class HistoricalVolumeManager:
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.historical_data_file = os.path.join(config_dir, "historical_volume.yaml")
        self.historical_data = {}
        self.data_lock = threading.Lock()
        self.ensure_config_dir()
        self.load_historical_data()

    def ensure_config_dir(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)

    def load_historical_data(self):
        if os.path.exists(self.historical_data_file):
            try:
                with open(self.historical_data_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                for k, v in data.items():
                    self.historical_data[k] = HistoricalVolumeConfig(
                        avg_volume_30d=v.get('avg_volume_30d', 0),
                        avg_volume_60d=v.get('avg_volume_60d', 0),
                        last_updated=v.get('last_updated', '')
                    )
                logging.info(f"已加载 {len(self.historical_data)} 只股票的历史成交量数据")
            except Exception as e:
                logging.error(f"加载历史成交量数据失败: {e}")
                self.historical_data = {}

    def save_historical_data(self):
        try:
            save_data = {}
            for k, v in self.historical_data.items():
                save_data[k] = {
                    'avg_volume_30d': v.avg_volume_30d,
                    'avg_volume_60d': v.avg_volume_60d,
                    'last_updated': v.last_updated
                }
            with open(self.historical_data_file, 'w', encoding='utf-8') as f:
                yaml.dump(save_data, f, allow_unicode=True, indent=2)
            logging.debug(f"已保存 {len(self.historical_data)} 条历史成交量数据")
        except Exception as e:
            logging.error(f"保存历史成交量数据失败: {e}")

    def get_historical_volume(self, stock_code: str) -> Optional[HistoricalVolumeConfig]:
        return self.historical_data.get(stock_code)

    def get_historical_volume_data(self, stock_code: str, force_update: bool = False) -> Optional[HistoricalVolumeConfig]:
        with self.data_lock:
            cfg = self.historical_data.get(stock_code)
            if not force_update and cfg and cfg.last_updated:
                try:
                    last = datetime.strptime(cfg.last_updated, '%Y-%m-%d').date()
                    if (datetime.now().date() - last).days < 7:
                        return cfg
                except Exception:
                    pass
            logging.info(f"开始获取 {stock_code} 的历史成交量数据...")
            success = self._fetch_historical_volume_data(stock_code)
            if success:
                return self.historical_data.get(stock_code)
            return None

    def _fetch_historical_volume_data(self, stock_code: str, days: int = 90) -> bool:
        try:
            # 对于新浪接口，需要注意股票代码格式
            # 新浪接口一般需要带市场前缀，如：sh600000, sz000001
            import re
            
            # 处理股票代码格式
            code_with_market = stock_code
            if not re.match(r'^(sh|sz)', stock_code, re.I):
                # 根据股票代码判断市场
                if stock_code.startswith('6'):
                    code_with_market = f"sh{stock_code}"
                elif stock_code.startswith('0') or stock_code.startswith('3'):
                    code_with_market = f"sz{stock_code}"
                else:
                    logging.warning(f"无法识别的股票代码格式: {stock_code}")
                    return False
            
            # 计算日期
            start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y%m%d')
            
            # 使用新浪接口
            try:
                # 尝试不同的新浪接口格式
                stock_history = ak.stock_zh_a_hist_sina(
                    symbol=code_with_market,
                    start_date=start_date,
                    end_date=end_date
                )
            except Exception as api_error:
                # 如果标准接口失败，尝试另一种可能的格式
                try:
                    # 有些情况下需要不带市场前缀
                    stock_history = ak.stock_zh_a_hist_sina(
                        symbol=stock_code,
                        start_date=start_date,
                        end_date=end_date
                    )
                except Exception:
                    logging.error(f"新浪接口调用失败: {api_error}")
                    return False
            
            if stock_history is None or stock_history.empty:
                logging.warning(f"未找到 {stock_code} 的历史数据")
                return False
            
            # 检查成交量列名 - 新浪接口可能有不同的列名
            volume_column = None
            for possible_name in ['volume', '成交量', 'vol', '成交额（手）', '成交手']:
                if possible_name in stock_history.columns:
                    volume_column = possible_name
                    break
            
            if volume_column is None:
                # 尝试查看所有列名
                logging.warning(f"历史数据列名: {stock_history.columns.tolist()}")
                logging.warning(f"历史数据中未找到成交量列: {stock_code}")
                return False
            
            volumes = stock_history[volume_column]
            volumes = volumes[volumes > 0]
            
            if len(volumes) < 30:
                logging.warning(f"历史数据不足: {len(volumes)} 天")
                return False
            
            avg30 = int(volumes.tail(30).mean())
            avg60 = int(volumes.tail(min(60, len(volumes))).mean())
            
            today = datetime.now().strftime('%Y-%m-%d')
            self.historical_data[stock_code] = HistoricalVolumeConfig(
                avg_volume_30d=avg30, 
                avg_volume_60d=avg60, 
                last_updated=today
            )
            
            self.save_historical_data()
            logging.info(f"成功获取 {stock_code} 历史成交量: 30日 {avg30}，60日 {avg60}")
            return True
        
        except Exception as e:
            logging.error(f"获取 {stock_code} 历史成交量失败: {e}")
            return False
    
    def get_historical_volume(self, stock_code: str) -> Optional[HistoricalVolumeConfig]:
        """获取股票的历史成交量配置（兼容旧接口）"""
        return self.get_historical_volume_data(stock_code)

    def preload_selected_stocks(self, stock_codes: List[str]):
        """预加载选定的股票历史数据"""
        if not stock_codes:
            return
            
        def preload_worker():
            for i, stock_code in enumerate(stock_codes):
                try:
                    logging.info(f"预加载新增股票历史数据 ({i+1}/{len(stock_codes)}): {stock_code}")
                    success = self.get_historical_volume_data(stock_code)
                    if success:
                        logging.info(f"成功预加载 {stock_code} 历史数据")
                    else:
                        logging.warning(f"预加载 {stock_code} 历史数据失败")
                    time.sleep(0.1)  # 避免请求过于频繁
                except Exception as e:
                    logging.error(f"预加载 {stock_code} 历史数据异常: {e}")
            logging.info(f"新增股票历史数据预加载完成，共 {len(stock_codes)} 只")
        
        preload_thread = threading.Thread(target=preload_worker, daemon=True)
        preload_thread.start()
    
    def preload_all_stocks(self, stock_codes: List[str]):
        """预加载所有股票的历史数据（兼容旧接口）"""
        self.preload_selected_stocks(stock_codes)