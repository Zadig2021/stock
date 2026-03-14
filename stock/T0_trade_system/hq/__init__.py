"""hq 包的公共接口。

导出:
- TickData, TickStorage: 存储与结构定义
- TickDataSystem: 逐笔采集系统主控制器（如果存在）
- helper: list_available_dates, read_tick_csv

这个模块简化了从 `tick_data/{code}_{YYYYMMDD}.csv` 读取逐笔文件的常见操作，便于回放使用。
"""
from .tick_storage import TickData, TickStorage

try:
	from .tick_main import TickDataSystem  # optional
except Exception:
	TickDataSystem = None

import os
import csv
from datetime import datetime
from typing import Generator, Optional

__all__ = [
	'TickData', 'TickStorage', 'TickDataSystem',
	'list_available_dates', 'read_tick_csv'
]


def list_available_dates(stock_code: str, data_dir: str = 'tick_data'):
	"""返回指定股票可用的日期列表（YYYYMMDD）"""
	if not os.path.exists(data_dir):
		return []
	dates = []
	for fn in os.listdir(data_dir):
		if fn.startswith(f"{stock_code}_") and fn.endswith('.csv'):
			dates.append(fn.replace(f"{stock_code}_", '').replace('.csv', ''))
	return sorted(dates)


def read_tick_csv(stock_code: str, date_str: str, data_dir: str = 'tick_data') -> Generator[dict, None, None]:
	"""逐行读取指定日期的 tick CSV，返回字典（timestamp -> datetime）。

	字段对应 tick_storage.py 写入的列：
	['timestamp', 'code', 'name', 'price', 'change_percent', 'volume', 'amount', 'bid_price', 'ask_price', 'bid_volume', 'ask_volume']
	"""
	fn = os.path.join(data_dir, f"{stock_code}_{date_str}.csv")
	if not os.path.exists(fn):
		return
	with open(fn, 'r', encoding='utf-8') as f:
		reader = csv.reader(f)
		headers = next(reader, None)
		for row in reader:
			if not row:
				continue
			try:
				ts = datetime.fromisoformat(row[0])
			except Exception:
				# skip malformed
				continue
			yield {
				'timestamp': ts,
				'code': row[1] if len(row) > 1 else stock_code,
				'name': row[2] if len(row) > 2 else '',
				'price': float(row[3]) if len(row) > 3 and row[3] else None,
				'change_percent': float(row[4]) if len(row) > 4 and row[4] else None,
				'volume': int(float(row[5])) if len(row) > 5 and row[5] else 0,
				'amount': float(row[6]) if len(row) > 6 and row[6] else 0.0,
				'bid_price': float(row[7]) if len(row) > 7 and row[7] else 0.0,
				'ask_price': float(row[8]) if len(row) > 8 and row[8] else 0.0,
				'bid_volume': int(float(row[9])) if len(row) > 9 and row[9] else 0,
				'ask_volume': int(float(row[10])) if len(row) > 10 and row[10] else 0,
			}

