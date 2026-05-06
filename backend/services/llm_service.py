"""
Optional LLM enhancement layer (Anthropic Claude).
Set USE_LLM=true and ANTHROPIC_API_KEY in .env to enable.
When disabled, all functions return None and the rule-based results are used as-is.
"""

import logging
import json
import re

from config import get_settings

logger = logging.getLogger(__name__)


async def enhance_analysis(raw_text: str, rule_result: dict) -> dict | None:
    """
    Ask Claude to refine the rule-based analysis.
    Returns a partial dict to merge into rule_result, or None on any failure.
    """
    settings = get_settings()
    if not settings.use_llm or not settings.anthropic_api_key:
        return None

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        prompt = (
            "You are a resume parser. Given the resume text below, return ONLY a JSON object "
            "with these keys: candidate_name (string), email (string), phone (string), "
            "skills (array of strings), education (string), experience_level (junior|mid|senior), "
            "domains (array), strengths (array of short strings), weak_areas (array of short strings).\n\n"
            f"Resume:\n{raw_text[:3000]}"
        )
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except Exception as exc:
        logger.warning("LLM enhancement skipped: %s", exc)

    return None
