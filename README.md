# Intelligent Mock Interview Agent

> An end-to-end AI-powered interview preparation platform built as a hackathon project.  
> Upload your resume → get personalised role & job matches → practice adaptive mock interviews → receive a multimodal feedback report with audio and video intelligence.

---

## Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Resume Intelligence** | Upload PDF/TXT → LLM/rule extraction of skills, experience, projects, strengths and weak areas |
| 2 | **Role Recommendations** | Match resume against 8 engineering roles; ranked by skill overlap |
| 3 | **Job Recommendations** | Score 50 curated job listings against your skills; canonical alias matching |
| 4 | **Adaptive Mock Interviews** | 5-question sessions that adjust difficulty based on your last score |
| 5 | **Real-time Evaluation** | Per-answer technical, depth and correctness scores with covered/missing point breakdown |
| 6 | **Final Feedback Report** | Radar chart + bar chart + personalised learning plan + LLM/rule-based feedback |
| 7 | **Audio Intelligence** | Optional mic recording → Whisper transcription → confidence, clarity, pause & pace scores |
| 8 | **Video Intelligence** | Optional webcam → OpenCV/MediaPipe face analysis → engagement, eye-contact, posture & stress |

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, Vite, Tailwind CSS, React Router v6, Axios, Recharts |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, Uvicorn, Motor (async MongoDB) |
| **Database** | MongoDB 7 · automatic in-memory fallback (no setup required) |
| **AI/LLM** | Anthropic Claude (optional) · rule-based engines always available |
| **Audio** | faster-whisper or openai-whisper (optional, fallback always works) |
| **Video** | OpenCV + MediaPipe (optional, fallback always works) |
| **Deploy** | Docker Compose (MongoDB + Backend + Frontend/nginx) |

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        Browser (React + Vite)                            │
│                                                                          │
│  /upload → /roles/:id → /jobs/:id → /interview/:id → /report/:id        │
│                                                                          │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ ResumeUpload│  │RoleRecommend│  │ InterviewRoom │  │ FeedbackReport│  │
│  │            │  │             │  │               │  │               │  │
│  │            │  │             │  │ AudioRecorder │  │ RadarChart    │  │
│  │            │  │             │  │ VideoRecorder │  │ BarChart      │  │
│  └─────┬──────┘  └──────┬──────┘  └──────┬────────┘  └───────┬───────┘  │
└────────┼────────────────┼────────────────┼───────────────────┼──────────┘
         │ REST/JSON       │                │                   │
