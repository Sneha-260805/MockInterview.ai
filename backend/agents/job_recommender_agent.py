"""
Phase 7 — Job Recommendation agent.

Loads jobs from sample_data/sample_jobs.json, scores each job against
the candidate's extracted skills, and returns the top matches with a
natural-language explanation of why each job is a good fit.

Matching algorithm
------------------
1. Normalise both candidate skills and job required_skills to lowercase.
2. For each required skill, check:
      a. Exact match (after lowercasing).
      b. Prefix match  — first 6 chars  (catches "postgresql" ≈ "postgres").
      c. Alias lookup  — common display-name aliases.
3. Raw score = len(matched) / len(required) × 100.
4. Experience-level bonus (+5 pts) when the candidate's seniority fits.
5. Cap at 95 to avoid unrealistic perfect scores.
6. Return the top-N jobs above a minimum threshold, sorted by score desc.

Optional LLM path
-----------------
When USE_LLM=true and an Anthropic API key is set, the agent requests a
richer, personalised why_fit blurb from Claude.  Rule-based why_fit is
always generated as the fallback.
"""

import json
import logging
from pathlib import Path
import asyncio

from models.jobs import JobListing, JobMatch, JobRecommendationResponse

logger = logging.getLogger(__name__)

_JOBS_PATH  = Path(__file__).parent.parent / "sample_data" / "sample_jobs.json"
_TOP_N      = 10          # maximum results returned
_MIN_SCORE  = 20          # jobs below this threshold are filtered out

# ── Normalised skill aliases ───────────────────────────────────────────────────
# Keys are canonical lowercase tokens; values are lists of accepted spellings.
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

# Build reverse lookup: any alias string → canonical key
_ALIAS_LOOKUP: dict[str, str] = {}
for _canon, _variants in _ALIASES.items():
    for _v in _variants:
        _ALIAS_LOOKUP[_v] = _canon


def _canonical(skill: str) -> str:
    """Return the canonical token for a skill string."""
    sl = skill.lower().strip()
    return _ALIAS_LOOKUP.get(sl, sl)


def _load_jobs() -> list[JobListing]:
    try:
        with _JOBS_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        jobs = []
        for j in raw:
            j.setdefault("source", "sample")
            j.setdefault("is_live", False)
            j.setdefault("is_fallback_sample", True)
            j.setdefault("apply_url", "")
            jobs.append(JobListing(**j))
        return jobs
    except Exception as exc:
        logger.error("Failed to load sample_jobs.json: %s", exc)
        return []


# ── Seniority alignment ───────────────────────────────────────────────────────

def _seniority_fit(candidate_level: str, job_experience: str, job_title: str) -> int:
    """
    Returns 0–10 points based on how well the candidate's seniority matches
    the job's required level. Title keywords take priority; experience band
    is the fallback.

    Fit matrix (job_level, candidate_level) → points:
      junior/junior=10  junior/mid=4   junior/senior=0
      mid/junior=5      mid/mid=10     mid/senior=5
      senior/junior=0   senior/mid=6   senior/senior=10
    """
    title = job_title.lower()

    if any(w in title for w in ("intern", "internship", "entry-level", "entry level")):
        job_level = "junior"
    elif "junior" in title or " jr " in title or title.startswith("jr "):
        job_level = "junior"
    elif any(w in title for w in ("senior", " sr ", "lead ", "principal", "staff")):
        job_level = "senior"
    else:
        exp = job_experience.lower()
        if any(x in exp for x in ("0-1", "0-2", "1-2", "1-3")):
            job_level = "junior"
        elif any(x in exp for x in ("5+", "4-6", "5-7", "6+", "7+")):
            job_level = "senior"
        else:
            job_level = "mid"

    cand = candidate_level.lower() if candidate_level else "mid"
    if cand not in ("junior", "mid", "senior"):
        cand = "mid"

    _FIT: dict[tuple[str, str], int] = {
        ("junior", "junior"): 10,
        ("junior", "mid"):     4,
        ("junior", "senior"):  0,
        ("mid",    "junior"):  5,
        ("mid",    "mid"):    10,
        ("mid",    "senior"):  5,
        ("senior", "junior"):  0,
        ("senior", "mid"):     6,
        ("senior", "senior"): 10,
    }
    return _FIT.get((job_level, cand), 5)


