# MockInterview.ai — Intelligent Mock Interview Agent

> An end-to-end AI-powered interview preparation platform.  
> Upload your resume → get AI-reasoned role and job matches → practice an adaptive mock interview → receive an explainable multimodal feedback report.

---

## Project Flow

```
Resume Upload
     │
     ▼
Resume Intelligence        ← Gemini: claims to verify, project deep-dives, interview risks
     │
     ▼
Role Recommendations       ← Gemini: why this role fits, resume evidence, realistic vs stretch
     │
     ▼
Job Recommendations        ← Live (Adzuna) or sample fallback, ranked by skill match
     │
     ▼
Adaptive Interview         ← Agent selects topic + difficulty based on your live signals
     │
     ▼
Agent Trace Reasoning      ← Observation → Decision → Reason → Evidence → Next Action
     │
     ▼
Multimodal Scoring         ← Technical answers + audio behavioral signals + video engagement
     │
     ▼
Explainable Feedback       ← Readiness verdict, skill mastery map, 7-day plan, per-question breakdown
```

---

## Key Features

| # | Feature | How it works |
|---|---------|-------------|
| 1 | **Resume Intelligence** | Three-stage pipeline: regex/rule extraction → Gemini normalization → Gemini interview-intelligence reasoning. Produces claims to verify, project deep-dives, interview risks, and strong/weak skill signals. |
| 2 | **Explainable Role Recommendations** | 15 engineering roles scored on core skills, bonus skills, project evidence, and experience affinity. Gemini adds: why this role fits, resume evidence, gaps, interview focus, and realistic vs stretch label. |
| 3 | **Live Job Recommendations** | Adzuna API integration for live job postings. Falls back to curated sample data with a visible "Demo Fallback" banner when no API credentials are configured. |
| 4 | **Adaptive Interview Agent** | 9 decision types (increase difficulty, deeper follow-up, confidence recovery, verify resume claim, etc.). Full agent decision trace shown in the UI after every adaptation. |
| 5 | **Agent Decision Trace** | Every question adaptation is fully explainable: Observation, Decision, Reason, Evidence, Next Action — all visible in the interview room. |
| 6 | **Audio Behavioral Signals** | Optional mic recording → faster-Whisper transcription → confidence indicator, speech clarity proxy, speaking rate, and pause count. Fallback uses heuristic estimation. |
| 7 | **Video Engagement Signals** | Optional webcam → OpenCV/MediaPipe face analysis → engagement proxy, framing, stability, motion level. Fallback uses session-length heuristics. |
| 8 | **Explainable Feedback Report** | Interview readiness verdict (Ready / Almost Ready / Needs Practice), radar chart, per-question breakdown, skill mastery map, 7-day practice plan, personalised learning resources. |
| 9 | **Fallback-Safe Architecture** | Every LLM call has a deterministic rule-based fallback. MongoDB, Whisper, and OpenCV are all optional. The system works fully without any API key or external service. |

---

## Honest AI Signal Labeling

The system uses the following language to accurately describe its behavioral signals:

| Signal | What it measures | What it is NOT |
|--------|-----------------|----------------|
| **Confidence indicator** | Whisper fluency score + pause frequency | Not psychological confidence measurement |
| **Clarity proxy** | Speech-to-text clarity score from Whisper | Not linguistic quality assessment |
| **Engagement proxy** | Face-presence rate and head stability from OpenCV | Not emotion detection or attention measurement |
| **Behavioral signals** | Derived from audio/video metadata in the session | Not psychological analysis |

Every report screen is labeled with its `behavioral_mode`: `audio`, `video`, `multimodal`, `audio_fallback`, `video_fallback`, or `placeholder`. Heuristic/fallback scores are visibly distinguished from real AI-derived scores.

---

## Architecture

### 3-Stage Resume Intelligence Pipeline

```
Stage 0: Rule-Based Extraction
  ├─ Regex patterns for skills, education, experience, projects
  ├─ Section splitting and structure detection
  └─ Output: raw ResumeAnalysis (always runs, never fails)
        │
        ▼
Stage 1: Gemini Normalization  (skipped if USE_LLM=false)
  ├─ Fixes fragmented projects (URL-only entries merged into parent)
  ├─ Normalizes abbreviations (Node→Node.js, Mongo→MongoDB)
  ├─ Expands pipe-separated stacks ("React | Node | Mongo")
  └─ Output: improved projects + skills (falls back to Stage 0 on failure)
        │
        ▼
Stage 2: Gemini Interview Intelligence  (skipped if USE_LLM=false)
  ├─ Claims to verify (with probe questions)
  ├─ Project deep-dive topics
  ├─ Interview risks and strong/weak skills
  └─ Output: intelligence fields added to ResumeAnalysis (never overwrites Stage 0/1)
```

