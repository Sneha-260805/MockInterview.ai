"""
Phase 7 — Job Recommendation agent.

Loads jobs from sample_data/sample_jobs.json, scores each job against
the candidate's extracted skills, and returns the top matches with a
natural-language explanation of why each job is a good fit.

is_live flag
------------
Jobs fetched from Adzuna (live API) are tagged is_live=True.
Jobs from sample_data/sample_jobs.json are tagged is_live=False.
The JobMatch response includes this field so the UI can clearly show
"Live Posting" vs "Demo / Sample Job" — no false claims.

Matching algorithm
------------------
1. Normalise both candidate skills and job required_skills to lowercase.
2. Exact canonical match (alias lookup handles react/reactjs, postgres/postgresql, etc.)
3. Raw score = len(matched) / len(required) × 100.
4. Experience-level bonus (+5 pts) when the candidate's seniority fits.
5. Cap at 95 to avoid unrealistic perfect scores.
6. Return the top-N jobs above a minimum threshold, sorted by score desc.

Optional LLM path
-----------------
When USE_LLM=true and an Anthropic API key is set, the agent requests a
richer, personalised why_fit blurb from Claude. Rule-based why_fit is
always generated as the fallback.
"""

import json
import logging
from pathlib import Path

from models.jobs import JobListing, JobMatch, JobRecommendationResponse

logger = logging.getLogger(__name__)

_JOBS_PATH  = Path(__file__).parent.parent / "sample_data" / "sample_jobs.json"
_TOP_N      = 10
_MIN_SCORE  = 20

# ── Normalised skill aliases ───────────────────────────────────────────────────

_ALIASES: dict[str, list[str]] = {
    "react":          ["react", "reactjs", "react.js"],
    "node":           ["node", "node.js", "nodejs"],
    "javascript":     ["javascript", "js"],
    "typescript":     ["typescript", "ts"],
    "python":         ["python", "py"],
    "postgres":       ["postgresql", "postgres"],
    "mongo":          ["mongodb", "mongo"],
    "redis":          ["redis"],
    "docker":         ["docker", "containers"],
    "kubernetes":     ["kubernetes", "k8s"],
    "aws":            ["aws", "amazon web services"],
    "gcp":            ["gcp", "google cloud", "google cloud platform"],
    "azure":          ["azure", "microsoft azure"],
    "tensorflow":     ["tensorflow", "tf"],
    "pytorch":        ["pytorch", "torch"],
    "sklearn":        ["scikit-learn", "sklearn"],
    "pandas":         ["pandas"],
    "numpy":          ["numpy"],
    "spark":          ["spark", "apache spark", "pyspark"],
    "kafka":          ["kafka", "apache kafka"],
    "airflow":        ["airflow", "apache airflow"],
    "dbt":            ["dbt"],
    "graphql":        ["graphql"],
    "nextjs":         ["next.js", "nextjs"],
    "vue":            ["vue", "vuejs", "vue.js"],
    "angular":        ["angular"],
    "django":         ["django"],
    "flask":          ["flask"],
    "fastapi":        ["fastapi", "fast api"],
    "express":        ["express", "expressjs", "express.js"],
    "mlflow":         ["mlflow"],
    "terraform":      ["terraform"],
    "cicd":           ["ci/cd", "cicd", "ci-cd", "jenkins", "github actions"],
    "linux":          ["linux", "unix"],
    "sql":            ["sql", "mysql", "sqlite"],
    "snowflake":      ["snowflake"],
    "git":            ["git"],
    "rest":           ["rest apis", "rest api", "rest", "restful"],
    "redux":          ["redux", "redux toolkit"],
    "flutter":        ["flutter"],
    "swift":          ["swift"],
    "kotlin":         ["kotlin"],
    "java":           ["java"],
    "go":             ["go", "golang"],
    "tailwind":       ["tailwind css", "tailwind"],
    "security":       ["security", "cybersecurity", "infosec"],
    "nlp":            ["nlp", "natural language processing"],
    "cuda":           ["cuda", "gpu"],
    "research":       ["research", "ml research"],
    "bert":           ["bert", "transformers"],
    "llm":            ["llm", "large language models", "langchain"],
    "opencv":         ["opencv", "cv2"],
    "prometheus":     ["prometheus"],
    "microservices":  ["microservices", "micro-services"],
    "statistics":     ["statistics", "statistical analysis", "stats"],
    "matplotlib":     ["matplotlib", "seaborn", "plotly"],
    "core data":      ["core data"],
    "rxjs":           ["rxjs"],
    "celery":         ["celery"],
    "storybook":      ["storybook"],
    "firebase":       ["firebase"],
    "figma":          ["figma"],
    "bash":           ["bash", "shell", "shell scripting"],
    "grpc":           ["grpc"],
    "testing":        ["testing", "jest", "pytest", "unit testing"],
    "mvvm":           ["mvvm", "architecture"],
}

