"""平台级配置，从 .env 读取。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """平台级配置。

    通过环境变量或 .env 文件加载，字段名不区分大小写（如 PLATFORM_DATABASE_URL）。
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    platform_database_url: str
    llm_model: str
    llm_api_key: str
    llm_base_url: str
    log_level: str = "INFO"
