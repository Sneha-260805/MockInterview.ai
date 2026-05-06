from fastapi import APIRouter, HTTPException

from models.analysis import RoleRecommendationResponse
from database import store
from database.connection import get_db, is_using_memory
from agents import role_agent
from models.analysis import ResumeAnalysis

router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get("/{candidate_id}", response_model=RoleRecommendationResponse)
async def get_roles(candidate_id: str):
    # Try in-memory store first (always populated when analyse was called this session)
    roles_data = store.get_roles(candidate_id)
    if roles_data:
        return RoleRecommendationResponse(**roles_data)

    # Fall back to MongoDB if available
    if not is_using_memory():
        db = get_db()
        doc = await db["role_recommendations"].find_one({"candidate_id": candidate_id})
        if doc:
            doc.pop("_id", None)
            return RoleRecommendationResponse(**doc)

    # If analysis exists but roles were never computed, compute now
    analysis_data = store.get_analysis(candidate_id)
    if not analysis_data and not is_using_memory():
        db = get_db()
        analysis_data = await db["resume_analysis"].find_one({"candidate_id": candidate_id})
        if analysis_data:
            analysis_data.pop("_id", None)

    if not analysis_data:
        raise HTTPException(
            status_code=404,
            detail="No analysis found for this candidate. Run POST /api/resume/analyze first.",
        )

    analysis = ResumeAnalysis(**analysis_data)
    result = role_agent.recommend(analysis)

    store.save_roles(candidate_id, result.model_dump())
    if not is_using_memory():
        db = get_db()
        await db["role_recommendations"].replace_one(
            {"candidate_id": candidate_id}, result.model_dump(), upsert=True
        )

    return result
