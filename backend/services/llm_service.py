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
