from pydantic import BaseModel, Field
from typing import List, Optional


class Project(BaseModel):
    name: str
    technologies: List[str]
    summary: str                          # backward-compat: first 3 bullets joined
    duration: Optional[str] = None        # e.g. "Jan 2024 – May 2024"
    description: List[str] = Field(default_factory=list)   # bullet points


class Certification(BaseModel):
    name: str
    issuer: str = ""                      # inferred from keywords (AWS, Google, Cisco…)
    date: str = ""                        # year or "Month YYYY"


class WorkExperience(BaseModel):
    company: str
    role: str = ""
    duration: str = ""
    responsibilities: List[str] = Field(default_factory=list)


class ResumeAnalysis(BaseModel):
    candidate_id: str
    candidate_name: str
    email: str
    phone: str
    skills: List[str]
    projects: List[Project]
    education: str
    experience_level: str                 # junior | mid | senior
    domains: List[str]
    strengths: List[str]
    weak_areas: List[str]
    # New structured extractions (default empty for backward compat)
    certifications: List[Certification] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    work_experience: List[WorkExperience] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    candidate_id: str
    raw_text: str


class RoleMatch(BaseModel):
    role: str
    match_score: int                      # 0-100
    reason: str
    focus_areas: List[str]
    weak_areas_to_probe: List[str]


class RoleRecommendationResponse(BaseModel):
    candidate_id: str
    recommended_roles: List[RoleMatch]
