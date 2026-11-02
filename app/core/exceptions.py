"""应用级异常类型。"""


class AppError(Exception):
    """应用基础异常。"""


class NotFoundError(AppError):
    """资源不存在。"""


class AppValidationError(AppError):
    """输入校验失败。"""


class LLMError(AppError):
    """LLM 系统失败（超时 / 网络错误 / key 未配置等）统一异常。"""
