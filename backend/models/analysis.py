from pydantic import BaseModel, Field
from typing import List, Optional


class ProjectDomain(BaseModel):
    """Domain classification for a single project (populated by project_classifier)."""
    primary_domain: str                                         # e.g. "ML / AI", "Backend"
    secondary_domains: List[str] = Field(default_factory=list) # domains ≥ 30% of primary score
    supporting_technologies: List[str] = Field(default_factory=list)  # techs from other domains
    confidence: int = 0                                         # 0-100


class Project(BaseModel):
    name: str
    technologies: List[str]
    summary: str                          # backward-compat: first 3 bullets joined
    duration: Optional[str] = None        # e.g. "Jan 2024 – May 2024"
    description: List[str] = Field(default_factory=list)   # bullet points
    domain: Optional[ProjectDomain] = None                 # set by project_classifier


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

    @property
    def experience(self) -> List[WorkExperience]:
        return self.work_experience

    @property
    def seniority_signals(self) -> List[str]:
        signals = [self.experience_level]
        text = " ".join(
            [exp.role for exp in self.work_experience]
            + [exp.company for exp in self.work_experience]
            + self.achievements
        ).lower()
        if any(term in text for term in ("lead", "led", "senior", "architect", "mentor", "managed")):
            signals.append("leadership")
        if self.work_experience:
            signals.append("work experience")
        return list(dict.fromkeys([s for s in signals if s]))

    @property
    def domain_exposure(self) -> List[str]:
        return self.domains


class AnalyzeRequest(BaseModel):
    candidate_id: str
    raw_text: str


class RoleMatch(BaseModel):
    role: str
    match_score: int                      # 0-100
    reason: str
    focus_areas: List[str]
    weak_areas_to_probe: List[str]
    # ── Evidence-driven fields ────────────────────────────────────────────────
    evidence: List[str] = Field(default_factory=list)
    confidence: Optional[int] = None
    interview_focus_areas: List[str] = Field(default_factory=list)
    project_deep_dive_areas: List[str] = Field(default_factory=list)
    boosted_by: List[str] = Field(default_factory=list)      # signals that raised the score
    reduced_by: List[str] = Field(default_factory=list)      # gaps that limited the score
    missing_skills: List[str] = Field(default_factory=list)  # to become more competitive
    rank: Optional[int] = None                               # 1-based rank among results


class RoleRecommendationResponse(BaseModel):
    candidate_id: str
    recommended_roles: List[RoleMatch]
