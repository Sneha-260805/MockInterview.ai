# Intelligent Mock Interview Agent

An end-to-end agentic AI-powered mock interview platform. Upload a resume, get role recommendations, discover matching jobs, conduct an adaptive interview with real-time multimodal scoring, and receive explainable coaching feedback.

---

## What It Does

- **Resume understanding** — extracts skills, projects, experience, seniority, education, certifications, domains, strengths, and weak areas
- **Role inference** — ranks 8 role profiles by skill overlap; includes focus areas, missing skills to probe, and project deep-dive topics
- **Job discovery** — matches resume against live Adzuna postings (or labelled sample jobs when credentials are absent), ranked by match score
- **Dynamic interview generation** — resume-aware, role-aware questions with difficulty, target skill, expected concepts, and rubric
- **Adaptive orchestration** — the intelligence engine selects next topic and difficulty using technical score, depth, audio clarity/confidence, hesitation, video engagement/stress, role coverage, and history
- **Technical evaluation** — uses Gemini when enabled, with deterministic rubric + semantic scoring fallback
- **Audio intelligence** — real Whisper transcription when enabled; returns clarity, confidence, pace, filler words, pause/hesitation metrics, pitch/tone proxies, and source labels
- **Visual intelligence** — webcam-based face/framing/stability/engagement/stress proxy scoring with honest heuristic labels
- **Multimodal aggregation** — combines technical, communication, confidence, engagement, and role-fit signals into final scores and coaching evidence
- **Feedback & coaching** — structured report with strengths, weaknesses, adaptation trace, learning plan, radar chart, and bar chart

---

## Prerequisites

- **Docker Desktop** — recommended; runs the full stack with one command
- **Python 3.11+** — only if running the backend locally
- **Node.js 20+** — only if running the frontend locally
- **MongoDB** — optional; Docker Compose includes it; local mode falls back to in-memory storage

Optional API keys (system works without all of them):

| Key | Purpose | Fallback |
|---|---|---|
| `GEMINI_API_KEY` | AI question generation and answer evaluation | Deterministic rubric + semantic scorer |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Live job discovery | Labelled sample job listings |
| `ENABLE_REAL_AUDIO_TRANSCRIPTION=true` | Whisper speech-to-text | File-size heuristic scoring |

---

## One-Command Run

```powershell
copy .env.example .env
docker compose up --build
```

| URL | Service |
|---|---|
| http://localhost:5173 | Frontend |
| http://localhost:8000 | Backend API |
| http://localhost:8000/docs | Swagger / OpenAPI |

Run in background:
```powershell
docker compose up --build -d
```

Stop:
```powershell
docker compose down
```

---

## Local Development Setup

### Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

---

## Configuration

Copy `.env.example` to `.env` and set only what you need:

