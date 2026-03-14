from datetime import datetime, time
from typing import List, Dict, Any
import pandas as pd

def format_time(t: datetime) -> str:
    """格式化时间"""
    return t.strftime('%H:%M:%S')

def format_price(price: float) -> str:
    """格式化价格"""
    return f"{price:.2f}"

def format_percentage(value: float) -> str:
    """格式化百分比"""
    return f"{value:.2%}"

def calculate_portfolio_stats(trades: List[Dict]) -> Dict[str, float]:
    """计算投资组合统计"""
    if not trades:
        return {}
    
    df = pd.DataFrame(trades)
    winning_trades = df[df['pnl'] > 0]
    
    return {
        'total_trades': len(df),
        'winning_trades': len(winning_trades),
        'win_rate': len(winning_trades) / len(df),
        'total_pnl': df['pnl'].sum(),
        'avg_trade_pnl': df['pnl'].mean(),
        'max_profit': df['pnl'].max(),
        'max_loss': df['pnl'].min(),
    }

def is_market_open() -> bool:
    """检查市场是否开盘"""
    now = datetime.now()
    
    # 检查周末
    if now.weekday() >= 5:  # 5=周六, 6=周日
        return False
    
    # 检查交易时间 (简化版)
    current_time = now.time()
    morning_start = time(9, 30)
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)
    
    return ((morning_start <= current_time <= morning_end) or 
            (afternoon_start <= current_time <= afternoon_end))

def format_stock_code_sx000000(code):
    if '.' in code:
        stock_num, market = code.split('.')
        return market.lower() + stock_num
    else:
        # 如果没有后缀，根据股票代码自动判断市场
        if code.startswith(('600', '601', '603', '605', '688')):
            return 'sh' + code
        elif code.startswith(('000', '001', '002', '003', '300')):
            return 'sz' + code
        elif code.startswith(('400', '420', '430', '830', '831')):
            return 'bj' + code
        else:
            return 'sh' + code  # 默认上海市场