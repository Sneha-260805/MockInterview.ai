# MockInterview.ai — Intelligent Mock Interview Agent

> An end-to-end agentic AI platform for interview preparation.  
> **Resume upload → Resume intelligence → Role & job recommendations → Adaptive interview → Multimodal scoring → Explainable feedback.**

---

## What Makes This Different

This is **not a chatbot**. It is a resume-aware, role-aware, adaptive interview coach:

| Capability | What the system does |
|---|---|
| **Resume Intelligence** | Extracts skills, projects, seniority, domains — then generates *claims to verify*, *deep-dive candidates*, *interview risks*, and *probe questions* |
| **Agentic Role Selection** | Claude reads the resume and selects the best-fit roles — ordered by fit, not just keyword overlap. Can surface a custom role not in the catalog (e.g. "NLP Research Engineer") with resume-specific evidence, focus areas, and gaps |
| **Live Job Recommendations** | Fetches live postings via Adzuna API; falls back to curated sample jobs (always clearly labelled as live or fallback) |
| **Adaptive Interview Engine** | Generates personalised first questions from your resume; adapts difficulty after every answer based on score + confidence |
| **Agent Decision Trace** | Shows the agent's full reasoning chain — observation → evidence → decision → why → next action |
| **Multimodal Scoring** | Technical (LLM/rule-based), Audio (Whisper confidence/clarity/pace), Video (OpenCV engagement/eye-contact proxy/stress proxy) |
| **Explainable Feedback** | Per-answer scores, covered/missing points, learning plan, radar chart |

---

## Demo Flow

```
Upload Resume
      ↓
Resume Intelligence Panel
(strong skills · project deep-dives · claims to verify · interview risks)
      ↓
Role Recommendations
(match score · resume evidence · gaps · realistic/stretch label)
      ↓
Job Recommendations
(live or sample · match score · why-fit · recommended preparation)
      ↓
Start Interview (personalised first question from resume)
      ↓
Submit Answer  →  Score + Agent Decision Trace
      ↓
Next Adaptive Question (harder if strong · simpler if weak)
      ↓
Final Feedback Report (radar chart · learning plan · per-question breakdown)
```

---

## Features at a Glance

| # | Feature | Implementation |
|---|---------|----------------|
| 1 | Resume Intelligence | Rule-based + optional LLM enhancement |
| 2 | Agentic Role Selection | Claude selects + orders roles; injects custom role if resume shows a specialisation not in catalog; rule-based scoring fallback |
| 3 | Live Job Recommendations | Adzuna API (fallback: sample_jobs.json) |
| 4 | Adaptive Interview | LLM question generation + static bank fallback |
| 5 | Agent Decision Trace | Frontend-rendered from backend scores + reason |
| 6 | Audio Intelligence | Whisper (faster-whisper) speech-to-text + heuristic scoring |
| 7 | Video Intelligence | OpenCV + MediaPipe face detection (heuristic proxies) |
| 8 | Final Feedback Report | Radar/bar charts + learning plan |

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, Vite, Tailwind CSS, React Router v6, Axios, Recharts |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, Uvicorn, Motor (async MongoDB) |
| **Database** | MongoDB 7 · automatic in-memory fallback (no setup required) |
| **AI / LLM** | Anthropic Claude `claude-sonnet-4-6` (optional; rule-based fallback always active) |
| **Audio** | `faster-whisper` or `openai-whisper` (optional; heuristic fallback always active) |
| **Video** | OpenCV + MediaPipe (optional; heuristic fallback always active) |
| **Job API** | Adzuna REST API (optional; sample_jobs.json fallback always active) |
| **Deploy** | Docker Compose (MongoDB + Backend + Frontend/nginx) |

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- MongoDB 7 *(optional — auto in-memory fallback)*
- Anthropic API key *(optional — rule-based fallback)*
- Adzuna API credentials *(optional — sample jobs fallback)*

---

## Quick Start — Local Development

### 1. Clone and configure

```bash
git clone <repo-url>
cd mock-interview-agent
cp .env.example .env
# Edit .env with your values (see Environment Variables below)
```

### 2. Run the backend

```bash
cd backend

# Create and activate virtualenv
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install core dependencies
pip install -r requirements.txt

# Optional — real Whisper audio transcription (much better than heuristic)
pip install faster-whisper

# Optional — real video face analysis
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

## One-Command Run (Docker)

```bash
cp .env.example .env   # edit as needed
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend (nginx) | http://localhost:5173 |
| Backend (FastAPI) | http://localhost:8000 |
| MongoDB | localhost:27017 |

