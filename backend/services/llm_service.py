"""
Optional LLM enhancement layer.
Set USE_LLM=true and configure Anthropic or Gemini in .env to enable.
When disabled, all functions return None and the rule-based results are used as-is.
"""

import logging
import json
import re

logger = logging.getLogger(__name__)


async def enhance_analysis(raw_text: str, rule_result: dict) -> dict | None:
    """
    Ask the configured LLM to refine the rule-based analysis.
    Returns a partial dict to merge into rule_result, or None on any failure.
    """
    try:
        from services.llm_client import call_llm

        prompt = (
            "You are a resume parser. Given the resume text below, return ONLY a JSON object "
            "with these keys: candidate_name (string), email (string), phone (string), "
            "skills (array of strings), education (string), experience_level (junior|mid|senior), "
            "domains (array), strengths (array of short strings), weak_areas (array of short strings).\n\n"
            f"Resume:\n{raw_text[:3000]}"
        )
        content = await call_llm(prompt, max_tokens=1024)
        if not content:
            logger.info("LLM resume enhancement unavailable; using rule-based resume analysis.")
            return None

        from services.llm_client import extract_json
        result = extract_json(content)
        if result:
            return result
        logger.warning(
            "LLM resume enhancement returned non-JSON output (len=%d); "
            "using rule-based resume analysis. tail=%s",
            len(content), content[-100:],
        )
    except Exception as exc:
        logger.warning("LLM enhancement skipped: %s: %s", type(exc).__name__, exc)

    return None
