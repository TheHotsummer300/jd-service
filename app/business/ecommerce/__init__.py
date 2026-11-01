"""电商业务线装配点：导入即注册 3 个意图。

由 app.main 触发 import，注册中心本身不 import 本模块（保持平台无业务硬编码）。
"""
from app.business.ecommerce import actions, intents
from app.business.registry import register

for spec in intents.INTENT_SPECS:
    register(spec, actions.handle)
