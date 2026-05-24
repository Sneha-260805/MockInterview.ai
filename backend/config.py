from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Intelligent Mock Interview Agent API"
    app_version: str = "0.1.0"
    debug: bool = False

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "mock_interview_db"

    frontend_url: str = "http://localhost:5173"

    # Optional LLM support — set USE_LLM=true and provide GROQ_API_KEY to enable
    use_llm: bool = False
    groq_api_key: str = ""
    anthropic_api_key: str = ""  # kept for backward compatibility

    # Adzuna live job API
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()