---

## Environment Variables

All variables live in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB_NAME` | `mock_interview_db` | Database name |
| `FRONTEND_URL` | `http://localhost:5173` | Allowed CORS origin |
| `USE_LLM` | `false` | Set `true` to enable Claude for richer responses |
| `ANTHROPIC_API_KEY` | *(empty)* | Required when `USE_LLM=true` |
| `ADZUNA_APP_ID` | *(empty)* | Adzuna API app ID for live job fetching |
| `ADZUNA_APP_KEY` | *(empty)* | Adzuna API app key |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend URL seen by the browser |

### Enabling LLM Mode

```bash
# .env
USE_LLM=true
ANTHROPIC_API_KEY=sk-ant-...
```

All agents use `claude-sonnet-4-6` for richer, personalised outputs. Rule-based fallbacks remain active for API failure resilience.

### Enabling Whisper Audio

```bash
pip install faster-whisper
# No env variable needed — auto-detected at startup
```

### Enabling Live Job Fetching (Adzuna)

```bash
# .env
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key
```

Without credentials, the system falls back to `sample_data/sample_jobs.json`. The UI clearly labels each job as **"Live Posting"** or **"Sample Job"** — no false claims.

---

## Project Structure

```
mock-interview-agent/
├── backend/
│   ├── main.py                      # FastAPI app + CORS + lifespan
│   ├── config.py                    # Pydantic settings (.env)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── agents/
│   │   ├── resume_agent.py          # Resume Intelligence — skills, claims, deep-dives, risks
│   │   ├── role_agent.py            # Role matching — evidence, gaps, role_type, why_fit
│   │   ├── job_recommender_agent.py # Job scoring — is_live, application_readiness, why_fit
│   │   ├── adzuna_job_fetcher.py    # Live job fetching (returns is_live flag)
│   │   ├── interview_orchestrator.py# Adaptive Q generation + adaptation_reason
│   │   ├── evaluator_agent.py       # Answer scoring (technical/depth/correctness)
│   │   └── feedback_agent.py        # Final report generation
│   ├── services/
│   │   ├── pdf_parser.py            # PyMuPDF text extraction
│   │   ├── llm_service.py           # Claude enhancement layer (all new intel fields)
│   │   ├── audio_analyzer.py        # Whisper transcription + confidence/clarity/pace
│   │   └── video_analyzer.py        # OpenCV/MediaPipe engagement/eye-contact proxy
│   ├── models/
│   │   ├── analysis.py              # ResumeAnalysis, ClaimToVerify, ProjectDeepDive, RoleMatch
│   │   ├── jobs.py                  # JobListing, JobMatch (is_live, apply_url, readiness)
│   │   ├── interview.py  resume.py  audio.py  video.py
│   ├── routes/
│   │   ├── resume_routes.py  role_routes.py  job_routes.py
│   │   ├── interview_routes.py
│   │   └── scoring_routes.py        # /api/scoring/audio + /api/scoring/video
│   ├── database/
│   │   ├── connection.py            # Motor async + in-memory fallback
│   │   └── store.py                 # In-memory key-value store
│   └── sample_data/
│       └── sample_jobs.json         # Curated fallback job listings
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── ResumeUpload.jsx     # Upload + full intelligence panel
│   │   │   ├── RoleRecommendation.jsx
│   │   │   ├── JobRecommendation.jsx
│   │   │   ├── InterviewRoom.jsx    # Interview + AgentTracePanel integration
│   │   │   └── FeedbackReport.jsx
│   │   └── components/
│   │       ├── AgentTracePanel.jsx  # 5-step agent reasoning UI (NEW)
│   │       ├── RoleCard.jsx         # + role_type, evidence, gaps, why_fit
│   │       ├── JobCard.jsx          # + is_live badge, apply_url, readiness
│   │       ├── AdaptationBadge.jsx
│   │       ├── AudioRecorder.jsx
│   │       └── VideoRecorder.jsx
├── docs/
│   ├── architecture.md
│   └── demo_script.md               # Full step-by-step demo guide with sample answers
├── sample_data/
│   └── sample_resume.txt            # Demo resume for presentations
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (React + Vite)                    │
│                                                             │
│  /upload → /roles → /jobs → /interview → /report           │
│                                                             │
│  AgentTracePanel: observation → evidence → decision → why  │
└────────────────────────┬────────────────────────────────────┘
                         │ REST / JSON
┌────────────────────────▼────────────────────────────────────┐
│                 FastAPI Backend (port 8000)                  │
│                                                             │
│  resume_agent      → skills, projects, claims_to_verify,   │
│                       project_deep_dives, interview_risks   │
│                                                             │
│  role_agent        → LLM selects roles + custom role;       │
│                       match_score, why_fit, resume_evidence,│
│                       gaps, role_type (Realistic/Stretch)   │
│                                                             │
│  job_recommender   → match_score, why_fit, is_live,        │
│  + adzuna_fetcher    apply_url, application_readiness       │
│                                                             │
│  interview_orchestrator → personalised first question,      │
│                           adaptive next question,           │
│                           reason_for_adaptation             │
│                                                             │
│  evaluator_agent   → technical/depth/correctness scores,   │
│                       covered/missing points, feedback      │
│                                                             │
│  audio_analyzer    → Whisper transcript + confidence score, │
│                       clarity score, pace, pause count      │
│                                                             │
│  video_analyzer    → engagement indicator,                  │
│                       eye-contact proxy, posture proxy,     │
│                       stress/nervousness proxy              │
│                                                             │
│  feedback_agent    → final report + learning plan           │
└─────────────────────────────────────────────────────────────┘
```

