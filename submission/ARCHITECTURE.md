# Architecture — MockInterview.ai

## 1. Problem Summary & User Journey

**Problem:** Candidates preparing for technical interviews have few affordable options for personalised, on-demand practice. Human coaches are expensive; generic flashcard tools do not adapt to a candidate's specific skill gaps, role target, or real-time performance. There is no readily available system that evaluates *both* what a candidate says and *how* they say it.

**Solution:** MockInterview.ai is an end-to-end AI interview prep platform that ingests a candidate's resume, infers their strengths and gaps, generates a personalised adaptive interview, and delivers a multimodal feedback report combining technical scoring with audio and video analysis.

**User Journey:**

1. **Upload Resume** — candidate submits a PDF or plain-text resume
2. **Resume Intelligence** — system extracts skills, experience, projects, and weak areas
3. **Role Recommendations** — candidate is ranked against 8 engineering role profiles; top matches surfaced
4. **Job Recommendations** — candidate's skills are scored against 50 curated job listings; top 10 returned
5. **Adaptive Interview** — candidate answers 5 questions; difficulty adjusts after each answer
6. **Multimodal Scoring** — each answer scored on technical correctness, audio confidence, and video engagement
7. **Feedback Report** — overall score, radar chart, per-question breakdown, and personalised learning plan

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│              Browser  (React 18 + Vite + Tailwind)           │
│                                                              │
│  /upload → /roles/:id → /jobs/:id → /interview → /report    │
│                                                              │
│  AudioRecorder (mic)   VideoRecorder (webcam)                │
│  RadarChart / BarChart (Recharts)                            │
└─────────────────────────┬────────────────────────────────────┘
                          │  REST / JSON  (Axios)
┌─────────────────────────▼────────────────────────────────────┐
│              FastAPI Backend  (Python 3.11, port 8000)       │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ resume_agent│  │  role_agent  │  │job_recommender_agent│  │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬─────────┘  │
│         │                │                      │            │
│  ┌──────▼──────────────────────────────────────▼──────────┐  │
│  │            intelligence_engine                          │  │
│  │       (interview plan · candidate state · adaptation)   │  │
│  └──────┬──────────────────────────────────────────────────┘  │
│         │                                                    │
│  ┌──────▼──────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │ interview_  │  │evaluator_agent│  │  feedback_agent   │  │
│  │orchestrator │  │               │  │                   │  │
│  └─────────────┘  └───────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │audio_analyzer│  │video_analyzer │  │multimodal_       │  │
│  │(Whisper ASR) │  │(MediaPipe)    │  │aggregator        │  │
│  └──────────────┘  └───────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │   LLM Layer: Claude · Gemini · Grok · Groq           │   │
│  │   (optional — rule-based fallbacks always active)    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │   MongoDB 7  ←→  In-memory store (automatic fallback)│   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

**Frontend** — React 18 SPA with Vite, served by Nginx inside Docker. Communicates with the backend exclusively via REST/JSON. Recharts renders the radar and bar charts in the feedback report.

**Backend** — FastAPI async application. Each route delegates to a single agent or service; agents do not call each other directly, keeping dependencies unidirectional. Pydantic v2 validates all inputs and outputs.

**Agent layer** — Stateless Python classes/functions. Agents read structured input (Pydantic models) and return structured output. Dual-mode: rule-based always runs; LLM layer is invoked on top when `USE_LLM=true` and a key is present.

**Service layer** — Domain computation (audio, video, scoring, PDF parsing, LLM abstraction). Services are called by agents and routes; they do not hold session state.

**Persistence** — Motor async MongoDB driver. If the connection fails at startup, the app transparently switches to an in-memory dict store; the CRUD interface is identical in both cases.

---

## 3. Key Design Choices & Trade-offs

| Choice | Rationale | Trade-off |
|--------|-----------|-----------|
| **Rule-based fallbacks for every agent** | Platform works fully offline without API keys — critical for hackathon demos and low-latency responses | Rule outputs are less nuanced than LLM; static question banks need manual maintenance |
| **Multi-provider LLM abstraction** (`llm_client.py`) | Vendor flexibility; swap Claude ↔ Gemini ↔ Groq without touching agent code | Added indirection; each provider has subtle response format differences requiring normalisation |
| **MongoDB + in-memory fallback** | Zero-setup local dev; no Docker dependency just to start coding | In-memory state is lost on server restart; not suitable for multi-user production without MongoDB |
| **Adaptive difficulty via thresholds** | Deterministic, debuggable, no training data required — score < 50 → easier, > 80 → harder | Coarse-grained; does not model candidate knowledge probabilistically (e.g., Item Response Theory) |
| **MediaPipe proxy metrics for video** | CPU-only, no GPU or cloud vision API required; runs anywhere | Face presence ≠ true eye contact; movement amplitude ≠ stress; these are proxies, not classifiers |
| **Whisper for audio** | State-of-the-art open-source transcription; runs locally | `faster-whisper tiny` model is ~150 MB and adds cold-start latency; heuristic fallback used when unavailable |
| **15s hard timeout on all LLM calls** | Prevents session stalls; user always gets a response | If the LLM is slow, the rule-based output is used — lower quality but never blocking |
| **Docker Compose single-command deploy** | Reproducible across machines; wraps MongoDB + backend + Nginx in one command | First build takes ~3 min; not suitable as-is for autoscaling production environments |