```bash
# Database
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DB_NAME=mock_interview_db

# CORS
FRONTEND_URL=http://localhost:5173

# LLM (optional)
USE_LLM=true
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash

# Audio transcription (optional)
ENABLE_REAL_AUDIO_TRANSCRIPTION=true
AUDIO_TRANSCRIPTION_MODEL=tiny
AUDIO_ANALYSIS_TIMEOUT_SECONDS=30

# Job discovery (optional)
ADZUNA_APP_ID=your_id_here
ADZUNA_APP_KEY=your_key_here

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

Do not commit `.env` — it may contain API keys.

---

## Project Structure

```
mock-interview-agent/
│
├── backend/
│   ├── agents/
│   │   ├── resume_agent.py              # Resume extraction: skills, projects, weak areas, seniority
│   │   ├── role_agent.py                # Role inference: ranks 8 profiles by skill overlap
│   │   ├── adzuna_job_fetcher.py        # Live job API integration + sample fallback
│   │   ├── job_recommender_agent.py     # Job matching: score and rank postings
│   │   ├── interview_orchestrator.py    # Session manager: 5-question flow
│   │   ├── intelligence_engine.py       # Adaptive decision engine: difficulty + topic + trace
│   │   ├── evaluator_agent.py           # Answer scoring: correctness, depth, relevance
│   │   └── feedback_agent.py            # Final report: strengths, learning plan, radar data
│   │
│   ├── services/
│   │   ├── question_generator.py        # Dynamic question creation (LLM → deterministic)
│   │   ├── audio_analyzer.py            # Whisper transcription + speech metrics
│   │   ├── video_analyzer.py            # OpenCV + MediaPipe face/engagement/stress
│   │   ├── multimodal_aggregator.py     # Weighted score combination (45/20/15/10/10)
│   │   ├── followup_generator.py        # Follow-up question generation from answer gaps
│   │   ├── semantic_scorer.py           # Embedding-based semantic answer scoring
│   │   ├── scoring_service.py           # Orchestrates evaluator + semantic + rubric scoring
│   │   ├── llm_client.py                # Gemini API wrapper with retry + fallback
│   │   ├── llm_service.py               # Higher-level LLM task helpers
│   │   ├── rubric_service.py            # Rule-based scoring fallback
│   │   └── pdf_parser.py                # PDF/TXT text extraction (PyMuPDF)
│   │
│   ├── routes/
│   │   ├── resume_routes.py             # POST /api/resume/upload, /analyse
│   │   ├── role_routes.py               # GET  /api/resume/roles/{id}
│   │   ├── job_routes.py                # GET  /api/jobs/{id}
│   │   ├── interview_routes.py          # POST /api/interview/start|evaluate|next|report
│   │   ├── scoring_routes.py            # POST /api/scoring/audio|video
│   │   └── health.py                    # GET  /api/health
│   │
│   ├── models/
│   │   ├── resume.py                    # ResumeUpload, ResumeAnalysis
│   │   ├── interview.py                 # InterviewSession, Question, FinalReport
│   │   ├── audio.py                     # AudioAnalysisRequest/Response
│   │   ├── video.py                     # VideoAnalysisRequest/Response
│   │   ├── analysis.py                  # WorkExperience, Project, Certification
│   │   ├── agent_state.py               # CandidateState, AdaptationDecision
│   │   └── jobs.py                      # JobRecommendation, JobMatch
│   │
│   ├── database/
│   │   ├── connection.py                # Motor async MongoDB client
│   │   └── store.py                     # CRUD + in-memory fallback (same interface)
│   │
│   ├── tests/
│   │   ├── test_audio_video_schema.py
│   │   ├── test_evaluator_multimodal.py
│   │   ├── test_intelligence_engine.py
│   │   ├── test_pdf_parser.py
│   │   ├── test_resume_role_question_jobs.py
│   │   ├── test_rubric_service.py
│   │   └── test_scoring_service.py
│   │
│   ├── sample_data/
│   │   └── sample_jobs.json             # Curated sample job listings (fallback pool)
│   │
│   ├── config.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.jsx                 # Landing page
│   │   │   ├── Dashboard.jsx            # Candidate dashboard
│   │   │   ├── ResumeUpload.jsx         # Resume upload + parsed-data preview
│   │   │   ├── RoleRecommendation.jsx   # Role recommendation cards
│   │   │   ├── JobRecommendation.jsx    # Job match list with live/sample badges
│   │   │   ├── InterviewRoom.jsx        # Question + audio/video + scoring UI
│   │   │   ├── FeedbackReport.jsx       # Radar chart, bar chart, learning plan
│   │   │   └── NotFound.jsx             # 404 page
│   │   │
│   │   ├── components/
│   │   │   ├── AudioRecorder.jsx        # Browser MediaRecorder → WAV blob → POST
│   │   │   ├── VideoRecorder.jsx        # getUserMedia → JPEG snapshot → POST
│   │   │   ├── QuestionPanel.jsx        # Current question + expected concepts display
│   │   │   ├── EvaluationPanel.jsx      # Per-turn score breakdown (technical/audio/video)
│   │   │   ├── ScoreCard.jsx            # Reusable score display card
│   │   │   ├── AdaptationBadge.jsx      # Next-question difficulty badge + reason tooltip
│   │   │   ├── AgentTracePanel.jsx      # Intelligence engine decision trace viewer
│   │   │   ├── CoachingNudge.jsx        # In-interview coaching hints
│   │   │   ├── ImprovementDelta.jsx     # Score change delta between turns
│   │   │   ├── InterviewPlanTimeline.jsx# Visual timeline of question topics/difficulty
│   │   │   ├── SkillMasteryMap.jsx      # Skill coverage heatmap across interview
│   │   │   ├── ReportSection.jsx        # Reusable final report section wrapper
│   │   │   ├── RoleCard.jsx             # Role recommendation card
│   │   │   ├── JobCard.jsx              # Job posting card with match score
│   │   │   ├── UploadBox.jsx            # Drag-and-drop resume upload widget
│   │   │   └── Navbar.jsx               # Top navigation bar
│   │   │
│   │   ├── services/
│   │   │   ├── api.js                   # Axios base client + interceptors
│   │   │   ├── resumeService.js         # Resume upload + analyse API calls
│   │   │   ├── interviewService.js      # Interview start/evaluate/next/report calls
│   │   │   ├── jobService.js            # Job recommendation API calls
│   │   │   └── analysisService.js       # Audio/video scoring API calls
│   │   │
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   │
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.js
│
├── sample_data/                         # Evaluation inputs + expected outputs
│   ├── sample_resume.txt                # Alex Morgan — 4-yr backend/ML engineer
│   ├── sample_jd.txt                    # Senior Backend/AI Platform Engineer JD
│   ├── expected_parsed_resume.json      # resume_agent output: 30 skills, 3 projects, certs, seniority
│   ├── expected_roles.json              # role_agent output: top-5 roles with evidence + focus areas
│   ├── expected_job_recommendations.json# job_recommender: 10 ranked jobs with match scores
│   ├── expected_interview_turn.json     # full turn: Q + eval + audio + video + adaptation trace
│   └── expected_final_report.md         # feedback_agent: per-Q breakdown, learning plan
│
├── architecture.md                      # System design, data flows, API contracts, trade-offs
├── project_structure.md                 # Module map, agent interactions, flow diagrams
├── demo_script.md                       # Step-by-step demo walkthrough
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## How Agents & Modules Interact