### Role Recommendation Pipeline

```
Deterministic Scoring:
  Core skill coverage (0-55) + Bonus coverage (0-20)
  + Project evidence scan (0-18) + Experience affinity (-5..+6)
  + Skill breadth bonus (0/3/6)
  → Calibrated to 65-91 range with deterministic ±3 jitter

Gemini Enrichment (Stage 3, optional):
  role_type (realistic | stretch) + why_fit
  + resume_evidence + gaps + what_interview_will_validate
```

### Adaptive Interview Engine

```
After each answer:
  Technical score + Depth score + Correctness score
  + Audio confidence indicator (if available)
  + Video engagement proxy (if available)
  → Multimodal aggregator → Combined candidate signal
  → Intelligence engine selects: next_topic, next_difficulty, decision_type
  → Decision trace recorded: Observation, Decision, Reason, Evidence, Next Action
```

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, Vite, Tailwind CSS, React Router v6, Recharts |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, Uvicorn |
| **Database** | MongoDB 7 with Motor async client · transparent in-memory fallback |
| **LLM** | Gemini 2.0 Flash (recommended) · Anthropic Claude · Groq · xAI Grok — all optional |
| **Audio** | faster-whisper (optional) · heuristic fallback always available |
| **Video** | OpenCV + MediaPipe (optional) · heuristic fallback always available |
| **Live Jobs** | Adzuna API (optional) · curated sample fallback always shown |
| **Deploy** | Docker Compose (MongoDB + Backend + Frontend/nginx) |

---

## Project Structure

