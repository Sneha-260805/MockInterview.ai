# MockInterview.ai — Intelligent Mock Interview Agent

> Upload your resume → get personalised role & job matches → practice adaptive mock interviews → receive a multimodal feedback report scored on technical accuracy, audio confidence, and video engagement.

![Python](https://img.shields.io/badge/Python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![React](https://img.shields.io/badge/React-18-61DAFB) ![Docker](https://img.shields.io/badge/Docker-Compose-2496ED) ![Anthropic](https://img.shields.io/badge/Anthropic-Claude-orange)

---

## Prerequisites

| Tool | Minimum Version | Notes |
|------|----------------|-------|
| **Docker** | 24.0+ | Only hard requirement for one-command run |
| **Docker Compose** | v2.0+ | Bundled with Docker Desktop |
| Node.js | 18+ | Only needed for local dev without Docker |
| Python | 3.11+ | Only needed for local dev without Docker |

> **No API keys required.** Every agent has a rule-based fallback — the platform runs fully offline and produces high-quality results without Claude, Whisper, or any external service.

---

## One-Command Run

```bash
# 1. Copy the environment template (edit to add optional API keys)
cp .env.example .env

# 2. Build and start all services
docker compose up --build
```

Then open **http://localhost:5173** in your browser.

| Service | URL |
|---------|-----|
| Frontend (React + Nginx) | http://localhost:5173 |
| Backend (FastAPI) | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Health Check | http://localhost:8000/api/health |
| MongoDB | localhost:27017 |

---

## Environment Variables

All variables live in `.env` (copy from `.env.example`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGODB_URL` | No | `mongodb://localhost:27017` | MongoDB connection string. App falls back to in-memory store if unreachable. |
| `MONGODB_DB_NAME` | No | `mock_interview_db` | Database name |
| `FRONTEND_URL` | No | `http://localhost:5173` | Allowed CORS origin |
| `USE_LLM` | No | `false` | Set `true` to enable Claude/Gemini enrichment for richer outputs |
| `LLM_PROVIDER` | No | `gemini` | Active LLM provider: `anthropic`, `gemini`, `grok`, `groq` |
| `ANTHROPIC_API_KEY` | No | *(empty)* | Claude API key — only needed when `USE_LLM=true` and provider is `anthropic` |
| `GEMINI_API_KEY` | No | *(empty)* | Google Gemini key |
| `ENABLE_REAL_AUDIO_TRANSCRIPTION` | No | `true` | Set `false` to skip Whisper download and use heuristic audio scoring |
| `AUDIO_TRANSCRIPTION_MODEL` | No | `tiny` | Whisper model size: `tiny`, `base`, `small`, `medium` |
| `ADZUNA_APP_ID` | No | *(empty)* | Adzuna job board App ID — enables live job listings |
| `ADZUNA_APP_KEY` | No | *(empty)* | Adzuna API key |
| `VITE_API_BASE_URL` | No | `http://localhost:8000` | Backend URL visible to the browser |

---

## Local Development (without Docker)

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install core dependencies
pip install -r requirements.txt

# Optional: real Whisper audio transcription (~150 MB model download on first run)
pip install faster-whisper

# Optional: real video face analysis
pip install opencv-python mediapipe

# Start the API server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

---

## Project Structure

```
MockInterview.ai/
├── backend/
│   ├── main.py                      # FastAPI app entry point, CORS, lifespan
│   ├── config.py                    # Pydantic settings loaded from .env
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── agents/                      # AI decision-making modules
│   │   ├── resume_agent.py          # PDF/TXT → structured skills, experience, gaps
│   │   ├── role_agent.py            # Scores candidate against 8 role profiles
│   │   ├── job_recommender_agent.py # Matches candidate to 50 curated job listings
│   │   ├── interview_orchestrator.py# Manages 5-question session + adaptive Q selection
│   │   ├── evaluator_agent.py       # Scores each answer: technical / depth / correctness
│   │   ├── feedback_agent.py        # Aggregates all scores → FinalReport + learning plan
│   │   └── intelligence_engine.py   # Builds interview plan, tracks candidate state
│   ├── services/                    # Domain-specific computation
│   │   ├── llm_client.py            # Multi-provider LLM abstraction (Claude/Gemini/Grok/Groq)
│   │   ├── audio_analyzer.py        # Whisper transcription + confidence/clarity/pace scoring
│   │   ├── video_analyzer.py        # MediaPipe face detection + engagement/posture proxies
│   │   ├── multimodal_aggregator.py # Weighted combination of all score dimensions
│   │   ├── question_generator.py    # Static question bank + optional LLM-enriched questions
│   │   ├── followup_generator.py    # Adaptive follow-up question generation
│   │   ├── scoring_service.py       # Rule-based per-answer scoring
│   │   ├── rubric_service.py        # Dimension-based evaluation rubrics
│   │   ├── semantic_scorer.py       # Semantic similarity for answer evaluation
│   │   ├── project_classifier.py    # Domain classification of resume projects
│   │   └── pdf_parser.py            # PyMuPDF text extraction from PDF files
│   ├── models/                      # Pydantic data models
│   │   ├── interview.py             # Question, InterviewSession, EvaluationResult, FinalReport
│   │   ├── analysis.py              # ResumeAnalysis, Project, WorkExperience, RoleMatch
│   │   ├── audio.py                 # AudioAnalysisResponse
│   │   ├── video.py                 # VideoAnalysisResponse
│   │   └── agent_state.py           # CandidateState, AgentDecisionTrace
│   ├── routes/                      # FastAPI endpoint handlers
│   │   ├── resume_routes.py         # /api/resume/*
│   │   ├── role_routes.py           # /api/resume/roles/*
│   │   ├── job_routes.py            # /api/jobs/*
│   │   ├── interview_routes.py      # /api/interview/*
│   │   └── scoring_routes.py        # /api/scoring/audio + /api/scoring/video
│   ├── database/                    # Persistence layer
│   │   ├── connection.py            # Motor async MongoDB client + in-memory fallback
│   │   └── store.py                 # In-memory key-value store (dict-based)
│   └── sample_data/
│       └── sample_jobs.json         # 50 curated job listings
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf                   # Production web server config
│   └── src/
│       ├── App.jsx                  # Route table
│       ├── pages/                   # Page-level React components
│       │   ├── Home.jsx             # Landing page
│       │   ├── ResumeUpload.jsx     # File upload + resume parsing UI
│       │   ├── RoleRecommendation.jsx
│       │   ├── JobRecommendation.jsx
│       │   ├── InterviewRoom.jsx    # Live interview session with Q/A loop
│       │   └── FeedbackReport.jsx   # Radar/bar charts, learning plan
│       ├── components/              # Reusable UI components
│       │   ├── AudioRecorder.jsx    # Mic recording + Whisper upload
│       │   ├── VideoRecorder.jsx    # Webcam preview + frame capture
│       │   ├── AdaptationBadge.jsx  # Shows why difficulty changed
│       │   ├── SkillMasteryMap.jsx  # Radar chart visualisation
│       │   ├── InterviewMonitor.jsx # Session progress tracking
│       │   └── CoachingNudge.jsx    # Real-time improvement suggestions
│       └── services/                # API client abstractions
│           ├── resumeService.js
│           ├── interviewService.js  # Includes analyzeAudio + analyzeVideo
│           └── jobService.js
├── docs/
│   ├── architecture.md
│   └── demo_script.md
├── sample_data/                     # Demo inputs and expected outputs
│   ├── sample_resume.txt
│   └── expected_*.json
├── submission/                      # This folder — submission deliverables
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## How Agents & Modules Interact

The platform follows a linear pipeline triggered by user actions. Each agent is stateless and communicates through structured Pydantic models stored in MongoDB (or the in-memory fallback).

```
1. Resume Upload
   User uploads PDF/TXT
   └─► pdf_parser.extract_text()
       └─► resume_agent.analyze(text)
           Extracts: skills, projects, experience, education, strengths, weak_areas
           Stores: ResumeAnalysis(candidate_id)

2. Role & Job Matching (parallel, after resume analysis)
   ├─► role_agent.recommend(candidate_id)
   │   Scores candidate against 8 role profiles
   │   Returns: top-5 roles with match_score, evidence, missing_skills
   │
   └─► job_recommender_agent.recommend(candidate_id)
       Alias-expands skills, scores 50 job listings
       Returns: top-10 jobs with match_score, apply URL

3. Interview Session (one question at a time)
   POST /api/interview/start
   └─► intelligence_engine.build_interview_plan()
       Picks 5 topics + difficulty levels based on candidate gaps
   └─► interview_orchestrator.start_session()
   └─► question_generator.generate_question()
       Returns: first Question + session_id

   For each answer:
   ├─► evaluator_agent.evaluate(question, answer)
   │   Rule-based keyword coverage + depth + correctness scoring
   │   Optional: Claude semantic scoring when USE_LLM=true
   │
   ├─► audio_analyzer.analyze(audio_blob)        [if audio recorded]
   │   Whisper transcription → confidence, clarity, pace, pauses
   │
   ├─► video_analyzer.analyze(video_blob)        [if webcam enabled]
   │   MediaPipe face detection → engagement, eye-contact, posture, stress
   │
   └─► intelligence_engine.next_decision()
       Reads last score → adapts difficulty
       └─► question_generator.generate_question()  → next Question

4. Final Report
   POST /api/interview/final-report
   └─► multimodal_aggregator.aggregate_session()
       Combines: technical(0.45) + communication(0.20) + confidence(0.15)
                + engagement(0.10) + role_fit(0.10)
   └─► feedback_agent.generate()
       Produces: overall_score, technical/communication/confidence/engagement/role_fit scores,
                 answer_summaries, recommended_learning_plan, strengths, improvement_areas,
                 behavioral_mode label, readiness_level, 7-day plan
       (Frontend renders radar + bar charts client-side from these score fields)
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/resume/upload` | Upload PDF or TXT; returns `candidate_id` and text preview |
| `POST` | `/api/resume/analyse` | Run AI analysis on extracted text; returns skills, experience, projects |
| `GET` | `/api/resume/roles/{candidate_id}` | Role recommendations ranked by match score |
| `GET` | `/api/jobs/{candidate_id}` | Top-10 job matches from 50-listing database |
| `POST` | `/api/interview/start` | Start a session; returns first question, session_id, interview plan |
| `GET` | `/api/interview/{session_id}` | Load an existing interview session |
| `POST` | `/api/interview/evaluate-answer` | Score an answer (technical / depth / correctness) |
| `POST` | `/api/interview/next-question` | Get next adaptive question with adaptation reason |
| `POST` | `/api/interview/final-report` | Generate full feedback report with radar/bar charts |
| `POST` | `/api/scoring/audio` | Upload audio blob → transcript + confidence + clarity + pace |
| `POST` | `/api/scoring/video` | Upload image/video → engagement + eye-contact + posture + stress |
| `GET` | `/api/health` | Health check |

---

## Sample Inputs & Expected Outputs

See the `sample_inputs_outputs/` folder (or `../sample_data/` in the repo root):

| File | Description |
|------|-------------|
| `sample_resume.txt` | Demo resume — Alex Morgan, 4-year full-stack/backend engineer |
| `sample_job_description.txt` | Example JD for a Mid-Level Full-Stack Engineer role |
| `expected_resume_analysis.json` | What `POST /api/resume/analyse` returns for the sample resume |
| `expected_role_recommendations.json` | Top-5 role matches with scores and evidence |
| `expected_interview_qa.json` | One complete Q/A turn with technical + audio + video scores |
| `expected_final_report.json` | Full 5-question session final report with radar data and learning plan |

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```

```bash
cd frontend
npm run build    # Type-checks and produces production bundle
```

---

## Demo Walkthrough

1. Open **http://localhost:5173**
2. Click **Start Practicing** → **Upload Resume**
3. Upload `sample_data/sample_resume.txt` (or your own PDF)
4. Click **Analyse Resume** → see extracted skills, experience, projects
5. Click **View Recommended Roles** → see ranked roles with evidence
6. Click **View Recommended Jobs** → see top job matches
7. On any role card, click **Start Mock Interview**
8. Answer the first question — type, or record audio, or enable webcam
9. Submit → see per-answer scores, covered/missing points, feedback
10. Click **Next Question** — observe the **Adaptation Badge** explaining why difficulty changed
11. After 3+ questions, click **Generate Final Report**
12. Explore the radar chart, bar chart, per-question breakdown, and learning plan

---

*Built as a hackathon project demonstrating agentic AI in real-world interview preparation.*
