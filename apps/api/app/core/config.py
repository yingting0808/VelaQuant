from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ai-us-stocks-api"
    database_url: str = "sqlite:///./local.db"
    cors_origin: str = "http://localhost:3000"
    data_mode: str = "hybrid"
    sec_user_agent: str = "VelaQuant research app contact@example.com"
    sec_timeout_seconds: float = 3.0
    strategy_command_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AI_STOCKS_")


def get_settings() -> Settings:
    return Settings()