_ALIAS_LOOKUP: dict[str, str] = {}
for _canon, _variants in _ALIASES.items():
    for _v in _variants:
        _ALIAS_LOOKUP[_v] = _canon


def _canonical(skill: str) -> str:
    sl = skill.lower().strip()
    return _ALIAS_LOOKUP.get(sl, sl)


def _load_jobs() -> list[JobListing]:
    try:
        with _JOBS_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return [JobListing(**j) for j in raw]
    except Exception as exc:
        logger.error("Failed to load sample_jobs.json: %s", exc)
        return []


# ── Experience-level matching ─────────────────────────────────────────────────

_EXP_BANDS = {
    "junior":  {"0-1 years", "0-2 years", "1-2 years"},
    "mid":     {"1-3 years", "2-3 years", "2-4 years"},
    "senior":  {"3-5 years", "4-6 years", "5+ years", "5-7 years"},
}


def _exp_bonus(candidate_level: str, job_exp: str) -> int:
    level = candidate_level.lower()
    target_bands = _EXP_BANDS.get(level, set())
    return 5 if job_exp in target_bands else 0


# ── Skill matching ────────────────────────────────────────────────────────────

def _match_skills(
    candidate_canonicals: set[str],
    required_skills: list[str],
) -> tuple[list[str], list[str]]:
    matched: list[str] = []
    missing: list[str] = []
    for req in required_skills:
        req_canon = _canonical(req)
        if req_canon in candidate_canonicals:
            matched.append(req)
        else:
            missing.append(req)
    return matched, missing


def _score(matched: list[str], total: int, exp_bonus: int) -> int:
    if total == 0:
        return 50
    raw = round(len(matched) / total * 100) + exp_bonus
    return min(raw, 95)


# ── Application readiness ─────────────────────────────────────────────────────

def _application_readiness(matched: list[str], missing: list[str], score: int) -> str:
    top_miss = missing[:2]
    if score >= 80:
        if missing:
            return (
                f"Strong match — apply now. Consider adding {' and '.join(top_miss)} to your portfolio "
                f"to make your application near-perfect."
            )
        return "Excellent match — apply now with confidence. You cover all core requirements."
    if score >= 60:
        if missing:
            return (
                f"Good match — apply. Brush up on {' and '.join(top_miss)} before the interview, "
                f"as these are likely to be probed."
            )
        return "Good match — apply. Review the role's tech stack to tailor your cover letter."
    if score >= 40:
        return (
            f"Apply with preparation. Spend 1–2 weeks building something with "
            f"{top_miss[0] if top_miss else 'the required skills'} before your interview."
        )
    return (
        f"Consider this a stretch goal. Build projects using "
        f"{' and '.join(top_miss[:2]) if top_miss else 'the required skills'} "
        f"before applying to be competitive."
    )


# ── Why-fit explanation ───────────────────────────────────────────────────────

def _why_fit_rule(
    matched: list[str],
    missing: list[str],
    score: int,
    title: str,
    company: str,
    candidate_name: str,
) -> str:
    name_clause = f"{candidate_name}'s" if candidate_name else "Your"
    top_m = matched[:3]
    top_miss = missing[:2]
    match_str = ", ".join(top_m) if top_m else "general engineering skills"
    miss_str  = " and ".join(top_miss) if top_miss else ""
    total_req = len(matched) + len(missing)
    coverage = f"{len(matched)} of {total_req}" if total_req else "several"

    if score >= 80:
        base = (
            f"{name_clause} {match_str} skills align directly with the core requirements "
            f"for this {title} role at {company} — covering {coverage} required skills."
        )
        return base + (
            f" Adding {miss_str} would make this a near-perfect fit." if miss_str else
            " All key required skills are covered — strong application recommended."
        )
    if score >= 60:
        base = (
            f"Good match for {company}'s {title} position. {name_clause} {match_str} "
            f"skills cover {coverage} requirements."
        )
        return base + (
            f" Strengthening {miss_str} would further boost your competitiveness." if miss_str else ""
        )
    if score >= 40:
        return (
            f"Emerging fit for this {title} role. {name_clause} {match_str} "
            f"foundation is a good starting point — developing {miss_str or 'the remaining skills'} "
            f"will make your application much stronger."
        )
    return (
        f"Stretch opportunity at {company}. {name_clause} current skills provide foundational overlap "
        f"({coverage} required skills matched), but significant upskilling in "
        f"{miss_str or 'the required areas'} is needed."
    )


