from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "velaquant-api"
    database_url: str = "sqlite:///./local.db"
    cors_origin: str = "http://localhost:3000"
    data_mode: str = "hybrid"
    sec_user_agent: str = "VelaQuant research app contact@example.com"
    sec_timeout_seconds: float = 3.0
    strategy_command_timeout_seconds: float = 5.0
    lean_backtest_timeout_seconds: float = 600.0
    paper_scheduler_enabled: bool = False
    paper_scheduler_cron: str = "30 6 * * *"
    paper_scheduler_timezone: str = "Asia/Shanghai"
    trading_day_mode: str = "utc"
    event_bus_mode: str = "memory"
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_name: str = "trading:events"
    openai_research_enabled: bool = True
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_research_model: str = "gpt-5.5"
    openai_timeout_seconds: float = 20.0

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AI_STOCKS_")

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.cors_origin]
        if self.cors_origin == "http://localhost:3000":
            origins.append("http://127.0.0.1:3000")
            origins.append("http://localhost:3100")
            origins.append("http://127.0.0.1:3100")
        return list(dict.fromkeys(origins))


def get_settings() -> Settings:
    return Settings()