```
MockInterview.ai/
├── backend/
│   ├── main.py                          # FastAPI app + CORS + lifespan
│   ├── config.py                        # Pydantic settings (reads .env)
│   ├── requirements.txt
│   ├── agents/
│   │   ├── resume_agent.py              # Stage 0+1: rule extraction + normalization
│   │   ├── role_agent.py                # 15-role deterministic scorer
│   │   ├── adzuna_job_fetcher.py        # Adzuna live job API client
│   │   ├── job_recommender_agent.py     # skill → job matching
│   │   ├── interview_orchestrator.py    # adaptive question selection + decision trace
│   │   ├── evaluator_agent.py           # per-answer technical scoring
│   │   └── feedback_agent.py            # final report generation
│   ├── services/
│   │   ├── pdf_parser.py                # PyMuPDF + python-docx text extraction
│   │   ├── llm_service.py               # enhance_analysis, build_interview_intelligence,
│   │   │                                #   normalize_resume_extraction, enrich_roles_with_gemini
│   │   ├── llm_client.py                # unified LLM provider (Gemini / Anthropic / Groq / Grok)
│   │   ├── audio_analyzer.py            # Whisper transcription + behavioral signal scoring
│   │   ├── video_analyzer.py            # OpenCV/MediaPipe engagement proxy
│   │   └── multimodal_aggregator.py     # tech×0.45 + comm×0.20 + conf×0.15 + eng×0.10 + fit×0.10
│   ├── models/
│   │   ├── analysis.py                  # ResumeAnalysis, RoleMatch, ClaimToVerify, ProjectDeepDive
│   │   ├── resume.py  interview.py  jobs.py  audio.py  video.py
│   ├── routes/
│   │   ├── resume_routes.py             # /api/resume/upload + /api/resume/analyze
│   │   ├── interview_routes.py
│   │   ├── job_routes.py
│   │   └── scoring_routes.py            # /api/scoring/audio + /api/scoring/video
│   └── database/
│       ├── connection.py                # Motor client + in-memory fallback
│       └── store.py                     # In-memory key-value store
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── ResumeUpload.jsx         # Upload + Resume Intelligence panel
│       │   ├── RoleRecommendation.jsx   # Role cards with Gemini explanations
│       │   ├── JobRecommendation.jsx    # Job cards with live/fallback banner
│       │   ├── InterviewRoom.jsx        # Adaptive interview + Agent Trace Panel
│       │   └── FeedbackReport.jsx       # Full multimodal report
│       └── components/
│           ├── AgentTracePanel.jsx      # Observation/Decision/Reason/Evidence/Next Action
│           ├── AdaptationBadge.jsx      # Named decision type badges
│           ├── RoleCard.jsx             # Role fit explanation + realistic/stretch badge
│           └── JobCard.jsx              # LIVE/SAMPLE badge + application readiness
├── docs/
│   ├── demo_script.md                   # Full presenter guide with sample answers
│   └── architecture.md
├── sample_data/
│   └── sample_resume.txt                # Demo resume for presentations
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## Quick Start — Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- MongoDB 7 *(optional — app uses in-memory store automatically if not running)*

### 1. Clone and configure

```bash
git clone <repo-url>
cd MockInterview.ai
cp .env.example .env
# Edit .env — minimum: set USE_LLM=true and add GEMINI_API_KEY for full experience
```

### 2. Run the backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Optional: real audio transcription
pip install faster-whisper

# Optional: real video face analysis
pip install opencv-python mediapipe

# Start server
uvicorn main:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

### 3. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# ── Database (optional — falls back to in-memory) ────────────────────────────
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=mock_interview_db

# ── Frontend origin (for CORS) ────────────────────────────────────────────────
FRONTEND_URL=http://localhost:5173

# ── LLM (optional — full rule-based fallback if disabled) ─────────────────────
USE_LLM=false                         # set true to enable Gemini-powered features
LLM_PROVIDER=gemini                   # gemini | anthropic | groq | grok

# Gemini (recommended — best performance for resume intelligence)
GEMINI_API_KEY=                       # console.cloud.google.com → Gemini API
GEMINI_MODEL=gemini-2.0-flash

# Anthropic Claude (alternative)
ANTHROPIC_API_KEY=                    # console.anthropic.com

# Groq (free tier, fast)
GROQ_API_KEY=                         # console.groq.com
GROQ_MODEL=mixtral-8x7b-32768

# xAI Grok (alternative)
GROK_API_KEY=                         # console.x.ai
GROK_MODEL=grok-3

# ── Live Jobs (optional — sample fallback if not configured) ───────────────────
ADZUNA_APP_ID=                        # developer.adzuna.com
ADZUNA_APP_KEY=

# ── Frontend (Vite) ──────────────────────────────────────────────────────────
VITE_API_BASE_URL=http://localhost:8000
```

### Enabling Gemini (Recommended)

1. Go to https://console.cloud.google.com → APIs & Services → Enable "Generative Language API"
2. Create an API key under "Credentials"
3. In `.env`:
   ```
   USE_LLM=true
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your-key-here
   ```

Gemini powers: resume normalization, interview intelligence (claims/risks/probes), role enrichment (why_fit, evidence, gaps), and answer quality enhancement.

### Enabling Live Jobs (Optional)

1. Register at https://developer.adzuna.com/
2. Create an app to get `App ID` and `App Key`
3. In `.env`:
   ```
   ADZUNA_APP_ID=your-id
   ADZUNA_APP_KEY=your-key
   ```

Without Adzuna credentials, job cards are labeled "SAMPLE" and a visible "Demo Fallback Data" banner is shown.

---

## Docker Compose

```bash
cp .env.example .env     # add your API keys
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| MongoDB | localhost:27017 |

---

## Scoring Reference

### Technical scoring (per answer)

| Score | What it measures |
|-------|-----------------|
| `technical_score` | Factual correctness of the answer |
| `depth_score` | Depth, nuance, and trade-off reasoning |
| `correctness_score` | Structure, relevance, and completeness |

### Behavioral signals (final report)

| Signal | Source | What it is |
|--------|--------|-----------|
| `communication_score` | Whisper clarity rating if recorded; word-count proxy otherwise | Speech clarity indicator — not linguistic quality assessment |
| `confidence_score` | Whisper fluency + pause analysis if recorded; score trajectory otherwise | Confidence indicator — not psychological confidence measurement |
| `engagement_score` | Face-presence rate from OpenCV if camera used; session length otherwise | Engagement proxy — not attention or emotion measurement |

The `behavioral_mode` field in the report tells you exactly which signals are real vs estimated:
- `multimodal` — both Whisper audio and OpenCV video used
- `audio` / `audio_fallback` — Whisper used / heuristic audio used
- `video` / `video_fallback` — OpenCV used / heuristic video used
- `placeholder` — all behavioral scores are text-derived proxies

### Overall score formula

```
overall = technical×0.45 + communication×0.20 + confidence×0.15
        + engagement×0.10 + role_fit×0.10