# ── Optional LLM enrichment ───────────────────────────────────────────────────

async def _llm_why_fit(
    job: JobListing,
    matched: list[str],
    missing: list[str],
    score: int,
    candidate_name: str,
    candidate_skills: list[str],
) -> str | None:
    from config import get_settings
    settings = get_settings()
    if not settings.use_llm or not settings.groq_api_key:
        return None
    try:
        from groq import AsyncGroq
        prompt = (
            f"Write ONE concise sentence (max 40 words) explaining why this candidate "
            f"is a good fit for the job. Be specific and mention matched skills.\n\n"
            f"Candidate: {candidate_name or 'the candidate'}\n"
            f"Candidate skills: {', '.join(candidate_skills[:10])}\n"
            f"Job title: {job.title} at {job.company}\n"
            f"Required skills: {', '.join(job.required_skills)}\n"
            f"Matched skills: {', '.join(matched)}\n"
            f"Missing skills: {', '.join(missing)}\n"
            f"Match score: {score}/100\n\n"
            "Return ONLY the sentence. No prefix, no explanation."
        )
        client = AsyncGroq(api_key=settings.groq_api_key)
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile", max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("LLM why_fit failed for %s: %s", job.job_id, exc)
    return None


# ── Main entry point ──────────────────────────────────────────────────────────

async def recommend(
    candidate_id: str,
    candidate_skills: list[str],
    candidate_level: str,
    candidate_name: str,
    use_llm_blurb: bool = False,
) -> JobRecommendationResponse:
    """
    Fetch live jobs from Adzuna first, fall back to sample_jobs.json if unavailable.
    is_live=True for Adzuna results, is_live=False for sample fallback — clearly
    distinguished in the response so the UI can display the source honestly.
    """
    from agents.adzuna_job_fetcher import fetch_live_jobs
    jobs, jobs_are_live = await fetch_live_jobs(candidate_skills, candidate_level)
    if not jobs:
        logger.info("No live jobs fetched — using sample_jobs.json as fallback (is_live=False).")
        jobs = _load_jobs()
        jobs_are_live = False

    if not jobs:
        return JobRecommendationResponse(
            candidate_id=candidate_id,
            total_jobs_analyzed=0,
            recommended_jobs=[],
        )

    candidate_canonicals: set[str] = {_canonical(s) for s in candidate_skills}
    scored: list[tuple[int, JobMatch]] = []

    for job in jobs:
        matched, missing = _match_skills(candidate_canonicals, job.required_skills)
        bonus  = _exp_bonus(candidate_level, job.experience)
        sc     = _score(matched, len(job.required_skills), bonus)

        if sc < _MIN_SCORE:
            continue

        why = None
        if use_llm_blurb:
            why = await _llm_why_fit(
                job, matched, missing, sc, candidate_name, candidate_skills
            )
        if not why:
            why = _why_fit_rule(matched, missing, sc, job.title, job.company, candidate_name)

        readiness = _application_readiness(matched, missing, sc)

        scored.append((
            sc,
            JobMatch(
                job_id=job.job_id,
                title=job.title,
                company=job.company,
                location=job.location,
                experience=job.experience,
                description=job.description,
                required_skills=job.required_skills,
                match_score=sc,
                matched_skills=matched,
                missing_skills=missing,
                why_fit=why,
                apply_url=getattr(job, "apply_url", ""),
                is_live=jobs_are_live,
                application_readiness=readiness,
            ),
        ))

    scored.sort(key=lambda t: -t[0])
    results = [match for _, match in scored[:_TOP_N]]

    return JobRecommendationResponse(
        candidate_id=candidate_id,
        total_jobs_analyzed=len(jobs),
        recommended_jobs=results,
    )
