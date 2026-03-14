import logging
import threading
import time
import signal
import os
import requests
from datetime import datetime, time as dt_time, date, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from colorama import Fore, Style, init

from .models import StockConfig, StockData
from .config import ConfigManager
from .historical import HistoricalVolumeManager
from .analyzer import VolumeAnalyzer, PriceChangeLogger


def create_sample_config(config_path: str = 'config.yaml'):
    """创建示例配置文件（简化版）"""
    sample_config = {
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
                    'enabled': True,
                    'price_alerts': {
                        'upper_limit': 60.0,
                        'lower_limit': 35.0
                    },
                    'change_speed_alerts': {
                        'max_change_per_minute': 3.0,
                        'volume_spike_ratio': 5.0,
                        'volume_time_ratio_alert': 3.0
                    },
                    'log_interval': 60  # 每60秒输出一次价格变化摘要
                },
                '601012': {
                    'name': '隆基绿能',
                    'interval': 15,
                    'enabled': True,
                    'price_alerts': {
                        'upper_limit': 25.0,
                        'lower_limit': 15.0
                    },
                    'change_speed_alerts': {
                        'max_change_per_minute': 3.0,
                        'volume_spike_ratio': 5.0,
                        'volume_time_ratio_alert': 2.5
                    },
                    'log_interval': 120  # 每120秒输出一次价格变化摘要
                },
                '300454': {
                    'name': '深信服',
                    'interval': 10,
                    'enabled': True,
                    'price_alerts': {
                        'upper_limit': 80.0,
                        'lower_limit': 50.0
                    },
                    'change_speed_alerts': {
                        'max_change_per_minute': 4.0,
                        'volume_spike_ratio': 6.0,
                        'volume_time_ratio_alert': 3.0
                    },
                    'log_interval': 90  # 每90秒输出一次价格变化摘要
                }
            }
        }
    }
    
    with open(g_config_file, 'w', encoding='utf-8') as f:
        yaml.dump(sample_config, f, allow_unicode=True, indent=2)
    
    print(f"已创建示例配置文件: {config_path}")

