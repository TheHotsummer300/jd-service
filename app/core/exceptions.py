"""应用级异常类型。"""


class AppError(Exception):
    """应用基础异常。"""


class NotFoundError(AppError):
    """资源不存在。"""


class AppValidationError(AppError):
    """输入校验失败。"""