```

---

## Verification Checklist

Run through this before a demo:

```
Backend
  [ ] uvicorn main:app --reload --port 8000  → starts without errors
  [ ] curl http://localhost:8000/api/health   → {"status": "ok"}
  [ ] Backend logs show "Using in-memory store" OR MongoDB connected

Frontend
  [ ] npm run dev  → starts at http://localhost:5173
  [ ] npm run build → completes with 0 errors

LLM (if enabled)
  [ ] USE_LLM=true in .env
  [ ] At least one API key configured (GEMINI_API_KEY recommended)
  [ ] Backend logs show "LLM normalization OK" / "LLM intelligence stage OK" after analyze

Fallback (works without any API key)
  [ ] Upload sample_data/sample_resume.txt with USE_LLM=false
  [ ] Analysis panel shows skills, projects, strengths
  [ ] Role recommendations appear (rule-based scores)
  [ ] Interview starts and evaluates an answer

Full flow
  [ ] Upload resume → analysis panel appears with skills + projects
  [ ] If USE_LLM=true → "Interview Intelligence" section visible with claims to verify
  [ ] Role recommendations page shows role cards with match scores
  [ ] If USE_LLM=true → "Why this role?" box and Realistic/Stretch badge visible
  [ ] Job recommendations page shows job cards
  [ ] LIVE badge with green pulse if Adzuna configured; SAMPLE badge otherwise
  [ ] Start interview → first question appears
  [ ] Submit answer → evaluation panel scores appear
  [ ] Click Next Question → AdaptationBadge shows decision type label
  [ ] Agent Trace Panel shows Observation / Decision / Reason / Evidence / Next Action
  [ ] Generate Final Report → readiness verdict + radar chart + per-question breakdown
```

---

## API Reference

### Resume

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/resume/upload` | Upload PDF/DOCX/TXT → `candidate_id` + raw text |
| `POST` | `/api/resume/analyze` | 3-stage analysis → skills, projects, intelligence fields |
| `GET`  | `/api/resume/roles/{id}` | Gemini-enriched role recommendations |

### Jobs

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/jobs/{id}` | Live (Adzuna) or sample jobs ranked by skill match |

### Interview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/interview/start` | Create session → first question |
| `GET`  | `/api/interview/{id}` | Load existing session |
| `POST` | `/api/interview/evaluate-answer` | Score answer; returns technical/depth/correctness |
| `POST` | `/api/interview/next-question` | Adaptive next question + decision trace |
| `POST` | `/api/interview/final-report` | Full multimodal report |

### Scoring

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scoring/audio` | Audio blob → transcript + behavioral signals |
| `POST` | `/api/scoring/video` | Image/clip → engagement proxy + framing |

---

## Limitations

- **Audio behavioral signals**: Without `faster-whisper`, confidence and clarity are estimated from file size and duration — not from real speech analysis. Install `pip install faster-whisper` for Whisper-derived signals.
- **Video engagement proxy**: Without `opencv-python`, engagement is estimated from session length. Install `pip install opencv-python mediapipe` for face-detection-derived signals.
- **Gemini intelligence**: All intelligence features (claims, risks, role enrichment) require `USE_LLM=true` and a configured API key. Rule-based outputs are always available without it.
- **In-memory storage**: Session data is lost on backend restart unless MongoDB is configured.
- **No persistent auth**: `candidate_id` is stored in `localStorage`. Multiple devices require MongoDB.
- **Sample jobs**: Without Adzuna credentials, job listings are curated demo data, not live postings.

---

## Adding a New Interview Role

1. Add role definition to `backend/agents/role_agent.py` (`_ROLES` list) — core skills, bonus skills, project signals, next_skills, focus_areas, probing, level_affinities
2. Add title mapping to `frontend/src/components/JobCard.jsx` (`mapToInterviewRole`)

---

*Built for hackathon demonstration of agentic AI in interview preparation.*
