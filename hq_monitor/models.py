from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


@dataclass
class HistoricalVolumeConfig:
    avg_volume_30d: int = 0
    avg_volume_60d: int = 0
    last_updated: str = ""


@dataclass
class StockConfig:
    code: str
    name: str
    interval: int
    upper_limit: float
    lower_limit: float
    max_change_per_minute: float
    volume_spike_ratio: float
    volume_time_ratio_alert: float
    log_interval: int = 60
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
    bid_volume: int
    ask_volume: int

@dataclass
class PriceChangeRecord:
    timestamp: datetime
    price: float
    change_percent: float
    volume: int


@dataclass
class DailyVolumeStats:
    date: date
    total_volume: int = 0
    last_update: Optional[datetime] = None
    volume_alerts_triggered: set = field(default_factory=set)
