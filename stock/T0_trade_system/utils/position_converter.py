import pandas as pd
import json
from typing import Dict, List
import os

from utils.logger import get_utils_logger
logger = get_utils_logger('position_converter')

class PositionConverter:
    """持仓数据转换器 - 将同花顺导出数据转换为系统格式"""
    
    @staticmethod
    def convert_from_tonghuashun(file_path: str, output_file: str = None) -> List[Dict]:
        """
        从同花顺导出文件转换持仓数据
        """
        try:
            # 读取Excel或CSV文件
            if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
                # 明确指定engine
                try:
                    # 先尝试openpyxl（用于.xlsx）
                    df = pd.read_excel(file_path, engine='openpyxl')
                except:
                    try:
                        # 再尝试xlrd（用于旧的.xls）
                        df = pd.read_excel(file_path, engine='xlrd')
                    except:
                        # 最后尝试默认引擎
                        df = pd.read_excel(file_path)
            elif file_path.endswith('.csv'):
                # 尝试多种编码
                try:
                    df = pd.read_csv(file_path, encoding='gbk')  # 同花顺通常用GBK编码
                except:
                    try:
                        df = pd.read_csv(file_path, encoding='utf-8')
                    except:
                        df = pd.read_csv(file_path, encoding='gb2312')
            else:
                raise ValueError("不支持的文件格式，请使用Excel(.xlsx/.xls)或CSV文件")
            
            logger.info(f"成功读取文件: {file_path}, 共 {len(df)} 条持仓记录")
            logger.info(f"文件列名: {df.columns.tolist()}")
            
            # 转换数据
            converted_positions = []
            
            for index, row in df.iterrows():
                position = PositionConverter._convert_single_position(row)
                if position:
                    converted_positions.append(position)
            
            logger.info(f"成功转换 {len(converted_positions)} 条持仓记录")
            
            # 保存到文件（如果指定了输出文件）
            if output_file:
                PositionConverter._save_to_json(converted_positions, output_file)
                logger.info(f"持仓数据已保存到: {output_file}")
            
            return converted_positions
            
        except Exception as e:
            logger.error(f"转换持仓数据失败: {str(e)}")
            raise
    
    @staticmethod
    def _convert_single_position(row: pd.Series) -> Dict:
        """转换单条持仓记录"""
        try:
            # 打印行数据用于调试
            logger.info(f"正在处理行数据: {row.to_dict()}")
            
            # 动态匹配列名（处理中英文列名）
            column_mapping = {
                'stock_code': ['证券代码', '代码', 'stock_code', 'code'],
                'stock_name': ['证券名称', '名称', 'stock_name', 'name'],
                'quantity': ['股票余额', '持仓数量', 'quantity', '持股数量'],
                'available_quantity': ['可用余额', '可用数量', 'available_quantity'],
                'cost_price': ['成本价', '成本', 'cost_price', 'avg_cost'],
                'current_price': ['市价', '当前价', 'current_price', 'price'],
                'total_pnl': ['盈亏', '浮动盈亏', 'profit_loss', 'pnl'],
                'pnl_rate': ['盈亏比(%)', '盈亏比例', 'profit_rate', 'pnl_rate'],
                'market_value': ['市值', 'market_value', 'value']
            }
            
            def get_column_value(row, possible_names):
                for name in possible_names:
                    if name in row:
                        return row[name]
                return None
            
            # 获取字段值
            stock_code = get_column_value(row, column_mapping['stock_code'])
            stock_name = get_column_value(row, column_mapping['stock_name'])
            quantity = get_column_value(row, column_mapping['quantity'])
            cost_price = get_column_value(row, column_mapping['cost_price'])
            current_price = get_column_value(row, column_mapping['current_price'])
            total_pnl = get_column_value(row, column_mapping['total_pnl'])
            pnl_rate = get_column_value(row, column_mapping['pnl_rate'])
            
            # 验证必要字段
            if not all([stock_code, stock_name, quantity, cost_price]):
                logger.info(f"缺少必要字段，跳过该行: {row.to_dict()}")
                return None
            
            # 清理和转换数据
            stock_code = str(stock_code).zfill(6)  # 确保6位代码
            stock_name = str(stock_name).strip()
            quantity = int(float(quantity))
            cost_price = float(cost_price)
            
            # 如果当前价为空，使用成本价
            if current_price is None or pd.isna(current_price):
                current_price = cost_price
            else:
                current_price = float(current_price)
            
            # 计算缺失的字段
            if total_pnl is None or pd.isna(total_pnl):
                total_pnl = (current_price - cost_price) * quantity
            else:
                total_pnl = float(total_pnl)
            
            if pnl_rate is None or pd.isna(pnl_rate):
                pnl_rate = (current_price - cost_price) / cost_price if cost_price > 0 else 0
            else:
                pnl_rate = float(pnl_rate) / 100  # 转换为小数
            
            # 构建持仓记录
            position = {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'quantity': quantity,
                'cost_price': round(cost_price, 4),
                'current_price': round(current_price, 4),
                'total_pnl': round(total_pnl, 2),
                'pnl_rate': round(pnl_rate, 4),
                'market_value': round(current_price * quantity, 2),
                'position_type': 'LONG',
                'available_quantity': quantity,  # 默认等于总数量
                'frozen_quantity': 0,
                'position_ratio': 0,  # 稍后计算
                'holding_days': 1,
                'exchange': 'SZ' if stock_code.startswith(('0', '3')) else 'SH'
            }
            
            logger.info(f"成功转换: {stock_code} {stock_name} {quantity}股 @ {cost_price}")
            return position
            
        except Exception as e:
            logger.info(f"转换持仓记录失败: {e}, 行数据: {row.to_dict()}")
            return None
    
    @staticmethod
    def _save_to_json(positions: List[Dict], output_file: str):
        """保存为JSON格式"""
        # 计算仓位占比
        total_value = sum(p['market_value'] for p in positions)
        for position in positions:
            position['position_ratio'] = round(position['market_value'] / total_value * 100, 2) if total_value > 0 else 0
        
        # 构建系统需要的格式
        system_format = {
            "initial_positions": positions,
            "converted_time": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
            "source": "tonghuashun_export",
            "total_positions": len(positions),
            "total_market_value": total_value
        }
        
        # 确保目录存在
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(system_format, f, ensure_ascii=False, indent=2)
        
        logger.info(f"持仓数据已保存到: {output_file}")