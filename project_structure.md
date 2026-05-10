# Project Structure & Module Interaction

## Repository Layout

```
mock-interview-agent/
├── backend/
│   ├── agents/                          # Core intelligent agents
│   │   ├── resume_agent.py              # Resume parsing → skills, projects, weak areas
│   │   ├── role_agent.py                # Role inference → ranked role profiles
│   │   ├── job_recommender_agent.py     # Job matching → live/sample postings
│   │   ├── interview_orchestrator.py    # Session management → question flow
│   │   ├── intelligence_engine.py       # Adaptive decision engine → difficulty/topic
│   │   ├── evaluator_agent.py           # Answer scoring → correctness/depth/relevance
│   │   ├── feedback_agent.py            # Final report → strengths, learning plan
│   │   └── __init__.py
│   │
│   ├── services/                        # Processing & analysis services
│   │   ├── question_generator.py        # Dynamic question creation (LLM + fallback)
│   │   ├── multimodal_aggregator.py     # Weighted score combination
│   │   ├── audio_analyzer.py            # Whisper transcription + speech metrics
│   │   ├── video_analyzer.py            # OpenCV face detection + behavioral metrics
│   │   ├── pdf_parser.py                # PDF/TXT text extraction (PyMuPDF)
│   │   ├── llm_client.py                # Gemini API wrapper with retry/fallback
│   │   ├── rubric_service.py            # Rule-based answer scoring fallback
│   │   └── adzuna_job_fetcher.py        # Live job API integration
│   │
│   ├── routes/                          # FastAPI route handlers
│   │   ├── resume_routes.py             # POST /api/resume/upload, /analyse
│   │   ├── role_routes.py               # GET  /api/resume/roles/{id}
│   │   ├── job_routes.py                # GET  /api/jobs/{id}
│   │   ├── interview_routes.py          # POST /api/interview/start|evaluate|next|report
│   │   ├── scoring_routes.py            # POST /api/scoring/audio|video
│   │   └── health.py                    # GET  /api/health
│   │
│   ├── models/                          # Pydantic data contracts
│   │   ├── resume.py                    # ResumeUpload, ResumeAnalysis
│   │   ├── interview.py                 # InterviewSession, Question, FinalReport
│   │   ├── audio.py                     # AudioAnalysisRequest/Response
│   │   ├── video.py                     # VideoAnalysisRequest/Response
│   │   ├── analysis.py                  # WorkExperience, Project, Certification
│   │   ├── agent_state.py               # CandidateState, AdaptationDecision
│   │   └── jobs.py                      # JobRecommendation, JobMatch
│   │
│   ├── database/                        # Storage layer
│   │   ├── connection.py                # Motor async MongoDB client
│   │   └── store.py                     # CRUD ops + transparent in-memory fallback
│   │
│   ├── tests/                           # Backend regression tests
│   │   └── test_*.py
│   │
│   ├── config.py                        # Environment variable management
│   ├── main.py                          # FastAPI app init, CORS, router registration
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Home.jsx                 # Dashboard / landing page
│       │   ├── ResumePage.jsx           # Upload + parsed-data preview
│       │   ├── RolesPage.jsx            # Role recommendation cards
│       │   ├── JobsPage.jsx             # Job match list with live/sample badges
│       │   ├── InterviewRoom.jsx        # Question + AudioRecorder + VideoRecorder
│       │   └── ReportPage.jsx           # Radar chart, bar chart, learning plan
│       ├── components/
│       │   ├── AudioRecorder.jsx        # Browser MediaRecorder → WAV blob → POST
│       │   ├── VideoRecorder.jsx        # getUserMedia → JPEG snapshot → POST
│       │   ├── ScoreDisplay.jsx         # Per-turn multimodal score breakdown
│       │   └── FeedbackCharts.jsx       # Recharts radar + bar chart wrappers
│       └── services/
│           └── api.js                   # Axios API client (all backend calls)
│
├── docs/
│   ├── architecture.md                  # Detailed system design & data flows
│   ├── architecture_doc.tex             # LaTeX: 2-page architecture document (PS)
│   ├── project_structure.md             # This file
│   ├── project_structure.tex            # LaTeX: full structure & interactions
│   ├── documentation.tex                # LaTeX: comprehensive reference doc
│   └── demo_script.md                   # Step-by-step demo walkthrough
│
├── sample_data/                         # Quick evaluation inputs & expected outputs
│   ├── sample_resume.txt                # ← start here when evaluating
│   ├── sample_jd.txt                    # Reference job description
│   ├── expected_parsed_resume.json      # resume_agent output for sample_resume.txt
│   ├── expected_roles.json              # role_agent output for sample candidate
│   ├── expected_job_recommendations.json# job_recommender output (sample postings)
│   ├── expected_interview_turn.json     # one full interview turn (Q + scores + trace)
│   └── expected_final_report.md         # feedback_agent final report
│
├── docker-compose.yml                   # Full stack: backend + frontend + MongoDB
├── .env.example                         # Template — copy to .env before running
├── .dockerignore
├── .gitignore
└── README.md
```

