from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import json
from config.trading_config import TradingConfig

from utils.logger import get_core_logger
logger = get_core_logger('deal_manager')

@dataclass
class DealData:
    """成交数据类"""
    deal_id: str
    stock_code: str
    stock_name: str
    direction: str  # BUY, SELL
    price: float
    quantity: int
    amount: float
    commission: float
    stamp_tax: float
    total_cost: float
    net_amount: float
    deal_time: datetime
    strategy: str
    order_type: str = "MARKET"  # MARKET, LIMIT
    status: str = "FILLED"      # PENDING, FILLED, CANCELLED
    fill_time: Optional[datetime] = None
    order_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'deal_id': self.deal_id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'direction': self.direction,
            'price': self.price,
            'quantity': self.quantity,
            'amount': self.amount,
            'commission': self.commission,
            'stamp_tax': self.stamp_tax,
            'total_cost': self.total_cost,
            'net_amount': self.net_amount,
            'deal_time': self.deal_time.isoformat(),
            'strategy': self.strategy,
            'order_type': self.order_type,
            'status': self.status,
            'fill_time': self.fill_time.isoformat() if self.fill_time else None,
            'order_id': self.order_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DealData':
        """从字典创建实例"""
        return cls(
            deal_id=data['deal_id'],
            stock_code=data['stock_code'],
            stock_name=data['stock_name'],
            direction=data['direction'],
            price=data['price'],
            quantity=data['quantity'],
            amount=data['amount'],
            commission=data['commission'],
            stamp_tax=data['stamp_tax'],
            total_cost=data['total_cost'],
            net_amount=data['net_amount'],
            deal_time=datetime.fromisoformat(data['deal_time']),
            strategy=data['strategy'],
            order_type=data.get('order_type', 'MARKET'),
            status=data.get('status', 'FILLED'),
            fill_time=datetime.fromisoformat(data['fill_time']) if data.get('fill_time') else None,
            order_id=datetime.fromisoformat(data['order_id']) if data.get('order_id') else None,
        )


