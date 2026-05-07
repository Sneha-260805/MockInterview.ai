# Architecture — Intelligent Mock Interview Agent

## 1. Problem Summary

Job seekers lack affordable, on-demand, personalised interview practice. Human mock-interview coaches are expensive and unavailable at scale; generic flashcard tools do not adapt to the candidate's specific skill set, struggle level, or target role.

This platform solves that by combining:
- **Resume intelligence** — automatically extracting skills, experience, and gaps
- **Role & job matching** — mapping the candidate to the most relevant positions
- **Adaptive interviews** — adjusting question difficulty in real time based on performance
- **Multimodal feedback** — scoring both the content of answers and the delivery (audio confidence, visual engagement)

---

## 2. User Journey

```
Upload Resume
     │
     ▼
Analyse → extracted skills, experience, projects, weak areas
     │
     ▼
Role Recommendations (ranked by skill overlap)
     │
     ▼
Job Recommendations (top-10 from 50-listing database)
     │
     ▼
Start Mock Interview (choose a role → 5 adaptive questions)
     │
     ├── Type answer   ─────────────────────────────┐
     ├── Record audio  → Whisper transcription        │  Each question
     └── Enable webcam → face analysis               │  evaluated in
                                                     │  real time
                         Per-answer scores ◄──────────┘
                         (technical / depth / correctness)
                               │
                               ▼
                    Generate Final Report
                               │
                    Radar chart · Bar chart
                    Learning plan · Behavioral summary
```

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Browser (React 18 + Vite)                     │
│                                                                     │
│  /        /upload    /roles/:id   /jobs/:id                         │
│  /interview/:id      /report/:id                                    │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│  │  Home    │ │  Resume  │ │ InterviewRoom│ │  FeedbackReport     │ │
│  │Dashboard │ │  Upload  │ │              │ │                     │ │
│  │          │ │          │ │ AudioRecorder│ │ RadarChart BarChart  │ │
│  │          │ │          │ │ VideoRecorder│ │ LearningPlan        │ │
│  └──────────┘ └──────────┘ └──────┬──────┘ └──────────┬──────────┘ │
└─────────────────────────────────── │ REST/JSON ─────── │ ───────────┘
                                     │                   │
┌──────────────────────────────────── ▼ ─────────────────▼ ──────────┐
│                  FastAPI Backend (port 8000)                        │
│                                                                     │
│  POST /api/resume/upload          resume_agent                      │
│  POST /api/resume/analyse         resume_agent                      │
│  GET  /api/resume/roles/:id       role_agent                        │
│  GET  /api/jobs/:id               job_recommender_agent             │
│  POST /api/interview/start        interview_orchestrator            │
│  POST /api/interview/evaluate-answer  evaluator_agent               │
│  POST /api/interview/next-question    interview_orchestrator        │
│  POST /api/interview/final-report     feedback_agent                │
│  POST /api/scoring/audio          audio_analyzer                    │
│  POST /api/scoring/video          video_analyzer                    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │      In-memory store (store.py) ←→ MongoDB 7 (motor)         │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Agent / Module Responsibilities

| Module | File | Responsibility |
|--------|------|----------------|
| **resume_agent** | `agents/resume_agent.py` | Parse PDF/TXT → structured skills, experience, projects, strengths, weak areas. Uses Claude if `USE_LLM=true`, else regex/keyword rules. |
| **role_agent** | `agents/role_agent.py` | Score candidate skills against 8 role profiles; rank by overlap percentage. Includes curated question banks per role. |
| **job_recommender_agent** | `agents/job_recommender_agent.py` | Score 50 curated job listings against candidate skills using canonical alias matching; return top-10. |
| **interview_orchestrator** | `agents/interview_orchestrator.py` | Maintain 5-question session state; select next question based on difficulty adaptation rules (`last_score < 50` → easier, `> 80` → harder). |
| **evaluator_agent** | `agents/evaluator_agent.py` | Score a single answer (0-100) across three axes: technical correctness, depth, and structural relevance. Identifies covered/missing points. |
| **feedback_agent** | `agents/feedback_agent.py` | Aggregate all per-answer scores + audio/video scores → FinalReport with behavioral mode detection, overall score formula, and personalised learning plan. |
| **audio_analyzer** | `services/audio_analyzer.py` | Transcribe audio via faster-whisper/whisper; score confidence, clarity, speaking rate, pause count. Falls back to file-size heuristics if no Whisper installed. |
| **video_analyzer** | `services/video_analyzer.py` | Analyse image/video frames via OpenCV + MediaPipe; score engagement, eye contact, posture, stress. Falls back to file-size heuristics if no OpenCV installed. |
| **pdf_parser** | `services/pdf_parser.py` | Extract text from PDF files using PyMuPDF. |
| **database layer** | `database/connection.py` + `store.py` | Motor async MongoDB client with transparent in-memory fallback. All CRUD operations go through the same interface regardless of backend. |