### Resume → Role → Job

```
Upload PDF/TXT
      │
      ▼
pdf_parser.extract_text()
      │
      ▼
resume_agent.analyse()          (Gemini LLM  or  regex/keyword fallback)
      │
      ├──▶ role_agent.recommend()
      │        Jaccard overlap vs 8 role profiles → top-5 ranked
      │
      └──▶ job_recommender_agent.recommend()
               adzuna_job_fetcher (live)  or  sample_jobs.json (fallback)
               → top-10 ranked with match score + why-fit
```

### Interview Session (per turn)

```
interview_orchestrator.start_session()
      │
      ▼
question_generator.generate()      ← role + resume + difficulty=medium
      │ Question {text, expected_concepts, rubric}
      ▼
── User answers ────────────────────────────────────────────────────────

evaluator_agent.evaluate()          audio_analyzer.analyse()    video_analyzer.analyse()
  scoring_service orchestrates        Whisper / heuristic          OpenCV / heuristic
  → semantic_scorer (embeddings)    → confidence, clarity         → engagement, eye contact
  → rubric_service  (keywords)      → hesitation, pace            → posture, stress
  → technical / depth / relevance
        │                                   │                              │
        └──────────────┬────────────────────┘                              │
                       ▼                                                   │
          multimodal_aggregator.aggregate() ◀─────────────────────────────┘
            0.45×T + 0.20×C + 0.15×Cf + 0.10×E + 0.10×R
                       │
                       ▼
          intelligence_engine.decide()
            score < 50%  → easier + encouragement
            score 50–80% → same difficulty, new topic
            score > 80%  → harder
            decision_trace stored per turn
                       │
                       ▼
          followup_generator  (if answer has gaps → targeted follow-up)
                       │
                       ▼
          question_generator.generate()    next question
```

### Final Report

```
feedback_agent.generate_report(session_id)
      ├─ mean(technical scores across all turns)
      ├─ mean(audio clarity / confidence scores)
      ├─ mean(video engagement scores)
      ├─ overall = 0.45T + 0.20C + 0.15Cf + 0.10E + 0.10R
      ├─ strengths  (covered concepts, score ≥ 70)
      ├─ weaknesses (missing concepts, score < 60)
      ├─ adaptation trace (why each difficulty shift happened)
      ├─ learning plan  (topic → curated resource + priority)
      └─ radar_data + bar_data for frontend charts
```

---

## Scoring

### Per-Answer Technical

| Dimension | Description | Range |
|---|---|---|
| Correctness | Factual accuracy of response | 0–100 |
| Depth | Detail relative to expected concepts | 0–100 |
| Relevance | Structure and alignment to question | 0–100 |
| **Overall** | Mean of the three above | 0–100 |

Evaluated by: `scoring_service` → `semantic_scorer` (embedding similarity) + `rubric_service` (keyword/concept matching), with Gemini for richer scoring when `USE_LLM=true`.

### Multimodal Aggregation

```
Overall = 0.45 × Technical
        + 0.20 × Communication Clarity   (audio)
        + 0.15 × Confidence              (audio)
        + 0.10 × Engagement              (video)
        + 0.10 × Role Fit
```

### Adaptive Difficulty

| Condition | Action |
|---|---|
| Score < 50% | Next question easier; `CoachingNudge` shown |
| Score 50–80% | Same difficulty; shift to uncovered topic |
| Score > 80% | Next question harder; probe deeper concepts |
| Repeated gaps | `followup_generator` creates targeted follow-up |
| Topic saturated | Shift to next uncovered skill area |

### Behavioral Mode Labels

