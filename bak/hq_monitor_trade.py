import akshare as ak
import requests
import time
from datetime import datetime, time as dt_time


def detect_exchange(stock_code: str) -> str:
    """
    根据股票代码判断所属交易所：返回 'sh' 或 'sz'.

    规则：
    - 若传入以 'sh' 或 'sz' 开头的代码，则直接返回该前缀。
    - 否则根据数字代码首位判断：以 '6' 或 '9' 开头的以 'sh' 为主（上证），其余默认为 'sz'（深证）。
    - 支持传入带前缀的完整形式（例如 'sz002466' 或 '002466'）。
    """
    code = stock_code.strip()
    # 如果已经包含前缀
    if code.startswith('sh') or code.startswith('sz'):
        return code[:2]
    # 取出数字部分（最后 6 位通常是代码）
    num = ''.join(ch for ch in code if ch.isdigit())
    if len(num) >= 6:
        first = num[0]
        if first == '6' or first == '9':
            return 'sh'
        return 'sz'
    # 回退默认深证
    return 'sz'

def is_trading_time():
    """
    判断当前是否为股票交易时间
    """
    now = datetime.now()
    current_time = now.time()
    current_weekday = now.weekday()
    
    # 判断是否为周末
    if current_weekday >= 5:  # 5=周六, 6=周日
        return False
    
    # 判断是否为交易日时间
    morning_start = dt_time(9, 30)   # 上午开盘
    morning_end = dt_time(11, 30)    # 上午收盘
    afternoon_start = dt_time(13, 0) # 下午开盘
    afternoon_end = dt_time(15, 0)   # 下午收盘
    
    return (morning_start <= current_time <= morning_end) or \
           (afternoon_start <= current_time <= afternoon_end)

def is_trading_day():
    """
    判断是否为交易日（简单版本，实际应该考虑节假日）
    """
    now = datetime.now()
    # 简单的判断：周一至周五为交易日
    return now.weekday() < 5  # 0-4为周一到周五

def get_stock_data_multisource(stock_code):
    """
    多数据源获取股票数据
    """
    prefix = detect_exchange(stock_code)
    # 方法1: 使用AkShare
    try:
        stock_info = ak.stock_zh_a_spot_em()
        # AkShare 返回的 '代码' 列有时带前缀，有时不带。尝试两种匹配。
        num_code = ''.join(ch for ch in stock_code if ch.isdigit())[-6:]
        candidates = [f"{prefix}{num_code}", num_code]
        target_stock = stock_info[stock_info['代码'].isin(candidates)]
        if not target_stock.empty:
            return {
                'source': 'akshare',
                'name': target_stock['名称'].values[0],
                'price': target_stock['最新价'].values[0],
                'change_percent': target_stock['涨跌幅'].values[0],
                'volume': target_stock['成交量'].values[0],
                'timestamp': datetime.now()
            }
    except Exception as e:
        print(f"AkShare获取失败: {e}")
    
    # 方法2: 使用新浪财经API
    try:
        prefix = detect_exchange(stock_code)
        url = f"https://hq.sinajs.cn/list={prefix}{''.join(ch for ch in stock_code if ch.isdigit())[-6:]}"
        headers = {
            'Referer': 'https://finance.sina.com.cn/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.text.split('="')[1].split(',')
            current_price = float(data[3])
            yesterday_close = float(data[2])
            change_percent = (current_price - yesterday_close) / yesterday_close * 100
            
            return {
                'source': 'sina',
                'name': data[0],
                'price': current_price,
                'change_percent': change_percent,
                'volume': data[8],
                'timestamp': datetime.now()
            }
    except Exception as e:
        print(f"新浪API获取失败: {e}")
    
    return None

def wait_until_trading_time():
    """
    等待直到下一个交易时间
    """
    now = datetime.now()
    current_time = now.time()
    
    print("当前为非交易时间，等待中...")
    
    if now.weekday() >= 5:  # 周末
        # 计算到下周一开盘的时间
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0:  # 已经是周一，但还没开盘
            next_time = datetime.combine(now.date(), dt_time(9, 30))
        else:
            next_monday = now.date().replace(day=now.day + days_until_monday)
            next_time = datetime.combine(next_monday, dt_time(9, 30))
    else:  # 周中，但在非交易时间
        if current_time < dt_time(9, 30):
            next_time = datetime.combine(now.date(), dt_time(9, 30))
        elif dt_time(11, 30) < current_time < dt_time(13, 0):
            next_time = datetime.combine(now.date(), dt_time(13, 0))
        else:  # 下午收盘后
            tomorrow = now.date().replace(day=now.day + 1)
            # 如果明天是周末，跳到下周一
            if tomorrow.weekday() >= 5:
                days_until_monday = (7 - tomorrow.weekday()) % 7
                next_monday = tomorrow.replace(day=tomorrow.day + days_until_monday)
                next_time = datetime.combine(next_monday, dt_time(9, 30))
            else:
                next_time = datetime.combine(tomorrow, dt_time(9, 30))
    
    sleep_seconds = (next_time - now).total_seconds()
    print(f"下次交易时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"等待时间: {sleep_seconds/3600:.2f} 小时")
    
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)

def monitor_stock_trading_hours(stock_code_list=['002466', '601012', '300454'], interval=5):
    """
    只在交易时间监控股票
    """
    print(f"开始监控股票列表 {stock_code_list} 每 {interval} 秒一次")
    print("监控策略: 只在交易时间(9:30-11:30, 13:00-15:00)请求数据")
    print("=" * 60)
    
    while True:
        try:
            if not is_trading_day():
                print(f"{datetime.now().strftime('%Y-%m-%d')} 是非交易日(周末)")
                wait_until_trading_time()
                continue
                
            if not is_trading_time():
                wait_until_trading_time()
                continue

            for stock_code in stock_code_list:
                print(stock_code)
                # 交易时间内正常监控
                data = get_stock_data_multisource(stock_code)
                if data:
                    print(f"[{data['timestamp'].strftime('%H:%M:%S')}] {data['name']}")
                    print(f"最新价: {data['price']}")
                    print(f"涨跌幅: {data['change_percent']:.2f}%")
                    print(f"成交量: {data['volume']}")
                    print(f"数据源: {data['source']}")
                    print("-" * 40)
                else:
                    print("数据获取失败，稍后重试...")
                time.sleep(1)
            
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n监控已停止")
            break
        except Exception as e:
            print(f"监控异常: {e}")
            time.sleep(interval)

# 启动监控
if __name__ == "__main__":
    monitor_stock_trading_hours(['002466', '601012', '300454'], interval=5)