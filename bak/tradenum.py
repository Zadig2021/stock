import yaml
import akshare as ak
import requests
import time
import logging
import threading
import signal
import os
import sys
from datetime import datetime, time as dt_time, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
from pathlib import Path
import hashlib

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
    volume_time_ratio_alert: float  # 成交量时间比例警报阈值
    enabled: bool = True

@dataclass
class StockData:
    """股票数据类"""
    code: str
    name: str
    price: float
    change_percent: float
    volume: int  # 当前成交量（手）
    amount: float  # 成交额（万元）
    timestamp: datetime

@dataclass
class DailyVolumeStats:
    """当日成交量统计"""
    date: date
    total_volume: int = 0  # 当日总成交量（手）
    last_update: Optional[datetime] = None
    volume_alerts_triggered: set = None  # 记录已触发的警报类型
    
    def __post_init__(self):
        if self.volume_alerts_triggered is None:
            self.volume_alerts_triggered = set()

class VolumeAnalyzer:
    """成交量分析器 - 修复版"""
    
    def __init__(self):
        self.daily_stats: Dict[str, DailyVolumeStats] = {}
        self.trading_minutes_per_day = 240  # 4小时 * 60分钟
        
    def get_trading_time_progress(self, current_time: datetime) -> Tuple[float, str, int]:
        """
        获取当日交易时间进度（修复版）
        返回: (进度比例, 交易时段描述, 已交易分钟数)
        """
        current_time_obj = current_time.time()
        
        # 定义交易时段
        morning_start = dt_time(9, 30)
        morning_end = dt_time(11, 30)
        afternoon_start = dt_time(13, 0)
        afternoon_end = dt_time(15, 0)
        
        total_minutes = self.trading_minutes_per_day
        
        if morning_start <= current_time_obj <= morning_end:
            # 上午时段：9:30-11:30 (2小时)
            elapsed_minutes = (current_time_obj.hour - morning_start.hour) * 60 + \
                            (current_time_obj.minute - morning_start.minute)
            progress = elapsed_minutes / 120  # 上午2小时=120分钟
            period = "上午"
            total_elapsed = elapsed_minutes
            
        elif afternoon_start <= current_time_obj <= afternoon_end:
            # 下午时段：13:00-15:00 (2小时)
            elapsed_minutes = (current_time_obj.hour - afternoon_start.hour) * 60 + \
                            (current_time_obj.minute - afternoon_start.minute)
            progress = (120 + elapsed_minutes) / total_minutes  # 上午120分钟 + 下午已交易时间
            period = "下午"
            total_elapsed = 120 + elapsed_minutes
            
        elif current_time_obj < morning_start:
            # 开盘前
            progress = 0.0
            period = "开盘前"
            total_elapsed = 0
            
        elif morning_end < current_time_obj < afternoon_start:
            # 午间休市
            progress = 120 / total_minutes  # 上午交易已完成
            period = "午间休市"
            total_elapsed = 120
            
        else:
            # 收盘后
            progress = 1.0
            period = "收盘后"
            total_elapsed = total_minutes
        
        return min(max(progress, 0.0), 1.0), period, total_elapsed
    
    def calculate_volume_ratio(self, stock_code: str, current_volume: int, 
                             current_time: datetime, avg_daily_volume: int = None) -> Tuple[float, float, str]:
        """
        计算成交量比例（修复版）
        返回: (成交量比例, 时间进度, 交易时段)
        """
        time_progress, period, elapsed_minutes = self.get_trading_time_progress(current_time)
        
        if stock_code not in self.daily_stats:
            self.daily_stats[stock_code] = DailyVolumeStats(date=current_time.date())
        
        daily_stats = self.daily_stats[stock_code]
        daily_stats.total_volume = current_volume
        daily_stats.last_update = current_time
        
        # 计算成交量比例
        volume_ratio = 0.0
        if time_progress > 0 and elapsed_minutes > 0:
            if avg_daily_volume:
                # 如果有历史平均成交量，计算相对于历史平均的比例
                expected_volume_by_time = avg_daily_volume * time_progress
                volume_ratio = current_volume / expected_volume_by_time if expected_volume_by_time > 0 else 0
            else:
                # 基于当前成交速度预测全天成交量
                if elapsed_minutes > 0:
                    current_volume_rate = current_volume / elapsed_minutes  # 每分钟成交量
                    predicted_daily_volume = current_volume_rate * self.trading_minutes_per_day
                    # 计算相对于预测全天成交量的进度比例
                    volume_ratio = current_volume / (predicted_daily_volume * time_progress) if predicted_daily_volume > 0 else 0
        
        return volume_ratio, time_progress, period
    
    def check_volume_time_ratio(self, stock_code: str, current_volume: int, 
                              current_time: datetime, alert_threshold: float) -> List[str]:
        """
        检查成交量时间比例（修复版）
        """
        alerts = []
        
        volume_ratio, time_progress, period = self.calculate_volume_ratio(
            stock_code, current_volume, current_time
        )
        
        if time_progress > 0 and volume_ratio > alert_threshold:
            alert_type = f"volume_ratio_{int(alert_threshold)}"
            stats = self.daily_stats[stock_code]
            
            if alert_type not in stats.volume_alerts_triggered:
                stats.volume_alerts_triggered.add(alert_type)
                
                alert_msg = (
                    f"成交量异常放量: 当前成交量 {current_volume:,}手，"
                    f"时间进度 {time_progress:.1%}，"
                    f"放量比例 {volume_ratio:.1f}倍 (阈值: {alert_threshold:.1f}倍)"
                )
                alerts.append(alert_msg)
        
        return alerts
    
    def get_volume_summary(self, stock_code: str, current_time: datetime) -> str:
        """获取成交量摘要信息（修复版）"""
        if stock_code not in self.daily_stats:
            return "无成交量数据"
        
        stats = self.daily_stats[stock_code]
        volume_ratio, time_progress, period = self.calculate_volume_ratio(
            stock_code, stats.total_volume, current_time
        )
        
        if time_progress > 0:
            return (
                f"成交量: {stats.total_volume:,}手 | "
                f"时间进度: {time_progress:.1%} | "
                f"放量比例: {volume_ratio:.1f}倍"
            )
        else:
            return f"成交量: {stats.total_volume:,}手 | 非交易时间"

