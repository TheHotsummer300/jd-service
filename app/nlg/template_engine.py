"""Jinja2 模板引擎 — 供业务 Handler 渲染 message 使用"""

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from loguru import logger


class TemplateEngine:
    """模板引擎 — 用于需要精确数据的场景（由业务 Handler 调用）

    所有模板渲染出的文本只能作为 BusinessResult 中的 message 字段内容，
    由业务 Handler 负责调用模板引擎渲染并填入 BusinessResult；
    NLGEngine 不直接调用 TemplateEngine。

    使用示例::

        engine = TemplateEngine(Path(__file__).parent.parent / "templates")
        message = await engine.render("order_query.j2", {"data": order_data})
        return BusinessResult.completed(message=message, **order_data)
    """

    def __init__(self, template_dir: str):
        """初始化模板引擎

        Args:
            template_dir: 模板目录的绝对路径，由调用方（业务 Handler）指定。
                          例如：Path(__file__).parent.parent / "templates"
        """
        self._env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=False,
        )

    async def render(self, template_name: str, context: dict) -> str:
        """渲染模板，返回字符串供业务 Handler 填入 BusinessResult.message

        Args:
            template_name: 模板文件名，如 "order_query.j2"
            context: 模板变量上下文，如 {"data": order_data}

        Returns:
            渲染后的文本字符串，失败时返回降级提示语
        """
        try:
            template = self._env.get_template(template_name)
            result = template.render(**context)
            logger.info(f"模板渲染成功: {template_name}")
            return result
        except TemplateNotFound:
            logger.error(f"模板未找到: {template_name}")
            return "抱歉，系统遇到了一些问题，请稍后重试。"
        except Exception as e:
            logger.error(f"模板渲染失败: {e}")
            return "抱歉，回复生成失败，请稍后重试。"
