from pydantic import BaseModel
from typing import List


class Project(BaseModel):
    name: str
    technologies: List[str]
    summary: str


class ResumeAnalysis(BaseModel):
    candidate_id: str
    candidate_name: str
    email: str
    phone: str
    skills: List[str]
    projects: List[Project]
    education: str
    experience_level: str  # junior | mid | senior
    domains: List[str]
    strengths: List[str]
    weak_areas: List[str]


class AnalyzeRequest(BaseModel):
    candidate_id: str
    raw_text: str


class RoleMatch(BaseModel):
    role: str
    match_score: int  # 0-100
    reason: str
    focus_areas: List[str]
    weak_areas_to_probe: List[str]


class RoleRecommendationResponse(BaseModel):
    candidate_id: str
    recommended_roles: List[RoleMatch]