# 修复StockMonitor类中的get_stock_data方法
class StockMonitor:
    # ... 其他代码保持不变 ...
    
    def get_stock_data(self, stock_code: str) -> Optional[StockData]:
        """获取股票数据（修复成交量单位）"""
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
                        volume=volume_in_hands,  # 修正为手
                        amount=float(data_str[9]),  # 成交额（万元）
                        timestamp=datetime.now()
                    )
        except Exception as e:
            logging.debug(f"获取股票 {stock_code} 数据失败: {e}")
        
        return None

# 测试函数，用于验证时间进度计算
def test_time_progress():
    """测试时间进度计算"""
    analyzer = VolumeAnalyzer()
    
    test_times = [
        datetime(2025, 11, 18, 9, 0),   # 开盘前
        datetime(2025, 11, 18, 9, 30),  # 开盘
        datetime(2025, 11, 18, 10, 0),  # 上午
        datetime(2025, 11, 18, 11, 0),  # 上午
        datetime(2025, 11, 18, 11, 30), # 上午收盘
        datetime(2025, 11, 18, 12, 0),  # 午间休市
        datetime(2025, 11, 18, 13, 0),  # 下午开盘
        datetime(2025, 11, 18, 14, 0),  # 下午
        datetime(2025, 11, 18, 15, 0),  # 收盘
        datetime(2025, 11, 18, 16, 0),  # 收盘后
    ]
    
    print("时间进度测试:")
    print("=" * 60)
    for test_time in test_times:
        progress, period, elapsed = analyzer.get_trading_time_progress(test_time)
        print(f"{test_time.strftime('%H:%M')} - {period:8} - 进度: {progress:5.1%} - 已交易: {elapsed:3}分钟")

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config_hash = None
        self.last_modified = 0
        self.config = {}
        self.config_listeners = []
        
    def add_listener(self, listener):
        """添加配置变更监听器"""
        self.config_listeners.append(listener)
    
    def load_config(self) -> dict:
        """加载配置文件"""
        try:
            current_mtime = os.path.getmtime(self.config_path)
            with open(self.config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            current_hash = hashlib.md5(content.encode()).hexdigest()
            
            if current_hash != self.config_hash:
                self.config = yaml.safe_load(content)
                self.config_hash = current_hash
                self.last_modified = current_mtime
                logging.info("配置文件已重新加载")
                
                for listener in self.config_listeners:
                    listener.on_config_updated(self.config)
                    
            return self.config
            
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            return self.config
    
    def get_config_snapshot(self) -> dict:
        """获取配置快照"""
        return self.config.copy()
    
    def start_monitoring(self, interval: int = 5):
        """启动配置监控"""
        def monitor_loop():
            while True:
                self.load_config()
                time.sleep(interval)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logging.info(f"配置监控已启动，检查间隔: {interval}秒")

class StockMonitor:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config_manager = ConfigManager(config_path)
        self.config_manager.add_listener(self)
        
        # 监控状态
        self.stock_configs: Dict[str, StockConfig] = {}
        self.monitor_threads: Dict[str, threading.Thread] = {}
        self.monitor_flags: Dict[str, bool] = {}
        self.price_history: Dict[str, List[StockData]] = defaultdict(list)
        self.volume_analyzer = VolumeAnalyzer()
        
        self.setup_logging()
        self.setup_signal_handlers()
        self.reload_config()
        
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('stock_monitor.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
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
    
    def reload_config(self):
        """重新加载配置"""
        config = self.config_manager.load_config()
        if not config:
            return
        
        monitor_settings = config.get('monitor_settings', {})
        global_settings = monitor_settings.get('global', {})
        stocks_config = monitor_settings.get('stocks', {})
        
        new_stock_configs = {}
        for code, stock_config in stocks_config.items():
            new_stock_configs[code] = StockConfig(
                code=code,
                name=stock_config['name'],
                interval=stock_config.get('interval', global_settings.get('default_interval', 10)),
                upper_limit=stock_config['price_alerts']['upper_limit'],
                lower_limit=stock_config['price_alerts']['lower_limit'],
                max_change_per_minute=stock_config['change_speed_alerts']['max_change_per_minute'],
                volume_spike_ratio=stock_config['change_speed_alerts']['volume_spike_ratio'],
                volume_time_ratio_alert=stock_config['change_speed_alerts'].get('volume_time_ratio_alert', 3.0),
                enabled=stock_config.get('enabled', True)
            )
        
        self.update_monitor_threads(new_stock_configs)
        self.stock_configs = new_stock_configs
        
        logging.info(f"配置重载完成，当前监控股票数量: {len(self.stock_configs)}")
    
    def update_monitor_threads(self, new_configs: Dict[str, StockConfig]):
        """更新监控线程"""
        current_codes = set(self.monitor_flags.keys())
        new_codes = set(new_configs.keys())
        
        codes_to_remove = current_codes - new_codes
        for code in codes_to_remove:
            self.stop_monitor_thread(code)
            logging.info(f"停止监控股票: {code}")
        
        codes_to_update = current_codes & new_codes
        for code in codes_to_update:
            old_config = self.stock_configs.get(code)
            new_config = new_configs[code]
            
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
        
        codes_to_add = new_codes - current_codes
        for code in codes_to_add:
            config = new_configs[code]
            if config.enabled:
                logging.info(f"新增监控: {config.name}({code})")
                self.start_monitor_thread(code, config)
    
    def is_config_changed(self, old_config: StockConfig, new_config: StockConfig) -> bool:
        """检查配置是否发生变化"""
        return any(
            getattr(old_config, field) != getattr(new_config, field)
            for field in ['interval', 'upper_limit', 'lower_limit', 
                         'max_change_per_minute', 'volume_spike_ratio', 
                         'volume_time_ratio_alert', 'enabled']
        )
    
    def stop_monitor_thread(self, stock_code: str):
        """停止监控线程"""
        if stock_code in self.monitor_flags:
            self.monitor_flags[stock_code] = False
        
        if stock_code in self.monitor_threads:
            thread = self.monitor_threads[stock_code]
            thread.join(timeout=5)
            del self.monitor_threads[stock_code]
    
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
                    
                    return StockData(
                        code=stock_code,
                        name=data_str[0],
                        price=current_price,
                        change_percent=round(change_percent, 2),
                        volume=int(data_str[8]),  # 成交量（手）
                        amount=float(data_str[9]),  # 成交额（万元）
                        timestamp=datetime.now()
                    )
        except Exception as e:
            logging.debug(f"获取股票 {stock_code} 数据失败: {e}")
        
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
        volume_alerts = self.volume_analyzer.check_volume_time_ratio(
            stock_data.code, 
            stock_data.volume, 
            stock_data.timestamp, 
            config.volume_time_ratio_alert
        )
        alerts.extend(volume_alerts)
        
        return alerts
    
    def monitor_single_stock(self, stock_code: str, config: StockConfig):
        """监控单个股票"""
        consecutive_errors = 0
        
        while self.monitor_flags.get(stock_code, False):
            try:
                if not self.is_trading_time():
                    time.sleep(60)
                    continue
                
                stock_data = self.get_stock_data(stock_code)
                if stock_data:
                    consecutive_errors = 0
                    
                    # 检查所有警报
                    alerts = self.check_alerts(stock_data, config)
                    for alert in alerts:
                        logging.warning(f"ALERT - {stock_data.name}({stock_code}): {alert}")
                    
                    # 获取成交量摘要
                    volume_summary = self.volume_analyzer.get_volume_summary(stock_code, stock_data.timestamp)
                    
                    # 正常日志（包含成交量信息）
                    logging.info(
                        f"{stock_data.name}({stock_code}) - "
                        f"价格: {stock_data.price:.2f} | 涨跌幅: {stock_data.change_percent:.2f}% | "
                        f"{volume_summary}"
                    )
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= 3:
                        logging.warning(f"连续获取 {stock_code} 数据失败")
                        time.sleep(30)
                
                time.sleep(config.interval)
                
            except Exception as e:
                logging.error(f"监控 {stock_code} 异常: {e}")
                time.sleep(config.interval)
    
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
        """启动监控系统"""
        logging.info("启动动态配置股票监控系统（含成交量分析）...")
        
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

def create_sample_config():
    """创建示例配置文件"""
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
                        'volume_time_ratio_alert': 3.0  # 新增：成交量时间比例警报阈值
                    }
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
                        'volume_time_ratio_alert': 2.5  # 隆基的阈值可以设置低一些
                    }
                }
            }
        }
    }
    
    with open('config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(sample_config, f, allow_unicode=True, indent=2)
    
    print("已创建示例配置文件: config.yaml")

if __name__ == "__main__":
    if not os.path.exists('config.yaml'):
        create_sample_config()
    
    monitor = StockMonitor("config.yaml")
    monitor.start_monitoring()