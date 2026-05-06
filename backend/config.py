from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Intelligent Mock Interview Agent API"
    app_version: str = "0.1.0"
    debug: bool = False

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "mock_interview_db"

    frontend_url: str = "http://localhost:5173"

    # Optional LLM support — set USE_LLM=true and provide the key to enable
    use_llm: bool = False
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