---

## 5. Data Flow

### 5a. Resume → Role → Job

```
User uploads PDF/TXT
        │
        ▼
pdf_parser.extract_text()
        │
        ▼
resume_agent.analyse(text)
  → {skills, experience, projects, strengths, weak_areas}
  → stored as ResumeAnalysis (candidate_id key)
        │
        ├──► role_agent.recommend(candidate_id)
        │      Jaccard-style overlap of candidate skills ∩ role_required_skills
        │      → [{role, score, matched_skills, missing_skills}]  top-5
        │
        └──► job_recommender_agent.recommend(candidate_id)
               Alias-expanded skill matching against 50 job listings
               → [{job, score, matched_skills}]  top-10
```

### 5b. Interview Session

```
POST /api/interview/start
  {candidate_id, selected_role}
  → creates InterviewSession (session_id, role, questions queue)
  → returns first Question

User answers (typed or audio-transcribed)
  → POST /api/interview/evaluate-answer
     evaluator_agent scores {technical, depth, correctness}
     → EvaluationResult persisted to session.answers[]

  → (optional) POST /api/scoring/audio
     audio_analyzer → AudioAnalysisResponse persisted to session.audio_scores[]

  → (optional) POST /api/scoring/video
     video_analyzer → VideoAnalysisResponse persisted to session.video_scores[]

  → POST /api/interview/next-question
     interview_orchestrator reads last_score → picks next difficulty tier
     → NextQuestionResponse {question, adaptation_reason}

After 3-5 questions:
  → POST /api/interview/final-report
     feedback_agent reads all answers + audio_scores + video_scores
     → FinalReport with overall_score, radar data, bar data, learning_plan
```

---

## 6. API Contracts

### POST `/api/resume/upload`
```
Request : multipart/form-data  { file: PDF|TXT }
Response: { candidate_id: str, filename: str, text_preview: str, word_count: int }
```

### POST `/api/resume/analyse`
```
Request : { candidate_id: str, text: str }
Response: { candidate_id, skills[], experience[], projects[], strengths[], weak_areas[], mode }
```

### GET `/api/resume/roles/{candidate_id}`
```
Response: { candidate_id, roles: [{ role_id, role_name, score, matched_skills[], missing_skills[], question_count }] }
```

### GET `/api/jobs/{candidate_id}`
```
Response: { candidate_id, jobs: [{ id, title, company, location, skills[], score, matched_skills[] }] }
```

### POST `/api/interview/start`
```
Request : { candidate_id: str, selected_role: str }
Response: { session_id, role, question: { id, text, difficulty, topic, expected_points[] }, question_number: 1 }
```

### POST `/api/interview/evaluate-answer`
```
Request : { session_id, question_id, question, answer, expected_points[] }
Response: { session_id, question_id, technical_score, depth_score, correctness_score,
            overall_score, covered_points[], missing_points[], feedback }
```

### POST `/api/interview/next-question`
```
Request : { session_id, last_answer_score, confidence_score, current_topic }
Response: { session_id, question, question_number, is_complete, adaptation_reason }
```

### POST `/api/interview/final-report`
```
Request : { session_id }
Response: { session_id, role, overall_score, technical_score, communication_score,
            confidence_score, engagement_score, role_fit_score, behavioral_mode,
            radar_data[], bar_data[], answers[], learning_plan{}, strengths[], areas_for_improvement[] }
```

### POST `/api/scoring/audio`
```
Request : multipart/form-data { audio: Blob, session_id?: str, question_number?: int }
Response: { transcript, confidence_score, communication_clarity_score, pause_count,
            speaking_rate, mode, word_count, duration_seconds }
```

