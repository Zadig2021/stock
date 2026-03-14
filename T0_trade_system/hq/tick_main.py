import logging
import time
import signal
import sys
from datetime import datetime
from tick_collector import TickDataCollector

class TickDataSystem:
    """逐笔数据系统主控制器"""
    
    def __init__(self):
        self.collector = TickDataCollector()
        self.setup_logging()
        self.setup_signal_handlers()
    
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('tick_system.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logging.info("接收到停止信号，正在关闭系统...")
            self.stop_system()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def start_collection(self, stock_list: dict):
        """开始数据采集"""
        for code, name in stock_list.items():
            self.collector.add_stock(code, name)
        
        self.collector.start_collection()
    
    def stop_collection(self):
        """停止数据采集"""
        self.collector.stop_collection()
    
    
    def stop_system(self):
        """停止系统"""
        self.stop_collection()

def main():
    """主函数"""
    system = TickDataSystem()
    
    # 示例股票列表
    stock_list = {
        '002466',
        '601012', 
        '300454'
    }
    
    try:
        # 开始采集数据
        logging.info("启动逐笔数据采集系统")
        system.start_collection(stock_list)
        
        # 保持运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logging.info("用户中断，正在停止系统...")
    finally:
        system.stop_system()

if __name__ == "__main__":
    main()