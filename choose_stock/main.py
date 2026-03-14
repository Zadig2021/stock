import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import time
import random
import warnings
warnings.filterwarnings('ignore')

class StockSelector:
    def __init__(self):
        self.stock_data = {}
        self.request_count = 0
        self.last_request_time = time.time()
        
    def safe_download(self, symbol, max_retries=3, period='6mo', interval='1d'):
        """安全的下载函数，包含延时和重试机制"""
        for attempt in range(max_retries):
            try:
                # 控制请求频率（每2-4秒一个请求）
                current_time = time.time()
                time_since_last = current_time - self.last_request_time
                if time_since_last < random.uniform(2, 4):
                    time.sleep(random.uniform(2, 4) - time_since_last)
                
                print(f"下载 {symbol} (尝试 {attempt+1}/{max_retries})...")
                stock = yf.download(
                    symbol, 
                    period=period, 
                    interval=interval, 
                    progress=False,
                    timeout=10
                )
                
                self.last_request_time = time.time()
                self.request_count += 1
                
                if stock.empty:
                    print(f"  {symbol}: 无数据")
                    return None
                
                print(f"  {symbol}: 下载成功 ({len(stock)}条数据)")
                return stock
                
            except Exception as e:
                print(f"  {symbol}: 尝试 {attempt+1} 失败 - {str(e)[:50]}...")
                if attempt < max_retries - 1:
                    # 指数退避
                    sleep_time = random.uniform(5, 10) * (2 ** attempt)
                    print(f"  等待 {sleep_time:.1f} 秒后重试...")
                    time.sleep(sleep_time)
                else:
                    print(f"  {symbol}: 所有尝试均失败")
                    return None
        
        return None
    
    def calculate_indicators(self, df):
        """计算技术指标"""
        if df is None or len(df) < 30:
            return None
            
        df = df.copy()
        
        # 移动平均线
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA10'] = df['Close'].rolling(window=10).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA30'] = df['Close'].rolling(window=30).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        # 成交量指标
        df['Volume_MA5'] = df['Volume'].rolling(window=5).mean()
        df['Volume_MA10'] = df['Volume'].rolling(window=10).mean()
        
        # 价格变化
        df['Price_Change'] = df['Close'].pct_change() * 100
        df['Price_Change_5d'] = df['Close'].pct_change(5) * 100
        df['Price_Change_10d'] = df['Close'].pct_change(10) * 100
        
        # 量价关系
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA5'].replace(0, np.nan)
        
        # 布林带
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        df['BB_Std'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + 2 * df['BB_Std']
        df['BB_Lower'] = df['BB_Middle'] - 2 * df['BB_Std']
        
        return df
    
    # 其他方法保持不变...
    def is_starting_stock(self, df):
        """判断是否启动股票"""
        if df is None or len(df) < 10:
            return False
            
        recent = df.iloc[-5:]  # 最近5天
        
        # 条件1: 近期突破平台或关键阻力位
        current_close = df.iloc[-1]['Close']
        resistance_level = df.iloc[-30:-5]['High'].max()  # 前25天的最高点作为阻力位
        broke_resistance = current_close > resistance_level
        
        # 条件2: 最近3天连续上涨
        recent_positive = all(recent.iloc[-3:]['Price_Change'] > 0)
        
        # 条件3: 突破布林带上轨或在中上轨之间运行
        last_row = df.iloc[-1]
        boll_condition = (last_row['Close'] > last_row['BB_Middle'])
        
        # 条件4: 放量突破
        volume_spike = last_row['Volume_Ratio'] > 1.5
        
        return (broke_resistance or boll_condition) and recent_positive and volume_spike
    
    def is_rising_stock(self, df):
        """判断是否上升趋势股票"""
        if df is None or len(df) < 20:
            return False
            
        # 短期均线向上
        ma5_trend = df['MA5'].iloc[-1] > df['MA5'].iloc[-5]
        ma10_trend = df['MA10'].iloc[-1] > df['MA10'].iloc[-10]
        
        # 价格在均线之上
        last_close = df['Close'].iloc[-1]
        above_ma20 = last_close > df['MA20'].iloc[-1]
        above_ma30 = last_close > df['MA30'].iloc[-1]
        
        # 近期涨幅
        recent_gain = df['Price_Change_5d'].iloc[-1] > 2  # 5日涨幅大于2%
        
        # 低点逐步抬高
        recent_lows = df['Low'].iloc[-15:].values
        ascending_lows = all(recent_lows[i] < recent_lows[i+1] for i in range(len(recent_lows)-1))
        
        return ma5_trend and ma10_trend and above_ma20 and recent_gain
    
    def has_increasing_volume(self, df):
        """判断量能是否明细增加"""
        if df is None or len(df) < 10:
            return False
            
        recent_volumes = df['Volume'].iloc[-5:].values
        recent_avg_volumes = df['Volume_MA5'].iloc[-5:].values
        
        # 最近3天成交量递增
        volume_increasing = all(recent_volumes[i] < recent_volumes[i+1] 
                              for i in range(len(recent_volumes)-3, len(recent_volumes)-1))
        
        # 成交量超过5日均量
        above_avg_volume = all(recent_volumes[i] > recent_avg_volumes[i] 
                              for i in range(-3, 0))
        
        # 量比大于1.2
        volume_ratio_high = df['Volume_Ratio'].iloc[-1] > 1.2
        
        return volume_increasing or (above_avg_volume and volume_ratio_high)
    
    def is_multi_moving_average(self, df):
        """判断是否多头排列"""
        if df is None or len(df) < 60:
            return False
            
        last_row = df.iloc[-1]
        
        # 多头排列条件：短中长期均线依次排列
        ma_condition = (last_row['MA5'] > last_row['MA10'] > 
                       last_row['MA20'] > last_row['MA30'] > last_row['MA60'])
        
        # 价格在所有均线之上
        price_above_all = (last_row['Close'] > last_row['MA5'] and
                          last_row['Close'] > last_row['MA10'] and
                          last_row['Close'] > last_row['MA20'] and
                          last_row['Close'] > last_row['MA30'] and
                          last_row['Close'] > last_row['MA60'])
        
        # 均线向上发散
        ma5_upward = df['MA5'].iloc[-1] > df['MA5'].iloc[-5]
        ma10_upward = df['MA10'].iloc[-1] > df['MA10'].iloc[-10]
        ma20_upward = df['MA20'].iloc[-1] > df['MA20'].iloc[-20]
        
        return ma_condition and price_above_all and ma5_upward and ma10_upward
    
    def scan_stocks(self, stock_list, batch_size=5):
        """分批扫描股票列表"""
        results = {
            'starting_stocks': [],
            'rising_stocks': [],
            'volume_increasing_stocks': [],
            'multi_ma_stocks': [],
            'all_conditions_stocks': []
        }
        
        print(f"开始扫描{len(stock_list)}只股票...")
        print("-" * 80)
        
        # 分批处理
        for batch_start in range(0, len(stock_list), batch_size):
            batch = stock_list[batch_start:batch_start + batch_size]
            print(f"\n处理批次 {batch_start//batch_size + 1}/{(len(stock_list)-1)//batch_size + 1}")
            
            for symbol in batch:
                print(f"正在分析: {symbol}")
                
                df = self.safe_download(symbol)
                if df is None:
                    continue
                    
                df = self.calculate_indicators(df)
                if df is None:
                    continue
                
                starting = self.is_starting_stock(df)
                rising = self.is_rising_stock(df)
                volume_inc = self.has_increasing_volume(df)
                multi_ma = self.is_multi_moving_average(df)
                
                current_price = df['Close'].iloc[-1]
                change_5d = df['Price_Change_5d'].iloc[-1]
                
                stock_info = {
                    'symbol': symbol,
                    'price': round(current_price, 2),
                    'change_5d': round(change_5d, 2),
                    'volume_ratio': round(df['Volume_Ratio'].iloc[-1], 2) if not pd.isna(df['Volume_Ratio'].iloc[-1]) else 0
                }
                
                if starting:
                    results['starting_stocks'].append(stock_info)
                if rising:
                    results['rising_stocks'].append(stock_info)
                if volume_inc:
                    results['volume_increasing_stocks'].append(stock_info)
                if multi_ma:
                    results['multi_ma_stocks'].append(stock_info)
                if starting and rising and volume_inc and multi_ma:
                    results['all_conditions_stocks'].append(stock_info)
            
            # 批次之间的延迟
            if batch_start + batch_size < len(stock_list):
                delay = random.uniform(10, 20)
                print(f"\n批次完成，等待 {delay:.1f} 秒后继续下一批...")
                time.sleep(delay)
        
        print("\n" + "=" * 80)
        return results
    
    def display_results(self, results):
        """显示扫描结果"""
        print("\n📈 选股结果汇总:")
        print("=" * 80)
        
        categories = [
            ('🚀 启动股票', 'starting_stocks'),
            ('📊 上升股票', 'rising_stocks'),
            ('💹 量能增加股票', 'volume_increasing_stocks'),
            ('🎯 多头排列股票', 'multi_ma_stocks'),
            ('🏆 符合所有条件股票', 'all_conditions_stocks')
        ]
        
        for label, key in categories:
            stocks = results[key]
            if stocks:
                print(f"\n{label} ({len(stocks)}只):")
                print("-" * 60)
                df_display = pd.DataFrame(stocks)
                print(df_display.to_string(index=False))
            else:
                print(f"\n{label}: 无符合条件的股票")
        
        print("\n" + "=" * 80)
        
        # 统计信息
        total_found = sum(len(results[key]) for key in results)
        print(f"\n📊 统计信息:")
        print(f"总计找到符合条件的股票: {total_found}只")
        
        if results['all_conditions_stocks']:
            print("\n✨ 重点关注股票（符合所有条件）:")
            for stock in results['all_conditions_stocks']:
                print(f"  代码: {stock['symbol']:10} 当前价: {stock['price']:8} "
                      f"5日涨幅: {stock['change_5d']:6.2f}% 量比: {stock['volume_ratio']:.2f}")


def get_sample_stocks():
    """获取示例股票列表（精简版）"""
    stocks = [
        '000001.SZ',  # 平安银行
        '000002.SZ',  # 万科A
        '000858.SZ',  # 五粮液
        '002415.SZ',  # 海康威视
        '600036.SS',  # 招商银行
        '600519.SS',  # 贵州茅台
        '601318.SS',  # 中国平安
        '000333.SZ',  # 美的集团
        '002475.SZ',  # 立讯精密
        '300750.SZ',  # 宁德时代
        '600276.SS',  # 恒瑞医药
        '000651.SZ',  # 格力电器
        '002594.SZ',  # 比亚迪
    ]
    return stocks


def main():
    """主函数"""
    print("=" * 80)
    print("📊 智能选股系统 v1.1 (防限速版)")
    print("=" * 80)
    print("筛选条件:")
    print("1. 启动股票 - 突破关键位置，放量启动")
    print("2. 上升股票 - 趋势向上，均线支撑")
    print("3. 量能增加股票 - 成交量明显放大")
    print("4. 多头排列股票 - 均线多头排列")
    print("=" * 80)
    
    # 创建选股器
    selector = StockSelector()
    
    # 获取股票列表
    print("\n获取股票列表...")
    stock_list = get_sample_stocks()
    
    # 扫描股票
    results = selector.scan_stocks(stock_list)
    
    # 显示结果
    selector.display_results(results)
    
    # 保存结果到Excel
    save_to_excel = input("\n是否保存结果到Excel文件？(y/n): ").lower()
    if save_to_excel == 'y':
        filename = f"stock_selection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            for key, stocks in results.items():
                if stocks:
                    df = pd.DataFrame(stocks)
                    sheet_name = key.replace('_stocks', '')[:31]
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"结果已保存到: {filename}")


if __name__ == "__main__":
    main()