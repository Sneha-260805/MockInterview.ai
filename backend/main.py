from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import get_settings
from database.connection import connect_db, close_db
from routes.health import router as health_router
from routes.resume_routes import router as resume_router
from routes.role_routes import router as role_router
from routes.interview_routes import router as interview_router
from routes.job_routes import router as job_router
from routes.scoring_routes import router as scoring_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(resume_router)
app.include_router(role_router)
app.include_router(interview_router)
app.include_router(job_router)
app.include_router(scoring_router)


@app.get("/")
async def root():
    return {"message": "Intelligent Mock Interview Agent API", "docs": "/docs"}
