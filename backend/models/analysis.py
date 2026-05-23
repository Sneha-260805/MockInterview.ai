from pydantic import BaseModel, Field
from typing import List, Optional


class Project(BaseModel):
    name: str
    technologies: List[str]
    summary: str


class ClaimToVerify(BaseModel):
    claim: str
    why_verify: str
    probe_question: str


class ProjectDeepDive(BaseModel):
    project: str
    why_selected: str
    probe_topics: List[str]


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

    # ── Interview Intelligence (explainability fields) ────────────────────────
    strong_skills: List[str] = Field(default_factory=list)
    role_signals: List[str] = Field(default_factory=list)
    claims_to_verify: List[ClaimToVerify] = Field(default_factory=list)
    project_deep_dives: List[ProjectDeepDive] = Field(default_factory=list)
    interview_risks: List[str] = Field(default_factory=list)
    suggested_probes: List[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    candidate_id: str
    raw_text: str


class RoleMatch(BaseModel):
    role: str
    match_score: int  # 0-100
    reason: str
    focus_areas: List[str]
    weak_areas_to_probe: List[str]

    # ── Explainability fields ─────────────────────────────────────────────────
    role_type: str = "realistic"          # realistic | stretch | aspirational
    why_fit: str = ""
    resume_evidence: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)


class RoleRecommendationResponse(BaseModel):
    candidate_id: str
    recommended_roles: List[RoleMatch]