┌────────▼────────────────▼────────────────▼───────────────────▼──────────┐
│                     FastAPI Backend (port 8000)                          │
│                                                                          │
│  POST /api/resume/upload         → resume_agent (parse + analyse)        │
│  GET  /api/resume/roles/:id      → role_agent   (score + rank)           │
│  GET  /api/jobs/:id              → job_recommender_agent                 │
│  POST /api/interview/start       → interview_orchestrator                │
│  POST /api/interview/evaluate    → evaluator_agent                       │
│  POST /api/interview/next-question → interview_orchestrator (adaptive)   │
│  POST /api/interview/final-report  → feedback_agent                      │
│  POST /api/scoring/audio         → audio_analyzer (Whisper / fallback)   │
│  POST /api/scoring/video         → video_analyzer (OpenCV / fallback)    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ In-memory store  ←→  MongoDB 7 (motor async)                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
mock-interview-agent/
├── backend/
│   ├── main.py                     # FastAPI app + CORS + lifespan hooks
│   ├── config.py                   # Pydantic settings (.env)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── agents/
│   │   ├── resume_agent.py         # PDF → structured analysis
│   │   ├── role_agent.py           # skill → role matching
│   │   ├── job_recommender_agent.py# skill → job scoring (50 jobs)
│   │   ├── interview_orchestrator.py# adaptive Q selection
│   │   ├── evaluator_agent.py      # answer scoring
│   │   └── feedback_agent.py       # final report generation
│   ├── services/
│   │   ├── pdf_parser.py           # PyMuPDF text extraction
│   │   ├── audio_analyzer.py       # Whisper transcription + scoring
│   │   └── video_analyzer.py       # OpenCV/MediaPipe face analysis
│   ├── models/
│   │   ├── resume.py  analysis.py  interview.py  jobs.py
│   │   ├── audio.py               # AudioAnalysisResponse
│   │   └── video.py               # VideoAnalysisResponse
│   ├── routes/
│   │   ├── resume_routes.py  role_routes.py  job_routes.py
│   │   ├── interview_routes.py
│   │   └── scoring_routes.py       # /api/scoring/audio + /api/scoring/video
│   ├── database/
│   │   ├── connection.py           # Motor async client + in-memory fallback
│   │   └── store.py                # In-memory key-value store
│   └── sample_data/
│       └── sample_jobs.json        # 50 curated job listings
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── src/
│   │   ├── App.jsx                 # Route table
│   │   ├── pages/
│   │   │   ├── Home.jsx            # Landing page
│   │   │   ├── Dashboard.jsx
│   │   │   ├── ResumeUpload.jsx
│   │   │   ├── RoleRecommendation.jsx
│   │   │   ├── JobRecommendation.jsx
│   │   │   ├── InterviewRoom.jsx
│   │   │   └── FeedbackReport.jsx
│   │   ├── components/
│   │   │   ├── AudioRecorder.jsx   # Mic recording + Whisper upload
│   │   │   ├── VideoRecorder.jsx   # Webcam preview + frame/clip upload
│   │   │   ├── AdaptationBadge.jsx
│   │   │   ├── ScoreCard.jsx
│   │   │   ├── ReportSection.jsx
│   │   │   ├── JobCard.jsx
│   │   │   └── RoleCard.jsx
│   │   └── services/
│   │       ├── api.js
│   │       ├── resumeService.js
│   │       ├── analysisService.js
│   │       ├── jobService.js
│   │       └── interviewService.js  # includes analyzeAudio + analyzeVideo
├── docs/
│   ├── architecture.md
│   └── demo_script.md
├── sample_data/
│   └── sample_resume.txt           # Demo resume for presentations
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
cd mock-interview-agent
cp .env.example .env          # edit values as needed
```

### 2. Run the backend

```bash
cd backend

# Create and activate virtualenv
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Core dependencies
pip install -r requirements.txt

# Optional: real audio transcription (much better than heuristic fallback)
pip install faster-whisper

# Optional: real video face analysis
pip install opencv-python mediapipe

# Start server
uvicorn main:app --reload --port 8000
```

- API: <http://localhost:8000>
- Swagger docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>

### 3. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

App: <http://localhost:5173>

---

## Running with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

| Service  | URL |
|----------|-----|
| Frontend (nginx) | <http://localhost:5173> |
| Backend (FastAPI) | <http://localhost:8000> |
| MongoDB | localhost:27017 |

---

## Environment Variables

All variables live in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB_NAME` | `mock_interview_db` | Database name |
| `FRONTEND_URL` | `http://localhost:5173` | Allowed CORS origin |
| `USE_LLM` | `false` | Enable Claude LLM for richer responses |
| `ANTHROPIC_API_KEY` | *(empty)* | Required only when `USE_LLM=true` |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend URL seen by the browser |

> **MongoDB is optional.** If `MONGODB_URL` is unreachable the app silently switches to an in-memory store. All features work; data is lost on server restart.

> **LLM is optional.** Every agent has a rule-based fallback that produces high-quality outputs without an API key.

---

## API Reference

### Resume

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/resume/upload` | Upload PDF/TXT; returns `candidate_id` + extracted text |
| `POST` | `/api/resume/analyse` | Run AI analysis on extracted text; returns skills, experience, projects |
| `GET`  | `/api/resume/roles/:id` | Role recommendations ranked by match score |

### Jobs

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/jobs/:id` | Top-10 job matches from 50-listing database |

