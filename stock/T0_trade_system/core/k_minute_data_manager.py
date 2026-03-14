import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional
from dataclasses import dataclass
from hq.tick_storage import TickStorage
from hq.tick_data import TickData
from config.trading_config import TradingConfig

from utils.logger import get_core_logger
logger = get_core_logger('k_minute_data_manager')
@dataclass
class MinuteBarData:
    """分钟K线数据"""
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_volume: int = 0
    ask_volume: int = 0

class MinuteDataManager:
    """分钟K线数据管理器（适配TickData）"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.tick_storage = TickStorage(config.tick_data_dir)
        self.historical_data: Dict[str, List[MinuteBarData]] = {}
        self.current_minute_bars: Dict[str, MinuteBarData] = {}
        self.last_minute: Dict[str, datetime] = {}
    
    def load_historical_minute_data(self, stock_code: str, target_date: str) -> bool:
        """
        从逐笔数据加载历史分钟K线
        
        Args:
            stock_code: 股票代码
            target_date: 目标日期 (YYYYMMDD)
        """
        try:
            # 清空现有数据
            if stock_code in self.historical_data:
                del self.historical_data[stock_code]
            
            # 加载逐笔数据
            tick_data_list = self.tick_storage.load_daily_data(stock_code, target_date)
            if not tick_data_list:
                logger.info(f"未找到 {stock_code} 在 {target_date} 的逐笔数据")
                return False
            
            # 过滤交易时间内的数据 (9:30-11:30, 13:00-15:00)
            filtered_ticks = self._filter_trading_hours(tick_data_list)
            if not filtered_ticks:
                logger.info(f"{stock_code} 在 {target_date} 无交易时间内的数据")
                return False
            
            # 生成分钟K线
            minute_bars = self._generate_minute_bars_from_ticks(filtered_ticks)
            self.historical_data[stock_code] = minute_bars
            
            logger.info(f"成功加载 {stock_code} {target_date} 的分钟K线: {len(minute_bars)} 根")
            return True
            
        except Exception as e:
            logger.info(f"加载历史分钟数据失败 {stock_code} {target_date}: {e}")
            return False

    # 判断是否为交易时段行情
    def _is_trading_hours(self, timestamp: datetime) -> bool:
        """判断给定时间是否在交易时间段内"""
        tick_time = timestamp.time()
        
        # 上午交易时间: 9:30-11:30
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        
        # 下午交易时间: 13:00-15:00
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)
        
        return ((morning_start <= tick_time <= morning_end) or 
                (afternoon_start <= tick_time <= afternoon_end))
    
    def _filter_trading_hours(self, tick_data_list: List[TickData]) -> List[TickData]:
        """过滤交易时间内的逐笔数据"""
        filtered_ticks = []
        
        for tick in tick_data_list:
            tick_time = tick.timestamp.time()
            
            # 上午交易时间: 9:30-11:30
            morning_start = time(9, 30)
            morning_end = time(11, 30)
            
            # 下午交易时间: 13:00-15:00
            afternoon_start = time(13, 0)
            afternoon_end = time(15, 0)
            
            if ((morning_start <= tick_time <= morning_end) or 
                (afternoon_start <= tick_time <= afternoon_end)):
                filtered_ticks.append(tick)
        
        return filtered_ticks
    
    def _generate_minute_bars_from_ticks(self, tick_data_list: List[TickData]) -> List[MinuteBarData]:
        """从逐笔数据生成分钟K线"""
        if not tick_data_list:
            return []
        
        # 按分钟分组
        minute_groups = {}
        for tick in tick_data_list:
            minute_key = tick.timestamp.replace(second=0, microsecond=0)
            
            if minute_key not in minute_groups:
                minute_groups[minute_key] = []
            minute_groups[minute_key].append(tick)
        
        # 为每个分钟生成K线
        minute_bars = []
        for minute_time, ticks in sorted(minute_groups.items()):
            if not ticks:
                continue
                
            # 按时间排序
            ticks_sorted = sorted(ticks, key=lambda x: x.timestamp)
            
            # 生成分钟K线
            minute_bar = self._create_minute_bar_from_ticks(minute_time, ticks_sorted)
            if minute_bar:
                minute_bars.append(minute_bar)
        
        return minute_bars
    
    def _create_minute_bar_from_ticks(self, minute_time: datetime, ticks: List[TickData]) -> Optional[MinuteBarData]:
        """从一组逐笔数据创建分钟K线"""
        if not ticks:
            return None
        
        # 初始化K线数据
        open_price = ticks[0].price
        high_price = max(tick.price for tick in ticks)
        low_price = min(tick.price for tick in ticks)
        close_price = ticks[-1].price
        
        # 计算成交量和成交额（使用增量）
        first_tick = ticks[0]
        last_tick = ticks[-1]
        
        total_volume = last_tick.volume - first_tick.volume
        total_amount = last_tick.amount - first_tick.amount
        
        # 如果无法计算增量，使用最后一条数据的绝对值
        if total_volume == 0 and len(ticks) > 0:
            total_volume = ticks[-1].volume
            total_amount = ticks[-1].amount
        
        return MinuteBarData(
            datetime=minute_time,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=total_volume,
            amount=total_amount,
            bid_price=last_tick.bid_price,
            ask_price=last_tick.ask_price,
            bid_volume=last_tick.bid_volume,
            ask_volume=last_tick.ask_volume
        )
    
    def get_historical_data_df(self, stock_code: str, lookback: int = 60) -> pd.DataFrame:
        """获取历史分钟K线数据（DataFrame格式）"""
        if stock_code not in self.historical_data or not self.historical_data[stock_code]:
            return pd.DataFrame()
        
        bars = self.historical_data[stock_code]
        # bars = self.historical_data[stock_code][-lookback:]
        
        data = {
            'datetime': [bar.datetime for bar in bars],
            'open': [bar.open for bar in bars],
            'high': [bar.high for bar in bars],
            'low': [bar.low for bar in bars],
            'close': [bar.close for bar in bars],
            'volume': [bar.volume for bar in bars],
            'amount': [bar.amount for bar in bars],
            'bid_price': [bar.bid_price for bar in bars],
            'ask_price': [bar.ask_price for bar in bars],
            'bid_volume': [bar.bid_volume for bar in bars],
            'ask_volume': [bar.ask_volume for bar in bars]
        }
        
        return pd.DataFrame(data)
    
    def plot_minute_chart(self, stock_code: str, date_str: str, save_path: str = None):
        """绘制分钟K线图"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from mpl_finance import candlestick_ohlc
            
            if stock_code not in self.historical_data:
                if not self.load_historical_minute_data(stock_code, date_str):
                    logger.info(f"无法加载 {stock_code} 的数据")
                    return
            
            bars = self.historical_data[stock_code]
            if not bars:
                logger.info(f"{stock_code} 无分钟K线数据")
                return
            
            # 准备绘图数据
            df = self.get_historical_data_df(stock_code, len(bars))
            df['datetime_num'] = mdates.date2num(df['datetime'])
            
            # 创建图表
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), 
                                          gridspec_kw={'height_ratios': [3, 1]})
            
            # 绘制K线
            ohlc_data = df[['datetime_num', 'open', 'high', 'low', 'close']].values
            candlestick_ohlc(ax1, ohlc_data, width=0.0004, colorup='r', colordown='g')
            
            # 设置K线图属性
            ax1.set_title(f'{stock_code} 分钟K线图 - {date_str}', fontsize=16)
            ax1.set_ylabel('价格', fontsize=12)
            ax1.grid(True, linestyle='--', alpha=0.7)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            
            # 绘制成交量
            ax2.bar(df['datetime_num'], df['volume'], width=0.0004, 
                   color=['r' if close >= open else 'g' for open, close in zip(df['open'], df['close'])])
            ax2.set_ylabel('成交量', fontsize=12)
            ax2.set_xlabel('时间', fontsize=12)
            ax2.grid(True, linestyle='--', alpha=0.7)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            
            # 自动调整布局
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"图表已保存至: {save_path}")
            
            plt.show()
            
        except ImportError as e:
            logger.info(f"绘图依赖未安装: {e}")
            logger.info("请安装: pip install matplotlib mpl_finance")
        except Exception as e:
            logger.info(f"绘制图表失败: {e}")
    
    def get_daily_summary(self, stock_code: str, date_str: str) -> Dict:
        """获取单日数据摘要"""
        if stock_code not in self.historical_data:
            if not self.load_historical_minute_data(stock_code, date_str):
                return {}
        
        bars = self.historical_data[stock_code]
        if not bars:
            return {}
        
        df = self.get_historical_data_df(stock_code, len(bars))
        
        summary = {
            'date': date_str,
            'stock_code': stock_code,
            'total_bars': len(bars),
            'start_time': bars[0].datetime.strftime('%H:%M'),
            'end_time': bars[-1].datetime.strftime('%H:%M'),
            'open_price': bars[0].open,
            'close_price': bars[-1].close,
            'high_price': df['high'].max(),
            'low_price': df['low'].min(),
            'total_volume': df['volume'].sum(),
            'total_amount': df['amount'].sum(),
            'avg_volume': df['volume'].mean(),
            'price_change': bars[-1].close - bars[0].open,
            'price_change_percent': (bars[-1].close - bars[0].open) / bars[0].open * 100
        }
        
        return summary

    def update_with_tick_data(self, tick_data: TickData) -> bool:
        """
        使用TickData更新分钟K线数据
        
        Args:
            tick_data: TickData对象
        """
        try:
            stock_code = tick_data.code
            current_time = tick_data.timestamp
            if not self._is_trading_hours(current_time):
                return False
            
            current_minute = current_time.replace(second=0, microsecond=0)
            # 初始化股票数据
            if stock_code not in self.historical_data:
                self.historical_data[stock_code] = []

            if stock_code not in self.last_minute:
                self.last_minute[stock_code] = current_minute
            
            # 如果是新的一分钟，完成上一分钟的K线
            if current_minute != self.last_minute[stock_code]:
                self._finalize_minute_bar(stock_code)
            
            # 更新当前分钟的K线数据
            self._update_current_minute(stock_code, tick_data, current_minute)
            return True
            
        except Exception as e:
            logger.error(f"更新分钟数据错误: {e}")
            return False
    
    def _update_current_minute(self, stock_code: str, tick: TickData, current_minute: datetime):
        """更新当前分钟的K线数据"""
        if stock_code not in self.current_minute_bars:
            # 创建新的分钟K线，K线的第一笔不做成交量和成交额累加
            self.current_minute_bars[stock_code] = MinuteBarData(
                datetime=current_minute,
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
                volume=tick.volume,
                amount=tick.amount,
                bid_price=tick.bid_price,
                ask_price=tick.ask_price,
                bid_volume=tick.bid_volume,
                ask_volume=tick.ask_volume
            )
            return 
        
        current_bar = self.current_minute_bars[stock_code]
        
        # 更新价格极值
        current_bar.high = max(current_bar.high, tick.price)
        current_bar.low = min(current_bar.low, tick.price)
        current_bar.close = tick.price
        current_bar.volume = tick.volume
        current_bar.amount = tick.amount
        # 更新买卖盘信息（使用最新数据）
        current_bar.bid_price = tick.bid_price
        current_bar.ask_price = tick.ask_price
        current_bar.bid_volume = tick.bid_volume
        current_bar.ask_volume = tick.ask_volume
    
    def _finalize_minute_bar(self, stock_code: str):
        """完成当前分钟的K线并添加到历史数据"""
        if stock_code in self.current_minute_bars:
            bar_data = self.current_minute_bars[stock_code]
            self.historical_data[stock_code].append(bar_data)
            # 保留最近60根分钟K线
            max_bars = 60  
            if len(self.historical_data[stock_code]) > max_bars:
                self.historical_data[stock_code] = self.historical_data[stock_code][-max_bars:]
            # 重置当前分钟数据
            del self.current_minute_bars[stock_code]
    
    def get_historical_data_df(self, stock_code: str, lookback: int = 60) -> pd.DataFrame:
        """获取历史分钟K线数据（DataFrame格式）"""
        if stock_code not in self.historical_data or not self.historical_data[stock_code]:
            return pd.DataFrame()
        
        bars = self.historical_data[stock_code][-lookback:]
        
        data = {
            'datetime': [bar.datetime for bar in bars],
            'open': [bar.open for bar in bars],
            'high': [bar.high for bar in bars],
            'low': [bar.low for bar in bars],
            'close': [bar.close for bar in bars],
            'volume': [bar.volume for bar in bars],
            'amount': [bar.amount for bar in bars],
            'bid_price': [bar.bid_price for bar in bars],
            'ask_price': [bar.ask_price for bar in bars],
            'bid_volume': [bar.bid_volume for bar in bars],
            'ask_volume': [bar.ask_volume for bar in bars]
        }
        
        return pd.DataFrame(data)
    
    def get_latest_minute_bar(self, stock_code: str) -> Optional[MinuteBarData]:
        """获取最新的完整分钟K线"""
        if (stock_code in self.historical_data and 
            self.historical_data[stock_code]):
            return self.historical_data[stock_code][-1]
        return None
    
    def get_current_minute_bar(self, stock_code: str) -> Optional[MinuteBarData]:
        """获取当前正在构建的分钟K线"""
        return self.current_minute_bars.get(stock_code)
    
    def get_technical_indicators(self, stock_code: str, lookback: int = 60) -> Dict:
        """计算技术指标"""
        df = self.get_historical_data_df(stock_code, lookback)
        if len(df) < 5:
            return {}
        
        closes = df['close'].values
        volumes = df['volume'].values
        
        indicators = {}
        
        # 计算MACD
        if len(closes) >= 26:
            macd, macd_signal, macd_hist = talib.MACD(closes)
            indicators['macd'] = macd[-1] if not np.isnan(macd[-1]) else 0
            indicators['macd_signal'] = macd_signal[-1] if not np.isnan(macd_signal[-1]) else 0
            indicators['macd_hist'] = macd_hist[-1] if not np.isnan(macd_hist[-1]) else 0
        
        # 计算RSI
        if len(closes) >= 14:
            rsi = talib.RSI(closes)
            indicators['rsi'] = rsi[-1] if not np.isnan(rsi[-1]) else 50
        
        # 计算移动平均线
        if len(closes) >= 5:
            indicators['ma5'] = talib.SMA(closes, timeperiod=5)[-1]
            if len(closes) >= 10:
                indicators['ma10'] = talib.SMA(closes, timeperiod=10)[-1]
        
        # 计算成交量均线
        if len(volumes) >= 5:
            indicators['volume_ma5'] = talib.SMA(volumes, timeperiod=5)[-1]
        
        return indicators