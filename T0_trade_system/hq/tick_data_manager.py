# tick_data_manager.py
import time
from typing import Dict, List, Optional, Callable
from datetime import datetime
from .tick_collector import TickDataCollector
from .tick_replayer import TickDataReplayer
from .tick_storage import TickData

# 设置日志
from utils.logger import get_hq_logger
logger = get_hq_logger('tick_data_manager')


class TickDataManager:
    """行情数据管理器 - 支持两种数据源"""
    
    def __init__(self, config):
        # 两种数据源
        self.tick_collector = None
        self.tick_replayer = None
        # 回调函数
        self.callback: Callable = None
        self.data_source = config.tick_data_source  # 默认使用采集器
        # tick数据存储或者回放目录
        self.tick_data_dir = config.tick_data_dir
        # 监控的股票列表
        self.monitoring_stocks = config.monitor_stocks
        # 实时配置
        self.collection_interval = config.collection_interval
        # 重放配置
        self.replay_speed = config.replay_speed
        self.replay_date = config.replay_date
    
    def set_callback(self, callback: Callable):
        """添加价格更新回调"""
        self.callback = callback
    
    def start(self):
        """启动行情数据服务"""
        logger.info(f"启动行情数据服务，数据源: {self.data_source}")
        # 根据数据源启动相应的服务
        if self.data_source == 'realtime':
            # 添加采集器的回调
            self.tick_collector = TickDataCollector(self.tick_data_dir, self.collection_interval)
            logger.info(f"开始实时采集行情,股票:{self.monitoring_stocks}")
            for stock_code in self.monitoring_stocks:
                self.tick_collector.add_stock(stock_code)
            self.tick_collector.set_data_callback(self.callback)
            self.tick_collector.start_collection()

            try:
                # 保持运行
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("用户中断采集")
            finally:
                logger.info("采集交易结束")
            
        elif self.data_source == 'replayer':
            # 添加回放器的回调
            self.tick_replayer = TickDataReplayer(self.tick_data_dir)
            replay_stocks = list(set(self.monitoring_stocks) & set(self.tick_replayer.get_available_stocks()))
            if len(replay_stocks) == 0:
                logger.error(f"不存在监控列表{self.monitoring_stocks}中的重放的行情")
                return
            if self.replay_date not in self.tick_replayer.get_available_dates(replay_stocks[0]):
                logger.error(f"不存在日期{self.replay_date}的重放的行情")
                return

            logger.info(f"开始重放的行情,日期:{self.replay_date},速度:{self.replay_speed},股票:{replay_stocks} ")
            self.tick_replayer.set_replay_callback(self.callback)
            try:
                self.tick_replayer.replay_daily_data_accurate(replay_stocks, self.replay_date, self.replay_speed)
            except KeyboardInterrupt:
                logger.info("用户中断回放")
            except Exception as e:
                logger.error(f"回放过程中出错: {str(e)}")
            finally:
                logger.info("回放交易结束")
    
    def stop(self):
        """停止行情数据服务"""
        logger.info("停止行情数据服务")
        
        if self.data_source == 'realtime':
            self.tick_collector.stop_collection()
        elif self.data_source == 'replayer':
            self.tick_replayer.stop_replay()
