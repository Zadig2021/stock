import requests
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable
import threading
from .tick_storage import TickData, TickStorage
from utils import format_stock_code_sx000000

# 设置日志
from utils.logger import get_hq_logger
logger = get_hq_logger('tick_collector')

class TickDataCollector:
    """逐笔数据采集器"""
    
    def __init__(self, data_dir: str = "tick_data", collection_interval: int = 3):
        self.storage = TickStorage(data_dir)
        self.monitoring_stocks: List[str] = []  # code -> name
        self.monitor_threads: Dict[str, threading.Thread] = {}
        self.monitor_flags: Dict[str, bool] = {}
        self.collection_interval = collection_interval  # 采集间隔（秒）
        self.data_callback: Callable = None
        
    def add_stock(self, stock_code: str):
        """添加监控股票"""
        if stock_code not in self.monitoring_stocks:
            self.monitoring_stocks.append(stock_code)
            logger.info(f"添加逐笔数据采集: {stock_code}")
    
    def remove_stock(self, stock_code: str):
        """移除监控股票"""
        if stock_code in self.monitoring_stocks:
            del self.monitoring_stocks[stock_code]
            self.stop_monitor_thread(stock_code)
            logger.info(f"移除逐笔数据采集: {stock_code}")

    def get_stock_data(self, stock_code: str) -> Optional[TickData]:
        """获取股票数据"""
        try:
            url = f"https://hq.sinajs.cn/list={format_stock_code_sx000000(stock_code)}"
            
            headers = {
                'Referer': 'https://finance.sina.com.cn/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data_str = response.text.split('="')[1].split(',')
                if len(data_str) > 30:
                    current_price = float(data_str[3])
                    yesterday_close = float(data_str[2])
                    change_percent = (current_price - yesterday_close) / yesterday_close * 100
                    
                    volume_in_shares = int(data_str[8])
                    volume_in_hands = volume_in_shares // 100
                    
                    return TickData(
                        code=stock_code,
                        name=data_str[0],
                        price=current_price,
                        change_percent=round(change_percent, 2),
                        volume=volume_in_hands,
                        amount=float(data_str[9]),
                        timestamp=datetime.now(),
                        bid_price=float(data_str[11]),  # 买一价
                        ask_price=float(data_str[21]),  # 卖一价
                        bid_volume=int(data_str[10]),   # 买一量
                        ask_volume=int(data_str[20])    # 卖一量
                    )
        except Exception as e:
            logger.warning(f"获取股票数据失败 {stock_code}: {e}")
        
        return None
    
    def start_collection(self):
        """开始采集"""
        logger.info("启动逐笔数据采集...")
        
        for stock_code in self.monitoring_stocks:
            self.start_monitor_thread(stock_code)
        
        logger.info(f"逐笔数据采集已启动，监控 {len(self.monitoring_stocks)} 只股票")
    
    def start_monitor_thread(self, stock_code: str):
        """启动监控线程"""
        if stock_code in self.monitor_threads and self.monitor_flags.get(stock_code, False):
            return
        
        self.monitor_flags[stock_code] = True
        # 使用lambda函数传递参数，避免线程参数传递问题
        thread = threading.Thread(
            target=lambda: self._collect_single_stock(stock_code),
            daemon=True,
            name=f"Collector-{stock_code}"
        )
        self.monitor_threads[stock_code] = thread
        thread.start()
    
    def _collect_single_stock(self, stock_code: str):
        """采集单个股票数据"""
        consecutive_errors = 0
        
        while self.monitor_flags.get(stock_code, False):
            try:
                tick_data = self.get_stock_data(stock_code)
                if tick_data:
                    consecutive_errors = 0
                    
                    # 执行回调
                    if self.data_callback:
                        self.data_callback(tick_data)

                    # 存储逐笔数据
                    self.storage.store_tick_data(tick_data)
                    
                    logger.debug(f"采集 {stock_code}: {tick_data.price:.2f}")
                    
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        logger.warning(f"连续采集 {stock_code} 数据失败")
                        time.sleep(10)
                
                time.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"采集 {stock_code} 异常: {e}")
                time.sleep(self.collection_interval)
    
    def stop_monitor_thread(self, stock_code: str):
        """停止监控线程"""
        if stock_code in self.monitor_flags:
            self.monitor_flags[stock_code] = False
        
        if stock_code in self.monitor_threads:
            thread = self.monitor_threads[stock_code]
            thread.join(timeout=5)
            if thread.is_alive():
                logger.warning(f"采集线程 {stock_code} 停止超时")
            del self.monitor_threads[stock_code]
    
    def stop_collection(self):
        """停止采集"""
        logger.info("停止逐笔数据采集...")
        
        for stock_code in list(self.monitor_flags.keys()):
            self.stop_monitor_thread(stock_code)
        
        self.storage.close_all_files()
        logger.info("逐笔数据采集已停止")

    def set_data_callback(self, callback: Callable[[TickData], None]):
        """设置回放回调函数"""
        self.data_callback = callback