| Mode | Condition |
|---|---|
| `multimodal` | Real Whisper + real OpenCV |
| `audio` | Real Whisper, no video |
| `video` | Real OpenCV, no audio |
| `audio_fallback` | Audio uploaded; Whisper timed out |
| `video_fallback` | Video uploaded; OpenCV unavailable |
| `placeholder` | No audio or video submitted |

---

## Sample Data & Expected Outputs

All files use **Alex Morgan** — a 4-year Python/backend engineer with ML experience — so evaluators can verify the full pipeline without a real resume.

### Input Files

| File | Description |
|---|---|
| `sample_data/sample_resume.txt` | Alex Morgan — Senior SWE; FastAPI, PostgreSQL, Redis, scikit-learn, Docker, AWS |
| `sample_data/sample_jd.txt` | Senior Backend / AI Platform Engineer at DataBridge Labs |
| `backend/sample_data/sample_jobs.json` | 50 curated job listings used as fallback pool when Adzuna credentials are absent |

### Expected Outputs

| File | What it shows |
|---|---|
| `expected_parsed_resume.json` | 30 skills, 3 projects with impact, 3 work experiences with highlights, 2 certs, seniority signals, 5 domains, 5 strengths, 5 weak areas |
| `expected_roles.json` | Top-5 roles (Backend 91%, ML Engineer 74%, Full Stack 72%, DevOps 61%, Data Analyst 55%) each with matched/missing skills, focus areas, weak areas to probe, project deep-dive topics |
| `expected_job_recommendations.json` | 10 ranked sample jobs; top match 94% (Senior Backend at DataBridge Labs); each with salary range, why-fit explanation, matched/missing skills, source label |
| `expected_interview_turn.json` | Q2 (hard, System Design): full question + rubric, candidate answer, technical eval (84/79/88), real Whisper audio metrics, real OpenCV video metrics, multimodal aggregate (83), adaptation decision with trace |
| `expected_final_report.md` | Overall 79/100; per-Q table; 5 strengths with evidence; 4 improvement areas with specific concept gaps; behavioral summary (Whisper + OpenCV); adaptation trace; 6-item learning plan with curated resources |

### Quick Evaluation Path

```
1.  docker compose up --build
2.  Open http://localhost:5173
3.  Upload sample_data/sample_resume.txt
4.  Verify: 30 skills, 3 projects, 2 certs extracted
    Compare → expected_parsed_resume.json
5.  Check roles: Backend Engineer #1 at ~91%
    Compare → expected_roles.json
6.  View jobs: top match ~94%, source=sample (without Adzuna keys)
    Compare → expected_job_recommendations.json
7.  Start interview → select Backend Engineer
8.  Answer Q1 with audio + webcam → submit
9.  Verify: technical score, audio metrics, video metrics, multimodal aggregate
    Compare structure → expected_interview_turn.json
10. Check AdaptationBadge: score > 80 → next question harder
11. Complete all 5 questions → generate final report
12. Verify: radar chart (5 dims), per-Q bar chart, strengths + evidence,
    learning plan with resources
    Compare → expected_final_report.md
```

---

## Tests

```powershell
# Backend
.\venv\Scripts\python.exe -B -m pytest backend\tests

# Frontend build
cd frontend && npm run build
```

Test files cover: audio/video schema validation, evaluator + multimodal pipeline, intelligence engine adaptation logic, PDF parser, resume/role/question/jobs pipeline, rubric service, and scoring service.

---

## Cloud Deployment

1. Provision Docker + Docker Compose on cloud VM
2. Clone repository; create `.env` from `.env.example`
3. Set `FRONTEND_URL` to your frontend origin
4. Set `VITE_API_BASE_URL` to your public backend URL
5. `docker compose up --build -d`
6. For production: managed MongoDB, HTTPS (reverse proxy), secret storage, authentication

---

## Known Limitations

| Area | Limitation |
|---|---|
| Authentication | None — localStorage sessions, single-device, no multi-user isolation |
| Eye contact | Face-centring proxy, not true gaze estimation |
| Posture | Face-size stability proxy, not pose estimation |
| Stress | Inter-frame head movement heuristic, not clinical classifier |
| Audio fallback | File-size heuristics without Whisper; transparent via mode label |
| Session depth | 5 questions per session; no cross-session memory |
| Language | English-only question banks and rubrics |
| Job listings | 50 curated sample jobs; Adzuna provides live postings when configured |

---

## Documentation

| File | Description |
|---|---|
| [architecture.md](architecture.md) | Deep-dive: system design, data flows, full API contracts, scoring formulas, design trade-offs |
| [project_structure.md](project_structure.md) | Module map, agent interactions, flow diagrams, API route table, scoring weights |
| [demo_script.md](demo_script.md) | Step-by-step live demo walkthrough |
