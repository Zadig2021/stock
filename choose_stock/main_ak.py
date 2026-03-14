import pandas as pd
import numpy as np
import akshare as ak
import requests
from datetime import datetime, timedelta
import time
import re
import warnings
warnings.filterwarnings('ignore')

class StockSelectorAKShare:
    def __init__(self):
        self.stock_data = {}
        
    def get_stock_list(self):
        """获取A股股票列表"""
        try:
            # 获取沪深京A股列表
            stock_info_a_code_name_df = ak.stock_info_a_code_name()
            stock_list = stock_info_a_code_name_df['code'].tolist()
            print(f"获取到 {len(stock_list)} 只A股股票")
            return stock_list[:100]  # 限制数量用于测试
        except:
            # 如果失败，使用预设列表
            print("使用预设股票列表")
            return ['000001', '000002', '000858', '002415', '600036', 
                   '600519', '601318', '000333', '002475', '300750',
                   '600276', '000651', '002594']
    
    def download_stock_data_sina(self, symbol):
        """使用新浪财经获取股票数据"""
        try:
            # 新浪财经数据接口
            url = f"http://hq.sinajs.cn/list={self.format_symbol_sina(symbol)}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            
            if response.text:
                data = response.text.split('="')[1].split(',')
                if len(data) > 10:
                    # 解析实时数据
                    current_price = float(data[3])  # 当前价
                    open_price = float(data[1])  # 开盘价
                    high_price = float(data[4])  # 最高价
                    low_price = float(data[5])  # 最低价
                    volume = float(data[8])  # 成交量(手)
                    amount = float(data[9])  # 成交额(万)
                    
                    return {
                        'symbol': symbol,
                        'current_price': current_price,
                        'open_price': open_price,
                        'high_price': high_price,
                        'low_price': low_price,
                        'volume': volume * 100,  # 转换为股数
                        'amount': amount * 10000,  # 转换为元
                        'time': data[30] + ' ' + data[31]
                    }
        except Exception as e:
            print(f"新浪接口错误: {e}")
        return None
    
    def download_stock_history_akshare(self, symbol, period="daily"):
        """使用AKShare获取股票历史数据"""
        try:
            # 根据不同市场代码确定股票代码格式
            if symbol.startswith('6'):
                # 上证股票
                symbol_full = f"sh{symbol}"
                df = ak.stock_zh_a_hist(symbol=symbol, period=period, adjust="qfq")
            elif symbol.startswith('0') or symbol.startswith('3'):
                # 深证股票
                symbol_full = f"sz{symbol}"
                df = ak.stock_zh_a_hist(symbol=symbol, period=period, adjust="qfq")
            elif symbol.startswith('8'):
                # 北证股票
                symbol_full = f"bj{symbol}"
                df = ak.stock_bj_a_hist(symbol=symbol, period=period, adjust="qfq")
            else:
                print(f"未知股票代码格式: {symbol}")
                return None
            
            if df.empty:
                print(f"股票 {symbol} 无历史数据")
                return None
            
            # 重命名列以匹配标准格式
            df = df.rename(columns={
                '日期': 'Date',
                '开盘': 'Open',
                '收盘': 'Close',
                '最高': 'High',
                '最低': 'Low',
                '成交量': 'Volume',
                '成交额': 'Amount',
                '振幅': 'Amplitude',
                '涨跌幅': 'Change',
                '涨跌额': 'ChangeAmount',
                '换手率': 'Turnover'
            })
            
            # 设置日期索引
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date')
            df = df.sort_index()
            
            # 确保数据类型正确
            df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
            df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
            df['Open'] = pd.to_numeric(df['Open'], errors='coerce')
            df['High'] = pd.to_numeric(df['High'], errors='coerce')
            df['Low'] = pd.to_numeric(df['Low'], errors='coerce')
            
            # 添加技术指标
            df = self.calculate_indicators(df)
            
            return df
            
        except Exception as e:
            print(f"获取 {symbol} 历史数据失败: {e}")
            return None
    
    def download_realtime_data_akshare(self, symbol):
        """使用AKShare获取实时数据"""
        try:
            if symbol.startswith('6'):
                market = "sh"
            elif symbol.startswith('0') or symbol.startswith('3'):
                market = "sz"
            elif symbol.startswith('8'):
                market = "bj"
            else:
                market = "sh"
            
            # 实时行情数据
            stock_zh_a_spot_em_df = ak.stock_zh_a_spot_em()
            stock_data = stock_zh_a_spot_em_df[stock_zh_a_spot_em_df['代码'] == symbol]
            
            if not stock_data.empty:
                return {
                    'symbol': symbol,
                    'name': stock_data.iloc[0]['名称'],
                    'current_price': float(stock_data.iloc[0]['最新价']),
                    'change_percent': float(stock_data.iloc[0]['涨跌幅']),
                    'change_amount': float(stock_data.iloc[0]['涨跌额']),
                    'volume': float(stock_data.iloc[0]['成交量']),
                    'turnover': float(stock_data.iloc[0]['成交额']),
                    'amplitude': float(stock_data.iloc[0]['振幅']),
                    'high': float(stock_data.iloc[0]['最高']),
                    'low': float(stock_data.iloc[0]['最低']),
                    'open': float(stock_data.iloc[0]['今开']),
                    'prev_close': float(stock_data.iloc[0]['昨收']),
                    'turnover_rate': float(stock_data.iloc[0]['换手率']),
                    'pe_ratio': float(stock_data.iloc[0]['市盈率-动态']) if stock_data.iloc[0]['市盈率-动态'] != '-' else 0,
                    'pb_ratio': float(stock_data.iloc[0]['市净率']) if stock_data.iloc[0]['市净率'] != '-' else 0,
                    'total_market_cap': float(stock_data.iloc[0]['总市值']),
                    'circulating_market_cap': float(stock_data.iloc[0]['流通市值'])
                }
        except Exception as e:
            print(f"获取实时数据失败: {e}")
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
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df
    
    def format_symbol_sina(self, symbol):
        """格式化股票代码为新浪财经格式"""
        if symbol.startswith('6'):
            return f"sh{symbol}"
        elif symbol.startswith('0') or symbol.startswith('3'):
            return f"sz{symbol}"
        elif symbol.startswith('8'):
            return f"bj{symbol}"
        else:
            return f"sh{symbol}"
    
    def is_starting_stock(self, df):
        """判断是否启动股票"""
        if df is None or len(df) < 10:
            return False
            
        recent = df.iloc[-5:]  # 最近5天
        
        # 条件1: 近期突破平台或关键阻力位
        current_close = df.iloc[-1]['Close']
        if len(df) > 30:
            resistance_level = df.iloc[-30:-5]['High'].max()  # 前25天的最高点作为阻力位
            broke_resistance = current_close > resistance_level
        else:
            broke_resistance = True
        
        # 条件2: 最近3天连续上涨
        recent_positive = all(recent.iloc[-3:]['Price_Change'] > 0) if len(recent) >= 3 else False
        
        # 条件3: 突破布林带上轨或在中上轨之间运行
        last_row = df.iloc[-1]
        boll_condition = (last_row['Close'] > last_row['BB_Middle'])
        
        # 条件4: 放量突破
        volume_spike = last_row['Volume_Ratio'] > 1.5 if not pd.isna(last_row['Volume_Ratio']) else False
        
        return (broke_resistance or boll_condition) and recent_positive and volume_spike
    
    def is_rising_stock(self, df):
        """判断是否上升趋势股票"""
        if df is None or len(df) < 20:
            return False
            
        # 短期均线向上
        ma5_trend = df['MA5'].iloc[-1] > df['MA5'].iloc[-5] if len(df) >= 6 else False
        ma10_trend = df['MA10'].iloc[-1] > df['MA10'].iloc[-10] if len(df) >= 11 else False
        
        # 价格在均线之上
        last_close = df['Close'].iloc[-1]
        above_ma20 = last_close > df['MA20'].iloc[-1] if 'MA20' in df.columns else False
        above_ma30 = last_close > df['MA30'].iloc[-1] if 'MA30' in df.columns else False
        
        # 近期涨幅
        recent_gain = df['Price_Change_5d'].iloc[-1] > 2 if 'Price_Change_5d' in df.columns else False
        
        # 低点逐步抬高
        if len(df) >= 15:
            recent_lows = df['Low'].iloc[-15:].values
            ascending_lows = all(recent_lows[i] < recent_lows[i+1] for i in range(len(recent_lows)-1))
        else:
            ascending_lows = False
        
        return ma5_trend and ma10_trend and above_ma20 and recent_gain
    
    def has_increasing_volume(self, df):
        """判断量能是否明细增加"""
        if df is None or len(df) < 10:
            return False
            
        recent_volumes = df['Volume'].iloc[-5:].values
        if len(df) >= 5:
            recent_avg_volumes = df['Volume_MA5'].iloc[-5:].values
        else:
            recent_avg_volumes = np.zeros(5)
        
        # 最近3天成交量递增
        if len(recent_volumes) >= 4:
            volume_increasing = all(recent_volumes[i] < recent_volumes[i+1] 
                                  for i in range(len(recent_volumes)-3, len(recent_volumes)-1))
        else:
            volume_increasing = False
        
        # 成交量超过5日均量
        if len(recent_volumes) >= 3:
            above_avg_volume = all(recent_volumes[i] > recent_avg_volumes[i] 
                                  for i in range(-3, 0))
        else:
            above_avg_volume = False
        
        # 量比大于1.2
        volume_ratio_high = df['Volume_Ratio'].iloc[-1] > 1.2 if 'Volume_Ratio' in df.columns and not pd.isna(df['Volume_Ratio'].iloc[-1]) else False
        
        return volume_increasing or (above_avg_volume and volume_ratio_high)
    
    def is_multi_moving_average(self, df):
        """判断是否多头排列"""
        if df is None or len(df) < 60:
            return False
            
        last_row = df.iloc[-1]
        
        # 检查所有需要的列是否存在
        required_cols = ['MA5', 'MA10', 'MA20', 'MA30', 'MA60']
        if not all(col in df.columns for col in required_cols):
            return False
        
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
        ma5_upward = df['MA5'].iloc[-1] > df['MA5'].iloc[-5] if len(df) >= 6 else False
        ma10_upward = df['MA10'].iloc[-1] > df['MA10'].iloc[-10] if len(df) >= 11 else False
        ma20_upward = df['MA20'].iloc[-1] > df['MA20'].iloc[-20] if len(df) >= 21 else False
        
        return ma_condition and price_above_all and ma5_upward and ma10_upward
    
    def scan_stocks(self, stock_list):
        """扫描股票列表"""
        results = {
            'starting_stocks': [],
            'rising_stocks': [],
            'volume_increasing_stocks': [],
            'multi_ma_stocks': [],
            'all_conditions_stocks': []
        }
        
        print(f"开始扫描 {len(stock_list)} 只股票...")
        print("=" * 80)
        
        for i, symbol in enumerate(stock_list, 1):
            print(f"正在分析: {symbol} ({i}/{len(stock_list)})")
            
            # 获取历史数据
            df = self.download_stock_history_akshare(symbol, period="daily")
            
            if df is None or len(df) < 30:
                print(f"  {symbol}: 数据不足")
                continue
            
            # 获取实时数据
            realtime_data = self.download_realtime_data_akshare(symbol)
            
            if df is not None:
                starting = self.is_starting_stock(df)
                rising = self.is_rising_stock(df)
                volume_inc = self.has_increasing_volume(df)
                multi_ma = self.is_multi_moving_average(df)
                
                current_price = df['Close'].iloc[-1]
                change_5d = df['Price_Change_5d'].iloc[-1] if 'Price_Change_5d' in df.columns else 0
                volume_ratio = df['Volume_Ratio'].iloc[-1] if 'Volume_Ratio' in df.columns and not pd.isna(df['Volume_Ratio'].iloc[-1]) else 0
                
                stock_info = {
                    'symbol': symbol,
                    'name': realtime_data['name'] if realtime_data else symbol,
                    'price': round(current_price, 2),
                    'change_5d': round(change_5d, 2),
                    'volume_ratio': round(volume_ratio, 2),
                    'market_cap': realtime_data['total_market_cap'] if realtime_data else 0,
                    'pe_ratio': realtime_data['pe_ratio'] if realtime_data else 0
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
                
                # 添加延迟避免请求过快
                time.sleep(0.5)
            else:
                print(f"  {symbol}: 获取数据失败")
        
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
                print("-" * 80)
                df_display = pd.DataFrame(stocks)
                # 格式化显示
                if 'market_cap' in df_display.columns:
                    df_display['market_cap'] = df_display['market_cap'].apply(
                        lambda x: f"{x/1e8:.2f}亿" if x > 0 else "N/A"
                    )
                if 'pe_ratio' in df_display.columns:
                    df_display['pe_ratio'] = df_display['pe_ratio'].apply(
                        lambda x: f"{x:.2f}" if x > 0 else "N/A"
                    )
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
                print(f"  代码: {stock['symbol']:8} 名称: {stock['name']:10} "
                      f"当前价: {stock['price']:8.2f} 5日涨幅: {stock['change_5d']:6.2f}% "
                      f"量比: {stock['volume_ratio']:.2f} 市值: {stock['market_cap']/1e8:.2f}亿")
    
    def get_market_status(self):
        """获取市场状态"""
        try:
            # 获取大盘指数
            index_data = ak.stock_zh_index_spot()
            sh_index = index_data[index_data['代码'] == 'sh000001']
            sz_index = index_data[index_data['代码'] == 'sz399001']
            cy_index = index_data[index_data['代码'] == 'sz399006']
            
            print("\n📊 大盘指数状态:")
            print("-" * 50)
            for idx, row in [('上证指数', sh_index), ('深证成指', sz_index), ('创业板指', cy_index)]:
                if not row.empty:
                    print(f"{idx}: {row.iloc[0]['最新价']:.2f} ({row.iloc[0]['涨跌幅']}%)")
            
            # 获取市场涨跌统计
            stock_zh_a_spot_em_df = ak.stock_zh_a_spot_em()
            total = len(stock_zh_a_spot_em_df)
            rise = len(stock_zh_a_spot_em_df[stock_zh_a_spot_em_df['涨跌幅'] > 0])
            fall = len(stock_zh_a_spot_em_df[stock_zh_a_spot_em_df['涨跌幅'] < 0])
            flat = total - rise - fall
            
            print(f"\n📈 市场涨跌统计:")
            print(f"上涨: {rise}只 ({rise/total*100:.1f}%)")
            print(f"下跌: {fall}只 ({fall/total*100:.1f}%)")
            print(f"平盘: {flat}只 ({flat/total*100:.1f}%)")
            
        except Exception as e:
            print(f"获取市场状态失败: {e}")


def main():
    """主函数"""
    print("=" * 80)
    print("📊 智能选股系统 v2.0 (AKShare版)")
    print("=" * 80)
    print("数据源: AKShare + 新浪财经")
    print("筛选条件:")
    print("1. 启动股票 - 突破关键位置，放量启动")
    print("2. 上升股票 - 趋势向上，均线支撑")
    print("3. 量能增加股票 - 成交量明显放大")
    print("4. 多头排列股票 - 均线多头排列")
    print("=" * 80)
    
    # 检查AKShare版本
    try:
        import akshare
        print(f"AKShare版本: {akshare.__version__}")
    except:
        print("未安装AKShare，请先安装: pip install akshare")
        return
    
    # 创建选股器
    selector = StockSelectorAKShare()
    
    # 显示市场状态
    selector.get_market_status()
    
    # 获取股票列表
    print("\n获取股票列表...")
    stock_list = selector.get_stock_list()
    
    if not stock_list:
        print("无法获取股票列表")
        return
    
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


def enhanced_main():
    """增强版主函数，包含更多功能"""
    print("=" * 80)
    print("📊 智能选股系统增强版")
    print("=" * 80)
    
    selector = StockSelectorAKShare()
    
    while True:
        print("\n请选择功能:")
        print("1. 快速扫描预设股票")
        print("2. 自定义股票扫描")
        print("3. 查看热门板块")
        print("4. 查看资金流向")
        print("5. 查看龙虎榜")
        print("6. 退出")
        
        choice = input("请输入选项 (1-6): ")
        
        if choice == '1':
            # 快速扫描
            stocks = selector.get_stock_list()
            if len(stocks) > 50:  # 限制数量
                stocks = stocks[:50]
            results = selector.scan_stocks(stocks)
            selector.display_results(results)
            
        elif choice == '2':
            # 自定义股票扫描
            custom_stocks = input("请输入股票代码(用逗号分隔，如: 000001,600519): ").strip()
            stocks = [s.strip() for s in custom_stocks.split(',') if s.strip()]
            if stocks:
                results = selector.scan_stocks(stocks)
                selector.display_results(results)
            else:
                print("请输入有效的股票代码")
                
        elif choice == '3':
            # 查看热门板块
            try:
                sector_data = ak.stock_board_industry_name_em()
                print("\n🏆 热门板块:")
                print("-" * 80)
                print(sector_data[['板块名称', '涨跌幅', '最新价']].head(20).to_string(index=False))
            except Exception as e:
                print(f"获取板块数据失败: {e}")
                
        elif choice == '4':
            # 查看资金流向
            try:
                money_flow = ak.stock_sector_fund_flow_rank(indicator="今日")
                print("\n💰 资金流向排名(今日):")
                print("-" * 80)
                print(money_flow[['名称', '主力净流入-净额', '涨跌幅']].head(15).to_string(index=False))
            except Exception as e:
                print(f"获取资金流向失败: {e}")
                
        elif choice == '5':
            # 查看龙虎榜
            try:
                longhubang = ak.stock_sina_lhb_detail_daily(trade_date=datetime.now().strftime('%Y-%m-%d'))
                if not longhubang.empty:
                    print("\n🐉 今日龙虎榜:")
                    print("-" * 80)
                    print(longhubang[['symbol', 'name', 'buy', 'sell', 'net']].head(10).to_string(index=False))
                else:
                    print("今日暂无龙虎榜数据")
            except Exception as e:
                print(f"获取龙虎榜失败: {e}")
                
        elif choice == '6':
            print("感谢使用，再见！")
            break
            
        else:
            print("请输入有效的选项")


if __name__ == "__main__":
    # 安装依赖命令
    # pip install akshare pandas numpy requests openpyxl
    
    # 运行基本版
    # main()
    
    # 运行增强版
    enhanced_main()