#!/usr/bin/env python3
"""
真实数据T0交易系统主程序
"""

import time
import sys
import os
from datetime import datetime, time
from typing import List

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.trading_config import TradingConfig
from core.real_trading_engine import RealTradingEngine
from utils.logger import get_main_logger, setup_module_loggers
from utils.helpers import format_time, format_price, format_percentage
from hq.tick_data_manager import TickDataManager
from hq.tick_data import TickData
from utils.position_converter import PositionConverter
from core.position_manager import PositionManager

logger = get_main_logger('real_trading_main')

class RealTradingSystem:
    """真实数据交易系统"""
    
    def __init__(self, config_file: str = None):
        try:
            self.config = TradingConfig(config_file)
            data_dir = self.config.tick_data_dir
            self.last_show_time = None
            logger.info(f"使用逐笔数据目录: {data_dir}")
            if not os.path.exists(data_dir):
                logger.error(f"数据目录不存在: {data_dir}")
                logger.error(f"请确保您的逐笔数据文件放在 {data_dir} 目录下")
                raise FileNotFoundError(f"数据目录不存在: {data_dir}")
            self.engine = RealTradingEngine(self.config, data_dir)
            self.tick_data_manager = TickDataManager(self.config)
            logger.info("真实数据交易系统初始化成功")
        except Exception as e:
            logger.error(f"系统初始化失败: {str(e)}")
            raise
    
    def setup_monitor_stocks(self, stock_codes: List[str]):
        """设置监控股票"""
        try:
            self.engine.set_monitor_stocks(stock_codes)
            logger.info(f"设置监控股票: {stock_codes}")
        except Exception as e:
            logger.error(f"设置监控股票失败: {str(e)}")
            raise
    
    def _is_trading_hours(self, timestamp: datetime) -> bool:
        """判断给定时间是否在交易时间段内"""
        tick_time = timestamp.time()
        
        # 精确的交易时间定义
        morning_start = time(9, 30, 0)
        morning_end = time(11, 30, 0)
        afternoon_start = time(13, 0, 0) 
        afternoon_end = time(15, 00, 0)
        
        # 严格的时间判断
        is_morning_trading = morning_start <= tick_time <= morning_end
        is_afternoon_trading = afternoon_start <= tick_time <= afternoon_end
        
        return is_morning_trading or is_afternoon_trading
    
    def start_t0_trading(self):
        """开始回放交易"""
        
        # self.engine.debug_position_files()
        self.setup_monitor_stocks(self.config.monitor_stocks)
        
        # 从配置中获取置信度阈值
        confidence_threshold = self.config.signal_confidence_threshold
        
        # 设置回放回调
        def tick_data_callback(tick_data: TickData):
            """逐笔数据回调处理"""
            # 仅在交易时段处理数据
            if not self._is_trading_hours(tick_data.timestamp):
                logger.debug(f"跳过非交易时段tick数据: {tick_data.code} 时间: {tick_data.timestamp}")
                return
            
            # 直接检查价格有效性
            if tick_data.price <= 0:
                logger.debug(f"跳过无效tick数据: {tick_data.code} 价格: {tick_data.price}")
                return
                
            if tick_data.volume <= 0:
                logger.debug(f"跳过无效tick数据: {tick_data.code} 成交量: {tick_data.volume}")
                return

            # 检查股票代码是否在监控列表中
            if tick_data.code not in self.config.monitor_stocks:
                return

            # 更新交易引擎
            self.engine.update_with_tick_data(tick_data)
            
            # 分析并生成交易信号
            recommendation = self.engine.analyze_with_tick_data(tick_data)
            
            # 再次检查推荐数据的有效性
            if (recommendation['current_price'] <= 0 or 
                recommendation['volume_ratio'] <= 0 or
                recommendation['confidence'] < 0):
                logger.debug(f"跳过无效推荐数据: {recommendation}")
                return
            
            # 显示信号
            self._show_tick_signal(tick_data, recommendation)
            
            # 自动执行高置信度信号（使用配置的阈值）T0策略无条件执行
            if (recommendation['signal'] != 'HOLD' and (
                    self.config.strategy_name == 'T0Reversion' or
                    recommendation['confidence'] >= confidence_threshold)):
                logger.info(
                    f"执行自动交易: {recommendation['stock_code']} "
                    f"{recommendation['signal']} 置信度: {recommendation['confidence']:.3f} "
                    f"(阈值: {confidence_threshold})"
                )
            elif recommendation['signal'] != 'HOLD':
                logger.info(
                    f"信号置信度不足: {recommendation['stock_code']} "
                    f"{recommendation['signal']} 置信度: {recommendation['confidence']:.3f} "
                    f"(阈值: {confidence_threshold})"
                )
        
        self.tick_data_manager.set_callback(tick_data_callback)
        
        logger.info(
            f"开始交易: {self.config.monitor_stocks} 策略 {self.config.strategy_name} "
            f"置信度阈值: {confidence_threshold} "
            f"数据源: {self.config.tick_data_source} "
        )
        
        self.tick_data_manager.start()
    
    def _show_tick_signal(self, tick_data, recommendation):
        """显示tick信号"""
        try:
            if recommendation['signal'] != 'HOLD':
                confidence = recommendation.get('confidence', 0)
                confidence_level = "高" if confidence > self.config.signal_confidence_threshold else "中"
                
                logger.info(f"\n🎯 交易信号 - {tick_data.timestamp.strftime('%H:%M:%S')}")
                logger.info(f"  股票: {tick_data.name}({tick_data.code})")
                logger.info(f"  价格: {format_price(tick_data.price)}")
                logger.info(f"  涨跌幅: {tick_data.change_percent:+.2f}%")
                logger.info(f"  信号: {recommendation['signal']}")
                logger.info(f"  建议价格: {format_price(recommendation['price'])}")
                logger.info(f"  建议数量: {recommendation['quantity']}")
                logger.info(f"  置信度: {confidence} ({confidence_level})")
            
            # 每10s显示一次摘要并且同一个一个时间戳显示一次
            if self.last_show_time is None or (tick_data.timestamp - self.last_show_time).total_seconds() >= 10:
                self.last_show_time = tick_data.timestamp
                self._show_trading_summary(tick_data.timestamp)
                
        except Exception as e:
            logger.error(f"显示信号失败: {str(e)}")
    
    # 使用行情数据的时间戳显示交易摘要，避免行情重放时钟不同步问题
    def _show_trading_summary(self, timestamp):
        """显示交易摘要 - 避免重复输出"""
        try:
            summary = self.engine.get_trading_summary()
            
            # 构建完整的摘要信息，一次性输出
            summary_lines = [
                f"\n{'='*60}",
                f"交易摘要 - {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                f"{'='*60}",
                f"策略: {summary['strategy']}",
                f"初始资金: {format_price(summary['initial_capital'])}",
                f"监控股票: {summary['monitor_stocks']}",
                f"持仓数量: {summary['total_positions']}",
                f"持仓市值: {format_price(summary['total_value'])}",
                f"持仓盈亏: {format_price(summary['total_pnl'])}",
                f"当日持仓盈亏: {format_price(summary['daily_position_pnl'])}",
                f"当日清仓盈亏: {format_price(summary['clear_trade_pnl'])}",
                f"当日交易盈亏: {format_price(summary['daily_trade_pnl'])}",
                f"当日交易: {summary['daily_trades']} 笔",
                f"交易时间: {'是' if summary['is_trading_hours'] else '否'}"
            ]
            
            if summary['positions']:
                summary_lines.append(f"\n当前持仓:")
                for pos in summary['positions']:
                    pnl_sign = '+' if pos['pnl'] > 0 else ''
                    today_pnl = pos['pnl'] - pos['initial_pnl']
                    today_pnl_sign = '+' if today_pnl > 0 else ''
                    today_pnl_rate = today_pnl / (pos['quantity'] * pos['entry_price'])
                    position_str = (f"  {pos['stock_code']}({pos['stock_name']}): {pos['quantity']}股 | "
                                f"成本:{format_price(pos['entry_price'])} | "
                                f"现价:{format_price(pos['current_price'])} | "
                                f"盈亏:{pnl_sign}{format_price(pos['pnl'])} "
                                f"({pnl_sign}{format_percentage(pos['pnl_rate'])}) | "
                                f"当日盈亏:{today_pnl_sign}{format_price(today_pnl)} "
                                f"({today_pnl_sign}{format_percentage(today_pnl_rate)}) | "
                                f"交易盈亏:{format_price(pos['daily_trade_pnl'])} | "
                                f"敞口:{format_price(pos['daily_openset'])}")
                    summary_lines.append(position_str)
            
            # 一次性输出所有信息
            full_summary = "\n".join(summary_lines)
            logger.info(full_summary)
            
        except Exception as e:
            logger.error(f"显示交易摘要失败: {str(e)}")

