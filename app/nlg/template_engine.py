"""Jinja2 模板引擎：精确渲染业务结果与槽位追问。"""
from typing import Any

from jinja2 import Environment, FileSystemLoader


class TemplateEngine:
    """基于 Jinja2 的模板渲染器，模板目录为 app/nlg/templates。"""

    def __init__(self) -> None:
        self._env = Environment(loader=FileSystemLoader("app/nlg/templates"))

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """渲染指定模板，返回文本。"""
        template = self._env.get_template(template_name)
        return template.render(**context)
