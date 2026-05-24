# Demo Script — MockInterview.ai

> **Duration:** ~10 minutes  
> **Audience:** Hackathon judges / technical reviewers  
> **Setup:** Backend running on port 8000, frontend on port 5173 (or `docker compose up`)

---

## Before You Start

- Open `http://localhost:5173` in a Chrome tab (Chrome supports MediaRecorder API best)
- Have `sample_data/sample_resume.txt` ready on your desktop
- Optional: plug in headphones / use a quiet room for the audio demo
- Optional: allow camera access when the browser prompts
- Have Gemini API key set — stages 1–3 (intelligence + role enrichment) activate automatically

---

## Step 1 — Landing Page (30 s)

**Say:** "This is MockInterview.ai — an end-to-end AI platform that takes your resume, extracts structured intelligence from it, matches you to realistic roles and live job listings, then runs a personalised adaptive interview and produces a multimodal feedback report."

**Show:**
- Point to the three-step visual flow on the hero section
- Hover the feature cards (Resume Intelligence, Adaptive Interviews, Multimodal Scoring)
- Note the API status badge — shows backend is live

**Click:** "Start Practicing"

---

## Step 2 — Upload Resume (45 s)

**Say:** "We start by uploading the candidate's resume. The platform accepts PDF or plain text."

**Show:**
- Drag `sample_data/sample_resume.txt` onto the upload zone
- File name and word count appear immediately

**Click:** "Analyse Resume"

**Say:** "A three-stage pipeline runs in sequence. Stage 0 uses rule-based extraction — so everything works offline with zero API keys. Stage 1 sends the text to Gemini 2.0 Flash for semantic normalization, deduplication, and level detection. Stage 2 runs Gemini again to build interview intelligence — identifying strong skills, weak areas, resume claims that deserve verification, and project-specific probe questions."

**Show:** Analysis cards appear:
- **Skills** (language badges)
- **Experience** timeline entries
- **Projects** cards

---

## Step 3 — Resume Intelligence Panel (90 s)

**Say:** "This is the key differentiator — six intelligence sections, all derived directly from the resume text using Gemini's reasoning. No mock data."

**Scroll** to the Resume Intelligence panel and walk through each section:

**Strong Skills (green chips)**
- **Say:** "Confirmed technical strengths — skills that appeared consistently across experience, projects, and explicit mentions. These become the baseline for interview difficulty calibration."

**Weak / Missing Areas (amber tags)**
- **Say:** "Skills the candidate touched lightly or is missing entirely. The interview agent targets these for remediation follow-up."

**Interview Risks (red alert rows)**
- **Say:** "Red flags the interviewer should probe — vague claims, unsupported depth, or patterns typical of tutorial-level experience. The agent uses these to choose verify_resume_claim and behavioral_probe decision types."

**Claims to Verify (violet cards)**
- **Say:** "Specific bold claims from the resume — 'led a team of 5', 'reduced latency by 40%', 'architected the system'. For each claim, Gemini generates a probe question designed to reveal whether the candidate can substantiate it."
- **Point to** the Claim / Why Verify / Probe layout in each card
- **Say:** "These become the verify_resume_claim questions in the adaptive interview."

**Project Deep Dives (blue cards)**
- **Say:** "Each project gets specific technical follow-up topics derived from the tech stack and description — not generic questions, but ones grounded in what the candidate actually built."

**Suggested Interview Probes (indigo rows)**
- **Say:** "A curated starting list of questions Gemini recommends, drawn from all the signals above. The interview agent pulls from these and adapts based on performance."

---

## Step 4 — Role Recommendations (60 s)

**Click:** "View Recommended Roles"

**Say:** "Stage 3 of the pipeline: Gemini enriches the rule-scored role recommendations. The scoring engine is deterministic — skill overlap, seniority affinity, bonus skills — but Gemini adds the why."

**Show:** Role cards. Walk through one card:

