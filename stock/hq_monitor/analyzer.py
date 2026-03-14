import logging
from datetime import datetime, time as dt_time, date, timedelta
from typing import Dict, List, Tuple
import numpy as np
from collections import defaultdict

from .models import DailyVolumeStats, PriceChangeRecord, StockData
from .historical import HistoricalVolumeManager


class VolumeAnalyzer:
    """成交量分析器 - 自动获取历史数据版"""
    
    def __init__(self, historical_manager: HistoricalVolumeManager):
        self.historical_manager = historical_manager
        self.daily_stats: Dict[str, DailyVolumeStats] = {}
        self.trading_minutes_per_day = 240
        
    def get_trading_time_progress(self, current_time: datetime) -> Tuple[float, str, int]:
        """获取当日交易时间进度"""
        current_time_obj = current_time.time()
        morning_start = dt_time(9, 30)
        morning_end = dt_time(11, 30)
        afternoon_start = dt_time(13, 00)
        afternoon_end = dt_time(15, 00)
        
        total_minutes = self.trading_minutes_per_day

        if morning_start <= current_time_obj <= morning_end:
            elapsed_minutes = (current_time_obj.hour - morning_start.hour) * 60 + \
                            (current_time_obj.minute - morning_start.minute)
            progress = elapsed_minutes / total_minutes
            period = "上午"
            total_elapsed = elapsed_minutes
            
        elif afternoon_start <= current_time_obj <= afternoon_end:
            elapsed_minutes = (current_time_obj.hour - afternoon_start.hour) * 60 + \
                            (current_time_obj.minute - afternoon_start.minute)
            progress = (120 + elapsed_minutes) / total_minutes
            period = "下午"
            total_elapsed = 120 + elapsed_minutes
            
        elif current_time_obj < morning_start:
            progress = 0.0
            period = "开盘前"
            total_elapsed = 0
            
        elif morning_end < current_time_obj < afternoon_start:
            progress = 120 / total_minutes
            period = "午间休市"
            total_elapsed = 120
            
        else:
            progress = 1.0
            period = "收盘后"
            total_elapsed = total_minutes
        
        return min(max(progress, 0.0), 1.0), period, total_elapsed
    
    def calculate_volume_ratio(self, stock_code: str, current_volume: int, 
                             current_time: datetime) -> Tuple[float, float, float, str, int]:
        """
        计算成交量比例
        返回: (历史比例, 进度比例, 时间进度, 交易时段, 历史平均成交量)
        """
        time_progress, period, elapsed_minutes = self.get_trading_time_progress(current_time)
        
        if stock_code not in self.daily_stats:
            self.daily_stats[stock_code] = DailyVolumeStats(date=current_time.date())
        
        daily_stats = self.daily_stats[stock_code]
        daily_stats.total_volume = current_volume
        daily_stats.last_update = current_time
        
        # 获取历史成交量数据（自动获取）
        historical_config = self.historical_manager.get_historical_volume_data(stock_code)
        avg_volume_30d = historical_config.avg_volume_30d if historical_config else 0
        
        # 计算相对于历史平均的比例
        historical_ratio = 0.0
        if avg_volume_30d > 0:
            historical_ratio = current_volume / avg_volume_30d
        
        # 计算相对于时间进度的比例
        time_progress_ratio = 0.0
        if time_progress > 0 and elapsed_minutes > 0:
            if avg_volume_30d > 0:
                # 基于历史平均成交量计算预期成交量
                expected_volume_by_time = avg_volume_30d * time_progress
                time_progress_ratio = current_volume / expected_volume_by_time if expected_volume_by_time > 0 else 0
            else:
                # 基于当前成交速度预测（结果是1）
                current_volume_rate = current_volume / elapsed_minutes
                predicted_daily_volume = current_volume_rate * self.trading_minutes_per_day
                time_progress_ratio = current_volume / (predicted_daily_volume * time_progress) if predicted_daily_volume > 0 else 0
        
        return historical_ratio, time_progress_ratio, time_progress, period, avg_volume_30d
    
    def check_volume_alerts(self, stock_code: str, current_volume: int, 
                          current_time: datetime, alert_threshold: float) -> List[str]:
        """检查成交量警报"""
        alerts = []
        
        historical_ratio, time_progress_ratio, time_progress, period, avg_volume = self.calculate_volume_ratio(
            stock_code, current_volume, current_time
        )
        
        # 检查相对于历史平均的放量
        if historical_ratio > alert_threshold:
            alert_type = f"historical_ratio_{int(alert_threshold)}"
            stats = self.daily_stats[stock_code]
            
            if alert_type not in stats.volume_alerts_triggered:
                stats.volume_alerts_triggered.add(alert_type)
                
                alert_msg = (
                    f"成交量显著放量: 当前 {current_volume:,}手，"
                    f"历史平均 {avg_volume:,}手，"
                    f"比例 {historical_ratio:.1f}倍 (阈值: {alert_threshold:.1f}倍)"
                )
                alerts.append(alert_msg)
        
        # 检查相对于时间进度的放量
        if time_progress > 0 and time_progress_ratio > alert_threshold:
            alert_type = f"time_ratio_{int(alert_threshold)}"
            stats = self.daily_stats[stock_code]
            
            if alert_type not in stats.volume_alerts_triggered:
                stats.volume_alerts_triggered.add(alert_type)
                
                alert_msg = (
                    f"成交量异常集中: 当前 {current_volume:,}手，"
                    f"比例 {time_progress_ratio:.1f}倍 (阈值: {alert_threshold:.1f}倍)"
                )
                alerts.append(alert_msg)
        
        return alerts
    
    def get_volume_summary(self, stock_code: str, current_time: datetime) -> str:
        """获取成交量摘要信息"""
        if stock_code not in self.daily_stats:
            return "无成交量数据"
        
        stats = self.daily_stats[stock_code]
        historical_ratio, time_progress_ratio, time_progress, period, avg_volume = self.calculate_volume_ratio(
            stock_code, stats.total_volume, current_time
        )
        
        if time_progress == 0:
            return (
                f"成交量: {stats.total_volume:,}手 | "
                f"历史平均: {avg_volume:,}手 | "
                f"历史比例: {historical_ratio*100:.1f}%"
            )
        else:
            return (
                f"成交量: {stats.total_volume:,}手 | "
                f"历史平均: {avg_volume:,}手 | "
                f"历史比例: {historical_ratio*100:.1f}% | "
                f"预期比例: {time_progress_ratio*100:.1f}%")

