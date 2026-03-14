import json
import csv
import os
from typing import Dict, List
from .tick_data import TickData
import threading
from datetime import datetime, date

# 设置日志
from utils.logger import get_hq_logger
logger = get_hq_logger('tick_storage')

class TickStorage:
    """逐笔行情存储器 - 包含文件读取功能"""
    
    def __init__(self, data_dir: str = "tick_data"):
        self.data_dir = data_dir
        self.current_files: Dict[str, str] = {}
        self.file_handles: Dict[str, any] = {}
        self.csv_writers: Dict[str, any] = {}
        self.lock = threading.Lock()
        self.ensure_data_dir()
        
    def ensure_data_dir(self):
        """确保数据目录存在"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            logger.info(f"创建逐笔数据目录: {self.data_dir}")
    
    def get_daily_filename(self, stock_code: str, date_str: str = None) -> str:
        """获取每日数据文件名"""
        if date_str is None:
            date_str = date.today().strftime('%Y%m%d')
        return os.path.join(self.data_dir, f"{stock_code}_{date_str}.csv")
    
    def initialize_csv_file(self, stock_code: str, stock_name: str):
        """初始化CSV文件"""
        filename = self.get_daily_filename(stock_code)
        
        # 如果文件不存在，创建并写入表头
        if not os.path.exists(filename):
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'code', 'name', 'price', 'change_percent',
                    'volume', 'amount', 'bid_price', 'ask_price', 
                    'bid_volume', 'ask_volume'
                ])
        
        # 打开文件句柄
        file_handle = open(filename, 'a', newline='', encoding='utf-8')
        csv_writer = csv.writer(file_handle)
        
        self.file_handles[stock_code] = file_handle
        self.csv_writers[stock_code] = csv_writer
        self.current_files[stock_code] = filename
        
        logger.info(f"初始化逐笔数据文件: {filename}")
    
    def store_tick_data(self, tick_data: TickData):
        """存储逐笔数据"""
        with self.lock:
            try:
                if tick_data.code not in self.csv_writers:
                    self.initialize_csv_file(tick_data.code, tick_data.name)
                
                # 写入CSV行
                writer = self.csv_writers[tick_data.code]
                writer.writerow([
                    tick_data.timestamp.isoformat(),
                    tick_data.code,
                    tick_data.name,
                    tick_data.price,
                    tick_data.change_percent,
                    tick_data.volume,
                    tick_data.amount,
                    tick_data.bid_price,
                    tick_data.ask_price,
                    tick_data.bid_volume,
                    tick_data.ask_volume
                ])
                
                # 立即刷新到磁盘
                self.file_handles[tick_data.code].flush()
                
            except Exception as e:
                logger.error(f"存储逐笔数据失败 {tick_data.code}: {e}")
    
    def load_daily_data(self, stock_code: str, date_str: str) -> List[TickData]:
        """加载单日数据"""
        filename = self.get_daily_filename(stock_code, date_str)
        tick_data_list = []
        
        if not os.path.exists(filename):
            logger.warning(f"数据文件不存在: {filename}")
            return tick_data_list
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tick_data = TickData(
                        code=row['code'],
                        name=row['name'],
                        price=float(row['price']),
                        change_percent=float(row['change_percent']),
                        volume=int(row['volume']),
                        amount=float(row['amount']),
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        bid_price=float(row.get('bid_price', 0)),
                        ask_price=float(row.get('ask_price', 0)),
                        bid_volume=int(row.get('bid_volume', 0)),
                        ask_volume=int(row.get('ask_volume', 0))
                    )
                    tick_data_list.append(tick_data)
            
            logger.info(f"加载 {stock_code} {date_str} 数据: {len(tick_data_list)} 条记录")
            return sorted(tick_data_list, key=lambda x: x.timestamp)  # 按时间排序
            
        except Exception as e:
            logger.error(f"加载数据失败 {filename}: {e}")
            return []
    
    def get_available_stocks(self) -> List[str]:
        """获取可用的股票列表"""
        stocks = set()
        try:
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.csv'):
                    stock_code = filename.split('_')[0]
                    stocks.add(stock_code)
        except Exception as e:
            logger.error(f"获取可用股票列表失败: {e}")
        
        return sorted(list(stocks))
    
    def get_available_dates(self, stock_code: str) -> List[str]:
        """获取可用的日期列表"""
        dates = []
        try:
            for filename in os.listdir(self.data_dir):
                if filename.startswith(f"{stock_code}_"):
                    date_str = filename.replace(f"{stock_code}_", "").replace(".csv", "")
                    dates.append(date_str)
        except Exception as e:
            logger.error(f"获取可用日期列表失败 {stock_code}: {e}")
        
        return sorted(dates)
    
    def analyze_daily_data(self, stock_code: str, date_str: str) -> Dict:
        """分析单日数据"""
        data = self.load_daily_data(stock_code, date_str)
        if not data:
            return {}
        
        # 统计信息
        total_ticks = len(data)
        time_span = data[-1].timestamp - data[0].timestamp
        avg_interval = time_span.total_seconds() / total_ticks if total_ticks > 1 else 0
        
        # 价格变化统计
        price_changes = []
        volumes = []
        amounts = []
        
        for i in range(1, len(data)):
            price_change = abs(data[i].price - data[i-1].price)
            price_changes.append(price_change)
            volumes.append(data[i].volume)
            amounts.append(data[i].amount)
        
        analysis = {
            'stock_code': stock_code,
            'date': date_str,
            'total_ticks': total_ticks,
            'time_span_seconds': time_span.total_seconds(),
            'time_span_human': str(time_span),
            'avg_interval_seconds': avg_interval,
            'avg_price_change': float(np.mean(price_changes)) if price_changes else 0,
            'max_price_change': float(max(price_changes)) if price_changes else 0,
            'avg_volume': float(np.mean(volumes)) if volumes else 0,
            'avg_amount': float(np.mean(amounts)) if amounts else 0,
            'start_time': data[0].timestamp.isoformat(),
            'end_time': data[-1].timestamp.isoformat(),
            'start_price': data[0].price,
            'end_price': data[-1].price,
            'price_change': data[-1].price - data[0].price,
            'price_change_percent': (data[-1].price - data[0].price) / data[0].price * 100
        }
        
        logger.info(f"数据分析 - {stock_code} {date_str}:")
        logger.info(f"  总记录数: {total_ticks}")
        logger.info(f"  时间跨度: {time_span}")
        logger.info(f"  平均间隔: {avg_interval:.2f}秒")
        logger.info(f"  平均价格变化: {analysis['avg_price_change']:.4f}")
        logger.info(f"  最大价格变化: {analysis['max_price_change']:.4f}")
        logger.info(f"  平均成交量: {analysis['avg_volume']:.0f}手")
        
        return analysis
    
    def get_data_summary(self) -> Dict:
        """获取数据目录摘要"""
        summary = {
            'total_stocks': 0,
            'total_files': 0,
            'stocks': {},
            'earliest_date': None,
            'latest_date': None
        }
        
        try:
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.csv'):
                    summary['total_files'] += 1
                    parts = filename.replace('.csv', '').split('_')
                    if len(parts) == 2:
                        stock_code, date_str = parts
                        
                        if stock_code not in summary['stocks']:
                            summary['stocks'][stock_code] = {
                                'file_count': 0,
                                'dates': []
                            }
                        
                        summary['stocks'][stock_code]['file_count'] += 1
                        summary['stocks'][stock_code]['dates'].append(date_str)
                        
                        # 更新最早和最晚日期
                        if summary['earliest_date'] is None or date_str < summary['earliest_date']:
                            summary['earliest_date'] = date_str
                        if summary['latest_date'] is None or date_str > summary['latest_date']:
                            summary['latest_date'] = date_str
            
            summary['total_stocks'] = len(summary['stocks'])
            
        except Exception as e:
            logger.error(f"获取数据摘要失败: {e}")
        
        return summary
    
    def close_all_files(self):
        """关闭所有文件句柄"""
        with self.lock:
            for code, file_handle in self.file_handles.items():
                try:
                    file_handle.close()
                except Exception as e:
                    logger.error(f"关闭文件失败 {code}: {e}")
            
            self.file_handles.clear()
            self.csv_writers.clear()
            self.current_files.clear()
    
    def __del__(self):
        self.close_all_files()