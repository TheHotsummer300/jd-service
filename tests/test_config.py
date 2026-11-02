from app.config import Settings


def test_settings_reads_env():
    """Settings 能从 .env.example 读取数据库与模型配置，且 log_level 有默认值。"""
    settings = Settings(_env_file=".env.example")
    assert settings.platform_database_url.startswith("mysql")
    assert settings.llm_model
    assert settings.log_level == "INFO"