---

## API Reference

### Resume

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/resume/upload` | Upload PDF/TXT; returns `candidate_id` + extracted text |
| `POST` | `/api/resume/analyse` | AI analysis → skills, claims_to_verify, project_deep_dives, roles |
| `GET`  | `/api/resume/roles/:id` | Role recommendations with evidence, gaps, why_fit |

### Jobs

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/jobs/:id` | Top-10 job matches with is_live, why_fit, application_readiness |

### Interview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/interview/start` | Begin session → personalised first question |
| `GET`  | `/api/interview/:id` | Load existing session |
| `POST` | `/api/interview/evaluate-answer` | Score an answer (technical/depth/correctness) |
| `POST` | `/api/interview/next-question` | Adaptive next question + reason_for_adaptation |
| `POST` | `/api/interview/final-report` | Full feedback report + learning plan |

### Scoring

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scoring/audio` | Audio blob → transcript + confidence + clarity + pace + pauses |
| `POST` | `/api/scoring/video` | Image/clip → engagement + eye-contact proxy + posture proxy + stress proxy |

---

## Scoring Approach

### Technical Score (per answer)
```
technical_score   (0–100)  — factual correctness + keyword coverage
depth_score       (0–100)  — depth, nuance, and detail level
correctness_score (0–100)  — structure and relevance
```

### Audio Signals (explainable behavioural proxies)
```
confidence_score               — derived from fluency, pause rate, and word count
communication_clarity_score    — derived from transcription quality and filler-word rate
speaking_rate                  — slow / medium / fast (words per minute)
pause_count                    — number of pauses > 1.5 seconds
```
> **Honest language:** When `faster-whisper` is installed, these are derived from Whisper transcription. Without it, they are estimated from audio file size and duration. Both modes are labelled in the UI (`mode: "whisper"` or `mode: "fallback"`).

### Video Signals (explainable behavioural proxies)
```
engagement_score    — face-presence rate proxy (fraction of frames with detected face)
eye_contact_score   — gaze-direction proxy (face position relative to camera centre)
posture_score       — shoulder/head landmark proxy (MediaPipe pose estimation)
stress_indicator    — low / medium / high (derived from blink rate and movement)
```
> **Honest language:** These are heuristic proxies using OpenCV and MediaPipe, not emotion detection models. The UI labels the mode (`mode: "opencv"` or `mode: "fallback"`). The problem statement explicitly permits heuristics-based scoring.

### Overall Score Formula
```
overall = technical × 0.45 + communication × 0.20 + confidence × 0.15
        + engagement × 0.10 + role_fit × 0.10
