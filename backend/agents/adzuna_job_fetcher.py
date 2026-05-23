"""
Adzuna live job fetcher.
Fetches real live job postings from Adzuna API based on candidate skills.

Returns a tuple (jobs: list[JobListing], is_live: bool).
is_live=True when jobs came from the Adzuna API.
is_live=False (and empty list) when credentials are missing or the API fails.
"""

import logging
import httpx
from models.jobs import JobListing
from config import get_settings

logger = logging.getLogger(__name__)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"


async def fetch_live_jobs(
    candidate_skills: list[str],
    candidate_level: str,
) -> tuple[list[JobListing], bool]:
    """
    Fetch real jobs from Adzuna using candidate skills as keywords.
    Returns (job_list, is_live).
    is_live=True when a successful live response was received.
    """
    settings = get_settings()

    app_id  = getattr(settings, "adzuna_app_id", None)
    app_key = getattr(settings, "adzuna_app_key", None)

    if not app_id or not app_key:
        logger.warning("Adzuna credentials missing — falling back to sample jobs.")
        return [], False

    keywords = " ".join(candidate_skills[:3]) if candidate_skills else "software developer"

    params = {
        "app_id":             app_id,
        "app_key":            app_key,
        "results_per_page":   20,
        "what":               keywords,
        "content-type":       "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(ADZUNA_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        jobs: list[JobListing] = []
        for i, item in enumerate(data.get("results", [])):
            description = item.get("description", "")
            required_skills = _extract_skills_from_text(description, candidate_skills)

            jobs.append(JobListing(
                job_id=f"adzuna_{i}_{item.get('id', i)}",
                title=item.get("title", "Software Developer"),
                company=item.get("company", {}).get("display_name", "Unknown Company"),
                location=item.get("location", {}).get("display_name", "India"),
                experience="1-3 years",
                description=description[:300] + "..." if len(description) > 300 else description,
                required_skills=required_skills,
                apply_url=item.get("redirect_url", ""),
                is_live=True,
            ))

        logger.info("Fetched %d live jobs from Adzuna.", len(jobs))
        return jobs, True

    except Exception as exc:
        logger.error("Adzuna API call failed: %s", exc)
        return [], False


def _extract_skills_from_text(text: str, candidate_skills: list[str]) -> list[str]:
    """
    Extract skills from job description text.
    Checks candidate's own skills first, then a common tech list.
    """
    COMMON_SKILLS = [
        "Python", "JavaScript", "TypeScript", "React", "Node.js",
        "FastAPI", "Django", "Flask", "Docker", "Kubernetes",
        "AWS", "GCP", "Azure", "MongoDB", "PostgreSQL", "MySQL",
        "Redis", "Kafka", "Git", "REST API", "GraphQL",
        "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch",
        "SQL", "Java", "Go", "Rust", "C++", "Linux",
    ]

    text_lower = text.lower()
    found: list[str] = []

    for skill in candidate_skills:
        if skill.lower() in text_lower and skill not in found:
            found.append(skill)

    for skill in COMMON_SKILLS:
        if skill.lower() in text_lower and skill not in found:
            found.append(skill)

    return found[:10] if found else ["Software Development"]