class PriceChangeLogger:
    """价格变化日志记录器"""
    
    def __init__(self):
        self.price_history: Dict[str, List[PriceChangeRecord]] = defaultdict(list)
        self.last_log_time: Dict[str, datetime] = {}
        self.max_records = 100  # 最大记录条数
    
    def record_price(self, stock_data: StockData):
        """记录价格"""
        record = PriceChangeRecord(
            timestamp=stock_data.timestamp,
            price=stock_data.price,
            change_percent=stock_data.change_percent,
            volume=stock_data.volume
        )
        
        self.price_history[stock_data.code].append(record)
        
        # 限制记录数量
        if len(self.price_history[stock_data.code]) > self.max_records:
            self.price_history[stock_data.code].pop(0)
    
    def should_log_price_change(self, stock_code: str, log_interval: int) -> bool:
        """判断是否应该输出价格变化日志"""
        current_time = datetime.now()
        
        if stock_code not in self.last_log_time:
            self.last_log_time[stock_code] = current_time
            return True
        
        time_diff = (current_time - self.last_log_time[stock_code]).total_seconds()
        if time_diff >= log_interval:
            self.last_log_time[stock_code] = current_time
            return True
        
        return False
    
    def get_price_change_summary(self, stock_code: str, stock_name: str) -> str:
        """获取价格变化摘要"""
        if stock_code not in self.price_history or len(self.price_history[stock_code]) < 2:
            return "无足够价格历史数据"
        
        records = self.price_history[stock_code]
        current_record = records[-1]
        previous_record = records[0]  # 对比最早记录
        
        price_change = current_record.price - previous_record.price
        price_change_percent = (price_change / previous_record.price) * 100 if previous_record.price > 0 else 0
        volume_change = current_record.volume - previous_record.volume
        
        time_period = current_record.timestamp - previous_record.timestamp
        hours = time_period.total_seconds() / 3600
        
        # 计算价格波动率（标准差）
        prices = [r.price for r in records]
        price_std = np.std(prices) if len(prices) > 1 else 0
        volatility = (price_std / np.mean(prices)) * 100 if np.mean(prices) > 0 else 0
        
        summary = (
            f"{stock_name}({stock_code}) 价格变化摘要:\n"
            f"  时间区间: {previous_record.timestamp.strftime('%H:%M:%S')} - {current_record.timestamp.strftime('%H:%M:%S')} ({hours:.1f}小时)\n"
            f"  价格变化: {previous_record.price:.2f} → {current_record.price:.2f} ({price_change:+.2f}, {price_change_percent:+.2f}%)\n"
            f"  成交量变化: {previous_record.volume:,} → {current_record.volume:,} ({volume_change:+,}手)\n"
            f"  价格波动率: {volatility:.2f}%\n"
            f"  当前涨跌幅: {current_record.change_percent:+.2f}%"
        )
        
        return summary
    
    def get_recent_price_trend(self, stock_code: str) -> str:
        """获取近期价格趋势"""
        if stock_code not in self.price_history or len(self.price_history[stock_code]) < 5:
            return "数据不足"
        
        records = self.price_history[stock_code][-5:]  # 最近5个记录
        prices = [r.price for r in records]
        
        if len(prices) < 2:
            return "数据不足"
        
        # 简单趋势判断
        first_price = prices[0]
        last_price = prices[-1]
        trend = "上涨" if last_price > first_price else "下跌" if last_price < first_price else "持平"
        change_percent = ((last_price - first_price) / first_price) * 100
        
        return f"近期趋势: {trend} ({change_percent:+.2f}%)"