```

---

## Sample Input / Expected Output

### Resume Input
See `sample_data/sample_resume.txt` — a MERN-stack junior developer profile.

### Expected Resume Analysis Output
```json
{
  "strong_skills": ["React", "Node.js", "MongoDB", "JavaScript", "Python"],
  "claims_to_verify": [
    {
      "claim": "Built a Spotify Clone using React and Node.js",
      "why_verify": "Resume does not mention authentication, deployment, or database design",
      "probe_question": "Walk me through the architecture — how did you handle user authentication and data flow?"
    }
  ],
  "project_deep_dives": [
    {
      "project": "Spotify Clone",
      "why_selected": "Most prominent project — best evidence of technical capability",
      "probe_topics": ["component architecture", "state management", "API integration"]
    }
  ],
  "interview_risks": [
    "No testing framework mentioned — may struggle with test strategy questions",
    "No deployment experience visible — cloud/infra questions may be weak"
  ]
}
```

### Expected Role Recommendation Output
```json
{
  "role": "Frontend Developer",
  "match_score": 84,
  "role_type": "realistic",
  "why_fit": "Strong match for Frontend Developer as a junior candidate. Key skills React, JavaScript, CSS align well with the role. Some gaps exist but the foundational competency is present.",
  "resume_evidence": [
    "React listed in skills",
    "JavaScript listed in skills",
    "Spotify Clone project uses react"
  ],
  "gaps": [
    "Testing frameworks (Jest, Cypress) not mentioned",
    "TypeScript not listed — increasingly required"
  ]
}
```

### Expected Job Match Output
```json
{
  "title": "Junior Frontend Developer",
  "company": "ABC Technologies",
  "location": "Hyderabad",
  "match_score": 78,
  "is_live": false,
  "matched_skills": ["React", "JavaScript", "CSS"],
  "missing_skills": ["TypeScript", "Jest"],
  "why_fit": "Good match for ABC Technologies's Junior Frontend Developer position. Your React, JavaScript, CSS skills cover 6 of 8 requirements.",
  "application_readiness": "Good match — apply. Brush up on TypeScript and Jest before the interview.",
  "apply_url": ""
}
```

---

## Known Limitations

| Area | Limitation |
|------|-----------|
| **Audio (no Whisper)** | Without `faster-whisper`, audio scores are estimated from file size. Install `pip install faster-whisper` for real transcription |
| **Video (no OpenCV)** | Without `opencv-python`, video scores use frame-count heuristics. Install `pip install opencv-python mediapipe` for real analysis |
| **Video signals** | Face-based proxies (engagement, eye-contact, posture) are heuristic indicators — not emotion models. Explicitly labelled in UI |
| **Job data** | Without Adzuna credentials, sample jobs from `sample_jobs.json` are used — labelled "Sample Job" in UI |
| **No auth** | `candidate_id` stored in `localStorage`. Multi-device continuity requires MongoDB |
| **In-memory** | Data lost on backend restart without MongoDB |
| **Agent trace** | Shown from Q2 onward (requires at least one previous answer) |

---

## Manual Verification Checklist

Run these checks after setup to confirm correctness:

```bash
# 1. Backend health
curl http://localhost:8000/api/health

# 2. Resume upload
curl -X POST http://localhost:8000/api/resume/upload \
  -F "file=@sample_data/sample_resume.txt"
# Expected: { "candidate_id": "...", "status": "success" }

# 3. Resume analysis
curl -X POST http://localhost:8000/api/resume/analyse \
  -H "Content-Type: application/json" \
  -d '{"candidate_id":"<id>","raw_text":"<text from step 2>"}'
# Expected: analysis.claims_to_verify is non-empty list
# Expected: analysis.strong_skills is non-empty list
# Expected: roles.recommended_roles[0].resume_evidence is non-empty

# 4. Job recommendations
curl http://localhost:8000/api/jobs/<candidate_id>
# Expected: recommended_jobs[0].is_live is true/false (not missing)
# Expected: recommended_jobs[0].application_readiness is non-empty
# Expected: recommended_jobs[0].why_fit mentions specific skills

# 5. Interview session
curl -X POST http://localhost:8000/api/interview/start \
  -H "Content-Type: application/json" \
  -d '{"candidate_id":"<id>","selected_role":"Frontend Developer"}'
# Expected: first_question references candidate's project or skills

# 6. Frontend — open http://localhost:5173
# - Upload sample_data/sample_resume.txt
# - Check: "Strongest Skills" section visible
# - Check: "Claims to Verify" section shows at least 1 claim
# - Check: "Interview Deep-Dive Candidates" section visible
# - Navigate to roles: RoleCard shows "Realistic Fit" / "Stretch Goal" badge
# - Click "Show resume evidence & gaps": evidence and gap lists visible
# - Navigate to jobs: "Live Posting" or "Sample Job" badge visible
# - Start interview, answer 2+ questions
# - Check: AgentTracePanel appears from Q2 onward with 5 trace steps
```

---

## Future Improvements

- [ ] Real-time voice-to-text during typing (Web Speech API)
- [ ] Live video proctoring with per-frame analysis
- [ ] User accounts and progress tracking dashboard
- [ ] Company-specific question banks
- [ ] Peer comparison analytics
- [ ] Export report as PDF
- [ ] Mobile-responsive interview room
- [ ] Coding round simulation with execution

---

*Built for the Hackathon — demonstrating agentic AI in real-world interview preparation.*
