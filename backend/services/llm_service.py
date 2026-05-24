"""
Optional LLM enhancement layer — powered by Groq (free tier).
Set USE_LLM=true and GROQ_API_KEY in .env to enable.
When disabled or when Groq fails, all functions return None
and the rule-based results are used as-is — no errors, no crashes.

Model: llama-3.3-70b-versatile (Groq free tier)
"""

import logging
import json
import re

from config import get_settings

logger = logging.getLogger(__name__)


def _groq_client():
    """Return an AsyncGroq client, or None if key is missing."""
    settings = get_settings()
    if not settings.use_llm or not settings.groq_api_key:
        return None
    try:
        from groq import AsyncGroq
        return AsyncGroq(api_key=settings.groq_api_key)
    except ImportError:
        logger.warning("groq package not installed. Run: pip install groq")
        return None


async def _chat(client, prompt: str, max_tokens: int = 1024) -> str | None:
    """Send a single-turn chat to Groq. Returns text or None on any failure."""
    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.warning("Groq API call failed: %s", exc)
        return None


async def enhance_analysis(raw_text: str, rule_result: dict) -> dict | None:
    """
    Ask Groq/Llama to refine the rule-based resume analysis.
    Returns a partial dict to merge into rule_result, or None on any failure.
    """
    client = _groq_client()
    if client is None:
        return None

    existing_skills = ", ".join(rule_result.get("skills", [])[:15])
    existing_projects = [p.get("name", "") for p in rule_result.get("projects", [])[:3]]
    existing_weak = rule_result.get("weak_areas", [])

    prompt = f"""You are an expert technical recruiter analysing a candidate's resume.

Resume text (first 3000 chars):
{raw_text[:3000]}

Rule-based analysis already extracted:
- Skills: {existing_skills}
- Projects: {', '.join(existing_projects) or 'none detected'}
- Weak areas: {', '.join(existing_weak) or 'none'}
- Level: {rule_result.get('experience_level', 'junior')}

Return ONLY a JSON object with these exact keys. Each string under 20 words.

{{
  "candidate_name": "string",
  "email": "string",
  "phone": "string",
  "skills": ["array of skill strings"],
  "education": "string",
  "experience_level": "junior|mid|senior",
  "domains": ["array of domain strings"],
  "strengths": ["3-5 short strength strings"],
  "weak_areas": ["2-4 short gap strings"],
  "strong_skills": ["top 5 most marketable skills"],
  "role_signals": ["2-4 signals inferred from resume"],
  "interview_risks": ["2-3 risk strings"],
  "suggested_probes": ["2-3 probe question strings"],
  "claims_to_verify": [
    {{
      "claim": "specific claim from resume",
      "why_verify": "reason to probe this",
      "probe_question": "exact interview question"
    }}
  ],
  "project_deep_dives": [
    {{
      "project": "project name",
      "why_selected": "one sentence reason",
      "probe_topics": ["topic1", "topic2", "topic3"]
    }}
  ]
}}"""

    content = await _chat(client, prompt, max_tokens=2048)
    if not content:
        return None

    try:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except Exception as exc:
        logger.warning("Failed to parse enhance_analysis response: %s", exc)

    return None


async def select_roles_llm(
    raw_text: str,
    available_roles: list[str],
    candidate_skills: list[str],
    experience_level: str,
) -> dict | None:
    """
    Ask Groq/Llama to select the most suitable roles for this candidate
    and optionally surface one custom role not in the catalog.
    Returns dict with 'selected_roles' and optional 'custom_role', or None on failure.
    Rule-based fallback is used automatically when this returns None.
    """
    client = _groq_client()
    if client is None:
        return None

    roles_list = "\n".join(f"- {r}" for r in available_roles)
    skills_str = ", ".join(candidate_skills[:20])

    prompt = f"""You are a senior career advisor acting as an intelligent agent.

Candidate resume (first 2500 chars):
{raw_text[:2500]}

Detected skills: {skills_str}
Experience level: {experience_level}

Available role catalog:
{roles_list}

Your task:
1. Select the 3-5 roles from the catalog that BEST match this candidate. Order best-fit first.
2. If the resume shows a clear specialisation NOT in the catalog (e.g. "NLP Research Engineer", "Prompt Engineer", "Computer Vision Engineer"), define it as a custom role with resume evidence. Otherwise set custom_role to null.

Return ONLY valid JSON — no explanation, no markdown:
{{
  "selected_roles": ["exact role name from catalog", ...],
  "custom_role": {{
    "name": "Specific Role Title",
    "match_score": <integer 0-100>,
    "why_fit": "One to two sentences using specific resume evidence.",
    "focus_areas": ["topic1", "topic2", "topic3"],
    "probing": ["probe area 1", "probe area 2", "probe area 3"],
    "resume_evidence": ["specific evidence 1", "specific evidence 2", "specific evidence 3"],
    "gaps": ["gap 1", "gap 2"]
  }}
}}

If no custom role applies: "custom_role": null"""

    content = await _chat(client, prompt, max_tokens=1024)
    if not content:
        return None

    try:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            result = json.loads(m.group(0))
            valid = set(available_roles)
            result["selected_roles"] = [
                r for r in result.get("selected_roles", []) if r in valid
            ]
            return result
    except Exception as exc:
        logger.warning("Failed to parse select_roles_llm response: %s", exc)

    return None
