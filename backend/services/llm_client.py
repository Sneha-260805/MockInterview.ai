"""
LLM provider abstraction — supports xAI Grok, Anthropic (Claude), Google Gemini.

Key guarantees
--------------
* call_llm() NEVER raises — it always returns str | None.
* Every call has a hard timeout (LLM_TIMEOUT_SECONDS, default 15 s).
* Failures are logged at WARNING with the provider name, error type, and a
  short prompt hash so the same request can be correlated across log lines.
* Raw prompts / responses are logged at DEBUG when LLM_LOG_PROMPTS=true.
* Provider selection order: configured provider first, then deterministic
  fallback chain (grok → anthropic → gemini) so the demo never silently breaks.

Provider selection (.env):
    LLM_PROVIDER=grok        GROK_API_KEY=xai-...        GROK_MODEL=grok-3
    LLM_PROVIDER=anthropic   ANTHROPIC_API_KEY=sk-ant-...
    LLM_PROVIDER=gemini      GEMINI_API_KEY=AIza...       GEMINI_MODEL=gemini-2.0-flash
    LLM_TIMEOUT_SECONDS=15   LLM_LOG_PROMPTS=false
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time

logger = logging.getLogger(__name__)


# ── JSON extraction helper (shared by callers) ────────────────────────────────

def extract_json(raw: str) -> dict | None:
    """
    Robustly extract the first JSON object from an LLM response.

    Handles:
    - Responses wrapped in markdown code blocks (```json ... ```)
    - Leading / trailing prose
    - Nested braces (uses greedy .* which handles most real cases)

    Returns a dict or None if no valid JSON found.
    """
    if not raw:
        return None

    # 1. Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", raw)
    text = re.sub(r"```", "", text).strip()

    # 2. Try parsing the whole thing (clean responses)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 3. Extract first {...} block — handles leading/trailing prose
    m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 4. Greedy fallback — largest {...} block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError as exc:
            logger.warning(
                "JSON extraction failed on greedy match: %s | raw_tail=%s",
                exc, raw[-120:],
            )

    return None


# ── Prompt ID for log correlation ─────────────────────────────────────────────

def _pid(prompt: str) -> str:
    """8-char MD5 prefix — ties prompt and response log lines together."""
    return hashlib.md5(prompt.encode("utf-8", errors="replace")).hexdigest()[:8]


# ── Internal logging helpers ──────────────────────────────────────────────────

def _log_prompt(prompt: str, pid: str, provider: str) -> None:
    from config import get_settings
    if get_settings().llm_log_prompts:
        logger.debug("[LLM:%s pid=%s] PROMPT (%d chars):\n%s", provider, pid, len(prompt), prompt[:2000])


def _log_response(raw: str | None, pid: str, provider: str, elapsed: float) -> None:
    from config import get_settings
    if get_settings().llm_log_prompts:
        preview = (raw or "")[:500]
        logger.debug("[LLM:%s pid=%s] RESPONSE (%.2fs, %d chars): %s",
                     provider, pid, elapsed, len(raw or ""), preview)


# ── Timeout wrapper ───────────────────────────────────────────────────────────

async def _with_timeout(coro, timeout_s: int, provider: str, pid: str):
    """Wrap a coroutine with an optional timeout. Returns result or raises."""
    if timeout_s <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=float(timeout_s))
    except asyncio.TimeoutError:
        logger.warning(
            "[LLM:%s pid=%s] Request timed out after %ds", provider, pid, timeout_s
        )
        raise


# ── Public entry point ────────────────────────────────────────────────────────

async def call_llm(prompt: str, max_tokens: int = 600) -> str | None:
    """
    Send a single-turn prompt to the configured LLM provider.

    Returns the response text (str) or None when:
    - LLM is disabled (USE_LLM=false)
    - No API key is configured for any provider
    - The provider call fails (network, auth, timeout, parse error)

    Never raises — all errors are logged and None is returned so callers can
    fall through to their deterministic fallback path.
    """
    from config import get_settings
    settings = get_settings()

    if not settings.use_llm:
        logger.debug("LLM disabled (USE_LLM=false); using deterministic fallback.")
        return None

    if not settings.has_llm_configured:
        logger.warning(
            "USE_LLM=true but no API key found for provider '%s'. "
            "Set GROK_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY in your .env.",
            settings.llm_provider,
        )
        return None

    pid     = _pid(prompt)
    timeout = settings.llm_timeout_seconds

    # Build the ordered provider list: configured provider first, then fallbacks
    provider = settings.llm_provider.lower()
    _all = _provider_chain(provider, settings)

    for pname, pfunc, pkey in _all:
        if not pkey:
            continue  # skip providers with no key
        _log_prompt(prompt, pid, pname)
        t0 = time.monotonic()
        try:
            result = await pfunc(pkey, prompt, max_tokens, timeout, pid)
            elapsed = time.monotonic() - t0
            if result is not None:
                _log_response(result, pid, pname, elapsed)
                logger.info("[LLM:%s pid=%s] OK (%.2fs, %d chars)", pname, pid, elapsed, len(result))
                return result
            # Provider returned None (soft failure) — try next in chain
            logger.warning("[LLM:%s pid=%s] returned empty response (%.2fs); trying next provider",
                           pname, pid, time.monotonic() - t0)
        except Exception as exc:
            logger.warning("[LLM:%s pid=%s] call failed: %s: %s",
                           pname, pid, type(exc).__name__, exc)
            # Continue to next provider in chain

    logger.warning("[LLM pid=%s] All providers exhausted; using deterministic fallback.", pid)
    return None


def _provider_chain(primary: str, settings) -> list[tuple]:
    """
    Return ordered list of (provider_name, call_func, api_key) tuples.
    Primary provider is first; others follow as silent fallback.
    """
    registry = {
        "grok":      (_call_grok,      settings.grok_api_key),
        "groq":      (_call_groq_ai,   settings.groq_api_key),
        "anthropic": (_call_anthropic, settings.anthropic_api_key),
        "gemini":    (_call_gemini,    settings.gemini_api_key),
    }
    # Start with the configured primary provider
    order = [primary] + [k for k in ["grok", "groq", "anthropic", "gemini"] if k != primary]
    return [(name, *registry[name]) for name in order if name in registry]


# ── Anthropic (Claude) ────────────────────────────────────────────────────────

async def _call_anthropic(api_key: str, prompt: str, max_tokens: int,
                          timeout: int, pid: str) -> str | None:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await _with_timeout(
            client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout, "anthropic", pid,
        )
        text = response.content[0].text
        return text if text else None
    except ImportError:
        logger.error("[LLM:anthropic pid=%s] 'anthropic' package not installed. "
                     "Run: pip install anthropic", pid)
        return None
    except Exception as exc:
        logger.warning("[LLM:anthropic pid=%s] %s: %s", pid, type(exc).__name__, exc)
        return None


# ── Google Gemini ─────────────────────────────────────────────────────────────

async def _call_gemini(api_key: str, prompt: str, max_tokens: int,
                       timeout: int, pid: str) -> str | None:
    """
    Gemini via google-genai SDK (pip install google-genai>=1.0.0).
    Falls back to google-generativeai (older SDK) if not installed.
    """
    from config import get_settings
    model_name = get_settings().gemini_model or "gemini-2.0-flash"

    # Try newer google-genai SDK first
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
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
        logger.warning("[LLM:gemini pid=%s] new SDK returned no text for model %s", pid, model_name)
        return None
    except ImportError:
        pass  # fall through to older SDK
    except Exception as exc:
        logger.warning("[LLM:gemini pid=%s] new SDK error (%s: %s); trying legacy", pid, type(exc).__name__, exc)

    # Fallback: older google-generativeai SDK
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={"max_output_tokens": max_tokens, "temperature": 0.4},
        )
        response = await _with_timeout(
            model.generate_content_async(prompt),
            timeout, "gemini", pid,
        )
        try:
            text = response.text
            return text if text else None
        except Exception:
            if response.candidates:
                parts = response.candidates[0].content.parts
                return "".join(p.text for p in parts if hasattr(p, "text")) or None
            return None
    except ImportError:
        logger.error("[LLM:gemini pid=%s] No Gemini SDK found. pip install google-genai", pid)
        return None
    except Exception as exc:
        logger.warning("[LLM:gemini pid=%s] %s: %s", pid, type(exc).__name__, exc)
        return None


# ── xAI Grok ─────────────────────────────────────────────────────────────────

async def _call_grok(api_key: str, prompt: str, max_tokens: int,
                     timeout: int, pid: str) -> str | None:
    """
    Grok uses an OpenAI-compatible API endpoint.
    Model is configurable via GROK_MODEL env var (default: grok-3).
    """
    try:
        from openai import AsyncOpenAI  # type: ignore
        from config import get_settings
        model = get_settings().grok_model or "grok-3"

        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
        response = await _with_timeout(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.4,
            ),
            timeout, "grok", pid,
        )
        text = response.choices[0].message.content
        return text if text else None
    except ImportError:
        logger.error("[LLM:grok pid=%s] 'openai' package not installed. "
                     "Run: pip install openai", pid)
        return None
    except Exception as exc:
        logger.warning("[LLM:grok pid=%s] %s: %s", pid, type(exc).__name__, exc)
        return None


# ── Groq.ai (free tier) ──────────────────────────────────────────────────────

async def _call_groq_ai(api_key: str, prompt: str, max_tokens: int,
                        timeout: int, pid: str) -> str | None:
    """
    Groq.ai free tier using OpenAI-compatible API.
    Model is configurable via GROQ_MODEL env var (default: mixtral-8x7b-32768).
    """
    try:
        from openai import AsyncOpenAI  # type: ignore
        from config import get_settings
        model = get_settings().groq_model or "mixtral-8x7b-32768"

        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        response = await _with_timeout(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.4,
            ),
            timeout, "groq", pid,
        )
        text = response.choices[0].message.content
        return text if text else None
    except ImportError:
        logger.error("[LLM:groq pid=%s] 'openai' package not installed. "
                     "Run: pip install openai", pid)
        return None
    except Exception as exc:
        logger.warning("[LLM:groq pid=%s] %s: %s", pid, type(exc).__name__, exc)
        return None