class DealManager:
    """成交管理器"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.deal_history = []
        self.daily_deals = 0
        if self.config.load_deal:
            self._load_deal_history()

    def _generate_deal_id(self) -> str:
        """生成唯一的交易ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]
        return f"T{timestamp}"
    
    def record_deal(self, stock_code: str, stock_name: str, direction: str,
                    price: float, quantity: int, strategy_name: str, current_time: str) -> DealData:
        """记录成交"""
        # 计算交易金额和费用
        amount = price * quantity
        commission = amount * self.config.commission_rate
        
        if direction == "SELL":
            stamp_tax = amount * self.config.stamp_tax_rate
        else:
            stamp_tax = 0
        
        total_cost = commission + stamp_tax
        net_amount = amount - total_cost if direction == "SELL" else -amount - total_cost
        
        # 创建成交记录
        deal = DealData(
            deal_id=self._generate_deal_id(),
            stock_code=stock_code,
            stock_name=stock_name,
            direction=direction,
            price=price,
            quantity=quantity,
            amount=amount,
            commission=commission,
            stamp_tax=stamp_tax,
            total_cost=total_cost,
            net_amount=net_amount,
            deal_time=datetime.fromisoformat(current_time),
            strategy=strategy_name,
            order_type="MARKET",
            status="FILLED",
            fill_time=datetime.fromisoformat(current_time)
        )
        
        self.deal_history.append(deal)
        self.daily_deals += 1
        
        # 立即保存到文件
        self._save_deal_record(deal)
        
        logger.info(f"记录成交: {direction} {stock_code} {quantity}股 @ {price}, "
                   f"金额: {amount:.2f}, 净额: {net_amount:.2f}")
        
        return deal
    
    def _save_deal_record(self, deal: DealData):
        """保存单条成交记录到文件"""
        try:
            date_str = deal.deal_time.strftime('%Y%m%d')
            deal_file = os.path.join(self.config.deal_data_dir, f"deals_{date_str}.json")
            
            # 读取现有数据或创建新文件
            data = {"deals": [], "summary": {}}
            
            if os.path.exists(deal_file):
                try:
                    with open(deal_file, 'r', encoding='utf-8') as f:
                        file_content = f.read().strip()
                        if file_content:  # 确保文件不为空
                            data = json.loads(file_content)
                        else:
                            logger.warning(f"成交文件为空: {deal_file}，创建新文件")
                except json.JSONDecodeError as e:
                    logger.warning(f"成交文件格式错误 {deal_file}，创建新文件: {e}")
                    # 备份损坏的文件
                    backup_file = deal_file + '.bak'
                    if os.path.exists(deal_file):
                        os.rename(deal_file, backup_file)
                        logger.info(f"已备份损坏文件到: {backup_file}")
            
            # 确保数据结构正确
            if "deals" not in data:
                data["deals"] = []
            if "summary" not in data:
                data["summary"] = {}
            
            # 添加新成交记录
            data["deals"].append(deal.to_dict())
            
            # 更新汇总信息
            data["summary"] = self._calculate_daily_summary(data["deals"])
            
            # 保存文件
            with open(deal_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"成交记录已保存到: {deal_file}")
                
        except Exception as e:
            logger.error(f"保存成交记录失败: {str(e)}")

    def _load_deal_history(self):
        """加载历史成交记录"""
        try:
            # 加载最近7天的成交记录
            for i in range(7):
                date_str = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
                deal_file = os.path.join(self.config.deal_data_dir, f"deals_{date_str}.json")
                
                if os.path.exists(deal_file):
                    try:
                        with open(deal_file, 'r', encoding='utf-8') as f:
                            file_content = f.read().strip()
                            if not file_content:
                                continue
                                
                            data = json.loads(file_content)
                        
                        # 确保数据格式正确
                        deals_data = data.get("deals", [])
                        if not isinstance(deals_data, list):
                            logger.warning(f"成交数据格式错误: {deal_file}")
                            continue
                        
                        for deal_dict in deals_data:
                            try:
                                deal = DealData.from_dict(deal_dict)
                                self.deal_history.append(deal)
                            except Exception as e:
                                logger.warning(f"解析成交记录失败: {e}, 数据: {deal_dict}")
                                
                    except json.JSONDecodeError as e:
                        logger.warning(f"成交文件格式错误，跳过: {deal_file}, 错误: {e}")
                    except Exception as e:
                        logger.warning(f"加载成交文件失败: {deal_file}, 错误: {e}")
            
            logger.info(f"加载了 {len(self.deal_history)} 条历史成交记录")
            
        except Exception as e:
            logger.error(f"加载成交记录失败: {str(e)}")
    
    def _calculate_daily_summary(self, deals: List[Dict]) -> Dict:
        """计算当日交易汇总"""
        if not deals:
            return {}
        
        buy_deals = [t for t in deals if t['direction'] == 'BUY']
        sell_deals = [t for t in deals if t['direction'] == 'SELL']
        
        total_buy_amount = sum(t['amount'] for t in buy_deals)
        total_sell_amount = sum(t['amount'] for t in sell_deals)
        total_commission = sum(t['commission'] for t in deals)
        total_stamp_tax = sum(t['stamp_tax'] for t in deals)
        total_cost = sum(t['total_cost'] for t in deals)
        
        return {
            'total_deals': len(deals),
            'buy_deals': len(buy_deals),
            'sell_deals': len(sell_deals),
            'total_buy_amount': total_buy_amount,
            'total_sell_amount': total_sell_amount,
            'net_cash_flow': total_sell_amount - total_buy_amount - total_cost,
            'total_commission': total_commission,
            'total_stamp_tax': total_stamp_tax,
            'total_cost': total_cost,
            'update_time': datetime.now().isoformat()
        }
    def get_deal_history(self, limit: int = 50) -> List[Dict]:
        """获取交易历史"""
        return self.deal_history[-limit:] if limit > 0 else self.deal_history

    def get_today_deal_num(self, limit: int = 50) -> List[Dict]:
        """获取交易历史记录数"""
        return len(self.deal_history)

    def calculate_trade_pnl(self, stock_code) -> float:
        """计算总的交易盈亏"""
        sell_trade_amount = 0.0
        sell_trade_quantity = 0.0
        buy_trade_amount = 0.0
        buy_trade_quantity = 0.0
        total_fees = 0.0
        for deal in self.deal_history:
            if deal.stock_code == stock_code:
                if deal.direction == "SELL":
                    sell_trade_amount += deal.amount
                    sell_trade_quantity += deal.quantity
                elif deal.direction == "BUY":
                    buy_trade_amount += deal.amount
                    buy_trade_quantity += deal.quantity
                total_fees += deal.total_cost
        
        if buy_trade_quantity == 0 or sell_trade_quantity == 0:
            return 0.0
        
        return (sell_trade_amount/sell_trade_quantity - buy_trade_amount/buy_trade_quantity) * \
                min(sell_trade_quantity, buy_trade_quantity) - total_fees * min(sell_trade_quantity, buy_trade_quantity) / \
                (sell_trade_quantity + buy_trade_quantity)
    
    def calculate_total_trade_pnl(self) -> float:
        """计算总的交易盈亏"""
        stock_codes = set(deal.stock_code for deal in self.deal_history)
        total_pnl = 0.0
        for stock_code in stock_codes:
            total_pnl += self.calculate_trade_pnl(stock_code)
        return total_pnl

    def calculate_openset(self, stock_code) -> float:
        """计算股票敞口"""
        openset = 0.0
        for deal in self.deal_history:
            if deal.stock_code == stock_code:
                if deal.direction == "SELL":
                    openset += deal.quantity
                elif deal.direction == "BUY":
                    openset -= deal.quantity
        return openset

    def calculate_total_openset(self) -> float:
        """计算股票总敞口"""
        stock_codes = set(deal.stock_code for deal in self.deal_history)
        total_openset = 0.0
        for stock_code in stock_codes:
            total_openset += self.calculate_openset(stock_code)
        return total_openset