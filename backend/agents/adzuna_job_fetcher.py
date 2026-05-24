"""
Adzuna live job fetcher.
Fetches real live job postings from Adzuna API
based on candidate skills and returns them as JobListing objects.
"""

import logging
import httpx
from models.jobs import JobListing
from config import get_settings

logger = logging.getLogger(__name__)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"

_LEVEL_TO_EXPERIENCE = {
    "junior":  "0-2 years",
    "mid":     "2-5 years",
    "senior":  "5+ years",
}

async def fetch_live_jobs(candidate_skills: list[str], candidate_level: str) -> list[JobListing]:
    """
    Fetch real jobs from Adzuna using candidate skills as keywords.
    Returns a list of JobListing objects, or empty list if API fails.
    """
    settings = get_settings()

    app_id  = getattr(settings, "adzuna_app_id", None)
    app_key = getattr(settings, "adzuna_app_key", None)

    if not app_id or not app_key:
        logger.warning("Adzuna credentials missing. Falling back to sample jobs.")
        return []

    # Pick top 3 skills as search keywords
    keywords = " ".join(candidate_skills[:3]) if candidate_skills else "software developer"

    params = {
        "app_id":         app_id,
        "app_key":        app_key,
        "results_per_page": 20,
        "what":           keywords,
        "content-type":   "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(ADZUNA_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        experience_label = _LEVEL_TO_EXPERIENCE.get(candidate_level, "1-3 years")
        jobs = []
        for i, item in enumerate(data.get("results", [])):
            # Extract skills from description (simple keyword match)
            description = item.get("description", "")
            required_skills = _extract_skills_from_text(description, candidate_skills)

            jobs.append(JobListing(
                job_id=f"adzuna_{i}_{item.get('id', i)}",
                title=item.get("title", "Software Developer"),
                company=item.get("company", {}).get("display_name", "Unknown Company"),
                location=item.get("location", {}).get("display_name", "India"),
                experience=experience_label,
                description=description[:300] + "..." if len(description) > 300 else description,
                required_skills=required_skills,
                apply_url=item.get("redirect_url", ""),
                source="adzuna",
                is_live=True,
                is_fallback_sample=False,
                remote=("remote" in (item.get("title", "") + " " + description).lower()),
            ))

        logger.info("Fetched %d live jobs from Adzuna.", len(jobs))
        return jobs

    except Exception as exc:
        logger.error("Adzuna API call failed: %s", exc)
        return []


def _extract_skills_from_text(text: str, candidate_skills: list[str]) -> list[str]:
    """
    Simple skill extractor - checks which candidate skills appear in job description.
    Also checks for common tech keywords.
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
    found = []

    # Check candidate's own skills first
    for skill in candidate_skills:
        if skill.lower() in text_lower and skill not in found:
            found.append(skill)

    # Also check common skills
    for skill in COMMON_SKILLS:
        if skill.lower() in text_lower and skill not in found:
            found.append(skill)

    return found[:10] if found else ["Software Development"]