**Realistic Fit / Stretch Opportunity badge**
- **Say:** "Green badge means the candidate's profile already maps well to this role. Amber means it's achievable with targeted preparation — the system never recommends roles outside the defined taxonomy."

**Why This Role section (indigo box)**
- **Say:** "Gemini's explanation of the fit, grounded in the resume content — not boilerplate."

**Resume Evidence section (green chips)**
- **Say:** "Specific resume artefacts that support this recommendation. These come from Gemini's reading of the actual resume, not invented."

**Skills Gaps section**
- **Say:** "Concrete gaps to address before the interview for this specific role."

**What Interview Will Validate**
- **Say:** "Exactly what the interview session will test — so the candidate knows what to prepare. This also informs the adaptive agent's question selection."

---

## Step 5 — Job Recommendations (30 s)

**Click:** "View Recommended Jobs" at the bottom of the roles page

**Say:** "Job recommendations use skill-alias matching against 50 curated listings. If Adzuna credentials are configured, these are live postings with apply URLs — the LIVE badge with the animated green dot confirms it. Without credentials, cards are clearly marked SAMPLE so there's no confusion."

**Show:**
- LIVE vs SAMPLE badge distinction
- Match score circle (colour-coded: green ≥75, yellow 50–74, orange <50)
- Application Readiness strip ("Application Ready" / "Almost Ready" / "Stretch Role")
- Why Fit box, matched skills, skills to develop
- "Apply / View Posting" button (only on live jobs)
- "Practice Interview for This Role" button — routes directly to the matching role

---

## Step 6 — Start Adaptive Interview (30 s)

**Navigate back** to roles. **Click** "Start Mock Interview" on the top-ranked role card.

**Say:** "The interview orchestrator creates a 5-question adaptive session. Each question is selected by the central intelligence engine — not by frontend heuristics. The agent considers: resume intelligence signals, previous answer scores, topic coverage, difficulty curve, and behavioral signals."

**Show:** First question — role label, difficulty badge, topic, question text.

---

## Step 7 — Strong Answer → Difficulty Increase (60 s)

**Say:** "Let me demonstrate the adaptive loop. First, a strong answer. The question is about database indexing."

**Type this answer into the text box:**

> "Indexing improves read performance by creating optimized lookup structures that eliminate full table scans. A B-tree index enables O(log n) lookups — the database traverses the tree to find matching rows rather than scanning every record. I've used composite indexes for multi-column WHERE clauses and partial indexes for filtered queries on large tables. The real trade-off is write overhead and storage cost — every INSERT or UPDATE must maintain the index structure, so I always run EXPLAIN ANALYZE before adding an index in production to confirm it's actually used by the query planner."

**Click:** "Submit Answer"

**Show:** Evaluation panel:
- Technical / Depth / Correctness bars — all high
- Covered points: trade-off awareness, specific index types, practical application
- Minimal or no missing points

**Click:** "Next Question"

**Show:** The Adaptation Badge above the new question:
- Named badge type: **"Difficulty Increased"** (green)
- Reason text: something like "Strong answer demonstrating B-tree internals and trade-off analysis. Moving to advanced query optimization."
- Question counter: "Question 2 of 5"

**Say:** "The agent recognised technical depth — specific O(log n) complexity, composite vs partial indexes, EXPLAIN ANALYZE in production — and escalated difficulty. The named badge type tells you exactly what decision was made."

---

## Step 8 — Weak Answer → Confidence Recovery (60 s)

**Click:** "Next Question" to advance to question 3, or submit the harder question with a weak answer.

**Say:** "Now watch what happens with a surface-level answer."

**Type this answer:**

> "Indexing makes the database faster."

**Click:** "Submit Answer"

**Show:** Evaluation panel:
- Low scores across technical / depth / correctness
- Missing points: no mechanism explained, no trade-offs, no practical context

**Click:** "Next Question"

