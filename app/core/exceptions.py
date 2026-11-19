"""统一异常定义"""


class AppException(Exception):
    """应用基础异常"""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundException(AppException):
    """资源未找到"""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, status_code=404)


class ValidationException(AppException):
    """校验异常"""

    def __init__(self, message: str = "参数校验失败"):
        super().__init__(message, status_code=422)


class BusinessException(AppException):
    """业务异常"""

    def __init__(self, message: str = "业务处理失败"):
        super().__init__(message, status_code=400)

