from datetime import datetime, date
from dataclasses import dataclass, asdict  # 添加 dataclass 导入

@dataclass
class TickData:
    """逐笔行情数据"""
    code: str
    name: str
    price: float
    change_percent: float
    volume: int
    amount: float
    timestamp: datetime
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_volume: int = 0
    ask_volume: int = 0
    
    def to_dict(self):
        return {
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'change_percent': self.change_percent,
            'volume': self.volume,
            'amount': self.amount,
            'timestamp': self.timestamp.isoformat(),
            'bid_price': self.bid_price,
            'ask_price': self.ask_price,
            'bid_volume': self.bid_volume,
            'ask_volume': self.ask_volume
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            code=data['code'],
            name=data['name'],
            price=data['price'],
            change_percent=data['change_percent'],
            volume=data['volume'],
            amount=data['amount'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            bid_price=data.get('bid_price', 0.0),
            ask_price=data.get('ask_price', 0.0),
            bid_volume=data.get('bid_volume', 0),
            ask_volume=data.get('ask_volume', 0)
        )
