#!/usr/bin/env python3
"""
持仓数据转换工具
将同花顺导出的持仓数据转换为系统格式
"""

import sys
import os
import argparse
from datetime import datetime
# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.position_converter import PositionConverter

# 设置日志
from utils.logger import get_tools_logger
logger = get_tools_logger('convert_position')

def main():
    parser = argparse.ArgumentParser(description='同花顺持仓数据转换工具')
    parser.add_argument('input_file', help='同花顺导出的Excel或CSV文件路径')
    parser.add_argument('-o', '--output', help='输出JSON文件路径', default=None)
    parser.add_argument('-c', '--config', help='合并到现有配置文件', default=None)
    parser.add_argument('--analyze', action='store_true', help='分析持仓数据')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_file):
        print(f"错误: 输入文件不存在: {args.input_file}")
        return
    
    try:
        # 转换持仓数据
        print("正在转换持仓数据...")
        positions = PositionConverter.convert_from_tonghuashun(args.input_file, args.output)
        
        if not positions:
            print("没有找到有效的持仓数据")
            return
        
        print(f"成功转换 {len(positions)} 条持仓记录")
        
        # 分析持仓数据
        if args.analyze:
            analysis = PositionConverter.analyze_positions(positions)
            print("\n" + "="*50)
            print("持仓分析报告")
            print("="*50)
            print(f"总持仓数: {analysis['total_positions']}")
            print(f"总市值: {analysis['total_market_value']:,.2f}")
            print(f"总盈亏: {analysis['total_pnl']:+,.2f} ({analysis['total_pnl_rate']:+.2%})")
            print(f"盈利持仓: {analysis['winning_count']}")
            print(f"亏损持仓: {analysis['losing_count']}")
            print(f"胜率: {analysis['win_rate']:.2%}")
            print(f"持仓集中度: {analysis['concentration_risk']:.2%}")
            
            if analysis['biggest_winner']:
                winner = analysis['biggest_winner']
                print(f"\n最大盈利: {winner['stock_code']} {winner['total_pnl']:+,.2f}")
            
            if analysis['biggest_loser']:
                loser = analysis['biggest_loser']
                print(f"最大亏损: {loser['stock_code']} {loser['total_pnl']:+,.2f}")
        
        # 合并到配置文件
        if args.config:
            print(f"\n正在合并到配置文件: {args.config}")
            system_config = PositionConverter.convert_to_system_config(positions, args.config)
            
            # 保存更新后的配置
            with open(args.config, 'w', encoding='utf-8') as f:
                import json
                json.dump(system_config, f, ensure_ascii=False, indent=2)
            
            print(f"配置已更新: {args.config}")
        
        # 显示转换后的持仓
        print(f"\n转换后的持仓列表:")
        for position in positions:
            pnl_sign = '+' if position['total_pnl'] > 0 else ''
            print(f"  {position['stock_code']} {position['stock_name']}: "
                  f"{position['quantity']}股 @ {position['cost_price']:.2f} | "
                  f"盈亏: {pnl_sign}{position['total_pnl']:+.2f} "
                  f"({pnl_sign}{position['pnl_rate']:+.2%})")
        
        if args.output:
            print(f"\n持仓数据已保存到: {args.output}")
        else:
            print(f"\n使用 --output 参数指定输出文件路径来保存数据")
            
    except Exception as e:
        logger.error(f"转换失败: {str(e)}")
        print(f"错误: {str(e)}")

if __name__ == "__main__":
    main()