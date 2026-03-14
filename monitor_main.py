import os

from hq_monitor.monitor import StockMonitor, create_sample_config

if __name__ == "__main__":
    cfg = 'config/config.yaml'
    if not os.path.exists(cfg):
        create_sample_config(cfg)
    monitor = StockMonitor(cfg)
    monitor.start_monitoring()