from fastapi import APIRouter, HTTPException

from models.jobs import JobRecommendationResponse
from models.analysis import ResumeAnalysis
from agents import job_recommender_agent
from database import store
from database.connection import get_db, is_using_memory
from config import get_settings

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


async def _load_analysis(candidate_id: str) -> ResumeAnalysis | None:
    data = store.get_analysis(candidate_id)
    if not data and not is_using_memory():
        db = get_db()
        doc = await db["resume_analysis"].find_one({"candidate_id": candidate_id})
        if doc:
            doc.pop("_id", None)
            data = doc
    return ResumeAnalysis(**data) if data else None


@router.get("/{candidate_id}", response_model=JobRecommendationResponse)
async def get_job_recommendations(candidate_id: str):
    """
    Phase 7 — Return ranked job recommendations for a candidate.

    Loads the candidate's resume analysis from the store, then scores
    every job in sample_data/sample_jobs.json against their skills.
    Returns the top 10 matches sorted by match_score descending.
    """
    if not candidate_id.strip():
        raise HTTPException(status_code=400, detail="candidate_id is required.")

    analysis = await _load_analysis(candidate_id)
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=(
                "Resume analysis not found for this candidate. "
                "Please upload and analyse your resume first."
            ),
        )

    settings = get_settings()

    result = await job_recommender_agent.recommend(
        candidate_id=candidate_id,
        candidate_skills=analysis.skills,
        candidate_level=analysis.experience_level,
        candidate_name=analysis.candidate_name,
        use_llm_blurb=settings.use_llm,
    )
    return result