---

## Agent Responsibilities

| Agent | File | Input | Output |
|---|---|---|---|
| **resume_agent** | `agents/resume_agent.py` | Raw resume text | Skills, experience, projects, weak areas, seniority |
| **role_agent** | `agents/role_agent.py` | ResumeAnalysis | Ranked role profiles with match score, focus areas |
| **job_recommender_agent** | `agents/job_recommender_agent.py` | Skills + selected role | Top-10 job matches (live or labelled sample) |
| **interview_orchestrator** | `agents/interview_orchestrator.py` | candidate_id + role | Session with 5-question queue + first question |
| **evaluator_agent** | `agents/evaluator_agent.py` | Question + answer + rubric | Correctness, depth, relevance scores (0–100) |
| **intelligence_engine** | `agents/intelligence_engine.py` | Turn scores + audio + video + history | Next difficulty, next topic, decision trace |
| **feedback_agent** | `agents/feedback_agent.py` | All answers + behavioral scores | Final report with radar data, learning plan |

---

## Service Responsibilities

| Service | File | Purpose |
|---|---|---|
| **question_generator** | `services/question_generator.py` | Generate role-aware, resume-aware questions (LLM → deterministic fallback) |
| **audio_analyzer** | `services/audio_analyzer.py` | Whisper transcription + confidence, clarity, pace, hesitation metrics |
| **video_analyzer** | `services/video_analyzer.py` | OpenCV + MediaPipe face detection + engagement, eye-contact, stress metrics |
| **multimodal_aggregator** | `services/multimodal_aggregator.py` | Combine technical + audio + video → weighted overall score |
| **pdf_parser** | `services/pdf_parser.py` | Extract plain text from PDF or TXT uploads |
| **llm_client** | `services/llm_client.py` | Gemini API wrapper with timeout, retry, and graceful fallback |
| **rubric_service** | `services/rubric_service.py` | Deterministic answer scoring when LLM is unavailable |
| **adzuna_job_fetcher** | `services/adzuna_job_fetcher.py` | Fetch live job postings; return labelled sample jobs when credentials missing |

---

## How Agents & Modules Interact

### Flow 1 — Resume → Role → Job

```
User uploads resume (PDF/TXT)
         │
         ▼
  pdf_parser.extract_text()
         │ raw text
         ▼
  resume_agent.analyse()
     ├─ LLM (Gemini) if USE_LLM=true
     └─ regex / keyword matching (fallback)
         │ ResumeAnalysis
         ▼
  ┌──────────────────────────────────────────────────┐
  │                                                  │
  ▼                                                  ▼
role_agent.recommend()                  job_recommender_agent.recommend()
  Jaccard overlap vs 8 role profiles      adzuna_job_fetcher (live)
  → top-5 ranked roles                   or 50-listing fallback (sample)
  → matched / missing skills             → top-10 ranked jobs
  → focus areas, weak areas to probe     → source label (live / sample)
```

### Flow 2 — Interview Session (per question turn)