### Interview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/interview/start` | Begin session; returns first question |
| `GET`  | `/api/interview/:id` | Load existing session |
| `POST` | `/api/interview/evaluate-answer` | Score an answer (technical / depth / correctness) |
| `POST` | `/api/interview/next-question` | Adaptive next question with reason |
| `POST` | `/api/interview/final-report` | Generate full feedback report |

### Scoring (Audio & Video)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scoring/audio` | Upload audio blob → transcript + confidence + clarity + pace + pauses |
| `POST` | `/api/scoring/video` | Upload image/clip → engagement + eye-contact + posture + stress |

Both scoring endpoints accept optional `session_id` and `question_number` form fields to persist results on the session so the final report includes them.

---

## Demo Flow

1. Open <http://localhost:5173>
2. Click **Start Practicing** → **Upload Resume**
3. Upload `sample_data/sample_resume.txt` (or your own PDF)
4. Click **Analyse Resume** → see parsed skills, experience, projects
5. Click **View Recommended Roles** → see ranked roles
6. Click **View Recommended Jobs** → see top job matches
7. On a role card click **Start Mock Interview**
8. Answer the first question (type *or* record audio/enable webcam)
9. Submit → see scores + feedback → click **Next Question**
10. See adaptation badge explaining *why* the difficulty changed
11. After 3+ questions click **Generate Final Report**
12. Explore radar chart, bar chart, learning plan, per-question breakdown

---

## Scoring Approach

### Technical score (per answer)
```
technical_score  (0-100)  — factual correctness
depth_score      (0-100)  — depth and nuance
correctness_score(0-100)  — structure and relevance
```

### Behavioral scores (final report)
```
communication_score  — audio clarity if recorded, else word-count proxy
confidence_score     — audio fluency/pauses if recorded, else score trajectory
engagement_score     — face-presence rate if camera used, else session length
```
`behavioral_mode` in the report indicates source: `"audio"` | `"video"` | `"multimodal"` | `"audio_fallback"` | `"video_fallback"` | `"placeholder"`

### Overall score formula
```
overall = technical×0.45 + communication×0.20 + confidence×0.15
        + engagement×0.10 + role_fit×0.10
```

---

## Limitations

- **Audio fallback**: Without `faster-whisper` installed, audio scores are estimated from file size. Install `pip install faster-whisper` for real Whisper transcription.
- **Video fallback**: Without `opencv-python`, video scores are heuristic. Install `pip install opencv-python mediapipe` for real face detection.
- **No persistent auth**: `candidate_id` is stored in `localStorage`. Multi-device/session continuity requires MongoDB.
- **Behavioral scores**: Even with audio/video, these are proxies — not replacements for human observation.
- **50 job listings**: The job database is curated sample data, not a live job board.
- **In-memory storage**: Data is lost on backend restart unless MongoDB is configured.

---

## Future Improvements

- [ ] Real-time voice-to-text during typing (Web Speech API integration)
- [ ] Live video proctoring with per-frame emotion detection
- [ ] Multi-turn conversation memory across sessions
- [ ] User accounts and progress tracking dashboard
- [ ] Live job board integration (LinkedIn / Indeed API)
- [ ] Company-specific question banks
- [ ] Peer comparison analytics
- [ ] Mobile-responsive interview room
- [ ] Export report as PDF

---

## Development Notes

### Adding a new interview role

1. Add role entry to `backend/agents/role_agent.py` (`_ROLE_QUESTION_BANKS`)
2. Add role mapping to `frontend/src/components/JobCard.jsx` (`mapToInterviewRole`)

### Enabling LLM mode

```bash
# .env
USE_LLM=true
ANTHROPIC_API_KEY=sk-ant-...
```

All agents will use `claude-sonnet-4-6` for richer outputs. Rule-based fallbacks remain for resilience.

### Running tests

```bash
cd backend
pytest                        # (test suite to be added)
```

---

*Built with ❤️ as a hackathon project demonstrating agentic AI in real-world interview preparation.*
