from .mean_reversion import MeanReversionStrategy
from .trend_following import TrendFollowingStrategy
from .breakout import BreakoutStrategy
from .scalping import ScalpingStrategy
from .t0_reversion import T0ReversionStrategy

# 策略映射
STRATEGY_MAP = {
    "MeanReversion": MeanReversionStrategy,
    "TrendFollowing": TrendFollowingStrategy,
    "Breakout": BreakoutStrategy,
    "Scalping": ScalpingStrategy,
    "T0Reversion": T0ReversionStrategy
}

def create_strategy(strategy_name: str, config):
    """创建策略实例"""
    if strategy_name in STRATEGY_MAP:
        strategy_class = STRATEGY_MAP[strategy_name]
        return strategy_class(config)
    else:
        raise ValueError(f"未知策略: {strategy_name}")

def get_available_strategies():
    """获取可用策略列表"""
    return list(STRATEGY_MAP.keys())

def get_strategy_parameters(strategy_name: str):
    """获取策略的默认参数"""
    default_params = {
        "MeanReversion": {
            "deviation_threshold": 0.03,
            "lookback_period": 20,
            "ma_period": 5,
            "volume_confirmation": True
        },
        "TrendFollowing": {
            "short_period": 5,
            "long_period": 20,
            "trend_threshold": 0.01,
            "momentum_period": 10
        },
        "Breakout": {
            "period": 20,
            "confirmation_bars": 2,
            "breakout_threshold": 0.01
        },
        "Scalping": {
            "price_spread_threshold": 0.005,
            "quick_profit_target": 0.008,
            "max_holding_period": 30
        }
    }
    return default_params.get(strategy_name, {})