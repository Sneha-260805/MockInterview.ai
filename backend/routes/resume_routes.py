import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from services.pdf_parser import extract_text
from services.llm_service import enhance_analysis, build_interview_intelligence, enrich_roles_with_gemini
from models.resume import ResumeUploadResponse, ResumeRecord
from models.analysis import ResumeAnalysis, AnalyzeRequest, RoleRecommendationResponse
from database.connection import get_db, memory_collection, is_using_memory
from database import store
from agents import resume_agent, role_agent

router = APIRouter(prefix="/api/resume", tags=["resume"])

ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...)):
    if _ext(file.filename) not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a PDF, DOCX, or TXT file.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds the 10 MB limit.")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        raw_text = extract_text(file_bytes, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}")

    if not raw_text.strip():
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted. The file may be scanned or image-only.",
        )

    candidate_id = str(uuid.uuid4())
    record = ResumeRecord(
        candidate_id=candidate_id,
        file_name=file.filename,
        raw_text=raw_text,
        status="success",
        uploaded_at=datetime.now(timezone.utc),
    )

    if is_using_memory():
        memory_collection("resumes").append(record.model_dump())
    else:
        db = get_db()
        await db["resumes"].insert_one(record.model_dump())

    return ResumeUploadResponse(
        candidate_id=candidate_id,
        file_name=file.filename,
        raw_text=raw_text,
        status="success",
    )


class AnalyzeResponse(BaseModel):
    analysis: ResumeAnalysis
    roles: RoleRecommendationResponse
    llm_enhancement_source: str = "rule_based_fallback"


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_resume(body: AnalyzeRequest):
    if not body.raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text is empty.")

    # Stage 0+1 — rule-based extraction + optional Gemini project/skill normalization
    # Falls back to pure rule-based output if LLM is disabled or fails.
    analysis = await resume_agent.analyze_with_normalization(body.raw_text, body.candidate_id)

    # Stage 1b — optional LLM field refinement (improves basic extraction quality)
    enhanced = await enhance_analysis(body.raw_text, analysis.model_dump())
    llm_enhancement_source = "rule_based_fallback"
    if enhanced:
        merged = {**analysis.model_dump(), **{
            k: v for k, v in enhanced.items()
            if k in analysis.model_fields and v
        }}
        merged["candidate_id"] = body.candidate_id  # never override
        analysis = ResumeAnalysis(**merged)
        from config import get_settings
        llm_enhancement_source = f"llm:{get_settings().llm_provider.lower()}"

    # Stage 2 — Gemini interview intelligence reasoning (additive; never overwrites
    # existing extraction fields; silently skipped if LLM is disabled or fails)
    intelligence = await build_interview_intelligence(analysis.model_dump())
    if intelligence:
        try:
            merged = {**analysis.model_dump(), **intelligence}
            merged["candidate_id"] = body.candidate_id
            analysis = ResumeAnalysis.model_validate(merged)
            from config import get_settings
            provider = get_settings().llm_provider.lower()
            llm_enhancement_source = (
                f"llm:{provider}+intelligence"
                if llm_enhancement_source == "rule_based_fallback"
                else f"{llm_enhancement_source}+intelligence"
            )
        except Exception as exc:
            import logging as _lg
            _lg.getLogger(__name__).warning(
                "Intelligence merge failed, preserving prior analysis: %s", exc
            )

    roles = role_agent.recommend(analysis)

    # Stage 3 — Gemini role enrichment (additive; silently skipped if LLM disabled or fails)
    enrichments = await enrich_roles_with_gemini(
        analysis.model_dump(),
        [r.model_dump() for r in roles.recommended_roles],
    )
    if enrichments:
        enriched_roles = []
        for role_match in roles.recommended_roles:
            enr = enrichments.get(role_match.role)
            if enr:
                role_match = role_match.model_copy(update={
                    "role_type": enr.get("role_type", "realistic"),
                    "why_fit": enr.get("why_fit", ""),
                    "resume_evidence": enr.get("resume_evidence", []),
                    "gaps": enr.get("gaps", []),
                    "interview_focus_areas": enr.get("interview_focus", role_match.interview_focus_areas),
                    "what_interview_will_validate": enr.get("what_interview_will_validate", []),
                })
            enriched_roles.append(role_match)
        roles = RoleRecommendationResponse(
            candidate_id=roles.candidate_id,
            recommended_roles=enriched_roles,
        )

    # Persist both
    store.save_analysis(body.candidate_id, analysis.model_dump())
    store.save_roles(body.candidate_id, roles.model_dump())

    if not is_using_memory():
        db = get_db()
        await db["resume_analysis"].replace_one(
            {"candidate_id": body.candidate_id}, analysis.model_dump(), upsert=True
        )
        await db["role_recommendations"].replace_one(
            {"candidate_id": body.candidate_id}, roles.model_dump(), upsert=True
        )

    return AnalyzeResponse(
        analysis=analysis,
        roles=roles,
        llm_enhancement_source=llm_enhancement_source,
    )