**Show:** The Adaptation Badge:
- Named badge type: **"Confidence Recovery"** or **"Strengthening Fundamentals"** (amber/purple)
- Reason text: something like "Answer lacks technical depth on indexing mechanisms. Revisiting fundamentals before continuing."
- The new question is simpler, more direct

**Say:** "The agent detected the gap and pivoted. Rather than continuing to escalate, it drops back to consolidate understanding. This keeps the interview productive — not demoralising."

---

## Step 9 — Agent Trace Panel (45 s)

**Show:** The Agent Trace Panel (collapsible sidebar or section below the question).

**Say:** "Every question selection is fully explainable. The trace shows four things:"

**Walk through each section:**

1. **OBSERVATION** — "What the agent saw: the candidate's previous score, topic history, and behavioral signals from audio or video if captured."

2. **DECISION** — "The specific decision type — one of nine: increase_difficulty, deeper_follow_up, strengthen_fundamentals, confidence_recovery, remediation, final_synthesis, switch_topic, verify_resume_claim, behavioral_probe. The badge color matches the AdaptationBadge above the question."

3. **REASON** — "The agent's explanation for why this decision was made. Not a generic template — derived from the actual score and signals."

4. **EVIDENCE** — "Green rows for supporting signals, amber rows for concern signals. Audio and video metrics appear here when captured."

5. **NEXT ACTION** — "The topic pill, difficulty level, and any score from the previous question for context."

**Say:** "This transparency is intentional. Judges and candidates can see exactly why each question was chosen. No black-box adaptation."

---

## Step 10 — Audio Demo (60 s)

**Click:** "Next Question" to advance.

**Expand** the AudioRecorder panel ("Record your answer").

**Click:** "Start Recording" — speak a brief answer aloud (15–30 seconds).

**Click:** "Stop & Upload"

**Say:** "The backend transcribes the audio using faster-Whisper, then extracts behavioral signals: speech rate (words per minute), pause frequency, filler word rate, and volume variation. We call these a confidence indicator and a clarity proxy — not emotion detection. The labels are honest about what the signal actually is."

**Show:** Audio scores card:
- Transcript text
- Confidence indicator, clarity proxy pills
- Speaking rate (slow / medium / fast)

**Click:** "Use as typed answer" → "Submit Answer"

**Show:** Combined evaluation with audio behavioral signals in the trace.

---

## Step 11 — Video Demo (45 s)

**Click:** "Enable Camera" in the video panel. Allow camera permission.

**Show:** Live mirrored webcam preview.

**Click:** "Capture Frame"

**Show:** Video scores card:
- Engagement proxy, eye contact estimate, posture indicators
- Each labelled accurately — "engagement proxy", not "emotion detection"

**Say:** "The behavioral mode badge in the feedback report will show 'multimodal' when both audio and video are captured. If only one is present, it shows 'audio' or 'video'. If neither, 'placeholder'. Each mode has a different score formula — the system never inflates scores from missing modalities."

---

## Step 12 — Final Feedback Report (90 s)

After 3+ questions, **click:** "Generate Final Report"

**Say:** "The feedback agent aggregates all signals into a structured report."

**Show and narrate each section:**

**Interview Readiness label**
- The bold section header above the readiness banner

**Behavioral Mode badge**
- "multimodal" (green) / "audio" / "video" / "audio_fallback" / "placeholder"
- **Say:** "Fallback modes are visibly marked — we don't hide when the system is operating with limited signals."

**Radar chart**
- 5-axis: Technical, Communication, Confidence, Engagement, Role Fit
- **Say:** "The weighted formula is transparent: tech×0.45 + comm×0.20 + conf×0.15 + eng×0.10 + role_fit×0.10. Technical depth carries the most weight because that's what interview performance correlates with."

**Per-question score bar chart**
- Shows difficulty progression and adaptation curve
- **Say:** "You can see the difficulty escalated after question 1, then dropped after the weak answer — the adaptation loop is visible in the data."

