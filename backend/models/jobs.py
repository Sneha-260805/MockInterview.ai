from pydantic import BaseModel, Field
from typing import List


class JobListing(BaseModel):
    job_id: str
    title: str
    company: str
    required_skills: List[str]
    experience: str
    location: str
    description: str
    apply_url: str = ""       # direct application link (populated by Adzuna)
    is_live: bool = False     # True = fetched from live API, False = sample/fallback


class JobMatch(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    experience: str
    description: str
    required_skills: List[str]
    match_score: int           # 0-100
    matched_skills: List[str]
    missing_skills: List[str]
    why_fit: str
    apply_url: str = ""
    is_live: bool = False      # clearly marked for demo transparency
    application_readiness: str = ""   # recommended preparation steps
