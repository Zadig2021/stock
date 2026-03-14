import akshare as ak
import yfinance as yfinance
import time
from datetime import datetime, timedelta

def get_stock_data_multisource(stock_code='002466'):
    """
    多数据源获取股票数据，提高成功率
    """
    # 方法1: 使用AkShare（国内数据）
    try:
        stock_info = ak.stock_zh_a_spot_em()
        target_stock = stock_info[stock_info['代码'] == f'sz{stock_code}']
        if not target_stock.empty:
            return {
                'source': 'akshare',
                'name': target_stock['名称'].values[0],
                'price': target_stock['最新价'].values[0],
                'change_percent': target_stock['涨跌幅'].values[0],
                'volume': target_stock['成交量'].values[0]
            }
    except Exception as e:
        print(f"AkShare获取失败: {e}")
    
    # 方法2: 使用新浪财经API
    try:
        import requests
        url = f"https://hq.sinajs.cn/list=sz{stock_code}"
        headers = {
            'Referer': 'https://finance.sina.com.cn/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.text.split('="')[1].split(',')
            return {
                'source': 'sina',
                'name': data[0],
                'price': float(data[3]),
                'change_percent': (float(data[3]) - float(data[2])) / float(data[2]) * 100,
                'volume': data[8]
            }
    except Exception as e:
        print(f"新浪API获取失败: {e}")
    
    return None


def is_market_open(now=None):
    """
    判断当前时间是否处于A股交易时段：周一到周五，09:30-11:30 或 13:00-15:00
    """
    now = now or datetime.now()
    # 周末休市
    if now.weekday() >= 5:
        return False
    secs = now.hour * 3600 + now.minute * 60 + now.second
    morning_start = 9 * 3600 + 30 * 60
    morning_end = 11 * 3600 + 30 * 60
    afternoon_start = 13 * 3600
    afternoon_end = 15 * 3600
    return (morning_start <= secs < morning_end) or (afternoon_start <= secs < afternoon_end)


def seconds_until_next_open(now=None):
    """
    计算从 now 到下次开市（当日 09:30 或次个交易日 09:30 或当日 13:00）的秒数。
    """
    now = now or datetime.now()
    secs = now.hour * 3600 + now.minute * 60 + now.second
    morning_start = 9 * 3600 + 30 * 60
    morning_end = 11 * 3600 + 30 * 60
    afternoon_start = 13 * 3600
    afternoon_end = 15 * 3600

    # 如果在早于当日开盘之前（例如 9:00），则等待到当日 09:30
    if now.weekday() < 5 and secs < morning_start:
        target = now.replace(hour=9, minute=30, second=0, microsecond=0)
        return int((target - now).total_seconds())

    # 如果在上午休市时段（11:30 到 13:00），等待到当日 13:00
    if now.weekday() < 5 and morning_end <= secs < afternoon_start:
        target = now.replace(hour=13, minute=0, second=0, microsecond=0)
        return int((target - now).total_seconds())

    # 如果在下午收盘后或周末，查找下一个交易日的 09:30
    # 计算天数增量直到下一个周一到周五
    days = 1
    next_day = now + timedelta(days=days)
    while next_day.weekday() >= 5:
        days += 1
        next_day = now + timedelta(days=days)

    target = (now + timedelta(days=days)).replace(hour=9, minute=30, second=0, microsecond=0)
    return int((target - now).total_seconds())

def monitor_stock_safe(stock_code='002466', interval=5):
    """
    安全的股票监控，避免被封禁
    """
    request_count = 0
    while True:
        try:
            # 先检查是否在交易时间，休市时睡眠到下次开市
            if not is_market_open():
                wait = seconds_until_next_open()
                # 防止意外过长等待（例如计算错误），最多睡眠 24 小时
                wait_display = wait if wait <= 24 * 3600 else 24 * 3600
                h = wait_display // 3600
                m = (wait_display % 3600) // 60
                s = wait_display % 60
                print(f"休市中，距离下次开市还有 {h:02d}:{m:02d}:{s:02d}，休眠 {wait_display} 秒...")
                # 当进行长时间休眠时，重置请求计数，避免触发频率保护
                request_count = 0
                time.sleep(wait_display)
                continue

            # 限制请求频率
            if request_count > 10:
                print("请求次数过多，休息5分钟...")
                time.sleep(300)
                request_count = 0
            
            data = get_stock_data_multisource(stock_code)
            if data:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {data['name']}")
                print(f"最新价: {data['price']}")
                print(f"涨跌幅: {data['change_percent']:.2f}%")
                print(f"数据源: {data['source']}")
                print("-" * 40)
            else:
                print("所有数据源获取失败，请检查网络或稍后重试")
            
            request_count += 1
            time.sleep(interval)
            
        except Exception as e:
            print(f"监控异常: {e}")
            time.sleep(interval * 2)  # 异常时延长等待时间

# 启动监控
monitor_stock_safe('002466')