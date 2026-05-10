from pydantic import BaseModel
from typing import List, Optional


class JobListing(BaseModel):
    job_id: str
    title: str
    company: str
    required_skills: List[str]
    experience: str
    location: str
    description: str
    source: str = "sample"
    apply_url: str = ""
    is_live: bool = False
    is_fallback_sample: bool = True
    remote: Optional[bool] = None


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
    source: str = "sample"
    apply_url: str = ""
    is_live: bool = False
    is_fallback_sample: bool = True
    remote: Optional[bool] = None
    explanation: Optional[str] = None


class JobRecommendationResponse(BaseModel):
    candidate_id: str
    total_jobs_analyzed: int
    recommended_jobs: List[JobMatch]
    source: str = "sample"
    is_live: bool = False
    fallback_reason: Optional[str] = None
