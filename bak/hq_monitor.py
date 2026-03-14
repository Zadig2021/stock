#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的 A 股行情监控脚本（使用新浪公共行情接口）

功能：
- 支持按股票代码（如 `002466`）自动添加交易所前缀（`sz` / `sh`）
- 支持一次性获取（`--once`）或持续轮询（`--interval` 秒）
- 打印行情变化并将时间序列记录到 CSV（可选 `--out`）

示例：
  python3 hq_monitor.py --stock 002466 --interval 5
  python3 hq_monitor.py --stock sz002466 --once --out 002466.csv

注意：该脚本使用新浪公共接口 `http://hq.sinajs.cn/list=`，仅用于示例和轻量监控。
"""

import argparse
import csv
import sys
import time
from datetime import datetime

try:
    import requests
except Exception:
    print("请确保运行环境已安装 requests 模块（pip install requests）")
    raise


def normalize_code(code: str) -> str:
    """将用户输入的代码规范成新浪接口需要的格式，例如 '002466' -> 'sz002466'"""
    code = code.strip()
    if code.startswith('sh') or code.startswith('sz'):
        return code
    # 简单按 A 股编码规则判断交易所：以 6 开头为上证，其它（0/2/3）为深证
    if code.startswith('6'):
        return 'sh' + code
    return 'sz' + code


def fetch_sina(code: str) -> dict:
    """从新浪获取单支股票行情并解析返回字典（若失败返回 None）"""
    url = f'http://hq.sinajs.cn/list={code}'
    r = requests.get(url, timeout=5)
    if r.status_code != 200:
        return None
    text = r.text
    # 返回示例: var hq_str_sz000001="平安银行,13.34,13.41,13.33,13.45,13.18,13.33,13.34,123456,....,2025-11-18,15:00:00";
    try:
        start = text.index('="') + 2
        end = text.rindex('";')
        body = text[start:end]
    except ValueError:
        return None
    fields = body.split(',')
    if len(fields) < 5:
        return None
    # 根据新浪接口字段位置解析常用字段
    data = {
        'name': fields[0],
        'open': float_or_none(fields[1]),
        'pre_close': float_or_none(fields[2]),
        'price': float_or_none(fields[3]),
        'high': float_or_none(fields[4]),
        'low': float_or_none(fields[5]) if len(fields) > 5 else None,
        'volume': int_or_none(fields[8]) if len(fields) > 8 else None,
        'date': fields[-3] if len(fields) >= 3 else '',
        'time': fields[-2] if len(fields) >= 2 else '',
    }
    return data


def float_or_none(x: str):
    try:
        return float(x)
    except Exception:
        return None


def int_or_none(x: str):
    try:
        return int(float(x))
    except Exception:
        return None


def write_csv_row(path: str, row: dict):
    header = ['timestamp', 'name', 'price', 'open', 'pre_close', 'high', 'low', 'volume', 'date', 'time']
    write_header = False
    try:
        # 如果文件不存在，先写 header
        with open(path, 'r', encoding='utf-8'):
            pass
    except Exception:
        write_header = True

    with open(path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if write_header:
            writer.writeheader()
        writer.writerow({
            'timestamp': row.get('timestamp'),
            'name': row.get('name'),
            'price': row.get('price'),
            'open': row.get('open'),
            'pre_close': row.get('pre_close'),
            'high': row.get('high'),
            'low': row.get('low'),
            'volume': row.get('volume'),
            'date': row.get('date'),
            'time': row.get('time'),
        })


def monitor(stock_code: str, interval: float = 5.0, out: str = None, once: bool = False):
    code = normalize_code(stock_code)
    last_price = None
    last_row = None
    print(f"monitoring {code} (interval={interval}s) - press Ctrl+C to stop")
    while True:
        try:
            data = fetch_sina(code)
            now_ts = datetime.now().isoformat(sep=' ')
            if data is None:
                print(f"[{now_ts}] 获取行情失败 for {code}")
            else:
                row = {
                    'timestamp': now_ts,
                    'name': data.get('name'),
                    'price': data.get('price'),
                    'open': data.get('open'),
                    'pre_close': data.get('pre_close'),
                    'high': data.get('high'),
                    'low': data.get('low'),
                    'volume': data.get('volume'),
                    'date': data.get('date'),
                    'time': data.get('time'),
                }
                price = row['price']
                if price is None:
                    print(f"[{now_ts}] 无法解析价格: {data}")
                else:
                    if last_price is None:
                        print(f"[{now_ts}] {code} {row['name']} 价格: {price}")
                    else:
                        diff = price - last_price
                        pct = (diff / last_price * 100) if last_price else 0
                        print(f"[{now_ts}] {code} {row['name']} 价格: {price:.3f} 变化: {diff:+.3f} ({pct:+.2f}%)")
                last_price = price
                last_row = row
                if out:
                    try:
                        write_csv_row(out, row)
                    except Exception as e:
                        print(f"写 CSV 失败: {e}")

            if once:
                break
            time.sleep(interval)
        except KeyboardInterrupt:
            print('\n监控已被用户中断')
            break
        except Exception as e:
            print(f"监控循环出错: {e}")
            time.sleep(interval)


def main():
    p = argparse.ArgumentParser(description='简单的新浪行情轮询监控')
    p.add_argument('--stock', '-s', required=True, help='股票代码，例如 002466 或 sz002466')
    p.add_argument('--interval', '-i', type=float, default=5.0, help='轮询间隔秒数（默认 5）')
    p.add_argument('--out', help='可选：输出 CSV 文件路径，追加写入')
    p.add_argument('--once', action='store_true', help='仅获取一次后退出')
    args = p.parse_args()

    monitor(args.stock, interval=args.interval, out=args.out, once=args.once)


if __name__ == '__main__':
    main()
import requests
import time
import pandas as pd
from datetime import datetime

def monitor_stock(stock_code='002466'):
    """
    监控天齐锂业(002466)股票行情
    """
    # 使用腾讯财经API（示例）
    url = f"http://qt.gtimg.cn/q={stock_code}"
    
    try:
        response = requests.get(url)
        data = response.text.split('~')
        
        if len(data) > 1:
            stock_name = data[1]  # 股票名称
            current_price = data[3]  # 当前价格
            change = data[4]  # 涨跌额
            change_percent = data[5]  # 涨跌幅
            volume = data[6]  # 成交量
            amount = data[7]  # 成交额
            
            print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"股票: {stock_name}({stock_code})")
            print(f"当前价: {current_price}")
            print(f"涨跌: {change} ({change_percent}%)")
            print(f"成交量: {volume}手")
            print(f"成交额: {amount}万元")
            print("-" * 50)
            
    except Exception as e:
        print(f"获取数据失败: {e}")

# 持续监控
while True:
    monitor_stock('002466')
    time.sleep(1)  # 每60秒更新一次