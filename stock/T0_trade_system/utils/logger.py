import logging
import sys
from datetime import datetime
import os
import inspect
from typing import Dict


# 预定义的日志配置
LOG_CONFIGS = {
    # 核心模块 - 详细日志
    'main': {
        'level': logging.INFO,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_suffix': 'main'
    },
    'core': {
        'level': logging.INFO,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_suffix': 'core'
    },
    # 策略模块 - 调试级别
    'strategy': {
        'level': logging.DEBUG,
        'format': '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        'file_suffix': 'strategy'
    },
    # 数据模块 - 信息级别
    'data': {
        'level': logging.INFO,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_suffix': 'data'
    },
    # 配置模块 - 警告级别
    'config': {
        'level': logging.WARNING,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_suffix': 'config'
    },
     # 行情模块 - 信息级别
    'hq': {
        'level': logging.INFO,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_suffix': 'hq'
    },
    # 工具模块 - 信息级别
    'utils': {
        'level': logging.INFO,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_suffix': 'utils'
    },
    # 工具模块 - 信息级别
    'tools': {
        'level': logging.INFO,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_suffix': 'tools'
    },
    # 默认配置
    'default': {
        'level': logging.INFO,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_suffix': 'general'
    }
}

def setup_logger(name: str, log_file: str = None, level: int = logging.INFO, enable_console: bool = True,
                 console_format: str = '%(message)s', file_format: str = None) -> logging.Logger:
    """设置日志器（可自定义格式）
    
    Args:
        name: logger名称
        log_file: 日志文件路径
        level: 日志级别
        enable_console: 是否开启命令行日志输出
        console_format: 控制台输出格式
        file_format: 文件输出格式
    """

    # 自动确定logger名称和配置
    if name is None:
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')

    # 创建日志
    logger = logging.getLogger(name)
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 根据模块路径选择配置
    config = _get_log_config(name)

    if level is not None:
        config['level'] = level
    if file_format is not None:
        config['format'] = file_format

    # 确定日志文件路径
    if log_file is None:
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(
            log_dir, 
            f"t0_trading_{config['file_suffix']}_{datetime.now().strftime('%Y%m%d')}.log"
        )

    logger.setLevel(config['level'])
    
    # 文件handler - 完整格式
    file_formatter = logging.Formatter(config['format'], datefmt='%Y-%m-%d %H:%M:%S')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(config['level'])
    logger.addHandler(file_handler)
    
    # 控制台handler - 简洁格式(可选)
    if enable_console:
        console_formatter = logging.Formatter(console_format)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(config['level'])
        logger.addHandler(console_handler)
    
    return logger

def disable_root_logger_propagation():
    """禁用root logger的传播，防止日志向上传递"""
    # 获取所有已知的logger并设置不向root传播
    known_loggers = ['main', 'core', 'strategy', 'config', 'utils', 'tools', 'hq']
    
    for logger_name in known_loggers:
        logger = logging.getLogger(logger_name)
        logger.propagate = False
        # print(f"设置logger '{logger_name}' 不向root传播")
    
    # 也可以设置root logger级别为CRITICAL来静默它
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)
    # print("设置root logger级别为CRITICAL")


def _get_log_config(module_name: str) -> Dict:
    """根据模块名称获取日志配置"""
    # 检查精确匹配
    for key, config in LOG_CONFIGS.items():
        if module_name == key or module_name.startswith(f"{key}."):
            return config.copy()
    
    # 检查模块路径匹配
    if module_name.startswith('core.'):
        return LOG_CONFIGS['core'].copy()
    elif module_name.startswith('strategy.'):
        return LOG_CONFIGS['strategy'].copy()
    elif module_name.startswith('data.'):
        return LOG_CONFIGS['data'].copy()
    elif module_name.startswith('config.'):
        return LOG_CONFIGS['config'].copy()
    elif module_name.startswith('utils.'):
        return LOG_CONFIGS['utils'].copy()
    elif module_name.startswith('tools.'):
        return LOG_CONFIGS['tools'].copy()
    elif module_name.startswith('hq.'):
        return LOG_CONFIGS['hq'].copy()
    elif module_name.startswith('main.'):
        return LOG_CONFIGS['main'].copy()
    else:
        return LOG_CONFIGS['default'].copy()

def setup_module_loggers():
    """为所有主要模块设置logger"""
    modules = {
        'core.data_provider': logging.INFO,
        'core.real_trading_engine': logging.INFO,
        'core.position_manager': logging.INFO,
        'core.real_data_provider': logging.INFO,
        'core.position_storage': logging.INFO,
        'core.tushare_data_provider': logging.INFO,
        'core.historical_cache': logging.INFO,
        'strategy.mean_reversion': logging.INFO,
        'strategy.trend_following': logging.INFO,
        'strategy.breakout': logging.INFO,
        'config.trading_config': logging.INFO,
        'utils.helpers': logging.INFO,
        'utils.position_converter': logging.INFO,
        'tools.convert_position': logging.INFO,
        'hq.tick_replayer': logging.INFO,
        'main': logging.INFO,
    }
    
    for module, level in modules.items():
        setup_logger(module, level=level)

    disable_root_logger_propagation()

# 便捷函数
def get_core_logger(name: str) -> logging.Logger:
    """获取核心模块logger"""
    full_name = f"core.{name}" if not name.startswith('core.') else name
    return setup_logger(full_name)

def get_strategy_logger(name: str) -> logging.Logger:
    """获取策略模块logger"""
    full_name = f"strategy.{name}" if not name.startswith('strategy.') else name
    return setup_logger(full_name, enable_console= False)

def get_data_logger(name: str) -> logging.Logger:
    """获取数据模块logger"""
    full_name = f"data.{name}" if not name.startswith('data.') else name
    return setup_logger(full_name, enable_console= False)

def get_utils_logger(name: str) -> logging.Logger:
    """获取工具模块logger"""
    full_name = f"utils.{name}" if not name.startswith('utils.') else name
    return setup_logger(full_name, enable_console= False)

def get_tools_logger(name: str) -> logging.Logger:
    """获取工具模块logger"""
    full_name = f"tools.{name}" if not name.startswith('tools.') else name
    return setup_logger(full_name, enable_console= False)

def get_hq_logger(name: str) -> logging.Logger:
    """获取行情模块logger"""
    full_name = f"hq.{name}" if not name.startswith('hq.') else name
    return setup_logger(full_name, enable_console= False)

def get_main_logger(name: str) -> logging.Logger:
    """获取主模块logger"""
    full_name = f"main.{name}" if not name.startswith('main.') else name
    return setup_logger(full_name)

def get_config_logger(name: str) -> logging.Logger:
    """获取配置模块logger"""
    full_name = f"config.{name}" if not name.startswith('config.') else name
    return setup_logger(full_name)