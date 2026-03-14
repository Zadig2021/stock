import csv
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import numpy as np
from .tick_data import TickData
from .tick_storage import TickStorage

# 设置日志
from utils.logger import get_hq_logger
logger = get_hq_logger('tick_replayer')

class TickDataReplayer:
    """逐笔数据回放器 - 修复版"""
    
    def __init__(self, data_dir: str = "tick_data"):
        self.storage = TickStorage(data_dir)
        self.is_replaying = False
        self.replay_callback = None
    
    def set_replay_callback(self, callback: Callable[[TickData], None]):
        """设置回放回调函数"""
        self.replay_callback = callback
    
    def replay_daily_data_accurate(self, stock_codes: List[str], date_str: str, speed: float = 1.0):
        """
        精确时间回放 - 按照实际采集的时间间隔回放
        """
        self.is_replaying = True
        
        # 合并所有股票数据并按时间排序
        all_ticks = []
        for stock_code in stock_codes:
            data = self.storage.load_daily_data(stock_code, date_str)
            all_ticks.extend(data)
        
        if not all_ticks:
            logger.error("没有可回放的数据")
            return
        
        # 按时间戳排序
        all_ticks.sort(key=lambda x: x.timestamp)
        
        logger.info(f"开始精确回放 {date_str}，共 {len(all_ticks)} 条记录，速度: {speed}x")
        
        start_time = all_ticks[0].timestamp
        logger.info(f"回放开始时间: {start_time}")
        
        # 回放数据
        for i in range(len(all_ticks)):
            if not self.is_replaying:
                break
            
            current_tick = all_ticks[i]
            
            # 计算相对时间
            if i == 0:
                # 第一条数据立即回放
                time_delay = 0
            else:
                # 计算与前一条数据的时间间隔
                prev_tick = all_ticks[i-1]
                time_delay = (current_tick.timestamp - prev_tick.timestamp).total_seconds()
            
            # 按速度调整等待时间
            if time_delay > 0:
                time.sleep(time_delay / speed)
            
            # 回放当前数据
            if self.replay_callback:
                self.replay_callback(current_tick)
            
            # 进度显示
            if i % 100 == 0:
                progress = (i + 1) / len(all_ticks) * 100
                logger.info(f"回放进度: {progress:.1f}% ({i+1}/{len(all_ticks)})")
        
        self.is_replaying = False
        logger.info("精确回放结束")
    
    def replay_daily_data_consolidated(self, stock_codes: List[str], date_str: str, 
                                     interval_seconds: int = 5, speed: float = 1.0):
        """
        合并回放 - 按固定时间间隔合并显示所有股票
        """
        self.is_replaying = True
        
        # 加载所有股票数据
        stock_data = {}
        for stock_code in stock_codes:
            data = self.load_daily_data(stock_code, date_str)
            if data:
                stock_data[stock_code] = data
        
        if not stock_data:
            logger.error("没有可回放的数据")
            return
        
        # 找到最早和最晚时间
        all_ticks = []
        for data in stock_data.values():
            all_ticks.extend(data)
        
        start_time = min(tick.timestamp for tick in all_ticks)
        end_time = max(tick.timestamp for tick in all_ticks)
        
        logger.info(f"开始合并回放 {date_str}，时间间隔: {interval_seconds}秒，速度: {speed}x")
        logger.info(f"回放时间范围: {start_time} - {end_time}")
        
        current_time = start_time
        
        while current_time <= end_time and self.is_replaying:
            # 找到当前时间窗口内的所有数据
            window_end = current_time + timedelta(seconds=interval_seconds)
            
            ticks_in_window = []
            for stock_code, data in stock_data.items():
                # 找到该股票在当前时间窗口内的最新数据
                latest_tick = None
                for tick in data:
                    if current_time <= tick.timestamp < window_end:
                        latest_tick = tick
                    elif tick.timestamp >= window_end:
                        break
                
                if latest_tick:
                    ticks_in_window.append(latest_tick)
            
            # 回放当前窗口的数据
            for tick in ticks_in_window:
                if self.replay_callback:
                    self.replay_callback(tick)
            
            # 等待到下一个时间窗口
            time.sleep(interval_seconds / speed)
            current_time = window_end
        
        self.is_replaying = False
        logger.info("合并回放结束")
    
    def replay_single_stock(self, stock_code: str, date_str: str, speed: float = 1.0):
        """
        单股票回放 - 专注于单个股票的完整数据流
        """
        data = self.load_daily_data(stock_code, date_str)
        if not data:
            logger.error(f"没有找到 {stock_code} 在 {date_str} 的数据")
            return
        
        self.is_replaying = True
        logger.info(f"开始单股票回放 {stock_code} {date_str}，速度: {speed}x")
        
        start_time = data[0].timestamp
        logger.info(f"数据时间范围: {start_time} - {data[-1].timestamp}")
        logger.info(f"总数据量: {len(data)} 条")
        
        for i in range(len(data)):
            if not self.is_replaying:
                break
            
            current_tick = data[i]
            
            # 计算时间间隔
            if i == 0:
                time_delay = 0
            else:
                prev_tick = data[i-1]
                time_delay = (current_tick.timestamp - prev_tick.timestamp).total_seconds()
            
            # 按速度调整等待时间
            if time_delay > 0:
                time.sleep(time_delay / speed)
            
            # 回放数据
            if self.replay_callback:
                self.replay_callback(current_tick)
            
            # 每50条显示一次进度
            if i % 50 == 0:
                progress = (i + 1) / len(data) * 100
                time_elapsed = (current_tick.timestamp - start_time).total_seconds() / 60
                logger.info(f"进度: {progress:.1f}% | 已回放: {time_elapsed:.1f}分钟")
        
        self.is_replaying = False
        logger.info("单股票回放结束")
    
    def analyze_replay_data(self, stock_code: str, date_str: str):
        """分析回放数据"""
        self.storage.analyze_daily_data(stock_code, date_str)
    
    def stop_replay(self):
        """停止回放"""
        self.is_replaying = False
        logger.info("停止回放")
    
    def get_available_stocks(self) -> List[str]:
        """获取可用的股票列表"""
        return self.storage.get_available_stocks()

    def get_available_dates(self, stock_code: str) -> List[str]:
        """获取可用的日期列表"""
        return self.storage.get_available_dates(stock_code)
        