**Score cards** — five axes with value and context tooltip

**Per-question breakdown** (collapsible)
- Question text, answer summary, evaluation scores, audio/video metrics per question

**Learning plan**
- Topic-specific recommendations based on missing points across all answers

---

## Closing Talking Points (30 s)

**Say:** "A few things worth highlighting:"

1. **Zero-setup fallbacks** — the app runs with no MongoDB (in-memory store), no API key (rule-based agents), no Whisper (heuristic audio), and no OpenCV (heuristic video). Every fallback is visible — no silent degradation.

2. **Three-stage resume pipeline** — Stage 0 (rule-based, always runs) → Stage 1 (Gemini normalization, additive) → Stage 2 (Gemini intelligence, additive) → Stage 3 (Gemini role enrichment, additive). Each stage only enhances what the previous stage produced.

3. **No hallucinated roles** — the role agent scores only from a fixed 11-role taxonomy. Gemini enriches the scoring but cannot add roles outside the list. The `_parse_role_enrichments()` function enforces this with exact + fuzzy matching and silently drops any unexpected role names.

4. **Honest AI labeling** — every signal uses accurate language: confidence indicator, clarity proxy, engagement proxy, behavioral signals. We do not claim real emotion detection, psychological profiling, or gaze tracking beyond heuristic estimation.

5. **Fully containerised** — `docker compose up --build` brings up MongoDB, the FastAPI backend, and the React frontend in one command.

---

## Judge Questions — Prepared Answers

**"What happens if the LLM API is down?"**
> "Every LLM call is wrapped in a try/except that never raises. The rule-based pipeline produces a complete, valid response. Gemini stages 1–3 are additive — if any stage fails, the output from the previous stage is returned unchanged. The API status badge on the landing page shows backend health."

**"How do you prevent the LLM from hallucinating role names?"**
> "`_parse_role_enrichments()` in `llm_service.py` accepts only roles whose names appear in the `expected_roles` list passed to it. It first tries exact match, then fuzzy match on the first 8 characters. Any name that doesn't match is dropped with a debug log. Gemini is also explicitly instructed in the prompt to only enrich roles from the provided list."

**"Are the job listings real?"**
> "With Adzuna credentials configured, yes — live postings fetched via the Adzuna Jobs API. Without credentials, 50 curated sample jobs are used. The LIVE badge with animated green dot vs. SAMPLE badge with amber dot makes the distinction explicit on every card."

**"What does 'confidence indicator' actually measure?"**
> "Speech rate (words per minute), pause frequency, filler word rate, and volume variation extracted from the Whisper transcript and audio features. It correlates with fluency and composure under pressure — which is measurable — but we don't claim it detects internal emotional states, which is not measurable from audio alone."

**"How does the adaptive loop work technically?"**
> "After each answer, the evaluate_answer endpoint returns a score and covered/missing points. The orchestrator passes the full conversation history — scores, topics covered, difficulty curve, audio/video signals — to the question_selection agent. The agent uses a decision tree of 9 decision types plus Gemini reasoning to select the next question from the role's question bank, with the specific decision type logged in the trace."

---

## Troubleshooting During Demo

| Issue | Fix |
|-------|-----|
| Backend offline (red API status) | `cd backend && uvicorn main:app --reload --port 8000` |
| Intelligence panel empty | Check `GEMINI_API_KEY` is set; rule-based fallback populates fewer fields |
| Role cards missing why_fit | Stage 3 Gemini enrichment skipped — set `GEMINI_API_KEY` to activate |
| Camera permission denied | Reload page, allow camera in browser permissions |
| Audio upload fails | Check browser console; ensure `python-multipart` is installed in backend venv |
| MongoDB not connecting | App silently uses in-memory store — no action needed |
| Scores all look the same | Whisper / OpenCV not installed — heuristic mode expected, labelled as fallback |
| Job cards all show SAMPLE | Set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` in `.env` for live postings |
