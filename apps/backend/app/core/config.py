from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    app_name: str = "IG Market Intelligence"
    backend_cors_origins: List[str] = ["http://localhost:3000"]
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/ig"
    redis_url: str = "redis://localhost:6379/0"
    ai_provider: str = "deepseek"
    deepseek_api_key: str = ""
    finnhub_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