def setup_logger():
    """设置日志"""
    logger.basicConfig(
        level=logger.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logger.FileHandler('tick_system.log', encoding='utf-8'),
            logger.StreamHandler()
        ]
    )

def start_replay(stock_codes: list, date_str: str, speed: float = 1.0):
    """开始数据回放"""
    def replay_callback(tick_data):
        logger.info(
            f"回放 {tick_data.name}({tick_data.code}) - "
            f"价格: {tick_data.price:.2f} | 涨跌幅: {tick_data.change_percent:+.2f}% | "
            f"时间: {tick_data.timestamp.strftime('%H:%M:%S')} | "
            f"成交量: {tick_data.volume}手"
        )

    replayer = TickReplayer()
    replayer.set_replay_callback(replay_callback)

    # 精确时间回放 - 按照实际采集间隔
    # replayer.replay_daily_data_accurate(['002466', '601012'], '20251120', speed=1.0)

    # 合并回放 - 每5秒显示一次所有股票的最新状态
    # replayer.replay_daily_data_consolidated(['002466', '601012'], '20251120', 
    #                                     interval_seconds=5, speed=1.0)

    # 单股票详细回放
    replayer.replay_single_stock('002466', '20251120', speed=5.0)

    # # 数据分析
    # replayer.analyze_replay_data('002466', '20251120')

def main():
    setup_logger()
    # 示例：回放2025年11月20日的三只股票数据，
    start_replay(['002466', '601012', '300454'], '20251120', 1.0)
    """主函数"""

if __name__ == "__main__":
    main()