"""
Optional LLM enhancement layer.
Set USE_LLM=true and configure Anthropic or Gemini in .env to enable.
When disabled, all functions return None and the rule-based results are used as-is.

Two public functions:
  enhance_analysis()         — asks LLM to refine basic extraction fields
  build_interview_intelligence() — second-stage reasoning; returns interview-
                                   intelligence fields (claims, risks, probes…)
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


# ── Second-stage: interview intelligence reasoning ────────────────────────────

async def build_interview_intelligence(analysis: dict) -> dict | None:
    """
    Second-stage LLM reasoning over the rule-extracted ResumeAnalysis.

    Accepts the analysis dict (output of resume_agent.analyze + optional
    enhance_analysis merge) and asks the configured LLM to reason about the
    candidate from an interview-intelligence perspective.

    Returns a dict with the intelligence keys ready to be merged into
    ResumeAnalysis, or None on any failure (LLM disabled, API error, bad JSON).
    The existing extraction fields are never touched.
    """
    try:
        from services.llm_client import call_llm, extract_json

        context = _build_intelligence_context(analysis)
        prompt  = _build_intelligence_prompt(context)

        raw = await call_llm(prompt, max_tokens=1500)
        if not raw:
            logger.info("LLM intelligence stage unavailable; skipping.")
            return None

        data = extract_json(raw)
        if not data:
            logger.warning(
                "LLM intelligence returned non-JSON (len=%d); skipping. tail=%s",
                len(raw), raw[-120:],
            )
            return None

        parsed = _parse_intelligence_output(data)
        logger.info(
            "LLM intelligence stage OK: %d claims, %d deep-dives, %d risks",
            len(parsed.get("claims_to_verify", [])),
            len(parsed.get("project_deep_dives", [])),
            len(parsed.get("interview_risks", [])),
        )
        return parsed

    except Exception as exc:
        logger.warning("LLM intelligence stage failed: %s: %s", type(exc).__name__, exc)
        return None


def _build_intelligence_context(analysis: dict) -> str:
    """
    Produce a concise, structured text summary of the extracted resume data.
    Passed verbatim inside the LLM prompt so it reasons only from evidence.
    """
    lines: list[str] = []

    lines.append(f"Experience level: {analysis.get('experience_level', 'unknown')}")

    skills = analysis.get("skills", [])
    if skills:
        display = ", ".join(skills[:15])
        extra   = f" (and {len(skills) - 15} more)" if len(skills) > 15 else ""
        lines.append(f"Skills: {display}{extra}")

    projects = analysis.get("projects", [])
    if projects:
        lines.append("Projects:")
        for p in projects[:5]:
            techs   = ", ".join((p.get("technologies") or [])[:6])
            summary = (p.get("summary") or "")[:100]
            lines.append(f"  - {p.get('name', 'Unnamed')}: {techs} | \"{summary}\"")

    work_exp = analysis.get("work_experience", [])
    if work_exp:
        lines.append("Work Experience:")
        for w in work_exp[:3]:
            resp = "; ".join((w.get("responsibilities") or [])[:2])
            lines.append(
                f"  - {w.get('role', '')} at {w.get('company', '')} "
                f"({w.get('duration', '')}): {resp}"
            )

    certs = analysis.get("certifications", [])
    if certs:
        cert_strs = [
            f"{c.get('name', '')} ({c.get('issuer', '')})" for c in certs[:3]
        ]
        lines.append(f"Certifications: {', '.join(cert_strs)}")

    achievements = analysis.get("achievements", [])
    if achievements:
        lines.append(f"Achievements: {'; '.join(achievements[:3])}")

    domains = analysis.get("domains", [])
    if domains:
        lines.append(f"Domains: {', '.join(domains)}")

    strengths = analysis.get("strengths", [])
    if strengths:
        lines.append(f"Rule-based strengths: {', '.join(strengths)}")

    weak_areas = analysis.get("weak_areas", [])
    if weak_areas:
        lines.append(f"Rule-based weak areas: {', '.join(weak_areas)}")

    return "\n".join(lines)


def _build_intelligence_prompt(context: str) -> str:
    return (
        "You are an expert technical interview strategist reviewing a candidate summary "
        "produced by a resume parser.\n\n"
        "TASK: Reason about this candidate from the perspective of a senior technical "
        "interviewer. Identify strengths backed by evidence, gaps, claims to verify, "
        "best projects for deep-dive questions, and likely interview risks.\n\n"
        "CRITICAL RULES:\n"
        "1. Reason ONLY from the evidence in CANDIDATE SUMMARY below. "
        "Do NOT hallucinate or fabricate any facts.\n"
        "2. If evidence for a claim is thin or absent, say so explicitly in why_verify.\n"
        "3. Return ONLY a single valid JSON object — no markdown fences, no prose, "
        "no explanation outside the JSON.\n"
        "4. Keep every individual string value under 150 characters.\n"
        "5. Each top-level array: 2–5 items (fewer is fine when evidence is limited).\n\n"
        f"CANDIDATE SUMMARY:\n{context}\n\n"
        "Return exactly this JSON structure (no extra keys):\n"
        "{\n"
        '  "strong_skills": ["skill clearly evidenced by ≥1 project or role"],\n'
        '  "weak_or_missing_areas": ["gap vs claimed skill set or typical role needs"],\n'
        '  "role_signals": ["one-line role-fit signal inferred from evidence"],\n'
        '  "claims_to_verify": [\n'
        '    {\n'
        '      "claim": "specific resume claim that needs verification",\n'
        '      "why_verify": "why the evidence is thin, absent, or ambiguous",\n'
        '      "probe_question": "exact interview question to verify this claim"\n'
        '    }\n'
        '  ],\n'
        '  "project_deep_dives": [\n'
        '    {\n'
        '      "project": "project name from the summary",\n'
        '      "why_selected": "why this project reveals the most about technical depth",\n'
        '      "probe_topics": ["technical area 1", "technical area 2", "technical area 3"]\n'
        '    }\n'
        '  ],\n'
        '  "interview_risks": ["risk or red flag a technical interviewer should know"],\n'
        '  "suggested_interview_probes": ["specific question to assess depth beyond the resume"]\n'
        "}"
    )


def _parse_intelligence_output(data: dict) -> dict:
    """
    Validate and sanitise the raw LLM output dict.
    Guarantees every returned list contains only the expected types/shapes.
    Never raises — bad items are silently dropped.
    """
    def _str_list(val, cap: int = 6) -> list[str]:
        if not isinstance(val, list):
            return []
        return [str(x).strip() for x in val if isinstance(x, str) and str(x).strip()][:cap]

    def _claims(val) -> list[dict]:
        if not isinstance(val, list):
            return []
        out: list[dict] = []
        for item in val:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim", "")).strip()
            why   = str(item.get("why_verify", "")).strip()
            probe = str(item.get("probe_question", "")).strip()
            if claim and why and probe:
                out.append({"claim": claim, "why_verify": why, "probe_question": probe})
        return out[:5]

    def _deep_dives(val) -> list[dict]:
        if not isinstance(val, list):
            return []
        out: list[dict] = []
        for item in val:
            if not isinstance(item, dict):
                continue
            project = str(item.get("project", "")).strip()
            why     = str(item.get("why_selected", "")).strip()
            topics  = item.get("probe_topics", [])
            topics  = [str(t).strip() for t in topics if str(t).strip()][:5] \
                      if isinstance(topics, list) else []
            if project and why:
                out.append({"project": project, "why_selected": why, "probe_topics": topics})
        return out[:3]

    return {
        "strong_skills":             _str_list(data.get("strong_skills")),
        "weak_or_missing_areas":     _str_list(data.get("weak_or_missing_areas")),
        "role_signals":              _str_list(data.get("role_signals")),
        "claims_to_verify":          _claims(data.get("claims_to_verify")),
        "project_deep_dives":        _deep_dives(data.get("project_deep_dives")),
        "interview_risks":           _str_list(data.get("interview_risks")),
        "suggested_interview_probes": _str_list(data.get("suggested_interview_probes")),
    }


# ── Extraction normalizer (project cleanup + skill expansion) ─────────────────

async def normalize_resume_extraction(
    projects: list[dict],
    skills: list[str],
    raw_projects_text: str,
    raw_skills_text: str,
) -> dict | None:
    """
    Second-stage Gemini cleanup for rule-extracted projects and skills.

    Problems it fixes:
    - GitHub / demo URLs parsed as standalone projects
    - Description bullets grouped as separate projects
    - Technology names in informal formats (Node→Node.js, Mongo→MongoDB)
    - Skills missed due to pipe/slash/comma formatting in the skills section
    - Fragmented project entries missing their technologies

    Returns {"projects": [...], "skills": [...]} with plain dicts ready for
    resume_agent._convert_normalized_projects() to turn into Project objects,
    or None on any failure so the caller falls back to the raw extraction.
    """
    try:
        from services.llm_client import call_llm, extract_json

        prompt = _build_normalization_prompt(
            projects_json=json.dumps(projects[:6], indent=2),
            raw_projects_text=raw_projects_text[:900],
            skills_list=skills,
            raw_skills_text=raw_skills_text[:450],
        )

        raw = await call_llm(prompt, max_tokens=1200)
        if not raw:
            logger.info("LLM normalization unavailable; using raw extraction.")
            return None

        data = extract_json(raw)
        if not data:
            logger.warning(
                "LLM normalization returned non-JSON (len=%d); using raw extraction. tail=%s",
                len(raw), raw[-120:],
            )
            return None

        # Pass the raw resume text so _parse_normalized_skills can verify
        # that any new skill Gemini returns actually appears in the source text.
        evidence_text = raw_skills_text + " " + raw_projects_text
        result = {
            "projects": _parse_normalized_projects(data.get("projects", [])),
            "skills":   _parse_normalized_skills(
                data.get("skills", []), skills, raw_text=evidence_text
            ),
        }
        logger.info(
            "LLM normalization OK: %d projects, %d skills",
            len(result["projects"]), len(result["skills"]),
        )
        return result

    except Exception as exc:
        logger.warning("LLM normalization failed: %s: %s", type(exc).__name__, exc)
        return None


def _build_normalization_prompt(
    projects_json: str,
    raw_projects_text: str,
    skills_list: list[str],
    raw_skills_text: str,
) -> str:
    return (
        "You are a resume parser cleanup assistant. Your job is to restructure and "
        "normalize already-extracted resume data — NOT to re-parse from scratch.\n\n"
        "CRITICAL RULES:\n"
        "1. Only restructure data present in the inputs. Do NOT invent facts.\n"
        "2. Return ONLY a single valid JSON object — no markdown, no prose.\n"
        "3. Project names MUST come from the raw text, not be invented.\n"
        "4. Merge any URL-only entries or lone description fragments into their "
        "nearest parent project.\n"
        "5. GitHub/demo URLs must be attached to the correct project's github_url "
        "field — never left as a standalone entry.\n"
        "6. Normalize tech abbreviations: Node→Node.js, Mongo→MongoDB, "
        "JS→JavaScript, TS→TypeScript, Postgres→PostgreSQL, k8s→Kubernetes, "
        "Express→Express.js, React.js→React, Next→Next.js.\n"
        "7. Expand slash/pipe-separated tech stacks: "
        "'React | Node | Mongo' → ['React', 'Node.js', 'MongoDB'].\n"
        "8. Do NOT duplicate projects. If unsure whether two entries are the same "
        "project, merge them.\n"
        "9. STRICTLY PROHIBITED — never add technologies or skills unless the exact "
        "word(s) appear verbatim in the raw input texts provided below:\n"
        "   • HTML, CSS — do NOT infer from Streamlit, Dash, Gradio, Bokeh, or any "
        "Python data-visualisation or dashboard library.\n"
        "   • React, Vue, Angular, Next.js, or any other frontend JavaScript framework "
        "— do NOT infer from Python web projects.\n"
        "   • JavaScript or TypeScript — only include if the exact words 'JavaScript' "
        "or 'TypeScript' (or 'JS'/'TS') appear in the raw text.\n"
        "   • Any technology not literally present in the input texts.\n"
        "10. Streamlit / Gradio / Plotly Dash / Bokeh are Python data-science tools. "
        "Never infer HTML, CSS, JavaScript, React, or any frontend framework from them.\n\n"
        f"EXTRACTED PROJECTS (may contain fragments or URL-only entries):\n"
        f"{projects_json}\n\n"
        f"RAW PROJECTS SECTION (source of truth for merging):\n"
        f"{raw_projects_text}\n\n"
        f"EXTRACTED SKILLS: {', '.join(skills_list[:30])}\n\n"
        f"RAW SKILLS SECTION (may have pipe/comma/slash-separated stacks):\n"
        f"{raw_skills_text}\n\n"
        "Return exactly this JSON structure:\n"
        "{\n"
        '  "projects": [\n'
        '    {\n'
        '      "name": "project title",\n'
        '      "description": ["bullet 1", "bullet 2"],\n'
        '      "technologies": ["Tech1", "Tech2"],\n'
        '      "github_url": "https://... or empty string",\n'
        '      "duration": "date range or empty string"\n'
        '    }\n'
        '  ],\n'
        '  "skills": ["CanonicalSkill1", "CanonicalSkill2"]\n'
        "}"
    )


def _parse_normalized_projects(raw: list) -> list[dict]:
    """Validate and sanitise Gemini project output. Returns list of plain dicts."""
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name or len(name) < 2:
            continue

        desc = item.get("description", [])
        if isinstance(desc, str):
            desc = [desc]
        elif not isinstance(desc, list):
            desc = []
        desc = [str(d).strip() for d in desc if str(d).strip()][:6]

        techs = item.get("technologies", [])
        if isinstance(techs, str):
            techs = [t.strip() for t in re.split(r"[,|/]", techs)]
        elif not isinstance(techs, list):
            techs = []
        techs = [str(t).strip() for t in techs if str(t).strip()][:8]

        github_url = str(item.get("github_url", "")).strip() or ""
        duration   = str(item.get("duration", "")).strip() or ""

        result.append({
            "name":        name,
            "description": desc,
            "technologies": techs,
            "github_url":  github_url,
            "duration":    duration,
        })
    return result[:6]


def _parse_normalized_skills(
    raw: list,
    original: list[str],
    raw_text: str = "",
) -> list[str]:
    """
    Evidence-based filter for LLM-returned skills.

    Accepts a skill from Gemini ONLY when at least one of these holds:
      (a) It already appears in the rule-based original extraction (case-insensitive).
      (b) It is a canonical normalization of an original skill — e.g. Gemini returns
          "Node.js" for a resume that literally said "NodeJS" which the regex missed
          (detected via 5-char prefix overlap between the two forms).
      (c) The stripped skill name (alphanumeric only) appears in the raw resume text
          sections (skills section + projects section) that were passed in.

    Skills that don't meet any criterion are silently dropped.  This prevents Gemini
    from inventing technologies (React, HTML, CSS…) for Python-only resumes.
    """
    if not isinstance(raw, list) or not raw:
        return original

    original_lower = {s.lower() for s in original}
    # Normalise raw text once for fast substring checks
    raw_plain = re.sub(r"[^a-z0-9]", "", raw_text.lower()) if raw_text else ""

    result: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if not s or len(s) > 40:
            continue
        s_lower = s.lower()

        # (a) Already in original extraction
        if s_lower in original_lower:
            result.append(s)
            continue

        # (b) Canonical normalization: 5-char prefix overlap with an existing skill
        # e.g. "postgresql" ↔ "postgres", "node.js" ↔ "nodejs", "react.js" ↔ "react"
        if any(
            len(s_lower) >= 4 and len(o) >= 4
            and (s_lower[:5] in o or o[:5] in s_lower)
            for o in original_lower
        ):
            result.append(s)
            continue

        # (c) Appears literally in raw skills/projects text (handles abbreviation variants
        # the rule-based regex missed, e.g. "NodeJS" in text → Gemini returns "Node.js")
        if raw_plain:
            s_plain = re.sub(r"[^a-z0-9]", "", s_lower)
            if len(s_plain) >= 4 and s_plain in raw_plain:
                result.append(s)
                continue

        # No evidence found → likely hallucinated; drop
        logger.debug("Rejected LLM-added skill not evidenced in resume: %s", s)

    return result if result else original


# ── Role recommendation enrichment ───────────────────────────────────────────

async def enrich_roles_with_gemini(analysis: dict, roles: list[dict]) -> dict | None:
    """
    Second-stage Gemini reasoning over the rule-scored role recommendations.

    Accepts the analysis dict and list of role dicts (from RoleMatch.model_dump()).
    Returns a mapping of role_name → enrichment_data ready to be merged into
    RoleMatch fields, or None on any failure (LLM disabled, API error, bad JSON).
    Existing role scores and evidence are never touched.
    """
    try:
        from services.llm_client import call_llm, extract_json

        prompt = _build_role_enrichment_prompt(analysis, roles)
        raw = await call_llm(prompt, max_tokens=1500)
        if not raw:
            logger.info("LLM role enrichment unavailable; using rule-based role output.")
            return None

        data = extract_json(raw)
        if not data:
            logger.warning(
                "LLM role enrichment returned non-JSON (len=%d); skipping. tail=%s",
                len(raw), raw[-120:],
            )
            return None

        expected = [r["role"] for r in roles]
        parsed = _parse_role_enrichments(data, expected)
        logger.info("LLM role enrichment OK: %d roles enriched", len(parsed))
        return parsed

    except Exception as exc:
        logger.warning("LLM role enrichment failed: %s: %s", type(exc).__name__, exc)
        return None


def _build_role_enrichment_prompt(analysis: dict, roles: list[dict]) -> str:
    skills = analysis.get("strong_skills") or analysis.get("skills", [])
    skills_str = ", ".join(skills[:20])

    role_signals = analysis.get("role_signals", [])
    interview_risks = analysis.get("interview_risks", [])
    experience_level = analysis.get("experience_level", "unknown")

    roles_text = []
    for r in roles:
        roles_text.append(
            f'- "{r["role"]}" (score: {r["match_score"]}, '
            f'evidence: {json.dumps(r.get("evidence", [])[:2])}, '
            f'reduced_by: {json.dumps(r.get("reduced_by", [])[:2])})'
        )
    roles_str = "\n".join(roles_text)

    role_signals_str = "; ".join(role_signals[:3]) if role_signals else "not available"
    risks_str = "; ".join(interview_risks[:2]) if interview_risks else "none identified"

    return (
        "You are an expert technical career advisor reviewing a candidate's role recommendations.\n\n"
        "TASK: For each recommended role, provide a concise evidence-based explanation of fit, "
        "classify as realistic or stretch, identify resume evidence supporting the fit, "
        "gaps to address, and what the interview will validate.\n\n"
        "CRITICAL RULES:\n"
        "1. Only use the provided candidate information. Do NOT invent facts.\n"
        "2. role_type MUST be 'realistic' only if score ≥ 75 AND the candidate has at least "
        "one concrete signal (skill, project, or experience) for this role. Otherwise 'stretch'.\n"
        "3. Return ONLY valid JSON — no markdown fences, no prose.\n"
        "4. Keep all string values under 150 characters.\n"
        "5. Each array: 2–4 items.\n"
        "6. Only enrich roles listed in RECOMMENDED ROLES — do NOT invent new roles.\n"
        "7. Do NOT infer frontend/HTML/CSS/JavaScript/React experience from Python data tools "
        "such as Streamlit, Dash, Gradio, or Bokeh — these are data-visualisation tools, "
        "not frontend frameworks.\n"
        "8. Do NOT add any technology to 'resume_evidence' unless it appears verbatim in "
        "the candidate's skills list above.\n"
        "9. When skill evidence is thin or indirect, set role_type to 'stretch' rather than "
        "'realistic', and clearly note the gap in 'gaps'.\n"
        "10. Reason strictly from the provided skills list and evidence. Do not assume "
        "technologies from job-title conventions or popular combinations.\n\n"
        f"CANDIDATE PROFILE:\n"
        f"Experience level: {experience_level}\n"
        f"Skills: {skills_str}\n"
        f"Role signals from intelligence: {role_signals_str}\n"
        f"Interview risks: {risks_str}\n\n"
        f"RECOMMENDED ROLES:\n{roles_str}\n\n"
        "Return exactly this JSON structure:\n"
        "{\n"
        '  "roles": [\n'
        '    {\n'
        '      "role": "exact role name from RECOMMENDED ROLES",\n'
        '      "role_type": "realistic or stretch",\n'
        '      "why_fit": "2-sentence explanation grounded in candidate evidence",\n'
        '      "resume_evidence": ["evidence point 1", "evidence point 2"],\n'
        '      "gaps": ["gap 1", "gap 2"],\n'
        '      "interview_focus": ["focus area 1", "focus area 2"],\n'
        '      "what_interview_will_validate": ["thing 1", "thing 2"]\n'
        '    }\n'
        '  ]\n'
        "}"
    )


def _parse_role_enrichments(data: dict, expected_roles: list[str]) -> dict[str, dict]:
    """
    Validate and map Gemini role enrichment output.
    Only accepts roles present in expected_roles — prevents hallucination.
    Returns {role_name: {role_type, why_fit, resume_evidence, gaps, interview_focus,
                         what_interview_will_validate}}
    """
    roles_raw = data.get("roles", [])
    if not isinstance(roles_raw, list):
        return {}

    expected_lower = {r.lower(): r for r in expected_roles}
    result: dict[str, dict] = {}

    def _str_list(val, cap: int = 4) -> list[str]:
        if not isinstance(val, list):
            return []
        return [str(x).strip() for x in val if isinstance(x, str) and str(x).strip()][:cap]

    for item in roles_raw:
        if not isinstance(item, dict):
            continue
        role_name = str(item.get("role", "")).strip()
        if not role_name:
            continue

        # Exact match first; then prefix fuzzy to handle minor name variations
        canonical = expected_lower.get(role_name.lower())
        if not canonical:
            for exp_lower, exp_orig in expected_lower.items():
                if role_name.lower()[:8] in exp_lower or exp_lower[:8] in role_name.lower():
                    canonical = exp_orig
                    break
        if not canonical:
            logger.debug("Skipping unexpected role from LLM enrichment: %s", role_name)
            continue

        role_type = str(item.get("role_type", "realistic")).strip().lower()
        if role_type not in ("realistic", "stretch"):
            role_type = "realistic"

        result[canonical] = {
            "role_type": role_type,
            "why_fit": str(item.get("why_fit", "")).strip()[:300],
            "resume_evidence": _str_list(item.get("resume_evidence")),
            "gaps": _str_list(item.get("gaps")),
            "interview_focus": _str_list(item.get("interview_focus")),
            "what_interview_will_validate": _str_list(item.get("what_interview_will_validate")),
        }

    return result
