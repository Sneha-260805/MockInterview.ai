import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from services.pdf_parser import extract_text
from services.llm_service import enhance_analysis
from models.resume import ResumeUploadResponse, ResumeRecord
from models.analysis import ResumeAnalysis, AnalyzeRequest, RoleRecommendationResponse
from database.connection import get_db, memory_collection, is_using_memory
from database import store
from agents import resume_agent, role_agent

router = APIRouter(prefix="/api/resume", tags=["resume"])

ALLOWED_EXTENSIONS = {"pdf", "txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...)):
    if _ext(file.filename) not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Upload a PDF or TXT file.",
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


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_resume(body: AnalyzeRequest):
    if not body.raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text is empty.")

    analysis = resume_agent.analyze(body.raw_text, body.candidate_id)

    # Optional LLM enhancement — merges improved fields if available
    enhanced = await enhance_analysis(body.raw_text, analysis.model_dump())
    if enhanced:
        merged = {**analysis.model_dump(), **{
            k: v for k, v in enhanced.items()
            if k in analysis.model_fields and v
        }}
        merged["candidate_id"] = body.candidate_id  # never override
        analysis = ResumeAnalysis(**merged)

    roles = role_agent.recommend(analysis)

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

    return AnalyzeResponse(analysis=analysis, roles=roles)
