"""
Optional LLM enhancement layer (Anthropic Claude).
Set USE_LLM=true and ANTHROPIC_API_KEY in .env to enable.
When disabled, all functions return None and the rule-based results are used as-is.

With LLM enabled, enhance_analysis() asks Claude to refine and extend the rule-based
resume analysis, including the new interview intelligence fields (claims_to_verify,
project_deep_dives, strong_skills, interview_risks, role_signals).
"""

import logging
import json
import re

from config import get_settings

logger = logging.getLogger(__name__)


async def enhance_analysis(raw_text: str, rule_result: dict) -> dict | None:
    """
    Ask Claude to refine the rule-based resume analysis.
    Returns a partial dict to merge into rule_result, or None on any failure.

    When LLM is enabled this returns enriched versions of:
      - candidate_name, email, phone, skills, education, experience_level,
        domains, strengths, weak_areas  (original fields)
      - strong_skills, role_signals, interview_risks, suggested_probes  (new fields)
      - claims_to_verify, project_deep_dives                             (new intelligence)
    """
    settings = get_settings()
    if not settings.use_llm or not settings.anthropic_api_key:
        return None

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        # Build context from rule-based result to guide Claude
        existing_skills = ", ".join(rule_result.get("skills", [])[:15])
        existing_projects = [
            p.get("name", "") for p in rule_result.get("projects", [])[:3]
        ]
        existing_weak = rule_result.get("weak_areas", [])

        prompt = f"""You are an expert technical recruiter and interview coach analysing a candidate's resume.

Resume text (first 3000 chars):
{raw_text[:3000]}

Rule-based analysis already extracted:
- Skills: {existing_skills}
- Projects: {', '.join(existing_projects) or 'none detected'}
- Weak areas: {', '.join(existing_weak) or 'none'}
- Level: {rule_result.get('experience_level', 'junior')}

Return ONLY a JSON object with these exact keys. Be concise — each string should be under 20 words.

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
  "interview_risks": ["2-3 risk strings for interviewer"],
  "suggested_probes": ["2-3 probe question strings"],
  "claims_to_verify": [
    {{
      "claim": "specific claim from resume",
      "why_verify": "reason to probe this claim",
      "probe_question": "exact interview question to ask"
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

        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except Exception as exc:
        logger.warning("LLM enhancement skipped: %s", exc)

    return None


async def select_roles_llm(
    raw_text: str,
    available_roles: list[str],
    candidate_skills: list[str],
    experience_level: str,
) -> dict | None:
    """
    Ask Claude to act as a career agent: read the resume, pick the most suitable
    roles from the catalog, and optionally surface one custom role the catalog misses.

    Returns:
      {
        "selected_roles": ["Role A", "Role B", ...],   # ordered best-first
        "custom_role": {                                # None if not applicable
          "name": "...", "match_score": int, "why_fit": "...",
          "focus_areas": [...], "probing": [...],
          "resume_evidence": [...], "gaps": [...]
        }
      }
    or None on failure — rule-based fallback is used.
    """
    settings = get_settings()
    if not settings.use_llm or not settings.anthropic_api_key:
        return None

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

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
1. Select the 3-5 roles from the catalog that BEST match this specific candidate. Order them best-fit first.
2. Decide if this candidate has a clear specialisation NOT covered by the catalog \
(e.g. "NLP Research Engineer", "Prompt Engineer", "Computer Vision Engineer"). \
If yes, define it as a custom role with specific evidence from the resume. \
If no clear specialisation exists beyond the catalog, set custom_role to null.

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

        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            result = json.loads(m.group(0))
            valid = set(available_roles)
            result["selected_roles"] = [
                r for r in result.get("selected_roles", []) if r in valid
            ]
            return result
    except Exception as exc:
        logger.warning("LLM role selection skipped: %s", exc)

    return None
