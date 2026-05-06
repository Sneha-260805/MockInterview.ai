from pydantic import BaseModel
from datetime import datetime


class ResumeRecord(BaseModel):
    candidate_id: str
    file_name: str
    raw_text: str
    status: str
    uploaded_at: datetime


class ResumeUploadResponse(BaseModel):
    candidate_id: str
    file_name: str
    raw_text: str
    status: str
