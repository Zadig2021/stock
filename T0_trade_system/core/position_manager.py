import os

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from .position_storage import PositionStorage
from .deal_manager import DealManager

from utils.logger import get_core_logger
logger = get_core_logger('position_manager')

class Position:
    """持仓类"""
    
    def __init__(self, stock_code: str, stock_name: str, quantity: int, price: float, initial_pnl: float, 
                 signal_type: str, timestamp: datetime, stop_loss_price: float = None, source: str = 'buy'):
        self.stock_code = stock_code
        self.stock_name = stock_name
        self.quantity = quantity
        self.entry_price = price
        self.current_price = price
        self.initial_pnl = initial_pnl
        self.signal_type = signal_type  # BUY or SELL
        self.entry_time = timestamp
        self.last_update = timestamp
        self.stop_loss_price = stop_loss_price
        self.source = source
        
    def update_price(self, price: float):
        """更新当前价格"""
        self.current_price = price
        self.last_update = datetime.now()
    
    @property
    def market_value(self) -> float:
        """当前市值"""
        return self.quantity * self.current_price
    
    @property
    def profit_loss(self) -> float:
        """盈亏金额"""
        if self.signal_type == "BUY":
            return (self.current_price - self.entry_price) * self.quantity
        else:  # SELL
            return (self.entry_price - self.current_price) * self.quantity
    
    @property
    def profit_loss_rate(self) -> float:
        """盈亏比例"""
        cost = self.entry_price * self.quantity
        if cost == 0:
            return 0.0
        return self.profit_loss / cost
    
    @property
    def holding_time(self) -> float:
        """持仓时间（分钟）"""
        return (datetime.now() - self.entry_time).total_seconds() / 60
    
    def to_dict(self) -> Dict:
        """转换为字典 - 修复版"""
        try:
            # 确保所有字段都有有效值
            entry_time_str = self.entry_time.isoformat() if hasattr(self.entry_time, 'isoformat') else datetime.now().isoformat()
            last_update_str = self.last_update.isoformat() if hasattr(self.last_update, 'isoformat') else datetime.now().isoformat()
            
            return {
                'stock_code': str(self.stock_code) if self.stock_code else '',
                'stock_name': str(self.stock_name) if self.stock_name else '',
                'quantity': int(self.quantity) if self.quantity else 0,
                'entry_price': float(self.entry_price) if self.entry_price else 0.0,
                'current_price': float(self.current_price) if self.current_price else 0.0,
                'signal_type': str(self.signal_type) if self.signal_type else 'UNKNOWN',
                'market_value': float(self.market_value) if hasattr(self, 'market_value') else 0.0,
                'initial_pnl': float(self.initial_pnl) if hasattr(self, 'initial_pnl') else 0.0,
                'pnl': float(self.profit_loss) if hasattr(self, 'profit_loss') else 0.0,
                'pnl_rate': float(self.profit_loss_rate) if hasattr(self, 'profit_loss_rate') else 0.0,
                'holding_time': float(self.holding_time) if hasattr(self, 'holding_time') else 0.0,
                'stop_loss_price': float(self.stop_loss_price) if self.stop_loss_price else None,
                'entry_time': entry_time_str,
                'last_update': last_update_str
            }
        except Exception as e:
            logger.error(f"转换持仓到字典失败: {str(e)}")
            # 返回一个安全的默认字典
            return {
                'stock_code': 'ERROR',
                'stock_name': 'ERROR',
                'quantity': 0,
                'entry_price': 0.0,
                'current_price': 0.0,
                'signal_type': 'ERROR',
                'market_value': 0.0,
                'initial_pnl': 0.0,
                'pnl': 0.0,
                'pnl_rate': 0.0,
                'holding_time': 0.0,
                'stop_loss_price': None,
                'entry_time': datetime.now().isoformat(),
                'last_update': datetime.now().isoformat()
            }

