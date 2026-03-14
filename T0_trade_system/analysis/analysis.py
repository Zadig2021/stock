import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import matplotlib.pyplot as plt

@dataclass
class PositionSnapshot:
    """持仓快照"""
    timestamp: datetime
    stock_code: str
    stock_name: str
    quantity: int
    cost_price: float
    current_price: float
    total_pnl: float
    pnl_percent: float
    daily_pnl: float

@dataclass
class DailyAnalysis:
    """每日分析结果"""
    date: str
    stock_code: str
    stock_name: str
    quantity: int
    best_price: float
    worst_price: float
    best_time: str
    worst_time: str
    open_price: float
    close_price: float
    max_daily_pnl: float
    min_daily_pnl: float
    actual_daily_pnl: float
    strategy_efficiency: float  # 策略效率 0-100%
    missed_opportunity: float   # 错失的收益

class TradingStrategyAnalyzer:
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.position_snapshots = defaultdict(list)
        self.daily_summaries = []
    
    def parse_trading_log(self):
        """解析交易日志文件 - 调试版本"""
        # 更宽松的持仓行匹配模式
        position_pattern = re.compile(
            r'(\d{6})\.(S[HZ])\(([^)]+)\):\s*(\d+)股\s*\|\s*成本:([\d.]+)\s*\|\s*现价:([\d.]+)\s*\|\s*盈亏:([-\d.]+)\s*\(([-\d.]+)%\)\s*\|\s*当日盈亏:([-\d.]+)'
        )
        
        current_timestamp = None
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # 检查是否是时间戳行
                timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if timestamp_match:
                    current_timestamp = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                    print(f"找到时间戳: {current_timestamp}")
                
                # 检查是否是持仓行（更宽松的条件）
                if line and any(x in line for x in ['SH(', 'SZ(', '成本:', '现价:']):
                    print(f"检查行: {line}")
                    
                    # 先尝试精确匹配
                    position_match = position_pattern.search(line)
                    if position_match:
                        code, market, name, quantity, cost_price, current_price, total_pnl, pnl_percent, daily_pnl = position_match.groups()
                        print(f"精确匹配成功: {code} - {name}")
                    else:
                        # 如果精确匹配失败，尝试分段匹配
                        print("精确匹配失败，尝试分段匹配...")
                        # 匹配股票代码和名称
                        stock_match = re.search(r'(\d{6})\.(S[HZ])\(([^)]+)\)', line)
                        if stock_match:
                            code, market, name = stock_match.groups()
                            print(f"股票信息: {code}, {market}, {name}")
                            
                            # 匹配数量
                            quantity_match = re.search(r'(\d+)股', line)
                            quantity = quantity_match.group(1) if quantity_match else "0"
                            
                            # 匹配成本价
                            cost_match = re.search(r'成本:([\d.]+)', line)
                            cost_price = cost_match.group(1) if cost_match else "0"
                            
                            # 匹配现价
                            price_match = re.search(r'现价:([\d.]+)', line)
                            current_price = price_match.group(1) if price_match else "0"
                            
                            # 修复正则表达式，确保能匹配正负号
                            # 匹配总盈亏 - 确保能匹配正负号
                            total_pnl_match = re.search(r'盈亏:([+-]?[\d.]+)', line)
                            total_pnl = total_pnl_match.group(1) if total_pnl_match else "0"

                            # 匹配盈亏百分比 - 确保能匹配正负号  
                            percent_match = re.search(r'\(([+-]?[\d.]+)%\)', line)
                            pnl_percent = percent_match.group(1) if percent_match else "0"

                            # 匹配当日盈亏 - 确保能匹配正负号
                            daily_match = re.search(r'当日盈亏:([+-]?[\d.]+)', line)
                            daily_pnl = daily_match.group(1) if daily_match else "0"
                            
                            print(f"分段匹配结果: {code}, {name}, {quantity}, {current_price}, {daily_pnl}")
                            
                            if stock_match:
                                position_match = True
                    
                    if position_match:
                        snapshot = PositionSnapshot(
                            timestamp=current_timestamp,
                            stock_code=code,
                            stock_name=name,
                            quantity=int(quantity),
                            cost_price=float(cost_price),
                            current_price=float(current_price),
                            total_pnl=float(total_pnl),
                            pnl_percent=float(pnl_percent),
                            daily_pnl=float(daily_pnl)
                        )
                        
                        self.position_snapshots[code].append(snapshot)
                        print(f"✅ 成功解析持仓: {name}({code}) - 价格: {current_price}, 当日盈亏: {daily_pnl}")
                
                i += 1
                
            print(f"\n解析完成，共处理 {len(self.position_snapshots)} 只股票的数据")
            for code, snapshots in self.position_snapshots.items():
                print(f"  {code}: {len(snapshots)} 个快照")
                
        except FileNotFoundError:
            print(f"日志文件 {self.log_file_path} 未找到")
        except Exception as e:
            print(f"解析日志文件时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def debug_specific_line(self, test_line: str):
        """调试特定行的匹配问题"""
        print(f"\n调试行: {test_line}")
        
        position_pattern = re.compile(
            r'(\d{6})\.(S[HZ])\(([^)]+)\):\s*(\d+)股\s*\|\s*成本:([\d.]+)\s*\|\s*现价:([\d.]+)\s*\|\s*盈亏:([-\d.]+)\s*\(([-\d.]+)%\)\s*\|\s*当日盈亏:([-\d.]+)'
        )
        
        match = position_pattern.search(test_line)
        if match:
            print("✅ 精确匹配成功!")
            print(f"匹配结果: {match.groups()}")
        else:
            print("❌ 精确匹配失败")
            
            # 分段调试
            patterns = [
                (r'(\d{6})\.(S[HZ])\(([^)]+)\)', "股票代码和名称"),
                (r'(\d+)股', "股数"),
                (r'成本:([\d.]+)', "成本价"),
                (r'现价:([\d.]+)', "现价"),
                (r'盈亏:([-\d.]+)', "总盈亏"),
                (r'\(([-\d.]+)%\)', "盈亏百分比"),
                (r'当日盈亏:([-\d.]+)', "当日盈亏")
            ]
            
            for pattern, desc in patterns:
                m = re.search(pattern, test_line)
                if m:
                    print(f"✅ {desc}: {m.groups()}")
                else:
                    print(f"❌ {desc}: 匹配失败")
    
    def analyze_stock_daily_performance(self, stock_code: str, target_date: str = None) -> Optional[DailyAnalysis]:
        """分析单只股票当日表现"""
        if stock_code not in self.position_snapshots:
            return None
        
        # 获取该股票的所有快照
        snapshots = self.position_snapshots[stock_code]
        
        if not target_date:
            target_date = datetime.now().strftime('%Y-%m-%d')
        else:
            # 转换日期格式
            target_date = datetime.strptime(target_date, '%Y%m%d').strftime('%Y-%m-%d')
        
        # 过滤指定日期的数据
        day_snapshots = [s for s in snapshots if s.timestamp.strftime('%Y-%m-%d') == target_date]
        
        if not day_snapshots:
            return None
        
        # 按时间排序
        day_snapshots.sort(key=lambda x: x.timestamp)
        
        # 获取基础信息
        quantity = day_snapshots[0].quantity
        stock_name = day_snapshots[0].stock_name
        
        # 提取价格和盈亏数据
        prices = [s.current_price for s in day_snapshots]
        daily_pnls = [s.daily_pnl for s in day_snapshots]
        times = [s.timestamp for s in day_snapshots]
        quantities = [s.quantity for s in day_snapshots]  # 获取持仓数量变化
        
        # 通过持仓数量变化判断是否有交易
        has_trading = len(set(quantities)) > 1

        # 找出最佳和最差价格点
        best_price = max(prices)
        worst_price = min(prices)
        best_time = times[prices.index(best_price)].strftime('%H:%M:%S')
        worst_time = times[prices.index(worst_price)].strftime('%H:%M:%S')
        
        # 开盘价和收盘价（第一个和最后一个快照）
        open_price = prices[0]
        close_price = prices[-1]
        
        # 计算各种盈亏情况
        max_daily_pnl = max(daily_pnls)
        min_daily_pnl = min(daily_pnls)
        actual_daily_pnl = daily_pnls[-1]  # 最终的当日盈亏
        # print(daily_pnls)
        # 计算策略效率
        strategy_efficiency = self.calculate_strategy_efficiency(
            prices, daily_pnls, quantity, actual_daily_pnl, max_daily_pnl, has_trading
        )
        
        # 计算错失机会（基于价格波动）
        price_range_profit = (best_price - worst_price) * quantity
        missed_opportunity = max(0, price_range_profit - actual_daily_pnl)
        
        return DailyAnalysis(
            date=target_date,
            stock_code=stock_code,
            stock_name=stock_name,
            quantity=quantity,
            best_price=best_price,
            worst_price=worst_price,
            best_time=best_time,
            worst_time=worst_time,
            open_price=open_price,
            close_price=close_price,
            max_daily_pnl=max_daily_pnl,
            min_daily_pnl=min_daily_pnl,
            actual_daily_pnl=actual_daily_pnl,
            strategy_efficiency=strategy_efficiency,
            missed_opportunity=missed_opportunity
        )
    
    def calculate_strategy_efficiency(self, prices: List[float], daily_pnls: List[float], 
                                   quantity: int, actual_pnl: float, max_pnl: float, has_trading: bool) -> float:
        """计算策略效率 - 修复极端情况"""
        if len(prices) < 2:
            return 0
        
        # 价格波动范围
        price_range = max(prices) - min(prices)
        if price_range == 0:
            return 100 if actual_pnl >= 0 else 0
        
        # 理论最大收益
        theoretical_max = price_range * quantity
        
        # print(f"实际收益: {actual_pnl}, 理论最大收益: {theoretical_max}")
        
        # 处理极端大的理论收益情况
        if theoretical_max > 1000000:  # 如果理论收益超过100万
            # 使用相对基准的方法
            baseline_pnl = (prices[-1] - prices[0]) * quantity
            if theoretical_max - baseline_pnl > 0:
                efficiency = 50 + ((actual_pnl - baseline_pnl) / (theoretical_max - baseline_pnl)) * 50
            else:
                efficiency = 50 if actual_pnl >= baseline_pnl else 0
        elif theoretical_max > 0:
            # 正常情况
            efficiency_ratio = actual_pnl / theoretical_max
            
            # 分段处理，避免极端负值
            if efficiency_ratio >= 1.0:
                efficiency = 100
            elif efficiency_ratio >= 0:
                efficiency = efficiency_ratio * 100
            elif efficiency_ratio >= -1.0:
                efficiency = 50 + (efficiency_ratio * 50)  # 负收益但有限
            else:
                efficiency = 0  # 严重亏损
        else:
            efficiency = 100 if actual_pnl >= 0 else 0
        
        # 考虑交易时机把握
        timing_score = self.calculate_timing_score(prices, daily_pnls, has_trading)
        
        # print(f"效率得分: {efficiency:.2f}%, 时机得分: {timing_score:.2f}")
        final_score = (efficiency + timing_score) / 2
        
        return max(0, min(100, final_score))
    
    def calculate_timing_score(self, prices: List[float], daily_pnls: List[float], has_trading: bool) -> float:
        """计算时机把握分数 - 专门处理无交易情况"""
        if len(prices) < 3:
            return 50
        
        if not has_trading:
            return self.calculate_no_trading_timing_score(prices)
        else:
            return self.calculate_with_trading_timing_score(prices, daily_pnls)

    def calculate_no_trading_timing_score(self, prices: List[float]) -> float:
        """无交易时的时机把握评分 - 优化版本"""
        if len(prices) < 2:
            return 100
        
        # 计算价格波动率
        price_range = max(prices) - min(prices)
        if prices[0] == 0:
            return 100  # 避免除以零
            
        price_volatility = (price_range / prices[0]) * 100  # 百分比形式
        
        print(f"无交易价格波动率: {price_volatility:.2f}%")
        
        # 根据价格波动判断是否应该交易
        if price_volatility > 10:  # 波动很大但没交易，时机把握很差
            return 10
        elif price_volatility > 7:  # 波动很大但没交易，时机把握差
            return 30
        elif price_volatility > 5:  # 波动较大但没交易，时机把握一般
            return 50
        elif price_volatility > 3:  # 有一定波动，时机把握尚可
            return 70
        elif price_volatility > 1:  # 波动较小，不交易是合理的
            return 85
        else:  # 几乎没波动，不交易是正确的选择
            return 100

    def calculate_with_trading_timing_score(self, prices: List[float], daily_pnls: List[float]) -> float:
        """有交易时的时机把握评分"""
        try:
            price_changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            pnl_changes = [daily_pnls[i] - daily_pnls[i-1] for i in range(1, len(daily_pnls))]
            
            if len(price_changes) != len(pnl_changes):
                min_len = min(len(price_changes), len(pnl_changes))
                price_changes = price_changes[:min_len]
                pnl_changes = pnl_changes[:min_len]
            
            if price_changes and pnl_changes:
                correlation = np.corrcoef(price_changes, pnl_changes)[0, 1]
                if np.isnan(correlation):
                    correlation = 0
                
                # 相关性越高，说明时机把握越好
                timing_score = 50 + (correlation * 50)
                
                # 额外考虑：如果最终盈利且相关性高，给予加分
                if daily_pnls[-1] > 0 and correlation > 0.3:
                    timing_score = min(100, timing_score + 10)
                    
                return timing_score
        except:
            pass
        
        return 50
    
    def generate_daily_performance_report(self, target_date: str = None) -> pd.DataFrame:
        """生成每日表现报告"""
        self.parse_trading_log()
        
        if not target_date:
            target_date = datetime.now().strftime('%Y%m%d')
        
        results = []
        total_actual_pnl = 0
        total_max_pnl = 0
        total_missed = 0
        
        # 分析所有有数据的股票
        analyzed_stocks = set()
        for code in self.position_snapshots.keys():
            analysis = self.analyze_stock_daily_performance(code, target_date)
            if analysis:
                analyzed_stocks.add(code)
                results.append({
                    '股票代码': code,
                    '股票名称': analysis.stock_name,
                    '持仓数量': analysis.quantity,
                    '开盘价': analysis.open_price,
                    '收盘价': analysis.close_price,
                    '最高价': analysis.best_price,
                    '最低价': analysis.worst_price,
                    '最佳时机': f"{analysis.best_time}",
                    '最差时机': f"{analysis.worst_time}",
                    '实际盈亏': f"{analysis.actual_daily_pnl:+.2f}",
                    '最大盈亏': f"{analysis.max_daily_pnl:+.2f}",
                    '策略效率': f"{analysis.strategy_efficiency:.1f}%",
                    '错失收益': f"{analysis.missed_opportunity:.2f}",
                    '评级': self.get_rating(analysis.strategy_efficiency)
                })
                
                total_actual_pnl += analysis.actual_daily_pnl
                total_max_pnl += analysis.max_daily_pnl
                total_missed += analysis.missed_opportunity
        
        # 添加汇总行
        if results:
            overall_efficiency = (total_actual_pnl / total_max_pnl * 100) if total_max_pnl > 0 else 0
            results.append({
                '股票代码': '汇总',
                '股票名称': f'共{len(analyzed_stocks)}只股票',
                '持仓数量': '-',
                '开盘价': '-',
                '收盘价': '-',
                '最高价': '-',
                '最低价': '-',
                '最佳时机': '-',
                '最差时机': '-',
                '实际盈亏': f"{total_actual_pnl:+.2f}",
                '最大盈亏': f"{total_max_pnl:+.2f}",
                '策略效率': f"{overall_efficiency:.1f}%",
                '错失收益': f"{total_missed:.2f}",
                '评级': self.get_rating(overall_efficiency)
            })
        
        return pd.DataFrame(results)
    
    def get_rating(self, efficiency: float) -> str:
        """根据效率评分获取评级"""
        if efficiency >= 90:
            return "★★★★★"
        elif efficiency >= 80:
            return "★★★★"
        elif efficiency >= 70:
            return "★★★"
        elif efficiency >= 60:
            return "★★"
        else:
            return "★"
    
    def plot_stock_performance(self, stock_code: str, target_date: str = None):
        """绘制股票表现图表"""
        if stock_code not in self.position_snapshots:
            print(f"未找到股票 {stock_code} 的数据")
            return
        
        snapshots = self.position_snapshots[stock_code]
        
        if not target_date:
            target_date = datetime.now().strftime('%Y-%m-%d')
        else:
            target_date = datetime.strptime(target_date, '%Y%m%d').strftime('%Y-%m-%d')
        
        day_snapshots = [s for s in snapshots if s.timestamp.strftime('%Y-%m-%d') == target_date]
        
        if not day_snapshots:
            print(f"未找到 {stock_code} 在 {target_date} 的数据")
            return
        
        day_snapshots.sort(key=lambda x: x.timestamp)
        
        times = [s.timestamp for s in day_snapshots]
        prices = [s.current_price for s in day_snapshots]
        daily_pnls = [s.daily_pnl for s in day_snapshots]
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # 价格走势
        ax1.plot(times, prices, 'b-o', linewidth=2, markersize=4)
        ax1.set_title(f'{day_snapshots[0].stock_name}({stock_code}) 当日价格走势', fontsize=14)
        ax1.set_ylabel('价格', fontsize=12)
        ax1.grid(True, alpha=0.3)
        
        # 标记最高最低点
        max_idx = prices.index(max(prices))
        min_idx = prices.index(min(prices))
        ax1.plot(times[max_idx], prices[max_idx], 'r^', markersize=10, label=f'最高点: {prices[max_idx]:.2f}')
        ax1.plot(times[min_idx], prices[min_idx], 'gv', markersize=10, label=f'最低点: {prices[min_idx]:.2f}')
        ax1.legend()
        
        # 当日盈亏走势
        ax2.plot(times, daily_pnls, 'g-o', linewidth=2, markersize=4)
        ax2.set_title('当日盈亏变化', fontsize=14)
        ax2.set_xlabel('时间', fontsize=12)
        ax2.set_ylabel('当日盈亏', fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='r', linestyle='--', alpha=0.7)
        
        # 标记最终盈亏
        final_pnl = daily_pnls[-1]
        ax2.plot(times[-1], final_pnl, 'ro', markersize=8, label=f'最终盈亏: {final_pnl:+.2f}')
        ax2.legend()
        
        # plt.tight_layout()
        plt.show()

# 使用示例
if __name__ == "__main__":
    # 初始化分析器
    analyzer = TradingStrategyAnalyzer("./logs/t0_trading_main_20251125.log")
    
    # 生成分析报告
    print("=== 交易策略执行分析报告 ===")
    report = analyzer.generate_daily_performance_report()
    print(report.to_string(index=False))
    
    # 分析特定股票
    print("\n=== 个股详细分析 ===")
    stock_codes = ['601012', '600938', '600686', '300676', '300454', '300015', '002466', '002451']
    
    for code in stock_codes:
        analysis = analyzer.analyze_stock_daily_performance(code)
        if analysis:
            print(f"\n{analysis.stock_name}({code}):")
            print(f"  策略效率: {analysis.strategy_efficiency:.1f}%")
            print(f"  实际盈亏: {analysis.actual_daily_pnl:+.2f}")
            print(f"  最大盈亏: {analysis.max_daily_pnl:+.2f}")
            print(f"  最佳卖点: {analysis.best_time} @ {analysis.best_price:.2f}")
            print(f"  最佳买点: {analysis.worst_time} @ {analysis.worst_price:.2f}")
    
    # 绘制图表
    analyzer.plot_stock_performance('601012')