---

## 4. Scoring Approach & Aggregation

### 4a. Per-Answer Technical Scoring

Each answer is evaluated independently by `evaluator_agent` on three axes:

| Axis | Method |
|------|--------|
| **Correctness** | Keyword coverage ratio: `len(covered_points) / len(expected_points)` mapped to 0–100 |
| **Depth** | Word-count thresholds + structural signals (examples present, elaboration beyond one sentence) |
| **Technical accuracy** | Weighted combination of correctness and depth |

Per-answer overall: `(correctness × 0.50) + (depth × 0.30) + (technical_accuracy × 0.20)`

When `USE_LLM=true`, Claude performs semantic scoring and classifies which expected points the answer covered, producing richer covered/missing point breakdowns.

### 4b. Multimodal Aggregation

`multimodal_aggregator` combines five dimensions into a single final score:

```
final_score = technical    × 0.45
            + communication × 0.20
            + confidence    × 0.15
            + engagement    × 0.10
            + role_fit      × 0.10
```

| Dimension | Primary source | Fallback |
|-----------|---------------|---------|
| `technical` | Average of all per-answer overall scores | Same |
| `communication` | Audio clarity score (Whisper path) | Word-count / answer-length proxy |
| `confidence` | Audio confidence score, adjusted for hesitation and pause count | Technical + depth average |
| `engagement` | Video face-detection rate (MediaPipe path) | Session duration proxy |
| `role_fit` | Static match between candidate experience level and role seniority | Same |

The `behavioral_mode` field in the report labels which sources were active: `placeholder` / `audio_fallback` / `audio` / `video_fallback` / `video` / `multimodal`.

### 4c. Role Scoring

`role_agent` scores the candidate against each role profile using:
- Core skill overlap (primary weight)
- Bonus/adjacent skill coverage
- Project domain evidence from resume
- Experience-level affinity
- Skill breadth bonus

Scores are calibrated to a 65–91 range with deterministic ±3 jitter seeded on `hash(candidate_id + role_id)` for reproducibility. Top-5 roles are returned with matched skills and evidence bullets.

---

## 5. Limitations, Assumptions & Next Steps

### Limitations

- **Video proxies, not classifiers** — eye contact is inferred from face centring; stress from head movement amplitude. A dedicated gaze-estimation or affect model would be needed for production accuracy.
- **Whisper download latency** — the `tiny` model (~150 MB) downloads on first audio submission. Subsequent requests are fast; first run adds 30–90 s depending on network.
- **Ephemeral sessions without MongoDB** — if MongoDB is not running, all session data lives in-memory and is lost on server restart.
- **English-only** — question banks, evaluation rubrics, and LLM prompts are English; Whisper supports multilingual audio but the rest of the pipeline does not.
- **5-question sessions** — deeper coverage would require more questions or a multi-session longitudinal model.
- **50 static job listings** — not a live job board; Adzuna integration is stubbed and activates only when credentials are provided.
- **No authentication** — `candidate_id` stored in `localStorage`; any tab sharing the ID can access the session.

### Assumptions

- Resumes are in English and follow conventional section headings (Skills, Experience, Projects, Education).
- Candidate device has a functional microphone and webcam for audio/video features (both are optional).
- LLM API keys and Whisper model are optional; the platform degrades gracefully in their absence.

### Next Steps

- Replace threshold-based difficulty adaptation with a probabilistic knowledge tracing model (Bayesian Knowledge Tracing or Item Response Theory)
- Add true gaze estimation using a dedicated eye-tracking model (dlib, MediaPipe Iris, or a pretrained CNN)
- Implement user accounts with JWT authentication and longitudinal session history
- Expand question bank with community contributions and automated LLM-generated diversity
- Add real-time streaming LLM feedback during the interview (Server-Sent Events) rather than only post-answer
- Integrate live job APIs (Adzuna, LinkedIn) — infrastructure already scaffolded
- Export feedback report as PDF
- Rate limiting, quota management, and horizontal scaling for production deployment