# ── Skill matching ────────────────────────────────────────────────────────────

def _match_skills(
    candidate_canonicals: set[str],
    required_skills: list[str],
) -> tuple[list[str], list[str]]:
    """
    Return (matched_display_list, missing_display_list).
    Uses canonical tokens so prefix/alias mismatches are handled.
    """
    matched: list[str] = []
    missing: list[str] = []

    for req in required_skills:
        req_canon = _canonical(req)
        # Exact canonical match
        if req_canon in candidate_canonicals:
            matched.append(req)
            continue
        # 6-char prefix match among candidate skills
        if any(
            c.startswith(req_canon[:6]) or req_canon.startswith(c[:6])
            for c in candidate_canonicals
            if len(c) >= 4 and len(req_canon) >= 4
        ):
            matched.append(req)
            continue
        missing.append(req)

    return matched, missing


def _score(
    matched: list[str],
    missing: list[str],
    required: list[str],
    candidate_canonicals: set[str],
    candidate_level: str,
    job: "JobListing",
) -> int:
    """
    Multi-factor deterministic scorer — no randomness, no LLM.

    Factor                Range      Description
    ─────────────────────────────────────────────────────────────
    Core skill ratio      0–50 pts   matched / total required
    Priority skill bonus  0–18 pts   top-3 required skills (+6 each if matched)
    Seniority fit         0–10 pts   candidate level vs job seniority signals
    Specialisation bonus  0–7  pts   skills in positions 4+ that are matched
    Gap penalty           0–10 pts   deducted for proportion of unmet requirements
    ─────────────────────────────────────────────────────────────
    Practical range ≈ 15–85, clamped to [_MIN_SCORE, 95].
    """
    total = len(required)
    if total == 0:
        return 50

    # 1. Core skill ratio (0–50 pts)
    ratio_pts = round(len(matched) / total * 50)

    # 2. Priority skill bonus — the first three required skills are most critical (0–18 pts)
    priority_pts = 0
    for req in required[:3]:
        rc = _canonical(req)
        if rc in candidate_canonicals:
            priority_pts += 6
        elif len(rc) >= 4 and any(c[:6] == rc[:6] for c in candidate_canonicals if len(c) >= 4):
            priority_pts += 6

    # 3. Seniority alignment (0–10 pts)
    seniority_pts = _seniority_fit(candidate_level, job.experience, job.title)

    # 4. Specialisation bonus — niche skills (position 4 onwards) that are matched (0–7 pts)
    spec_count = sum(
        1 for req in required[3:]
        if _canonical(req) in candidate_canonicals
        or (len(_canonical(req)) >= 4
            and any(c[:6] == _canonical(req)[:6] for c in candidate_canonicals if len(c) >= 4))
    )
    spec_pts = min(spec_count * 2, 7)

    # 5. Gap penalty — proportional to unmet requirements (0–10 pts deducted)
    gap_penalty = round(len(missing) / total * 10)

    raw = ratio_pts + priority_pts + seniority_pts + spec_pts - gap_penalty
    return max(_MIN_SCORE, min(95, raw))


