import yaml
import akshare as ak
import requests
import time
import json
import logging
from datetime import datetime, time as dt_time
from typing import Dict, List, Optional
import threading
from dataclasses import dataclass
from collections import defaultdict
import os
import random

@dataclass
class StockConfig:
    """股票配置数据类"""
    code: str
    name: str
    interval: int
    upper_limit: float
    lower_limit: float
    max_change_per_minute: float
    volume_spike_ratio: float

@dataclass
class StockData:
    """股票数据类"""
    code: str
    name: str
    price: float
    change_percent: float
    volume: int
    timestamp: datetime
    previous_data: Optional['StockData'] = None

class StableStockMonitor:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self.load_config()
        self.stock_configs: Dict[str, StockConfig] = {}
        self.price_history: Dict[str, List[StockData]] = defaultdict(list)
        self.data_source_priority = ['sina', 'tencent', 'akshare']  # 数据源优先级
        self.setup_logging()
        self.parse_config()
        
    def load_config(self) -> dict:
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            self.create_default_config()
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            'monitor_settings': {
                'global': {
                    'default_interval': 10,
                    'log_file': 'stock_monitor.log',
                    'alert_file': 'stock_alerts.log'
                },
                'stocks': {
                    '002466': {
                        'name': '天齐锂业',
                        'interval': 10,
                        'price_alerts': {
                            'upper_limit': 60.0,
                            'lower_limit': 35.0
                        },
                        'change_speed_alerts': {
                            'max_change_per_minute': 3.0,
                            'volume_spike_ratio': 5.0
                        }
                    },
                    '601012': {
                        'name': '隆基绿能',
                        'interval': 10,
                        'price_alerts': {
                            'upper_limit': 25.0,
                            'lower_limit': 15.0
                        },
                        'change_speed_alerts': {
                            'max_change_per_minute': 3.0,
                            'volume_spike_ratio': 5.0
                        }
                    },
                    '300454': {
                        'name': '深信服',
                        'interval': 10,
                        'price_alerts': {
                            'upper_limit': 80.0,
                            'lower_limit': 50.0
                        },
                        'change_speed_alerts': {
                            'max_change_per_minute': 4.0,
                            'volume_spike_ratio': 6.0
                        }
                    }
                }
            }
        }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, allow_unicode=True)
        print(f"已创建默认配置文件: {self.config_path}")
    
    def setup_logging(self):
        """设置日志"""
        log_file = self.config['monitor_settings']['global']['log_file']
        alert_file = self.config['monitor_settings']['global']['alert_file']
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.alert_logger = logging.getLogger('alerts')
        self.alert_logger.setLevel(logging.WARNING)
        alert_handler = logging.FileHandler(alert_file, encoding='utf-8')
        alert_handler.setFormatter(logging.Formatter('%(asctime)s - ALERT - %(message)s'))
        self.alert_logger.addHandler(alert_handler)
    
    def parse_config(self):
        """解析配置到数据类"""
        stocks_config = self.config['monitor_settings']['stocks']
        for code, config in stocks_config.items():
            self.stock_configs[code] = StockConfig(
                code=code,
                name=config['name'],
                interval=config.get('interval', self.config['monitor_settings']['global']['default_interval']),
                upper_limit=config['price_alerts']['upper_limit'],
                lower_limit=config['price_alerts']['lower_limit'],
                max_change_per_minute=config['change_speed_alerts']['max_change_per_minute'],
                volume_spike_ratio=config['change_speed_alerts']['volume_spike_ratio']
            )
    
    def get_stock_code_prefix(self, stock_code: str) -> str:
        """根据股票代码确定交易所前缀"""
        if stock_code.startswith('6'):
            return 'sh'  # 上交所
        elif stock_code.startswith('0') or stock_code.startswith('3'):
            return 'sz'  # 深交所
        else:
            return 'sz'
    
    def get_stock_data_sina(self, stock_code: str) -> Optional[StockData]:
        """使用新浪财经API（最稳定）"""
        try:
            prefix = self.get_stock_code_prefix(stock_code)
            url = f"https://hq.sinajs.cn/list={prefix}{stock_code}"
            
            headers = {
                'Referer': 'https://finance.sina.com.cn/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200 and len(response.text) > 10:
                data_str = response.text.split('="')[1].split(',')
                if len(data_str) > 30:  # 新浪返回数据有30多个字段
                    current_price = float(data_str[3])
                    yesterday_close = float(data_str[2])
                    change_percent = (current_price - yesterday_close) / yesterday_close * 100
                    
                    return StockData(
                        code=stock_code,
                        name=data_str[0],
                        price=current_price,
                        change_percent=round(change_percent, 2),
                        volume=int(data_str[8]),
                        timestamp=datetime.now()
                    )
        except Exception as e:
            logging.debug(f"新浪API获取 {stock_code} 失败: {str(e)[:100]}")
        
        return None
    
    def get_stock_data_tencent(self, stock_code: str) -> Optional[StockData]:
        """使用腾讯财经API"""
        try:
            prefix = self.get_stock_code_prefix(stock_code)
            url = f"http://qt.gtimg.cn/q={prefix}{stock_code}"
            
            headers = {
                'Referer': 'https://gu.qq.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.text.split('~')
                if len(data) > 40:
                    return StockData(
                        code=stock_code,
                        name=data[1],
                        price=float(data[3]),
                        change_percent=float(data[32] if data[32] else data[5]),
                        volume=int(data[6]),
                        timestamp=datetime.now()
                    )
        except Exception as e:
            logging.debug(f"腾讯API获取 {stock_code} 失败: {str(e)[:100]}")
        
        return None
    
    def get_stock_data_akshare(self, stock_code: str) -> Optional[StockData]:
        """使用AkShare（备用）"""
        try:
            # 尝试不同的AkShare函数
            for func_name in ['stock_zh_a_spot_em', 'stock_zh_a_spot']:
                try:
                    if func_name == 'stock_zh_a_spot_em':
                        stock_info = ak.stock_zh_a_spot_em()
                    else:
                        stock_info = ak.stock_zh_a_spot()
                    
                    prefix = self.get_stock_code_prefix(stock_code)
                    full_code = f"{prefix}{stock_code}"
                    target_stock = stock_info[stock_info['代码'] == full_code]
                    
                    if not target_stock.empty:
                        return StockData(
                            code=stock_code,
                            name=target_stock['名称'].values[0],
                            price=float(target_stock['最新价'].values[0]),
                            change_percent=float(target_stock['涨跌幅'].values[0]),
                            volume=int(target_stock['成交量'].values[0]),
                            timestamp=datetime.now()
                        )
                except Exception as e:
                    continue
                    
        except Exception as e:
            logging.debug(f"AkShare获取 {stock_code} 失败: {str(e)[:100]}")
        
        return None
    
    def get_stock_data(self, stock_code: str) -> Optional[StockData]:
        """多数据源获取股票数据"""
        data_sources = {
            'sina': self.get_stock_data_sina,
            'tencent': self.get_stock_data_tencent,
            'akshare': self.get_stock_data_akshare
        }
        
        # 按优先级尝试不同数据源
        for source_name in self.data_source_priority:
            if source_name in data_sources:
                data = data_sources[source_name](stock_code)
                if data:
                    logging.debug(f"使用 {source_name} 成功获取 {stock_code} 数据")
                    return data
                else:
                    logging.debug(f"{source_name} 获取 {stock_code} 失败")
        
        logging.error(f"所有数据源获取 {stock_code} 均失败")
        return None
    
    def check_alerts(self, stock_data: StockData, config: StockConfig) -> List[str]:
        """检查各种警报条件"""
        alerts = []
        
        # 价格边界检查
        if stock_data.price >= config.upper_limit:
            alerts.append(f"价格突破上限 {config.upper_limit}，当前价: {stock_data.price:.2f}")
        
        if stock_data.price <= config.lower_limit:
            alerts.append(f"价格跌破下限 {config.lower_limit}，当前价: {stock_data.price:.2f}")
        
        # 价格变化速度检查
        if len(self.price_history[stock_data.code]) > 0:
            previous_data = self.price_history[stock_data.code][-1]
            time_diff = (stock_data.timestamp - previous_data.timestamp).total_seconds() / 60
            if time_diff > 0:
                price_diff_percent = abs(stock_data.change_percent - previous_data.change_percent)
                change_speed = price_diff_percent / time_diff
                
                if change_speed > config.max_change_per_minute:
                    alerts.append(f"价格变化过快: {change_speed:.2f}%/分钟")
        
        # 成交量突增检查
        if len(self.price_history[stock_data.code]) > 1:
            previous_volume = self.price_history[stock_data.code][-1].volume
            if previous_volume > 0:
                volume_ratio = stock_data.volume / previous_volume
                if volume_ratio > config.volume_spike_ratio:
                    alerts.append(f"成交量突增: {volume_ratio:.1f}倍")
        
        return alerts
    
    def monitor_single_stock(self, stock_code: str):
        """监控单个股票"""
        config = self.stock_configs[stock_code]
        consecutive_errors = 0
        max_errors = 5
        
        while True:
            try:
                if not self.is_trading_time():
                    time.sleep(60)
                    continue
                
                stock_data = self.get_stock_data(stock_code)
                if stock_data:
                    consecutive_errors = 0  # 重置错误计数
                    
                    # 记录数据
                    self.price_history[stock_code].append(stock_data)
                    if len(self.price_history[stock_code]) > 10:
                        self.price_history[stock_code].pop(0)
                    
                    # 检查警报
                    alerts = self.check_alerts(stock_data, config)
                    for alert in alerts:
                        alert_msg = f"{stock_data.name}({stock_data.code}) - {alert}"
                        self.alert_logger.warning(alert_msg)
                        logging.warning(f"ALERT: {alert_msg}")
                    
                    # 正常日志
                    logging.info(
                        f"{stock_data.name}({stock_data.code}) - "
                        f"价格: {stock_data.price:.2f} | 涨跌幅: {stock_data.change_percent:.2f}% | "
                        f"成交量: {stock_data.volume:,}"
                    )
                else:
                    consecutive_errors += 1
                    logging.warning(f"获取 {stock_code} 数据失败 ({consecutive_errors}/{max_errors})")
                    
                    if consecutive_errors >= max_errors:
                        logging.error(f"连续{max_errors}次获取失败，暂停监控 {stock_code} 5分钟")
                        time.sleep(300)  # 暂停5分钟
                        consecutive_errors = 0
                
                # 添加随机延迟，避免规律请求
                time.sleep(config.interval + random.uniform(0, 2))
                
            except Exception as e:
                consecutive_errors += 1
                logging.error(f"监控 {stock_code} 异常: {e}")
                time.sleep(min(config.interval * 2, 60))
    
    def is_trading_time(self) -> bool:
        """判断是否为交易时间"""
        now = datetime.now()
        current_time = now.time()
        current_weekday = now.weekday()
        
        if current_weekday >= 5:
            return False
        
        morning_start = dt_time(9, 30)
        morning_end = dt_time(11, 30)
        afternoon_start = dt_time(13, 0)
        afternoon_end = dt_time(15, 0)
        
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)
    
    def start_monitoring(self):
        """启动监控"""
        logging.info("启动增强版股票监控系统...")
        logging.info(f"监控股票数量: {len(self.stock_configs)}")
        logging.info("数据源优先级: 新浪财经 -> 腾讯财经 -> AkShare")
        
        threads = []
        for stock_code in self.stock_configs:
            thread = threading.Thread(
                target=self.monitor_single_stock,
                args=(stock_code,),
                daemon=True
            )
            thread.start()
            threads.append(thread)
            logging.info(f"开始监控: {self.stock_configs[stock_code].name}({stock_code})")
            time.sleep(1)  # 错开启动时间
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("监控系统已停止")

if __name__ == "__main__":
    # 设置更详细的日志级别用于调试
    logging.getLogger().setLevel(logging.INFO)
    monitor = StableStockMonitor("config.yaml")
    monitor.start_monitoring()