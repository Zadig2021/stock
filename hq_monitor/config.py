import os
import threading
import yaml
import hashlib
import logging
import time
from typing import Dict

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = 'config.yaml'):
        self.config_path = config_path
        self.config_hash = None
        self.last_modified = 0
        self.config = {}
        self.config_listeners = []
        
    def add_listener(self, listener):
        """添加配置变更监听器"""
        self.config_listeners.append(listener)
    
    def load_config(self, initial_load: bool = False) -> dict:
        """加载配置文件"""
        try:
            current_mtime = os.path.getmtime(self.config_path)
            with open(self.config_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 如果是初始加载，直接加载配置
            if initial_load:
                self.config = yaml.safe_load(content)
                return self.config

            current_hash = hashlib.md5(content.encode()).hexdigest()
            
            if current_hash != self.config_hash:
                logging.info("配置文件已重新加载")
                self.config_hash = current_hash
                self.config = yaml.safe_load(content)
                self.last_modified = current_mtime
                for listener in self.config_listeners:
                    listener.on_config_updated(self.config)
                    
            return self.config
            
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            return self.config
    
    def get_config_snapshot(self) -> dict:
        """获取配置快照"""
        return self.config.copy()
    
    def start_monitoring(self, interval: int = 5):
        """启动配置监控"""
        def monitor_loop():
            while True:
                self.load_config()
                time.sleep(interval)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        logging.info(f"配置监控已启动，检查间隔: {interval}秒")