# ── Why-fit template ──────────────────────────────────────────────────────────

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

    if score >= 80:
        base = (
            f"{name_clause} {match_str} skills align directly with the core requirements "
            f"for this {title} role at {company}."
        )
        return base + (
            f" Adding {miss_str} would make you a near-perfect fit." if miss_str else
            " You cover all key required skills — strong application recommended."
        )
    if score >= 60:
        base = (
            f"Good match for {company}'s {title} position. {name_clause} {match_str} "
            f"skills cover {len(matched)} of the {len(matched) + len(missing)} requirements."
        )
        return base + (
            f" Strengthening {miss_str} would further boost your competitiveness." if miss_str else ""
        )
    if score >= 40:
        return (
            f"Emerging fit for this {title} role. {name_clause} {match_str} "
            f"foundation is a good start; developing {miss_str or 'the remaining skills'} "
            f"will make your application much stronger."
        )
    return (
        f"Stretch opportunity at {company}. {name_clause} current skills provide a "
        f"foundational overlap, but significant upskilling in "
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
    if not settings.has_llm_configured:
        return None
    try:
        from services.llm_client import call_llm
        prompt = (
            f"Write ONE concise sentence (max 35 words) explaining why this candidate "
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
        result = await call_llm(prompt, max_tokens=80)
        return result.strip() if result else None
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
    Fetch live jobs from Adzuna first, fall back to sample_jobs.json
    if API is unavailable.
    """
    from agents.adzuna_job_fetcher import fetch_live_jobs
    jobs = await fetch_live_jobs(candidate_skills, candidate_level)
    source = "adzuna"
    fallback_reason = None
    if not jobs:
        logger.info("No live jobs fetched, using sample_jobs.json as fallback.")
        jobs = _load_jobs()
        source = "sample"
        fallback_reason = "Live job API credentials are missing or the provider returned no usable postings."
    if not jobs:
        return JobRecommendationResponse(
            candidate_id=candidate_id,
            total_jobs_analyzed=0,
            recommended_jobs=[],
        )

    # Normalise candidate skills to canonical tokens once
    candidate_canonicals: set[str] = {_canonical(s) for s in candidate_skills}

    # First: score all jobs deterministically (no LLM calls)
    intermediate: list[dict] = []
    for job in jobs:
        matched, missing = _match_skills(candidate_canonicals, job.required_skills)
        sc = _score(matched, missing, job.required_skills, candidate_canonicals, candidate_level, job)
        if sc < _MIN_SCORE:
            continue
        intermediate.append({
            "job": job,
            "matched": matched,
            "missing": missing,
            "score": sc,
        })

    # Sort descending and take top-N candidates
    intermediate.sort(key=lambda e: -e["score"])
    top_entries = intermediate[:_TOP_N]

    # Optionally call LLM for concise 'why_fit' blurbs concurrently (bounded concurrency)
    llm_results: list[str | None] = [None] * len(top_entries)
    settings = None
    if use_llm_blurb:
        from config import get_settings
        settings = get_settings()

    async def _gather_llm_blurbs(entries, candidate_name, candidate_skills, max_concurrency=3):
        sem = asyncio.Semaphore(max_concurrency)

        async def _run(entry):
            async with sem:
                try:
                    return await _llm_why_fit(
                        entry["job"], entry["matched"], entry["missing"], entry["score"],
                        candidate_name, candidate_skills,
                    )
                except Exception as exc:
                    logger.warning("LLM why_fit task failed: %s", exc)
                    return None

        tasks = [asyncio.create_task(_run(e)) for e in entries]
        if not tasks:
            return []
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        # Normalize to str|None
        out = []
        for r in gathered:
            if isinstance(r, Exception):
                out.append(None)
            else:
                out.append(r)
        return out

    if use_llm_blurb and settings and settings.has_llm_configured:
        try:
            llm_results = await _gather_llm_blurbs(top_entries, candidate_name, candidate_skills, max_concurrency=3)
        except Exception as exc:
            logger.warning("Bulk LLM gather failed: %s", exc)

    # Build final JobMatch list, using LLM blurb when available and falling back to rule-based text
    scored: list[tuple[int, JobMatch]] = []
    for idx, entry in enumerate(top_entries):
        job = entry["job"]
        matched = entry["matched"]
        missing = entry["missing"]
        sc = entry["score"]

        why = None
        why_source = "rule_based_fallback"
        # Use LLM result if provided (call_llm already enforces per-provider timeout)
        if llm_results and idx < len(llm_results) and llm_results[idx]:
            why = llm_results[idx]
            try:
                from config import get_settings
                why_source = f"llm:{get_settings().llm_provider.lower()}"
            except Exception:
                why_source = "llm"

        if not why:
            why = _why_fit_rule(matched, missing, sc, job.title, job.company, candidate_name)

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
                explanation=why,
                source=job.source,
                apply_url=job.apply_url,
                is_live=job.is_live,
                is_fallback_sample=job.is_fallback_sample,
                remote=job.remote,
                why_fit_source=why_source,
            ),
        ))

    results = [match for _, match in scored]

    return JobRecommendationResponse(
        candidate_id=candidate_id,
        total_jobs_analyzed=len(jobs),
        recommended_jobs=results,
        source=source,
        is_live=source != "sample",
        fallback_reason=fallback_reason,
    )
