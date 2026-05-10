from fastapi import APIRouter
from database.connection import is_using_memory
from config import get_settings

router = APIRouter(prefix="/api", tags=["health"])
settings = get_settings()


@router.get("/health")
async def health_check():
    # Use the canonical property so Grok (and any future provider) is handled correctly
    llm_configured = settings.has_llm_configured
    active_key_hint = ""
    if llm_configured:
        key = settings.active_llm_key
        active_key_hint = f"{key[:6]}…" if len(key) > 6 else "(set)"

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "storage": "in-memory" if is_using_memory() else "mongodb",
        "llm": {
            "enabled": settings.use_llm,
            "provider": settings.llm_provider,
            "model": settings.grok_model if settings.llm_provider.lower() == "grok" else "default",
            "configured": llm_configured,
            "key_hint": active_key_hint,
            "timeout_s": settings.llm_timeout_seconds,
            "mode": f"{settings.llm_provider}_enabled" if llm_configured else "rule_based_fallback",
        },
    }
