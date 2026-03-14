import json
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

from utils.logger import get_core_logger
logger = get_core_logger('position_storage')

class PositionStorage:
    """持仓数据存储管理"""
    
    def __init__(self, config):
        self.config = config
        self.data_dir = config.position_data_dir
        self.ensure_data_dir()
    
    def ensure_data_dir(self):
        """确保数据目录存在"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            logger.info(f"创建持仓数据目录: {self.data_dir}")
    
    def get_init_positions_file(self) -> str:
        """获取期初持仓文件路径"""
        return os.path.join(self.data_dir, "positions_init.json")

    def get_current_positions_file(self) -> str:
        """获取当前持仓文件路径"""
        return os.path.join(self.data_dir, "positions_current.json")
    
    def get_history_positions_file(self, date_str: str = None) -> str:
        """获取历史持仓文件路径"""
        if date_str is None:
            date_str = date.today().strftime('%Y%m%d')
        return os.path.join(self.data_dir, f"positions_history_{date_str}.json")
    
    def save_current_positions(self, positions_data: Dict) -> bool:
        """保存当前持仓"""
        try:
            filename = self.get_current_positions_file()
            
            # 添加元数据
            data_with_meta = {
                'metadata': {
                    'save_time': datetime.now().isoformat(),
                    'strategy': self.config.strategy_name,
                    'initial_capital': self.config.initial_capital,
                    'version': '1.0'
                },
                'data': positions_data
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data_with_meta, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"当前持仓已保存: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"保存当前持仓失败: {str(e)}")
            return False
    
    def load_current_positions(self) -> Optional[Dict]:
        """加载当前持仓"""
        try:
            filename = self.get_current_positions_file()
        
            if not os.path.exists(filename):
                return None
            
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"当前持仓已加载: {filename}")
            return data.get('data', {})
            
        except Exception as e:
            logger.error(f"加载当前持仓失败: {str(e)}")
            return None
    
    def archive_current_positions(self) -> bool:
        """归档当前持仓到历史"""
        try:
            current_data = self.load_current_positions()
            if not current_data:
                logger.warning("没有当前持仓数据可归档")
                return False
            
            # 保存到历史文件
            history_file = self.get_history_positions_file()
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=2)
            
            # 清空当前持仓文件
            os.remove(self.get_current_positions_file())
            
            logger.info(f"持仓已归档到: {history_file}")
            return True
            
        except Exception as e:
            logger.error(f"归档持仓失败: {str(e)}")
            return False
    
    def get_position_history(self, days: int = 7) -> List[Dict]:
        """获取持仓历史"""
        history_data = []
        for i in range(days):
            date_str = (date.today() - timedelta(days=i)).strftime('%Y%m%d')
            history_file = self.get_history_positions_file(date_str)
            
            if os.path.exists(history_file):
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    history_data.append({
                        'date': date_str,
                        'data': data
                    })
                except Exception as e:
                    logger.warning(f"加载历史持仓文件失败 {history_file}: {e}")
        
        return history_data
    
    def get_all_history_dates(self) -> List[str]:
        """获取所有有历史持仓记录的日期"""
        history_dates = []
        for filename in os.listdir(self.data_dir):
            if filename.startswith("positions_history_") and filename.endswith(".json"):
                # 提取日期部分: positions_history_20231201.json -> 20231201
                date_str = filename.replace("positions_history_", "").replace(".json", "")
                history_dates.append(date_str)
        
        return sorted(history_dates, reverse=True)
    
    def load_history_positions_by_date(self, date_str: str) -> Optional[Dict]:
        """按日期加载特定的历史持仓"""
        try:
            history_file = self.get_history_positions_file(date_str)
            
            if not os.path.exists(history_file):
                logger.warning(f"历史持仓文件不存在: {history_file}")
                return None
            
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"历史持仓已加载: {history_file}")
            return data
            
        except Exception as e:
            logger.error(f"加载历史持仓失败: {str(e)}")
            return None

    def load_initial_positions(self) -> List[Dict]:
        """加载期初持仓 - 简化版本"""
        try:
            filename = self.get_init_positions_file()
            if not os.path.exists(filename):
                return []
            
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取持仓列表
            if 'initial_positions' in data:
                raw_positions = data['initial_positions']
            else:
                raw_positions = data
            
            # 简单转换格式
            converted_positions = []
            for pos in raw_positions:
                try:
                    stock_code = pos['stock_code']
                    # 格式化股票代码
                    if not stock_code.endswith(('.SH', '.SZ')):
                        if pos.get('exchange') == 'SH' or stock_code.startswith('6'):
                            stock_code = f"{stock_code}.SH"
                        else:
                            stock_code = f"{stock_code}.SZ"
                    
                    converted_positions.append({
                        'stock_code': stock_code,
                        'stock_name': pos['stock_name'],
                        'quantity': pos['quantity'],
                        'cost_price': pos['cost_price'],
                        'current_price': pos.get('current_price', pos['cost_price']),
                        'total_pnl': pos.get('total_pnl')
                    })
                except Exception as e:
                    logger.error(f"转换期初持仓失败: {pos}, 错误: {e}")
                    continue
            
            logger.info(f"加载期初持仓: {len(converted_positions)} 个持仓")
            return converted_positions
            
        except Exception as e:
            logger.error(f"加载期初持仓失败: {str(e)}")
            return []