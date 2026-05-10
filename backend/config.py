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
    llm_provider: str = "anthropic"   # "anthropic" | "gemini" | "grok" | "groq"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    grok_api_key: str = ""           # xAI Grok (console.x.ai)
    grok_model: str = "grok-3"        # model name for xAI Grok (grok-3 / grok-2)
    groq_api_key: str = ""            # Groq.ai free tier (console.groq.com)
    groq_model: str = "mixtral-8x7b-32768"  # Groq.ai model name

    # LLM request settings
    llm_timeout_seconds: int = 15     # per-request timeout; 0 = no timeout
    llm_log_prompts: bool = False     # set true locally to debug raw prompts/responses

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

    @property
    def has_llm_configured(self) -> bool:
        """
        True when LLM is enabled AND at least one provider API key is present.
        Use this instead of checking individual key fields — supports all providers.
        """
        if not self.use_llm:
            return False
        return bool(self.anthropic_api_key or self.gemini_api_key or self.grok_api_key or self.groq_api_key)

    @property
    def active_llm_key(self) -> str:
        """Return the key for the currently configured provider, or ''."""
        p = self.llm_provider.lower()
        if p == "grok":
            return self.grok_api_key
        if p == "groq":
            return self.groq_api_key
        if p == "gemini":
            return self.gemini_api_key
        return self.anthropic_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