def archive_current_positions(config_file):
    """需要重新加载日初持仓"""
    load_initial = input("是否重新加载日初持仓数据? (y/n): ").lower()
    if load_initial == 'y':
        config = TradingConfig(config_file)
        postion_manager = PositionManager(config, False)
        postion_manager.archive_current_positions()
        output_file = postion_manager.get_init_positions_file()
        if os.path.exists(output_file):
            os.remove(output_file)
        try :
            PositionConverter.convert_from_tonghuashun(config.initial_position_file, output_file)
        except Exception as e:
            logger.error(f"期初持仓文件转换失败: {str(e)}")
            raise
        logger.info(f"期初持仓文件转换完成: {output_file}")
        if config.tick_data_source == 'realtime':
            trade_date = datetime.now().strftime('%Y%m%d')
        else:
            trade_date = config.replay_date
        deal_file = os.path.join(config.deal_data_dir , f"deals_{trade_date}.json")
        if os.path.exists(deal_file):
            os.remove(deal_file)
            logger.info(f"清理当日成交: {deal_file}")


def main():
    """主函数"""
    # setup_module_loggers()
    config_file = 'config/default_config.yaml'
    try:
        # 归档当前持仓
        archive_current_positions(config_file)

        # 创建交易系统
        trading_system = RealTradingSystem(config_file=config_file)
        
        # 启动交互模式
        trading_system.start_t0_trading()
        
    except Exception as e:
        logger.error(f"系统启动失败: {str(e)}")

if __name__ == "__main__":
    main()