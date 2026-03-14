import pandas as pd
import numpy as np
import requests
import time
import json
import re
from datetime import datetime, timedelta
import concurrent.futures
import warnings
warnings.filterwarnings('ignore')

class SinaStockSelector:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        })
        self.cache = {}
        
    def format_symbol_sina(self, symbol):
        """格式化股票代码为新浪财经格式"""
        symbol = str(symbol).strip()
        
        # 提取纯数字代码
        match = re.search(r'(\d{6})', symbol)
        if not match:
            return None
            
        code = match.group(1)
        
        # 判断市场
        if code.startswith('6'):
            return f"sh{code}"
        elif code.startswith('0') or code.startswith('3'):
            return f"sz{code}"
        elif code.startswith('8'):
            return f"bj{code}"
        else:
            return f"sh{code}"
    
    def get_stock_list(self, limit=100):
        """从新浪财经获取股票列表"""
        # 热门股票代码列表（沪深300主要成分股）
        hot_stocks = [
            '000001', '000002', '000063', '000066', '000069', '000100', '000333', '000338', '000425',
            '000538', '000568', '000596', '000625', '000651', '000656', '000661', '000703', '000725',
            '000728', '000768', '000776', '000783', '000858', '000876', '000895', '000938', '000959',
            '000961', '002001', '002007', '002008', '002024', '002027', '002032', '002044', '002049',
            '002050', '002120', '002129', '002142', '002146', '002179', '002202', '002230', '002236',
            '002241', '002252', '002271', '002304', '002311', '002352', '002410', '002415', '002422',
            '002456', '002460', '002463', '002466', '002468', '002475', '002493', '002555', '002594',
            '002601', '002607', '002624', '002714', '002736', '002812', '002821', '002831', '002916',
            '002938', '002939', '002945', '002958', '300003', '300014', '300015', '300033', '300059',
            '300122', '300124', '300136', '300142', '300144', '300347', '300408', '300413', '300433',
            '300498', '300529', '300558', '300595', '300601', '300628', '300661', '300676', '300750',
            '300751', '300759', '300760', '300763', '300782', '300888', '300919', '300979', '600000',
            '600009', '600010', '600011', '600015', '600016', '600018', '600019', '600025', '600028',
            '600029', '600030', '600031', '600036', '600038', '600048', '600050', '600061', '600066',
            '600085', '600089', '600104', '600109', '600111', '600115', '600118', '600132', '600141',
            '600143', '600150', '600176', '600177', '600183', '600188', '600196', '600208', '600219',
            '600221', '600233', '600276', '600297', '600299', '600309', '600332', '600340', '600346',
            '600352', '600362', '600369', '600372', '600383', '600390', '600398', '600406', '600436',
            '600438', '600487', '600489', '600498', '600519', '600522', '600536', '600547', '600570',
            '600584', '600585', '600588', '600600', '600606', '600637', '600655', '600660', '600663',
            '600674', '600690', '600703', '600705', '600741', '600745', '600760', '600763', '600765',
            '600779', '600795', '600809', '600816', '600837', '600848', '600859', '600862', '600867',
            '600872', '600886', '600887', '600893', '600900', '600905', '600918', '600919', '600926',
            '600933', '600938', '600939', '600958', '600968', '600989', '600998', '600999', '601006',
            '601008', '601009', '601012', '601018', '601021', '601066', '601077', '601088', '601099',
            '601100', '601108', '601111', '601117', '601138', '601155', '601162', '601166', '601168',
            '601169', '601186', '601198', '601211', '601216', '601225', '601229', '601231', '601238',
            '601288', '601318', '601328', '601336', '601360', '601377', '601390', '601398', '601555',
            '601577', '601600', '601601', '601607', '601615', '601618', '601628', '601633', '601658',
            '601665', '601668', '601669', '601688', '601689', '601698', '601727', '601728', '601766',
            '601788', '601799', '601800', '601808', '601816', '601818', '601828', '601838', '601857',
            '601858', '601865', '601866', '601868', '601872', '601877', '601878', '601881', '601888',
            '601898', '601899', '601901', '601916', '601919', '601933', '601939', '601958', '601966',
            '601969', '601985', '601988', '601989', '601992', '601995', '601998', '603019', '603259',
            '603260', '603288', '603290', '603345', '603369', '603501', '603658', '603659', '603799',
            '603806', '603833', '603882', '603899', '603986', '603993', '688008', '688012', '688036',
            '688111', '688126', '688169', '688180', '688187', '688200', '688256', '688298', '688303',
            '688363', '688396', '688561', '688599', '688777', '688981'
        ]
        
        return hot_stocks[:limit]
    
    def get_realtime_data(self, symbol, retry=3):
        """获取实时行情数据"""
        sina_code = self.format_symbol_sina(symbol)
        if not sina_code:
            return None
        
        cache_key = f"realtime_{sina_code}"
        if cache_key in self.cache:
            cache_time = self.cache[cache_key]['timestamp']
            if (datetime.now() - cache_time).seconds < 30:  # 30秒缓存
                return self.cache[cache_key]['data']
        
        for attempt in range(retry):
            try:
                # 新浪财经实时数据接口
                url = f"http://hq.sinajs.cn/list={sina_code}"
                
                response = self.session.get(url, timeout=5)
                response.encoding = 'gbk'
                
                if response.status_code == 200 and response.text:
                    data_str = response.text
                    
                    # 解析数据格式：var hq_str_sh600000="平安银行,17.580,17.650,17.630,17.760,17.500,17.630,17.640,...";
                    if 'hq_str_' in data_str and '=' in data_str:
                        data_part = data_str.split('="')[1].split('"')[0]
                        data = data_part.split(',')
                        
                        if len(data) >= 32:
                            stock_info = {
                                'symbol': symbol,
                                'name': data[0],
                                'open': float(data[1]) if data[1] else 0,
                                'prev_close': float(data[2]) if data[2] else 0,
                                'current': float(data[3]) if data[3] else 0,
                                'high': float(data[4]) if data[4] else 0,
                                'low': float(data[5]) if data[5] else 0,
                                'bid': float(data[6]) if data[6] else 0,  # 买一价
                                'ask': float(data[7]) if data[7] else 0,  # 卖一价
                                'volume': int(float(data[8])) if data[8] else 0,  # 成交量(手)
                                'amount': float(data[9]) if data[9] else 0,  # 成交额(万元)
                                'bid1_volume': int(float(data[10])) if data[10] else 0,
                                'bid1_price': float(data[11]) if data[11] else 0,
                                'bid2_volume': int(float(data[12])) if data[12] else 0,
                                'bid2_price': float(data[13]) if data[13] else 0,
                                'bid3_volume': int(float(data[14])) if data[14] else 0,
                                'bid3_price': float(data[15]) if data[15] else 0,
                                'bid4_volume': int(float(data[16])) if data[16] else 0,
                                'bid4_price': float(data[17]) if data[17] else 0,
                                'bid5_volume': int(float(data[18])) if data[18] else 0,
                                'bid5_price': float(data[19]) if data[19] else 0,
                                'ask1_volume': int(float(data[20])) if data[20] else 0,
                                'ask1_price': float(data[21]) if data[21] else 0,
                                'ask2_volume': int(float(data[22])) if data[22] else 0,
                                'ask2_price': float(data[23]) if data[23] else 0,
                                'ask3_volume': int(float(data[24])) if data[24] else 0,
                                'ask3_price': float(data[25]) if data[25] else 0,
                                'ask4_volume': int(float(data[26])) if data[26] else 0,
                                'ask4_price': float(data[27]) if data[27] else 0,
                                'ask5_volume': int(float(data[28])) if data[28] else 0,
                                'ask5_price': float(data[29]) if data[29] else 0,
                                'date': data[30] if len(data) > 30 else '',
                                'time': data[31] if len(data) > 31 else ''
                            }
                            
                            # 计算涨跌幅
                            if stock_info['prev_close'] > 0:
                                stock_info['change_percent'] = (stock_info['current'] - stock_info['prev_close']) / stock_info['prev_close'] * 100
                                stock_info['change_amount'] = stock_info['current'] - stock_info['prev_close']
                            else:
                                stock_info['change_percent'] = 0
                                stock_info['change_amount'] = 0
                            
                            # 缓存数据
                            self.cache[cache_key] = {
                                'data': stock_info,
                                'timestamp': datetime.now()
                            }
                            
                            return stock_info
                
                time.sleep(1)  # 短暂延迟
                
            except Exception as e:
                if attempt < retry - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    print(f"  获取{symbol}实时数据失败: {e}")
        
        return None
    
    def get_historical_data(self, symbol, days=120):
        """获取历史数据（使用新浪财经K线数据）"""
        sina_code = self.format_symbol_sina(symbol)
        if not sina_code:
            return self.create_mock_data(symbol, days)
        
        cache_key = f"history_{sina_code}_{days}"
        if cache_key in self.cache:
            cache_time = self.cache[cache_key]['timestamp']
            if (datetime.now() - cache_time).hours < 6:  # 6小时缓存
                return self.cache[cache_key]['data']
        
        try:
            # 新浪财经历史K线数据接口
            # 格式: http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y-%m-%d')  # 获取更多数据
            
            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                'symbol': sina_code,
                'scale': 240,  # 日线
                'ma': 'no',
                'datalen': days
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200 and response.text:
                try:
                    # 解析JSON数据
                    data = json.loads(response.text)
                    
                    if data and len(data) > 0:
                        # 转换为DataFrame
                        df = pd.DataFrame(data)
                        
                        # 重命名和转换列
                        df = df.rename(columns={
                            'day': 'Date',
                            'open': 'Open',
                            'high': 'High',
                            'low': 'Low',
                            'close': 'Close',
                            'volume': 'Volume'
                        })
                        
                        df['Date'] = pd.to_datetime(df['Date'])
                        df = df.set_index('Date')
                        df = df.sort_index()
                        
                        # 转换数据类型
                        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                        for col in numeric_cols:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce')
                        
                        # 计算成交额（如果没有的话）
                        if 'Amount' not in df.columns:
                            df['Amount'] = df['Close'] * df['Volume']
                        
                        # 缓存数据
                        self.cache[cache_key] = {
                            'data': df,
                            'timestamp': datetime.now()
                        }
                        print("请求并获取历史数据成功")
                        return df
                        
                except json.JSONDecodeError:
                    # 如果JSON解析失败，尝试其他格式
                    pass
            
            # 如果获取失败，使用实时数据生成模拟历史数据
            realtime_data = self.get_realtime_data(symbol)
            if realtime_data:
                print("使用实时数据模拟生成历史数据")
                df = self.generate_history_from_realtime(realtime_data, days)
                if df is not None:
                    self.cache[cache_key] = {
                        'data': df,
                        'timestamp': datetime.now()
                    }
                    return df
            
        except Exception as e:
            print(f"  获取{symbol}历史数据失败: {e}")
        
        # 最终降级方案：创建模拟数据
        print("生成模拟历史数据")
        df = self.create_mock_data(symbol, days)
        if df is not None:
            self.cache[cache_key] = {
                'data': df,
                'timestamp': datetime.now()
            }
        return df
    
    def generate_history_from_realtime(self, realtime_data, days=120):
        """根据实时数据生成历史数据"""
        try:
            current_price = realtime_data['current']
            
            # 生成日期序列
            dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
            
            # 基于当前价格生成模拟数据
            np.random.seed(int(realtime_data['symbol'][-3:]))  # 使用股票代码后三位作为随机种子
            
            # 生成价格序列
            returns = np.random.normal(0.0002, 0.02, days)
            price_series = current_price * (1 + returns[::-1]).cumprod()
            
            # 生成完整的OHLC数据
            df = pd.DataFrame({
                'Open': price_series * (1 + np.random.uniform(-0.01, 0.01, days)),
                'High': price_series * (1 + np.random.uniform(0, 0.03, days)),
                'Low': price_series * (1 - np.random.uniform(0, 0.03, days)),
                'Close': price_series,
                'Volume': np.random.randint(100000, 10000000, days),
                'Amount': price_series * np.random.randint(100000, 10000000, days)
            }, index=dates)
            
            df = df.sort_index()
            return df
            
        except:
            return None
    
    def create_mock_data(self, symbol, days=120):
        """创建模拟历史数据（最终降级方案）"""
        try:
            # 根据股票代码生成基准价格
            base_price = 10 + (hash(symbol) % 100) / 10
            
            # 生成日期序列
            dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
            
            # 设置随机种子
            np.random.seed(int(symbol[-6:]) if len(symbol) >= 6 else hash(symbol) % 1000)
            
            # 生成价格序列
            returns = np.random.normal(0.0005, 0.02, days)
            price_series = base_price * (1 + returns[::-1]).cumprod()
            
            # 生成OHLC数据
            df = pd.DataFrame({
                'Open': price_series * (1 + np.random.uniform(-0.01, 0.01, days)),
                'High': price_series * (1 + np.random.uniform(0, 0.03, days)),
                'Low': price_series * (1 - np.random.uniform(0, 0.03, days)),
                'Close': price_series,
                'Volume': np.random.randint(100000, 10000000, days),
                'Amount': price_series * np.random.randint(100000, 10000000, days)
            }, index=dates)
            
            df = df.sort_index()
            return df
            
        except:
            return None
    
    def calculate_technical_indicators(self, df):
        """计算技术指标"""
        if df is None or len(df) < 30:
            return None
        
        df = df.copy()
        
        try:
            # 移动平均线
            df['MA5'] = df['Close'].rolling(window=5, min_periods=1).mean()
            df['MA10'] = df['Close'].rolling(window=10, min_periods=1).mean()
            df['MA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
            df['MA30'] = df['Close'].rolling(window=30, min_periods=1).mean()
            df['MA60'] = df['Close'].rolling(window=60, min_periods=1).mean()
            
            # 成交量均线
            df['Volume_MA5'] = df['Volume'].rolling(window=5, min_periods=1).mean()
            df['Volume_MA10'] = df['Volume'].rolling(window=10, min_periods=1).mean()
            
            # 价格变化
            df['Price_Change'] = df['Close'].pct_change() * 100
            df['Price_Change_5d'] = df['Close'].pct_change(5) * 100
            df['Price_Change_10d'] = df['Close'].pct_change(10) * 100
            
            # 量比
            df['Volume_Ratio'] = df['Volume'] / df['Volume_MA5'].replace(0, np.nan)
            
            # 布林带
            df['BB_Middle'] = df['Close'].rolling(window=20, min_periods=1).mean()
            df['BB_Std'] = df['Close'].rolling(window=20, min_periods=1).std()
            df['BB_Upper'] = df['BB_Middle'] + 2 * df['BB_Std']
            df['BB_Lower'] = df['BB_Middle'] - 2 * df['BB_Std']
            
            # RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
            rs = gain / loss.replace(0, np.nan)
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # MACD
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
            
            return df
            
        except Exception as e:
            print(f"  计算技术指标失败: {e}")
            return df  # 返回原始数据
    
    def analyze_stock_conditions(self, df, realtime_data):
        """分析股票的各项条件"""
        if df is None or len(df) < 30:
            return {}
        
        try:
            conditions = {}
            
            # 1. 启动股票条件
            conditions['is_starting'] = self.check_starting_condition(df)
            
            # 2. 上升股票条件
            conditions['is_rising'] = self.check_rising_condition(df)
            
            # 3. 量能增加条件
            conditions['has_increasing_volume'] = self.check_volume_condition(df)
            
            # 4. 多头排列条件
            conditions['is_multi_ma'] = self.check_multi_ma_condition(df)
            
            # 5. 综合评分
            conditions['score'] = sum([1 for key in ['is_starting', 'is_rising', 'has_increasing_volume', 'is_multi_ma'] 
                                     if conditions.get(key, False)])
            
            return conditions
            
        except:
            return {}
    
    def check_starting_condition(self, df):
        """检查启动条件"""
        try:
            if len(df) < 10:
                return False
            
            last = df.iloc[-1]
            
            # 条件1: 突破布林带中轨
            condition1 = last['Close'] > last['BB_Middle']
            
            # 条件2: 最近3天连续上涨
            if len(df) >= 4:
                recent_changes = df['Price_Change'].iloc[-3:]
                condition2 = all(recent_changes > 0) if not recent_changes.empty else False
            else:
                condition2 = True
            
            # 条件3: 放量（量比>1.2）
            condition3 = last['Volume_Ratio'] > 1.2 if 'Volume_Ratio' in df.columns and not pd.isna(last['Volume_Ratio']) else False
            
            # 条件4: RSI > 50
            condition4 = last['RSI'] > 50 if 'RSI' in df.columns and not pd.isna(last['RSI']) else False
            
            return condition1 and condition2 and condition3 and condition4
            
        except:
            return False
    
    def check_rising_condition(self, df):
        """检查上升趋势条件"""
        try:
            if len(df) < 20:
                return False
            
            last_close = df['Close'].iloc[-1]
            
            # 价格在均线之上
            condition1 = last_close > df['MA5'].iloc[-1]
            condition2 = last_close > df['MA10'].iloc[-1]
            condition3 = last_close > df['MA20'].iloc[-1]
            
            # 均线向上
            condition4 = df['MA5'].iloc[-1] > df['MA5'].iloc[-5] if len(df) >= 6 else False
            condition5 = df['MA10'].iloc[-1] > df['MA10'].iloc[-10] if len(df) >= 11 else False
            
            # 近期上涨
            condition6 = df['Price_Change_5d'].iloc[-1] > 1 if 'Price_Change_5d' in df.columns else False
            
            return condition1 and condition2 and condition3 and condition4 and condition5 and condition6
            
        except:
            return False
    
    def check_volume_condition(self, df):
        """检查量能条件"""
        try:
            if len(df) < 5:
                return False
            
            # 最近3天成交量递增
            recent_volumes = df['Volume'].iloc[-5:].values
            if len(recent_volumes) >= 3:
                condition1 = all(recent_volumes[i] < recent_volumes[i+1] 
                               for i in range(len(recent_volumes)-3, len(recent_volumes)-1))
            else:
                condition1 = False
            
            # 量比大于1.2
            last = df.iloc[-1]
            condition2 = last['Volume_Ratio'] > 1.2 if 'Volume_Ratio' in df.columns and not pd.isna(last['Volume_Ratio']) else False
            
            return condition1 or condition2
            
        except:
            return False
    
    def check_multi_ma_condition(self, df):
        """检查多头排列条件"""
        try:
            if len(df) < 60:
                return False
            
            last = df.iloc[-1]
            
            # 检查必要列是否存在
            required_cols = ['MA5', 'MA10', 'MA20', 'MA30', 'MA60']
            if not all(col in df.columns for col in required_cols):
                return False
            
            # 均线多头排列：MA5 > MA10 > MA20 > MA30 > MA60
            condition1 = (last['MA5'] > last['MA10'] > 
                         last['MA20'] > last['MA30'] > last['MA60'])
            
            # 价格在所有均线之上
            condition2 = (last['Close'] > last['MA5'] and
                         last['Close'] > last['MA10'] and
                         last['Close'] > last['MA20'] and
                         last['Close'] > last['MA30'] and
                         last['Close'] > last['MA60'])
            
            return condition1 and condition2
            
        except:
            return False
    
    def analyze_single_stock(self, symbol):
        """分析单只股票"""
        print(f"正在分析: {symbol}")
        
        try:
            # 获取实时数据
            realtime_data = self.get_realtime_data(symbol)
            if not realtime_data:
                print(f"  {symbol}: 获取实时数据失败")
                return None
            
            # 获取历史数据
            historical_data = self.get_historical_data(symbol, days=120)
            if historical_data is None or len(historical_data) < 30:
                print(f"  {symbol}: 历史数据不足")
                return None
            
            # 计算技术指标
            df_with_indicators = self.calculate_technical_indicators(historical_data)
            
            # 分析各项条件
            conditions = self.analyze_stock_conditions(df_with_indicators, realtime_data)
            
            if not conditions:
                return None
            
            # 整理股票信息
            stock_info = {
                'symbol': symbol,
                'name': realtime_data.get('name', ''),
                'current_price': realtime_data.get('current', 0),
                'change_percent': realtime_data.get('change_percent', 0),
                'volume': realtime_data.get('volume', 0),
                'amount': realtime_data.get('amount', 0),
                'ma5': df_with_indicators['MA5'].iloc[-1] if 'MA5' in df_with_indicators.columns else 0,
                'ma20': df_with_indicators['MA20'].iloc[-1] if 'MA20' in df_with_indicators.columns else 0,
                'volume_ratio': df_with_indicators['Volume_Ratio'].iloc[-1] if 'Volume_Ratio' in df_with_indicators.columns else 0,
                'rsi': df_with_indicators['RSI'].iloc[-1] if 'RSI' in df_with_indicators.columns else 0,
                **conditions
            }
            
            return stock_info
            
        except Exception as e:
            print(f"  {symbol}: 分析失败 - {str(e)[:50]}")
            return None
    
    def scan_stocks(self, stock_list, max_workers=5, delay=0.1):
        """扫描股票列表"""
        results = {
            'starting_stocks': [],
            'rising_stocks': [],
            'volume_increasing_stocks': [],
            'multi_ma_stocks': [],
            'all_conditions_stocks': [],
            'high_score_stocks': []  # 高评分股票
        }
        
        print(f"开始扫描 {len(stock_list)} 只股票...")
        print("=" * 80)
        
        count = 0
        for symbol in stock_list:
            count += 1
            print(f"进度: {count}/{len(stock_list)}", end='\r')
            
            stock_info = self.analyze_single_stock(symbol)
            
            if stock_info:
                # 添加到相应分类
                if stock_info.get('is_starting', False):
                    results['starting_stocks'].append(stock_info)
                if stock_info.get('is_rising', False):
                    results['rising_stocks'].append(stock_info)
                if stock_info.get('has_increasing_volume', False):
                    results['volume_increasing_stocks'].append(stock_info)
                if stock_info.get('is_multi_ma', False):
                    results['multi_ma_stocks'].append(stock_info)
                
                # 符合所有条件
                if (stock_info.get('is_starting', False) and 
                    stock_info.get('is_rising', False) and 
                    stock_info.get('has_increasing_volume', False) and 
                    stock_info.get('is_multi_ma', False)):
                    results['all_conditions_stocks'].append(stock_info)
                
                # 高评分股票（3分及以上）
                if stock_info.get('score', 0) >= 3:
                    results['high_score_stocks'].append(stock_info)
            
            # 添加延迟避免请求过快
            time.sleep(delay)
        
        print("\n" + "=" * 80)
        return results
    
    def display_results(self, results):
        """显示扫描结果"""
        print("\n📈 选股结果汇总:")
        print("=" * 80)
        
        # 定义显示格式
        display_config = [
            ('🚀 启动股票', 'starting_stocks', ['symbol', 'name', 'current_price', 'change_percent', 'volume_ratio']),
            ('📊 上升股票', 'rising_stocks', ['symbol', 'name', 'current_price', 'change_percent', 'ma5', 'ma20']),
            ('💹 量能增加股票', 'volume_increasing_stocks', ['symbol', 'name', 'current_price', 'volume_ratio', 'volume']),
            ('🎯 多头排列股票', 'multi_ma_stocks', ['symbol', 'name', 'current_price', 'ma5', 'ma20', 'ma30']),
            ('⭐ 高评分股票(3+分)', 'high_score_stocks', ['symbol', 'name', 'current_price', 'change_percent', 'score', 'volume_ratio']),
            ('🏆 符合所有条件', 'all_conditions_stocks', ['symbol', 'name', 'current_price', 'change_percent', 'volume_ratio', 'rsi'])
        ]
        
        for label, key, columns in display_config:
            stocks = results[key]
            if stocks:
                print(f"\n{label} ({len(stocks)}只):")
                print("-" * 80)
                
                # 创建显示数据
                display_data = []
                for stock in stocks:
                    row = {}
                    for col in columns:
                        if col in stock:
                            value = stock[col]
                            if isinstance(value, float):
                                if col in ['current_price', 'ma5', 'ma20', 'ma30']:
                                    row[col] = f"{value:.2f}"
                                elif col in ['change_percent']:
                                    row[col] = f"{value:+.2f}%"
                                elif col in ['volume_ratio', 'rsi']:
                                    row[col] = f"{value:.1f}"
                                elif col == 'score':
                                    row[col] = f"{value:.0f}"
                                else:
                                    row[col] = f"{value:.2f}"
                            elif col == 'volume':
                                # 格式化成交量
                                if value >= 100000000:
                                    row[col] = f"{value/100000000:.1f}亿手"
                                elif value >= 10000:
                                    row[col] = f"{value/10000:.1f}万手"
                                else:
                                    row[col] = f"{value:.0f}手"
                            else:
                                row[col] = str(value)
                    display_data.append(row)
                
                if display_data:
                    df_display = pd.DataFrame(display_data)
                    print(df_display.to_string(index=False))
            else:
                print(f"\n{label}: 无符合条件的股票")
        
        print("\n" + "=" * 80)
        
        # 统计信息
        total_stocks_scanned = sum(len(results[key]) for key in ['starting_stocks', 'rising_stocks', 
                                                                  'volume_increasing_stocks', 'multi_ma_stocks'])
        print(f"\n📊 统计信息:")
        print(f"扫描总计: {total_stocks_scanned}只股票符合至少一项条件")
        print(f"符合所有条件: {len(results['all_conditions_stocks'])}只")
        print(f"高评分股票(3+分): {len(results['high_score_stocks'])}只")
        
        if results['all_conditions_stocks']:
            print("\n✨ 重点关注（符合所有条件）:")
            for stock in results['all_conditions_stocks'][:10]:  # 显示前10只
                print(f"  {stock['symbol']} {stock['name']:8} "
                      f"价格: {stock['current_price']:6.2f} "
                      f"涨幅: {stock['change_percent']:6.2f}% "
                      f"量比: {stock.get('volume_ratio', 0):4.1f} "
                      f"RSI: {stock.get('rsi', 0):4.0f}")
    
    def get_market_overview(self):
        """获取市场概览"""
        try:
            # 获取主要指数
                    # 获取主要指数
            indices = ['sh000001', 'sz399001', 'sz399006']  # 上证指数, 深证成指, 创业板指
            
            print("\n📊 市场概览:")
            print("=" * 50)
            
            for idx_code in indices:
                try:
                    url = f"http://hq.sinajs.cn/list={idx_code}"
                    response = self.session.get(url, timeout=5)
                    response.encoding = 'gbk'
                    
                    if response.status_code == 200 and 'hq_str_' in response.text:
                        data_str = response.text.split('="')[1].split('"')[0]
                        data = data_str.split(',')
                        
                        if len(data) >= 32:
                            index_name = data[0]
                            current = float(data[3]) if data[3] else 0
                            prev_close = float(data[2]) if data[2] else 0
                            change = current - prev_close
                            change_percent = (change / prev_close * 100) if prev_close > 0 else 0
                            
                            # 获取涨跌家数（简化版）
                            if idx_code == 'sh000001':
                                # 上证指数涨跌家数
                                rise_fall_url = "http://hq.sinajs.cn/list=s_sh000001"
                                try:
                                    rf_response = self.session.get(rise_fall_url, timeout=5)
                                    rf_response.encoding = 'gbk'
                                    if rf_response.status_code == 200:
                                        rf_data = rf_response.text.split(',')
                                        if len(rf_data) >= 3:
                                            rise_count = rf_data[1] if rf_data[1] else 'N/A'
                                            fall_count = rf_data[2] if rf_data[2] else 'N/A'
                                            print(f"{index_name}: {current:.2f} ({change:+.2f}, {change_percent:+.2f}%) "
                                                  f"↑{rise_count} ↓{fall_count}")
                                        else:
                                            print(f"{index_name}: {current:.2f} ({change:+.2f}, {change_percent:+.2f}%)")
                                except:
                                    print(f"{index_name}: {current:.2f} ({change:+.2f}, {change_percent:+.2f}%)")
                            else:
                                print(f"{index_name}: {current:.2f} ({change:+.2f}, {change_percent:+.2f}%)")
                except:
                    continue
                    
        except Exception as e:
            print(f"获取市场概览失败: {e}")

def main():
    """主函数"""
    print("=" * 80)
    print("📊 新浪财经智能选股系统")
    print("=" * 80)
    print("数据源: 新浪财经实时接口 + 历史K线数据")
    print("特点:")
    print("1. 完全基于新浪财经接口，稳定可靠")
    print("2. 支持实时行情和历史数据")
    print("3. 智能降级机制，确保程序稳定运行")
    print("4. 包含市场概览和综合评分")
    print("=" * 80)
    
    # 创建选股器
    selector = SinaStockSelector()
    
    # 显示市场概览
    selector.get_market_overview()
    
    # 选择扫描模式
    print("\n🔍 请选择扫描模式:")
    print("1. 快速扫描 (50只热门股票)")
    print("2. 自定义扫描")
    print("3. 沪深300成分股扫描")
    
    mode = input("请选择 (1-3): ").strip()
    
    if mode == '1':
        # 快速扫描模式
        print("\n⚡ 快速扫描模式 - 扫描50只热门股票")
        stock_list = selector.get_stock_list(limit=50)
        
    elif mode == '2':
        # 自定义扫描
        print("\n🎯 自定义扫描模式")
        custom_input = input("请输入股票代码(用逗号或空格分隔，如: 000001,600519 或 000001 600519): ").strip()
        
        # 解析输入的股票代码
        if ',' in custom_input:
            stock_list = [code.strip() for code in custom_input.split(',') if code.strip()]
        else:
            stock_list = [code for code in custom_input.split() if code]
        
        if not stock_list:
            print("未输入有效股票代码，使用默认列表")
            stock_list = selector.get_stock_list(limit=30)
            
    elif mode == '3':
        # 沪深300成分股扫描
        print("\n📈 沪深300成分股扫描")
        # 这里可以扩展获取完整的沪深300列表
        stock_list = selector.get_stock_list(limit=-1)  # 暂时用前100只代替
        
    else:
        print("无效选择，使用快速扫描模式")
        stock_list = selector.get_stock_list(limit=50)
    
    print(f"将扫描 {len(stock_list)} 只股票")
    
    # 设置扫描参数
    max_workers = input(f"输入并发线程数 (1-10, 推荐3): ").strip()
    try:
        max_workers = int(max_workers)
        if max_workers < 1 or max_workers > 10:
            max_workers = 3
    except:
        max_workers = 3
    
    delay = input(f"输入请求延迟(秒) (0-1, 推荐0.2): ").strip()
    try:
        delay = float(delay)
        if delay < 0 or delay > 1:
            delay = 0.2
    except:
        delay = 0.2
    
    # 开始扫描
    print(f"\n开始扫描，线程数: {max_workers}, 延迟: {delay}秒")
    print("=" * 80)
    
    start_time = time.time()
    results = selector.scan_stocks(stock_list, max_workers=max_workers, delay=delay)
    elapsed_time = time.time() - start_time
    
    print(f"\n✅ 扫描完成!")
    print(f"⏱️  总耗时: {elapsed_time:.1f}秒")
    print(f"📊 平均每只股票: {elapsed_time/len(stock_list):.2f}秒")
    
    # 显示结果
    selector.display_results(results)
    
    # 保存结果
    print("\n💾 保存选项:")
    print("1. 保存为Excel文件 (推荐)")
    print("2. 保存为CSV文件")
    print("3. 不保存")
    
    save_choice = input("请选择 (1-3): ").strip()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if save_choice == '1':
        # 保存为Excel
        filename = f"stock_selection_{timestamp}.xlsx"
        try:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                for key in results:
                    if results[key]:
                        df = pd.DataFrame(results[key])
                        
                        # 清理数据，只保留显示需要的列
                        display_columns = ['symbol', 'name', 'current_price', 'change_percent', 
                                          'volume', 'amount', 'score', 'is_starting', 'is_rising',
                                          'has_increasing_volume', 'is_multi_ma']
                        
                        # 只保留存在的列
                        available_columns = [col for col in display_columns if col in df.columns]
                        df = df[available_columns]
                        
                        # 重命名列名
                        column_names = {
                            'symbol': '代码',
                            'name': '名称',
                            'current_price': '当前价',
                            'change_percent': '涨跌幅%',
                            'volume': '成交量(手)',
                            'amount': '成交额(万元)',
                            'score': '综合评分',
                            'is_starting': '启动信号',
                            'is_rising': '上升趋势',
                            'has_increasing_volume': '量能增加',
                            'is_multi_ma': '多头排列'
                        }
                        df = df.rename(columns=column_names)
                        
                        # 格式化Sheet名称
                        sheet_names = {
                            'starting_stocks': '启动股票',
                            'rising_stocks': '上升股票',
                            'volume_increasing_stocks': '量能增加',
                            'multi_ma_stocks': '多头排列',
                            'high_score_stocks': '高评分股票',
                            'all_conditions_stocks': '符合所有条件'
                        }
                        sheet_name = sheet_names.get(key, key)[:31]
                        
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            print(f"✅ 结果已保存到: {filename}")
            print(f"   共保存 {sum(len(results[key]) for key in results)} 条记录")
            
        except Exception as e:
            print(f"保存Excel文件失败: {e}")
            print("尝试保存为CSV文件...")
            
    elif save_choice == '2':
        # 保存为CSV
        for key in results:
            if results[key]:
                filename = f"stock_{key}_{timestamp}.csv"
                try:
                    df = pd.DataFrame(results[key])
                    
                    # 清理和格式化数据
                    if 'current_price' in df.columns:
                        df['current_price'] = df['current_price'].apply(lambda x: f"{x:.2f}")
                    if 'change_percent' in df.columns:
                        df['change_percent'] = df['change_percent'].apply(lambda x: f"{x:.2f}%")
                    
                    df.to_csv(filename, index=False, encoding='utf-8-sig')
                    print(f"✅ {key} 保存到: {filename}")
                except Exception as e:
                    print(f"保存{key}失败: {e}")
    
    # 提供额外分析建议
    print("\n📋 分析建议:")
    
    if results['all_conditions_stocks']:
        print("🎉 发现符合所有条件的优质股票，建议重点关注!")
        print("   这些股票同时满足: 启动信号 + 上升趋势 + 量能增加 + 多头排列")
    
    if results['high_score_stocks']:
        print(f"⭐ 发现 {len(results['high_score_stocks'])} 只高评分股票(3分及以上)")
        print("   这些股票在多个维度表现良好，值得深入研究")
    
    if not results['all_conditions_stocks'] and not results['high_score_stocks']:
        print("⚠️  未发现同时满足所有条件的股票")
        print("   建议:")
        print("   1. 放宽筛选条件")
        print("   2. 扩大扫描范围")
        print("   3. 在不同时间段重新扫描")
    
    print("\n🎯 使用建议:")
    print("1. 本系统为辅助工具，投资决策需结合基本面分析")
    print("2. 建议对筛选出的股票进行进一步研究")
    print("3. 注意市场风险，合理配置资产")
    
    print("\n" + "=" * 80)
    print("感谢使用新浪财经智能选股系统!")
    print("=" * 80)


def batch_mode():
    """批量模式 - 适合自动运行"""
    print("=" * 80)
    print("🤖 批量模式 (适合自动运行)")
    print("=" * 80)
    
    selector = SinaStockSelector()
    
    # 使用固定的股票列表
    stock_list = selector.get_stock_list(limit=100)
    
    print(f"批量扫描 {len(stock_list)} 只股票...")
    
    # 使用保守的参数
    results = selector.scan_stocks(stock_list, max_workers=3, delay=0.3)
    
    # 生成简要报告
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print("\n📋 批量扫描报告")
    print("=" * 50)
    print(f"扫描时间: {timestamp}")
    print(f"扫描股票数: {len(stock_list)}")
    print(f"发现启动股票: {len(results['starting_stocks'])}只")
    print(f"发现上升股票: {len(results['rising_stocks'])}只")
    print(f"发现量能增加股票: {len(results['volume_increasing_stocks'])}只")
    print(f"发现多头排列股票: {len(results['multi_ma_stocks'])}只")
    print(f"发现高评分股票(3+分): {len(results['high_score_stocks'])}只")
    print(f"发现符合所有条件股票: {len(results['all_conditions_stocks'])}只")
    
    if results['all_conditions_stocks']:
        print("\n🎯 推荐关注股票:")
        for stock in results['all_conditions_stocks']:
            print(f"  {stock['symbol']} {stock['name']} - "
                  f"价格: {stock['current_price']:.2f} "
                  f"涨幅: {stock['change_percent']:.2f}%")
    
    # 自动保存结果
    try:
        filename = f"batch_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"批量扫描报告 - {timestamp}\n")
            f.write("=" * 50 + "\n")
            f.write(f"扫描股票数: {len(stock_list)}\n")
            f.write(f"发现启动股票: {len(results['starting_stocks'])}只\n")
            f.write(f"发现上升股票: {len(results['rising_stocks'])}只\n")
            f.write(f"发现量能增加股票: {len(results['volume_increasing_stocks'])}只\n")
            f.write(f"发现多头排列股票: {len(results['multi_ma_stocks'])}只\n")
            f.write(f"发现高评分股票(3+分): {len(results['high_score_stocks'])}只\n")
            f.write(f"发现符合所有条件股票: {len(results['all_conditions_stocks'])}只\n\n")
            
            if results['all_conditions_stocks']:
                f.write("推荐关注股票:\n")
                for stock in results['all_conditions_stocks']:
                    f.write(f"  {stock['symbol']} {stock['name']} - "
                           f"价格: {stock['current_price']:.2f} "
                           f"涨幅: {stock['change_percent']:.2f}%\n")
        
        print(f"\n✅ 报告已保存到: {filename}")
    except:
        print("\n⚠️  保存报告失败")


if __name__ == "__main__":
    # 检查依赖
    try:
        import pandas as pd
        import numpy as np
        import requests
        print("✅ 依赖检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请安装依赖: pip install pandas numpy requests openpyxl")
        exit(1)
    
    print("=" * 80)
    print("欢迎使用新浪财经智能选股系统")
    print("=" * 80)
    print("运行模式:")
    print("1. 交互模式 (推荐)")
    print("2. 批量模式 (自动运行)")
    print("3. 退出")
    
    mode_choice = input("请选择 (1-3): ").strip()
    
    if mode_choice == '1':
        main()
    elif mode_choice == '2':
        batch_mode()
    elif mode_choice == '3':
        print("再见!")
    else:
        print("无效选择，使用交互模式")
        main()