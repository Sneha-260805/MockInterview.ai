"""
LLM provider abstraction — supports Anthropic (Claude) and Google Gemini.

Usage in agents:
    from services.llm_client import call_llm
    raw = await call_llm(prompt, max_tokens=600)
    if raw is None:
        return None   # fall back to rule-based path

Provider selection (backend/.env):
    LLM_PROVIDER=anthropic   ANTHROPIC_API_KEY=sk-ant-...
    LLM_PROVIDER=gemini      GEMINI_API_KEY=AIza...
"""

import logging

logger = logging.getLogger(__name__)


async def call_llm(prompt: str, max_tokens: int = 600) -> str | None:
    """
    Send a single-turn prompt to the configured LLM.
    Returns the response text, or None if not configured / on error.
    """
    from config import get_settings
    settings = get_settings()

    if not settings.use_llm:
        return None

    provider = settings.llm_provider.lower()

    if provider == "gemini" and settings.gemini_api_key:
        return await _call_gemini(settings.gemini_api_key, prompt, max_tokens)

    if settings.anthropic_api_key:
        return await _call_anthropic(settings.anthropic_api_key, prompt, max_tokens)

    logger.warning(
        "USE_LLM=true but no API key found. "
        "Set ANTHROPIC_API_KEY or GEMINI_API_KEY in your .env file."
    )
    return None


# ── Anthropic (Claude) ────────────────────────────────────────────────────────

async def _call_anthropic(api_key: str, prompt: str, max_tokens: int) -> str | None:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as exc:
        logger.warning("Anthropic LLM call failed: %s", exc)
        return None


# ── Google Gemini ─────────────────────────────────────────────────────────────

async def _call_gemini(api_key: str, prompt: str, max_tokens: int) -> str | None:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"max_output_tokens": max_tokens, "temperature": 0.4},
        )
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as exc:
        logger.warning("Gemini LLM call failed: %s", exc)
        return None
