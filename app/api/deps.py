"""通道层 FastAPI 依赖（复用平台数据库依赖）。"""

from app.core.database import get_db

__all__ = ["get_db"]
