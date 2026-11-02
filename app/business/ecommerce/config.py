"""电商业务线数据库配置

业务线数据库连接信息属于业务线自己的管理范围，
不属于平台配置（app/config.py）。
"""
from pydantic_settings import BaseSettings


class EcommerceSettings(BaseSettings):
    """电商业务数据库配置"""

    eco_database_url: str = "mysql+asyncmy://root:123321@localhost:3307/ecs"

    # Neo4j 知识图谱连接配置
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j123456"

    # 嵌入模型配置（用于 Neo4j 向量检索，DashScope 兼容 OpenAI 接口）
    dashscope_api_key: str = "sk-ws-H.PIERIRX.lmDd.MEYCIQCC1PDEj_y6rIJISrUQMDoBxq7PLGUP1cwbFWi1LoFbdwIhAOakV6_LJGVuRwZtm1dOSX0bkONx4Sk4N_cWvZzde34n"  # 阿里云百炼 API Key
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 1024
    embedding_api_base_url: str = "https://llm-fxrkx8nfqvsdmqj8.cn-beijing.maas.aliyuncs.com/api/v1"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


ecommerce_settings = EcommerceSettings()