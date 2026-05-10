from pydantic_settings import BaseSettings
from pydantic import field_validator
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
    llm_provider: str = "anthropic"   # "anthropic" | "gemini"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Adzuna live job API
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value):
        if isinstance(value, str) and value.lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            return False
        return value

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