class StockMonitor:
    def __init__(self, config_path: str = "config.yaml"):
        init(autoreset=True)
        self.config_path = config_path
        self.config_manager = ConfigManager(config_path)
        self.config_manager.add_listener(self)
        
        # 初始化历史成交量管理器
        self.historical_manager = HistoricalVolumeManager()
        
        # 监控状态
        self.stock_configs: Dict[str, StockConfig] = {}
        self.global_settings: Dict[str, str] = {}
        self.monitor_threads: Dict[str, threading.Thread] = {}
        self.monitor_flags: Dict[str, bool] = {}
        self.price_history: Dict[str, List[StockData]] = defaultdict(list)
        self.volume_analyzer = VolumeAnalyzer(self.historical_manager)
        self.price_logger = PriceChangeLogger()
        
        self.reload_config(True)
        self.setup_logging()
        self.setup_signal_handlers()
        
        # 启动历史数据更新线程
        self.start_historical_data_updater()
    
    def setup_logging(self):
        """设置日志"""
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        # 移除已有 handlers
        for h in list(root.handlers):
            root.removeHandler(h)

        log_file = os.path.join(self.global_settings['log_dir'], f"monitor_{datetime.now().strftime("%Y%m%d")}.log")
        alert_file = os.path.join(self.global_settings['log_dir'], f"alerts_{datetime.now().strftime("%Y%m%d")}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        # 单独设置警报日志
        self.alert_logger = logging.getLogger('alerts')
        self.alert_logger.setLevel(logging.WARNING)
        alert_handler = logging.FileHandler(alert_file, encoding='utf-8')
        alert_handler.setFormatter(logging.Formatter('%(asctime)s - ALERT - %(message)s'))
        self.alert_logger.addHandler(alert_handler)
        
    def setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logging.info(f"接收到信号 {signum}，重新加载配置...")
            self.config_manager.load_config()
        
        signal.signal(signal.SIGHUP, signal_handler)
        signal.signal(signal.SIGUSR1, signal_handler)
    
    def on_config_updated(self, new_config: dict):
        """配置更新回调"""
        logging.info("检测到配置变更，重新加载监控规则...")
        self.reload_config()
    
    def reload_config(self, initial_load: bool = False):
        """重新加载配置（优化版，只预加载新增股票）"""
        config = self.config_manager.load_config(initial_load)
        if not config:
            return
        
        monitor_settings = config.get('monitor_settings', {})
        # 用于设置日志级别
        self.global_settings = monitor_settings.get('global', {})
        if initial_load:
            logging.info("初始加载配置文件")
            return
        
        stocks_config = monitor_settings.get('stocks', {})
        
        new_stock_configs = {}
        for code, stock_config in stocks_config.items():
            new_stock_configs[code] = StockConfig(
                code=code,
                name=stock_config['name'],
                interval=stock_config.get('interval', self.global_settings.get('default_interval', 10)),
                upper_limit=stock_config['price_alerts']['upper_limit'],
                lower_limit=stock_config['price_alerts']['lower_limit'],
                max_change_per_minute=stock_config['change_speed_alerts']['max_change_per_minute'],
                volume_spike_ratio=stock_config['change_speed_alerts']['volume_spike_ratio'],
                volume_time_ratio_alert=stock_config['change_speed_alerts'].get('volume_time_ratio_alert', 3.0),
                log_interval=stock_config.get('log_interval', 60),
                enabled=stock_config.get('enabled', True)
            )
        
        # 获取需要新监控的股票代码
        added_codes = []
        for code in new_stock_configs:
            if new_stock_configs[code].enabled == True and ( 
                code not in self.stock_configs or self.stock_configs[code].enabled == False):
                added_codes.append(code)
                
        # 更新监控线程
        self.update_monitor_threads(new_stock_configs)
        self.stock_configs = new_stock_configs
        
        # 只预加载新增的股票历史数据
        if added_codes:
            logging.info(f"检测到 {len(added_codes)} 只新增股票，开始预加载历史数据...")
            self.historical_manager.preload_selected_stocks(list(added_codes))
        else:
            logging.info("配置重载完成，无新增股票，无需预加载历史数据")
    
    def update_monitor_threads(self, new_configs: Dict[str, StockConfig]):
        """更新监控线程"""
        current_codes = set(self.monitor_flags.keys())
        new_codes = set(new_configs.keys())
        # 停止需要删除的股票监控
        codes_to_remove = current_codes - new_codes
        for code in codes_to_remove:
            self.stop_monitor_thread(code)
            logging.info(f"停止监控股票: {code}")
        
        # 更新现有股票的配置
        codes_to_update = current_codes & new_codes
        for code in codes_to_update:
            old_config = self.stock_configs.get(code)
            new_config = new_configs[code]
            
            # 如果配置有变化且线程在运行，重启线程
            if old_config and self.is_config_changed(old_config, new_config):
                logging.info(f"配置变更，重启监控: {new_config.name}({code})")
                self.stop_monitor_thread(code)
                self.start_monitor_thread(code, new_config)
            elif not new_config.enabled and self.monitor_flags.get(code, False):
                logging.info(f"暂停监控: {new_config.name}({code})")
                self.stop_monitor_thread(code)
            elif new_config.enabled and not self.monitor_flags.get(code, False):
                logging.info(f"恢复监控: {new_config.name}({code})")
                self.start_monitor_thread(code, new_config)
        
        # 启动新增股票的监控
        codes_to_add = new_codes - current_codes
        for code in codes_to_add:
            config = new_configs[code]
            if config.enabled:
                logging.info(f"新增监控: {config.name}({code})")
                self.start_monitor_thread(code, config)

        current_codes = set(self.monitor_flags.keys())
        logging.info(f"监控更新完成，当前监控股票数量: {len(current_codes)}")
    
    def is_config_changed(self, old_config: StockConfig, new_config: StockConfig) -> bool:
        """检查配置是否发生变化"""
        return any(
            getattr(old_config, field) != getattr(new_config, field)
            for field in ['interval', 'upper_limit', 'lower_limit', 
                         'max_change_per_minute', 'volume_spike_ratio', 
                         'volume_time_ratio_alert', 'log_interval', 'enabled']
        )
    
    def stop_monitor_thread(self, stock_code: str):
        """停止监控线程（增强版）"""
        if stock_code not in self.monitor_flags or not self.monitor_flags[stock_code]:
            logging.info(f"监控线程 {stock_code} 未运行或已停止")
            return
    
        logging.info(f"正在停止监控线程: {stock_code}")
        self.monitor_flags[stock_code] = False
        
        if stock_code in self.monitor_threads:
            thread = self.monitor_threads[stock_code]
            
            # 等待线程正常退出
            for i in range(5):  # 最多等待5次
                thread.join(timeout=1)
                if not thread.is_alive():
                    logging.info(f"监控线程 {stock_code} 已正常停止")
                    break
                logging.debug(f"等待线程 {stock_code} 停止... ({i+1}/5)")
            else:
                logging.warning(f"监控线程 {stock_code} 停止超时，将在下次循环时退出")
            
            # 清理资源
            try:
                del self.monitor_threads[stock_code]
                if stock_code in self.monitor_flags:
                    del self.monitor_flags[stock_code]
                logging.info(f"监控线程 {stock_code} 资源已清理")
            except KeyError:
                pass
    
    # 计算买卖盘比例
    def calculate_limit_status(self, bid_volume, ask_volume):
        """
        计算涨跌停状态和金额
        """
        # 涨停判断
        if ask_volume == 0:
            ask_bid_status = f"{Fore.RED}涨停 封板量 {int(bid_volume/100)} 手"

        # 跌停判断  
        elif bid_volume == 0:
            ask_bid_status = f"{Fore.GREEN}跌停 封板量 {int(ask_volume/100)} 手"
        
        else:
            ask_bid_status = f"卖盘{ask_volume} 买盘{bid_volume} 买卖比{bid_volume/ask_volume*100:.2f}%"
        
        return ask_bid_status

    def monitor_single_stock(self, stock_code: str, config: StockConfig):
        """监控单个股票（优化停止检查）"""
        consecutive_errors = 0
        last_price = None
        
        logging.info(f"启动监控线程: {stock_code}")
        
        while self.monitor_flags.get(stock_code, False):
            try:
                # 在关键位置频繁检查停止标志
                if not self.monitor_flags.get(stock_code, False):
                    break
                    
                if not self.is_trading_time():
                    # 非交易时间，减少检查频率但保持响应性
                    for _ in range(6):  # 每分钟检查一次停止标志
                        if not self.monitor_flags.get(stock_code, False):
                            break
                        time.sleep(10)
                    continue
                
                # 获取数据前检查
                if not self.monitor_flags.get(stock_code, False):
                    break
                    
                stock_data = self.get_stock_data(stock_code)
                
                # 处理数据后立即检查
                if not self.monitor_flags.get(stock_code, False):
                    break
                    
                if stock_data:
                    consecutive_errors = 0
                    
                    # 记录价格变化
                    self.price_logger.record_price(stock_data)
                    
                    # 检查价格变化是否需要输出详细日志
                    if self.price_logger.should_log_price_change(stock_code, config.log_interval):
                        # 输出价格变化摘要
                        price_summary = self.price_logger.get_price_change_summary(stock_code, stock_data.name)
                        logging.info(f"📊 {price_summary}")
                    
                    # 检查所有警报
                    alerts = self.check_alerts(stock_data, config)
                    for alert in alerts:
                        logging.warning(f"🚨 ALERT - {stock_data.name}({stock_code}): {alert}")
                    
                    # 正常监控日志
                    volume_summary = self.volume_analyzer.get_volume_summary(stock_code, stock_data.timestamp)

                    # 买卖盘状态
                    ask_bid_status = self.calculate_limit_status(stock_data.bid_volume, stock_data.ask_volume)
                    
                    # 添加价格变化箭头
                    price_change_indicator = ""
                    if last_price is not None:
                        if stock_data.price > last_price:
                            price_change_indicator = "📈"
                        elif stock_data.price < last_price:
                            price_change_indicator = "📉"
                    
                    if stock_data.change_percent > 0: 
                        front_color = Fore.RED
                    elif stock_data.change_percent < 0: 
                        front_color = Fore.GREEN
                    else: 
                        front_color = Fore.BLACK

                    logging.info(
                        f"{price_change_indicator} {stock_data.name}({stock_code}) - "
                        f"价格: {stock_data.price:.2f} | 涨跌幅: {front_color}{stock_data.change_percent:+.2f}%{Style.RESET_ALL} | "
                        f"{volume_summary} | "
                        f"{ask_bid_status}"
                    )
                    
                    last_price = stock_data.price
                    
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        logging.warning(f"连续获取 {stock_code} 数据失败")
                        # 在等待期间也要检查停止标志
                        for _ in range(6):
                            if not self.monitor_flags.get(stock_code, False):
                                break
                            time.sleep(5)
                
                # 在睡眠期间分段检查停止标志
                sleep_interval = config.interval
                chunk_size = 2  # 每2秒检查一次
                chunks = max(1, sleep_interval // chunk_size)
                
                for _ in range(chunks):
                    if not self.monitor_flags.get(stock_code, False):
                        break
                    time.sleep(chunk_size)
                    
            except Exception as e:
                logging.error(f"监控 {stock_code} 异常: {e}")
                # 异常后也要检查停止标志
                if not self.monitor_flags.get(stock_code, False):
                    break
                time.sleep(min(config.interval, 10))
        
        logging.info(f"监控线程 {stock_code} 已退出循环")
    
    def start_monitor_thread(self, stock_code: str, config: StockConfig):
        """启动监控线程"""
        if stock_code in self.monitor_threads and self.monitor_flags.get(stock_code, False):
            return
        
        self.monitor_flags[stock_code] = True
        thread = threading.Thread(
            target=self.monitor_single_stock,
            args=(stock_code, config),
            daemon=True
        )
        self.monitor_threads[stock_code] = thread
        thread.start()
    
    def get_stock_data(self, stock_code: str) -> Optional[StockData]:
        """获取股票数据"""
        try:
            prefix = 'sh' if stock_code.startswith('6') else 'sz'
            url = f"https://hq.sinajs.cn/list={prefix}{stock_code}"
            
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
                    
                    # 修复：新浪API返回的成交量单位是股，需要转换为手（1手=100股）
                    volume_in_shares = int(data_str[8])  # 成交量（股）
                    volume_in_hands = volume_in_shares // 100  # 成交量（手）
                    return StockData(
                        code=stock_code,
                        name=data_str[0],
                        price=current_price,
                        change_percent=round(change_percent, 2),
                        volume=volume_in_hands,
                        amount=float(data_str[9]),
                        timestamp=datetime.now(),
                        bid_volume=int(data_str[10]),
                        ask_volume=int(data_str[20])
                    )
            else:
                logging.warning(f"获取股票 {stock_code} 数据失败，状态码: {response.status_code}")
        except Exception as e:
            logging.warning(f"获取股票 {stock_code} 数据失败: {e}")
        return None
    
    def check_alerts(self, stock_data: StockData, config: StockConfig) -> List[str]:
        """检查所有警报条件"""
        alerts = []
        
        # 价格边界检查
        if stock_data.price >= config.upper_limit:
            alerts.append(f"价格突破上限 {config.upper_limit}，当前价: {stock_data.price:.2f}")
        
        if stock_data.price <= config.lower_limit:
            alerts.append(f"价格跌破下限 {config.lower_limit}，当前价: {stock_data.price:.2f}")
        
        # 成交量时间比例检查
        volume_alerts = self.volume_analyzer.check_volume_alerts(
            stock_data.code, 
            stock_data.volume, 
            stock_data.timestamp, 
            config.volume_time_ratio_alert
        )
        alerts.extend(volume_alerts)
        
        return alerts
    
    def is_trading_time(self) -> bool:
        """判断是否为交易时间"""
        now = datetime.now()
        current_time = now.time()
        current_weekday = now.weekday()
        
        if current_weekday >= 5:
            return False
        
        morning_start = dt_time(9, 25)
        morning_end = dt_time(11, 30)
        afternoon_start = dt_time(12, 59)
        afternoon_end = dt_time(15, 0)
        
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)
    
    def start_historical_data_updater(self):
        """启动历史数据更新器"""
        def update_historical_data():
            while True:
                try:
                    current_time = datetime.now()
                    # 每天收盘后（下午6点）更新历史数据
                    if current_time.hour == 18 and current_time.minute == 0:
                        logging.info("开始自动更新历史成交量数据...")
                        for stock_code in self.stock_configs.keys():
                            if self.stock_configs[stock_code].enabled:
                                self.historical_manager.get_historical_volume_data(stock_code, force_update=True)
                                time.sleep(1)  # 避免请求过于频繁
                        logging.info("历史成交量数据自动更新完成")
                        time.sleep(3600)  # 1小时后再次检查
                    else:
                        time.sleep(300)  # 5分钟检查一次
                except Exception as e:
                    logging.error(f"历史数据更新失败: {e}")
                    time.sleep(600)
        
        updater_thread = threading.Thread(target=update_historical_data, daemon=True)
        updater_thread.start()
        logging.info("历史数据自动更新器已启动")
    
    def start_monitoring(self):
        """启动监控系统"""
        logging.info("启动动态配置股票监控系统（含定时价格变化日志）...")
        
        self.config_manager.start_monitoring(interval=5)
        
        for code, config in self.stock_configs.items():
            if config.enabled:
                self.start_monitor_thread(code, config)
        
        logging.info(f"监控系统已启动，当前监控 {len(self.stock_configs)} 只股票")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("正在停止监控系统...")
            self.stop_all_monitors()
            logging.info("监控系统已停止")

    def stop_all_monitors(self):
        """停止所有监控"""
        for code in list(self.monitor_flags.keys()):
            self.stop_monitor_thread(code)

