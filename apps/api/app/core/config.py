from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ai-us-stocks-api"
    database_url: str = "sqlite:///./local.db"
    cors_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AI_STOCKS_")


def get_settings() -> Settings:
    return Settings()
