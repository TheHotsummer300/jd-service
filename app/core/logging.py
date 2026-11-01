"""日志配置（loguru）。"""
import sys

from loguru import logger


def setup_logging(level: str = "INFO") -> None:
    """初始化日志：移除默认 handler 并输出到 stdout。"""
    logger.remove()
    logger.add(sys.stdout, level=level)
