from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

def configure_logging(
    log_path: Optional[Path] = None,
    log_level: int = logging.INFO,
    rotate_size: int = 10
) -> None:
    """全局日志配置函数"""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清理旧Handler（避免重复）
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 控制台Handler（始终启用）
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 文件Handler（可选）
    if log_path:
        # 确保路径为绝对路径且父目录存在
        log_path = log_path.resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)  # 关键修改：路径创建责任在此
        
        file_handler = RotatingFileHandler(
            filename=str(log_path),  # 兼容Windows
            maxBytes=rotate_size * 1024 * 1024,
            backupCount=3,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(module)s:%(lineno)d] - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

def get_logger(name: str = "bilidownloader") -> logging.Logger:
    """获取预配置的记录器"""
    return logging.getLogger(name)