"""
LLM provider abstraction — supports Anthropic (Claude) and Google Gemini.

Usage in agents:
    from services.llm_client import call_llm
    raw = await call_llm(prompt, max_tokens=600)
    if raw is None:
        return None   # fall back to rule-based path

Provider selection (.env):
    LLM_PROVIDER=anthropic   ANTHROPIC_API_KEY=sk-ant-...
    LLM_PROVIDER=gemini      GEMINI_API_KEY=AIza... GEMINI_MODEL=gemini-2.0-flash
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
        return await _call_gemini(
            settings.gemini_api_key,
            getattr(settings, "gemini_model", "gemini-2.0-flash"),
            prompt,
            max_tokens,
        )

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

async def _call_gemini(api_key: str, model_name: str, prompt: str, max_tokens: int) -> str | None:
    try:
        import asyncio
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        def _generate():
            return client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.4,
                ),
            )

        response = await asyncio.to_thread(_generate)
        text = getattr(response, "text", None)
        if text:
            return text

        logger.warning(
            "Gemini LLM call returned no text. Model=%s Response=%r",
            model_name,
            response,
        )
        return None
    except Exception as exc:
        logger.warning("Gemini LLM call failed for model %s: %s", model_name, exc)
        return None