### POST `/api/scoring/video`
```
Request : multipart/form-data { video: Blob|JPEG, session_id?: str, question_number?: int }
Response: { engagement_score, eye_contact_score, posture_score, stress_indicator,
            mode, frames_analyzed, face_detection_rate }
```

---

## 7. Scoring Approach

### Per-Answer (Technical)
| Axis | Formula |
|------|---------|
| `technical_score` | Factual correctness of answer content (0-100) |
| `depth_score` | Detail and nuance relative to expected points (0-100) |
| `correctness_score` | Structure, relevance, and completeness (0-100) |
| `overall_score` | `(technical + depth + correctness) / 3` |

### Behavioral (Final Report)
| Axis | Source Priority |
|------|----------------|
| `communication_score` | Audio clarity score → word-count proxy |
| `confidence_score` | Audio confidence score → score trajectory |
| `engagement_score` | Video face-detection rate → session duration |

### Overall Score
```
overall = technical   × 0.45
        + communication × 0.20
        + confidence    × 0.15
        + engagement    × 0.10
        + role_fit      × 0.10
```

### Behavioral Mode
The `behavioral_mode` field in FinalReport indicates data quality:

| Mode | Meaning |
|------|---------|
| `placeholder` | No audio/video uploaded; all behavioral scores are proxies |
| `audio_fallback` | Audio uploaded but Whisper not installed; heuristic scores |
| `audio` | Real Whisper transcription; audio scores are genuine |
| `video_fallback` | Video uploaded but OpenCV not installed; heuristic scores |
| `video` | Real OpenCV/MediaPipe analysis; video scores are genuine |
| `multimodal` | Both real audio and real video analysis |

### Video Scoring Details
- **Engagement**: `detection_rate × 75 + 20` — how often a face is visible
- **Eye contact**: `95 − avg_center_distance × 140` — face centred in frame = looking at camera
- **Posture**: `88 − face_size_stdev × 350` — stable face size = stable posture
- **Stress indicator**: inter-frame head movement → `> 0.06` high, `> 0.025` medium, else low

---

## 8. Design Choices & Trade-offs

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **In-memory fallback** | Zero-setup demo experience; no MongoDB required | Data lost on restart; not suitable for production multi-user |
| **Rule-based + LLM dual mode** | Works without API key; LLM enriches output when available | Rule outputs are less nuanced; LLM adds latency + cost |
| **Whisper for audio** | State-of-the-art transcription, open-source | `faster-whisper` is large (~1GB); fallback works but scores are heuristic |
| **OpenCV + MediaPipe** | Face detection without cloud API | Accuracy lower than cloud vision; adds heavy deps |
| **Heuristic fallback seeding** | `random.Random(file_size % 99_991)` makes scores reproducible per recording | Scores don't reflect actual content; useful only for demo/dev |
| **Multipart form for audio/video** | Standard browser `FormData`; works with any HTTP client | Larger payloads; 25 MB audio / 50 MB video caps enforced |
| **candidate_id in localStorage** | Simple, no auth required for hackathon | Single-device; cleared on browser data wipe |
| **Adaptive difficulty** | Keeps candidates engaged; not too easy / too hard | Simple threshold-based (< 50 → easier, > 80 → harder); not a full IRT model |

---

## 9. Limitations

- **No authentication** — any browser tab sharing a `candidate_id` can access that session
- **50 static job listings** — not a live job board; listings may be stale
- **5-question sessions** — deeper coverage would require more questions or follow-up probing
- **Audio heuristic** — without Whisper, confidence/clarity are estimated from file size
- **Video heuristic** — without OpenCV, all video scores are reproducible random numbers
- **Face = eye contact proxy** — centred face does not guarantee actual eye contact; gaze estimation would require a dedicated model
- **Single-turn evaluation** — the evaluator scores each answer independently; no cross-question memory
- **English-only** — Whisper supports many languages but prompts, question banks, and evaluator logic are English-only

---

## 10. Next Steps

- [ ] Real-time Web Speech API transcription during typing
- [ ] Gaze-estimation model replacing face-centring proxy
- [ ] Per-session user accounts with JWT authentication
- [ ] Multi-turn conversation memory (chain questions across sessions)
- [ ] Live job board integration (LinkedIn / Indeed API)
- [ ] Company-specific question banks
- [ ] Peer-comparison percentile analytics
- [ ] PDF export of the final report
- [ ] Mobile-responsive interview room layout
- [ ] Rate-limiting and quota management for production
