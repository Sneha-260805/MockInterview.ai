import logging
import sys

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

# ── Logging configuration ─────────────────────────────────────────────────────
# Root logger: INFO in production, DEBUG when debug=true or llm_log_prompts=true
_log_level = logging.DEBUG if (settings.debug or settings.llm_log_prompts) else logging.INFO
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Always show WARNING+ for noisy third-party libs
for _noisy in ("httpx", "httpcore", "openai", "anthropic", "google"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_startup_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    # Log LLM configuration at startup so it's visible in the console
    if settings.has_llm_configured:
        _startup_logger.info(
            "LLM enabled: provider=%s model=%s timeout=%ds log_prompts=%s",
            settings.llm_provider,
            settings.grok_model if settings.llm_provider.lower() == "grok" else "default",
            settings.llm_timeout_seconds,
            settings.llm_log_prompts,
        )
    else:
        _startup_logger.info(
            "LLM disabled or not configured (USE_LLM=%s, provider=%s). "
            "All responses will use deterministic fallbacks.",
            settings.use_llm,
            settings.llm_provider,
        )
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