class PositionManager:
    """仓位管理器"""
    
    def __init__(self, config, load_config: bool = True ):
        self.config = config
        self.positions: Dict[str, Position] = {}
        self.clear_trade_pnl = 0.0
        self.clear_positions = {}  # 日内清仓股票记录
        self.position_storage = PositionStorage(config)
        
        if load_config:
            # 启动时按简单逻辑加载持仓
            self._initialize_positions()
            logger.info(f"持仓初始化完成，总持仓数: {len(self.positions)}")
            self.deal_manager = DealManager(config)

    def _initialize_positions(self):
        """初始化持仓 - 简化逻辑"""
        # 1. 优先从当前持仓文件加载
        if os.path.exists(self.position_storage.get_current_positions_file()):
            logger.info("检测到当前持仓文件，从中加载...")
            success = self.recover_positions_from_file()
            if success:
                logger.info(f"从当前持仓文件加载成功: {len(self.positions)} 个持仓")
                return
        
        # 2. 如果没有当前持仓文件，从期初持仓文件加载
        logger.info("没有当前持仓文件，从期初持仓文件加载...")
        initial_positions = self.position_storage.load_initial_positions()
        if initial_positions:
            self._load_initial_positions(initial_positions)
            logger.info(f"从期初持仓文件加载成功: {len(self.positions)} 个持仓")
        else:
            logger.info("期初持仓文件也不存在，使用空持仓")

    def _load_initial_positions(self, initial_positions: List[Dict]):
        """加载期初持仓到内存"""
        for pos_data in initial_positions:
            try:
                position = Position(
                    stock_code=pos_data['stock_code'],
                    stock_name=pos_data['stock_name'],
                    quantity=pos_data['quantity'],
                    price=pos_data['cost_price'],
                    initial_pnl=pos_data['total_pnl'],  # 期初盈亏
                    signal_type="BUY",  # 期初持仓都是多头
                    timestamp=datetime.now(),
                    source='initial'  # 标记来源
                )
                
                # 设置当前价格
                if 'current_price' in pos_data:
                    position.current_price = pos_data['current_price']
                
                self.positions[pos_data['stock_code']] = position
                logger.debug(f"加载期初持仓: {pos_data['stock_code']} {pos_data['quantity']}股")
            
            except Exception as e:
                logger.error(f"加载期初持仓失败 {pos_data.get('stock_code', '未知')}: {str(e)}")

    def recover_positions_from_file(self) -> bool:
        """从文件恢复持仓"""
        try:
            positions_data = self.position_storage.load_current_positions()
            if not positions_data:
                logger.info("没有找到可恢复的持仓数据")
                return False
            
            recovered_count = 0
            for pos_data in positions_data.get('positions', []):
                # 创建Position对象
                position = Position(
                    stock_code=pos_data['stock_code'],
                    stock_name=pos_data['stock_name'],
                    quantity=pos_data['quantity'],
                    price=pos_data['entry_price'],
                    initial_pnl=pos_data['initial_pnl'],
                    signal_type=pos_data['signal_type'],
                    timestamp=datetime.fromisoformat(pos_data['entry_time']),
                    stop_loss_price=pos_data.get('stop_loss_price')
                )
                position.current_price = pos_data.get('current_price', pos_data['entry_price'])
                
                self.positions[pos_data['stock_code']] = position
                recovered_count += 1
            
            logger.info(f"从文件恢复持仓完成，共恢复 {recovered_count} 个持仓")
            return True
            
        except Exception as e:
            logger.error(f"恢复持仓失败: {str(e)}")
            return False
    
    def save_positions_to_file(self) -> bool:
        """保存持仓到文件"""
        try:
            positions_data = {
                'positions': [
                    {
                        'stock_code': pos.stock_code,
                        'stock_name': pos.stock_name,
                        'quantity': pos.quantity,
                        'entry_price': pos.entry_price,
                        'current_price': pos.current_price,
                        'signal_type': pos.signal_type,
                        'entry_time': pos.entry_time.isoformat(),
                        'stop_loss_price': pos.stop_loss_price,
                        'market_value': pos.market_value,
                        'initial_pnl': pos.initial_pnl,
                        'pnl': pos.profit_loss,
                        'pnl_rate': pos.profit_loss_rate,
                        'holding_time': pos.holding_time,
                        'source': pos.source,
                        'daily_trade_pnl': self.deal_manager.calculate_trade_pnl(pos.stock_code),
                        'daily_openset': self.deal_manager.calculate_openset(pos.stock_code)
                    }
                    for pos in self.positions.values()
                ],
                'summary': {
                    'total_positions': len(self.positions),
                    'total_value': self.total_position_value,
                    'total_pnl': self.total_pnl,
                    'clear_trade_pnl': self.clear_trade_pnl,
                    'daily_trade_pnl': self.deal_manager.calculate_total_trade_pnl(),
                    'daily_position_pnl': self.total_pnl - self.total_initial_pnl,
                    'daily_trades': self.deal_manager.get_today_deal_num(),
                }
            }
            
            success = self.position_storage.save_current_positions(positions_data)
            if success:
                logger.debug("持仓数据已保存到文件")
            return success
            
        except Exception as e:
            logger.error(f"保存持仓到文件失败: {str(e)}")
            return False
    
    def auto_save_positions(self):
        """自动保存持仓（由外部定时器调用）"""
        if self.config.enable_position_persistence:
            self.save_positions_to_file()
    
    def buy_position(self, stock_code: str, stock_name: str, signal_type: str, 
                     price: float, quantity: int, stop_loss_price: float, current_time: str) -> bool:
        """买入持仓"""
        if stock_code not in self.positions:
            position = Position(stock_code, stock_name, quantity, price, 0, signal_type, datetime.now(), stop_loss_price)
            if self.clear_positions.get(stock_code):
                # 如果之前日内清仓过，累加初始盈亏
                position.initial_pnl = self.clear_positions[stock_code].initial_pnl
                position.entry_time = self.clear_positions[stock_code].entry_time
                position.source = 'reopen'
                position.entry_price = (price * quantity - self.clear_positions[stock_code].profit_loss) / quantity
                self.clear_trade_pnl -= self.clear_positions[stock_code].profit_loss
                del self.clear_positions[stock_code]
            self.positions[stock_code] = position
        
        position = self.positions[stock_code]
        # 检查仓位限制
        if self.config.position_risk_check and not self.check_position_limit(stock_code, signal_type, price, quantity):
            return False
        
        # 买入增加持仓数量，调整成本价
        position.quantity += quantity
        position.entry_price = (
            (position.entry_price * (position.quantity - quantity) + price * quantity)
            / position.quantity
        )
        
        # 记录成交
        self.deal_manager.record_deal(stock_code, stock_name, signal_type, price, quantity, self.config.strategy_name, current_time)
        
        logger.info(f"买入: {signal_type} {stock_code} {quantity}股 @ {price}, 止损价: {stop_loss_price}")
        return True
    
    def sell_position(self, stock_code: str, stock_name: str, signal_type: str, 
                     price: float, quantity: int, current_time: str) -> bool:
        """卖出持仓"""
        if stock_code not in self.positions:
            logger.warning(f"尝试卖出不存在的持仓: {stock_code} {quantity}股 @ {price}")
            return False
        
        position = self.positions[stock_code]

        if position.quantity < quantity:
            logger.warning(f"尝试卖出超过持仓数量: {stock_code} {quantity}股 @ {price} 持仓仅有 {position.quantity}股")
            return False

        # 检查仓位限制
        if self.config.position_risk_check and not self.check_position_limit(stock_code, signal_type, price, quantity):
            return False
        
        # 卖出减少持仓数量，调整成本价
        if position.quantity == quantity:
            self.clear_trade_pnl +=  position.profit_loss
            self.clear_positions[stock_code] = self.positions.pop(stock_code, None)
            logger.info(f"持仓已清空: {stock_code}")
        elif position.quantity > quantity:
            position.quantity -= quantity
            position.entry_price = (
                (position.entry_price * (position.quantity + quantity) - price * quantity)
                / position.quantity
            )
        else:
            logger.error(f"卖出数量超过持仓数量: {stock_code} 持仓{position.quantity}股，尝试卖出{quantity}股")
            return False

        # 记录成交
        self.deal_manager.record_deal(stock_code, stock_name, signal_type, price, quantity, self.config.strategy_name, current_time)

        logger.info(f"卖出: {signal_type} {stock_code} {quantity}股 @ {price}")
        return True

    def update_position_prices(self, price_data: Dict[str, float]):
        """更新持仓价格 - 安全版本"""
        updated_count = 0

        for stock_code, price in price_data.items():
            # 检查持仓是否存在
            if stock_code not in self.positions:
                logger.debug(f"尝试更新不存在的持仓: {stock_code}")
                continue
                
            # 检查价格有效性
            if price <= 0:
                logger.debug(f"跳过无效价格: {stock_code} -> {price}")
                continue
                
            try:
                position = self.positions[stock_code]
                
                # 验证持仓完整性
                if not self.validate_position(position):
                    logger.error(f"持仓 {stock_code} 数据不完整，跳过更新")
                    continue
                    
                # 记录更新前状态
                old_price = position.current_price
                
                # 更新价格
                position.update_price(price)
                updated_count += 1
                
                logger.debug(f"成功更新持仓价格: {stock_code} {old_price:.2f} -> {price:.2f}")
                
            except Exception as e:
                logger.error(f"更新持仓 {stock_code} 价格时发生错误: {str(e)}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")
                continue
            
        if updated_count > 0:
            logger.debug(f"价格更新完成: {updated_count} 个持仓已更新")
            
            # 自动保存
            if self.config.enable_position_persistence:
                self.auto_save_positions()
        else:
            logger.debug("没有持仓被更新")
    
    def validate_position(self, position: Position) -> bool:
        """验证持仓对象的完整性"""
        try:
            # 检查必要属性
            required_attrs = ['stock_code', 'quantity', 'entry_price', 'current_price', 'signal_type']
            for attr in required_attrs:
                if not hasattr(position, attr):
                    logger.error(f"持仓缺少属性: {attr}")
                    return False
            
            # 检查属性值有效性
            if not position.stock_code or not isinstance(position.stock_code, str):
                logger.error(f"持仓股票代码无效: {position.stock_code}")
                return False
                
            if position.quantity <= 0:
                logger.error(f"持仓数量无效: {position.quantity}")
                return False
                
            if position.entry_price <= 0:
                logger.error(f"持仓成本价无效: {position.entry_price}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"验证持仓失败: {str(e)}")
            return False
            
    def check_position_limit(self, stock_code: str, signal_type: str, 
                           price: float, quantity: int) -> bool:
        """检查仓位限制"""
        trade_amount = price * quantity
        
        # 1. 检查总持仓限制
        total_position_value = self.total_position_value
        if total_position_value + trade_amount > self.config.initial_capital * self.config.max_position_ratio:
            logger.warning(
                f"超过最大持仓限制: 当前{total_position_value:.2f} + 交易{trade_amount:.2f} > "
                f"限制{self.config.initial_capital * self.config.max_position_ratio:.2f}"
            )
            return False
        
        # 2. 检查单只股票风险暴露
        current_position_value = self.positions.get(stock_code, Position(stock_code, '', 0, 0, 0, "", datetime.now())).market_value
        new_position_value = current_position_value + trade_amount
        
        single_stock_exposure = new_position_value / self.config.initial_capital
        max_single_exposure = self.config.max_single_loss * 3  # 例如止损2%，最大暴露6%
        
        if single_stock_exposure > max_single_exposure:
            logger.warning(
                f"单只股票风险暴露过高: {stock_code} 暴露={single_stock_exposure:.2%} > "
                f"限制={max_single_exposure:.2%}"
            )
            return False
        
        # 3. 检查交易金额合理性
        if trade_amount < self.config.min_trade_amount:
            logger.warning(f"交易金额过小: {trade_amount:.2f} < 最小要求={self.config.min_trade_amount}")
            return False
        
        return True
    
    def check_risk_limits(self, stock_code: str, current_price: float) -> bool:
        """检查风险限制 - 添加详细日志"""
        if stock_code not in self.positions:
            return True
        
        position = self.positions[stock_code]
        
        logger.debug(f"风险检查 {stock_code}: 现价{current_price:.2f}, "
                    f"成本{position.entry_price:.2f}, 盈亏率{position.profit_loss_rate:.2%}, "
                    f"持仓时间{position.holding_time:.1f}分钟")
        
        # 1. 检查止损价格
        if position.stop_loss_price is not None:
            stop_triggered = False
            if position.signal_type == "BUY" and current_price <= position.stop_loss_price:
                stop_triggered = True
                reason = f"止损触发 (当前{current_price:.2f} <= 止损{position.stop_loss_price:.2f})"
            elif position.signal_type == "SELL" and current_price >= position.stop_loss_price:
                stop_triggered = True
                reason = f"止损触发 (当前{current_price:.2f} >= 止损{position.stop_loss_price:.2f})"
            
            if stop_triggered:
                logger.warning(f"🚨 触发止损平仓: {stock_code}, {reason}")
                self.close_position(stock_code, current_price, reason)
                return False
        
        # 2. 检查盈亏比例止损
        if position.profit_loss_rate < -self.config.stop_loss_rate:
            reason = f"比例止损 (盈亏率{position.profit_loss_rate:.2%} < 止损线{-self.config.stop_loss_rate:.2%})"
            logger.warning(f"🚨 触发比例止损: {stock_code}, {reason}")
            self.close_position(stock_code, current_price, reason)
            return False
        
        # 3. 检查止盈
        if position.profit_loss_rate > self.config.take_profit_rate:
            reason = f"止盈触发 (盈亏率{position.profit_loss_rate:.2%} > 止盈线{self.config.take_profit_rate:.2%})"
            logger.info(f"🎯 触发止盈: {stock_code}, {reason}")
            self.close_position(stock_code, current_price, reason)
            return False
        
        # 4. 检查持仓时间
        if position.holding_time > self.config.max_holding_time:
            reason = f"超时平仓 (持仓{position.holding_time:.1f}分钟 > 限制{self.config.max_holding_time}分钟)"
            logger.warning(f"⏰ 超过最大持仓时间: {stock_code}, {reason}")
            self.close_position(stock_code, current_price, reason)
            return False
        
        return True
    
    def force_close_all_positions(self, current_prices: Dict[str, float] = None):
        """强制平仓所有持仓"""
        if not self.positions:
            logger.info("没有持仓需要平仓")
            return
        
        closed_count = 0
        for stock_code in list(self.positions.keys()):
            if current_prices and stock_code in current_prices:
                price = current_prices[stock_code]
            else:
                price = self.positions[stock_code].current_price
            
            if self.close_position(stock_code, price, "强制平仓"):
                closed_count += 1
        
        logger.info(f"强制平仓完成，共平仓 {closed_count} 个持仓")
    
    def get_position(self, stock_code: str) -> Optional[Position]:
        """获取指定股票的持仓"""
        return self.positions.get(stock_code)
    
    def has_position(self, stock_code: str) -> bool:
        """检查是否有指定股票的持仓"""
        return stock_code in self.positions
    
    def get_position_value(self, stock_code: str) -> float:
        """获取指定股票的持仓市值"""
        if stock_code in self.positions:
            return self.positions[stock_code].market_value
        return 0.0
    
    @property
    def total_position_value(self) -> float:
        """总持仓市值"""
        return sum(pos.market_value for pos in self.positions.values())
    
    @property
    def total_pnl(self) -> float:
        """总盈亏（包含已平仓和未平仓）"""
        # 未平仓盈亏
        unrealized_pnl = sum(pos.profit_loss for pos in self.positions.values())
        return self.clear_trade_pnl + unrealized_pnl

    @property
    def total_initial_pnl(self) -> float:
        """总期初盈亏"""
        return sum(pos.initial_pnl for pos in self.positions.values())
    
    @property
    def position_count(self) -> int:
        """持仓数量"""
        return len(self.positions)
    
    def get_position_summary(self) -> Dict:
        """获取持仓摘要"""
        positions_list = []
        for position in self.positions.values():
            pos_dict = position.to_dict()
            # 添加风险信息
            pos_dict['risk_status'] = self._get_position_risk_status(position)
            pos_dict['daily_trade_pnl'] = self.deal_manager.calculate_trade_pnl(position.stock_code)
            pos_dict['daily_openset'] = self.deal_manager.calculate_openset(position.stock_code)
            positions_list.append(pos_dict)
        
        return {
            'total_positions': len(self.positions),
            'total_value': self.total_position_value,
            'total_pnl': self.total_pnl,
            'clear_trade_pnl': self.clear_trade_pnl,
            'daily_trade_pnl': self.deal_manager.calculate_total_trade_pnl(),
            'daily_position_pnl': self.total_pnl - self.total_initial_pnl,
            'daily_trades': self.deal_manager.get_today_deal_num(),
            'positions': positions_list,
            'exposure_ratio': self.total_position_value / self.config.initial_capital if self.config.initial_capital > 0 else 0
        }
    
    def _get_position_risk_status(self, position: Position) -> str:
        """获取持仓风险状态"""
        if position.stop_loss_price is not None:
            if position.signal_type == "BUY":
                stop_loss_distance = (position.current_price - position.stop_loss_price) / position.current_price
            else:
                stop_loss_distance = (position.stop_loss_price - position.current_price) / position.current_price
            
            if stop_loss_distance <= 0.01:  # 距离止损1%以内
                return "高风险"
            elif stop_loss_distance <= 0.03:  # 距离止损3%以内
                return "中风险"
        
        if position.profit_loss_rate >= self.config.take_profit_rate * 0.8:  # 接近止盈
            return "接近止盈"
        
        return "正常"
    
    def reset_daily_statistics(self):
        """重置每日统计（用于新交易日）"""
        self.clear_trade_pnl = 0.0
    
    def cleanup(self):
        """清理资源"""
        self.force_close_all_positions()
        logger.info("仓位管理器清理完成")

    def get_position_history(self, days: int = 7) -> List[Dict]:
        """获取持仓历史记录"""
        try:
            history_data = self.position_storage.get_position_history(days)
            return history_data
        except Exception as e:
            logger.error(f"获取持仓历史失败: {str(e)}")
            return []

    def get_all_history_dates(self) -> List[str]:
        """获取所有有历史持仓记录的日期"""
        try:
            return self.position_storage.get_all_history_dates()
        except Exception as e:
            logger.error(f"获取历史持仓日期失败: {str(e)}")
            return []

    def load_history_positions_by_date(self, date_str: str) -> Optional[Dict]:
        """按日期加载特定的历史持仓"""
        try:
            return self.position_storage.load_history_positions_by_date(date_str)
        except Exception as e:
            logger.error(f"加载历史持仓失败: {str(e)}")
            return None

    def archive_current_positions(self) -> bool:
        """归档当前持仓到历史"""
        try:
            success = self.position_storage.archive_current_positions()
            if success:
                logger.info("当前持仓已成功归档到历史")
            return success
        except Exception as e:
            logger.error(f"归档持仓失败: {str(e)}")
            return False

    def get_init_positions_file(self) -> str:
        """获取期初持仓文件路径"""
        return self.position_storage.get_init_positions_file()