```
POST /api/interview/start
         │ candidate_id + selected_role
         ▼
  interview_orchestrator.start_session()
         │ creates session_id, 5-question queue
         ▼
  question_generator.generate()            ← resume data + role + difficulty=medium
         │ Question {text, expected_concepts, rubric}
         ▼
  ─── User answers ───────────────────────────────────────────────────────

  evaluator_agent.evaluate()         audio_analyzer.analyse()    video_analyzer.analyse()
    Gemini / rubric_service             faster-whisper / heuristic   OpenCV / heuristic
    → technical_score                   → confidence_score           → engagement_score
    → depth_score                       → clarity_score              → eye_contact_score
    → correctness_score                 → hesitation_rate            → stress_indicator
    → covered / missing concepts
         │                                     │                            │
         └─────────────────┬───────────────────┘                            │
                           │                                                │
                           ▼                                                │
              multimodal_aggregator.aggregate() ◄──────────────────────────┘
                 0.45×T + 0.20×C + 0.15×Cf + 0.10×E + 0.10×R
                           │ overall_turn_score
                           ▼
              intelligence_engine.decide()
                 score < 50%  → easier
                 score 50–80% → same difficulty, new topic
                 score > 80%  → harder
                           │ {next_difficulty, next_topic, decision_trace}
                           ▼
              question_generator.generate()    ← new difficulty + topic
                           │ next Question
                           ▼
                    (repeat ×5 questions)
```

### Flow 3 — Final Report

```
POST /api/interview/final-report  {session_id}
         │
         ▼
  feedback_agent.generate_report()
     ├─ fetch all answers + scores from session
     ├─ fetch all audio_scores[] + video_scores[]
     ├─ detect behavioral_mode
     │    (multimodal | audio | video | audio_fallback | placeholder)
     ├─ compute dimension averages
     │    technical   = mean(all technical_scores)
     │    communication = mean(audio clarity scores) or proxy
     │    confidence  = mean(audio confidence) – hesitation penalty
     │    engagement  = mean(video engagement scores) or proxy
     │    role_fit    = from role recommendation match score
     ├─ overall = 0.45T + 0.20C + 0.15Cf + 0.10E + 0.10R
     ├─ extract strengths  (covered concepts with score ≥ 70)
     ├─ extract weak areas (missing concepts with score < 60)
     ├─ build learning_plan (topic → curated resource + reason + priority)
     └─ build radar_data + bar_data for frontend charts
         │
         ▼
  FinalReport returned → frontend renders radar, bar, learning plan
```

---

## API Route Map

```
POST /api/resume/upload              → resume_routes   → pdf_parser + store
POST /api/resume/analyse             → resume_routes   → resume_agent
GET  /api/resume/roles/{id}          → role_routes     → role_agent
GET  /api/jobs/{id}                  → job_routes      → job_recommender_agent

POST /api/interview/start            → interview_routes → orchestrator + question_generator
POST /api/interview/evaluate-answer  → interview_routes → evaluator_agent
POST /api/interview/next-question    → interview_routes → intelligence_engine + question_generator
POST /api/interview/final-report     → interview_routes → feedback_agent

POST /api/scoring/audio              → scoring_routes  → audio_analyzer
POST /api/scoring/video              → scoring_routes  → video_analyzer

GET  /api/health                     → health          → status + timestamp
```

---

## Multimodal Score Weights

| Signal | Weight | Source |
|---|---|---|
| Technical correctness | **45%** | evaluator_agent (LLM / rubric) |
| Communication clarity | **20%** | audio_analyzer (Whisper / heuristic) |
| Confidence | **15%** | audio_analyzer (confidence score) |
| Engagement | **10%** | video_analyzer (face detection rate) |
| Role fit | **10%** | role_agent (match score) |

```
Overall = 0.45 × Technical + 0.20 × Clarity + 0.15 × Confidence
        + 0.10 × Engagement + 0.10 × RoleFit
```

---

## Behavioral Mode Labels

| Mode | Condition | Reliability |
|---|---|---|
| `multimodal` | Real Whisper + Real OpenCV | Highest |
| `audio` | Real Whisper, no video | High (audio only) |
| `video` | Real OpenCV, no audio | High (video only) |
| `audio_fallback` | Audio uploaded, Whisper timed out | Heuristic |
| `video_fallback` | Video uploaded, OpenCV unavailable | Heuristic |
| `placeholder` | No audio or video submitted | Proxy scores |

---

## Quick Evaluation Path

```
1. docker compose up --build
2. Open http://localhost:5173
3. Upload sample_data/sample_resume.txt
4. Compare parsed output with sample_data/expected_parsed_resume.json
5. Select "Backend Engineer" role
6. Compare role list with sample_data/expected_roles.json
7. View job recommendations (note live/sample badge)
8. Start interview → answer one question → submit with audio + video
9. Check turn scores match structure in sample_data/expected_interview_turn.json
10. Generate final report → compare with sample_data/expected_final_report.md
```
