# Demo Script — Intelligent Mock Interview Agent

> **Duration:** ~8 minutes  
> **Audience:** Hackathon judges / technical reviewers  
> **Setup:** Backend running on port 8000, frontend on port 5173, or Docker Compose up

---

## Before You Start

- Open `http://localhost:5173` in a Chrome tab (Chrome supports MediaRecorder best)
- Have `sample_data/sample_resume.txt` ready on your desktop
- Optional: plug in headphones / use a quiet room for audio demo
- Optional: allow camera access when the browser prompts

---

## Step 1 — Landing Page (30 s)

**Say:** "This is the Intelligent Mock Interview Agent — an end-to-end AI platform that takes your resume, matches you to roles and jobs, runs a personalised adaptive interview, and gives you a multimodal feedback report."

**Show:**
- Point out the hero headline and the three-step visual flow
- Hover the feature cards (Resume Intelligence, Adaptive Interviews, Audio + Video scoring)
- Note the API status badge in the footer — shows the backend is live

**Click:** "Start Practicing"

---

## Step 2 — Upload Resume (45 s)

**Say:** "First, we upload the candidate's resume. The platform accepts PDF or plain text."

**Show:**
- Drag `sample_data/sample_resume.txt` onto the upload zone (or click to browse)
- The file name and word count appear immediately

**Click:** "Analyse Resume"

**Say:** "The resume agent parses the document — using Claude if an API key is present, or a rule-based engine as fallback — and extracts structured data."

**Show:** The analysis cards appear:
- **Skills** (language badges in blue)
- **Experience** (timeline entries)
- **Projects** (project cards)
- **Strengths** (green pills) and **Weak Areas** (orange pills)

---

## Step 3 — Role Recommendations (30 s)

**Click:** "View Recommended Roles"

**Say:** "The role agent scores the candidate against eight engineering role profiles using skill-overlap matching."

**Show:**
- Top 3–5 role cards with match percentage
- Matched vs. missing skills inside each card

**Say:** "Notice the match scores — Backend Engineer and ML Engineer rank highest for this resume."

---

## Step 4 — Job Recommendations (20 s)

**Click:** "View Recommended Jobs" (bottom of the roles page)

**Say:** "We also score 50 curated job listings against the candidate's skills — using alias matching so 'JS' and 'JavaScript' resolve to the same skill."

**Show:** Top-10 job cards with company, location, score, and matched skills.

---

## Step 5 — Start Mock Interview (30 s)

**Navigate back** to roles, **click** "Start Mock Interview" on the top-ranked role card.

**Say:** "The interview orchestrator creates a 5-question adaptive session tailored to the selected role."

**Show:** The first question appears — role, difficulty badge, topic, question text.

---

## Step 6 — Type an Answer & Evaluate (45 s)

**Say:** "The candidate types their answer. Let me use the sample answer for speed."

**Type** a short answer (e.g., for a Backend Engineering question about REST APIs):
> "REST APIs use HTTP verbs — GET for retrieval, POST for creation, PUT/PATCH for updates, DELETE for removal. They are stateless, which means each request contains all information needed to process it. I've built REST APIs with FastAPI and Express, using proper status codes and versioning."

**Click:** "Submit Answer"

**Show:** The evaluation panel slides in:
- Three score bars (Technical, Depth, Correctness)
- Covered points in green ticks
- Missing points with improvement suggestions

---

## Step 7 — Audio Recording Demo (60 s)

**Say:** "Now the highlight — audio intelligence. The candidate can record their answer using the microphone."

**Click:** "Next Question" to advance.

**Expand** the AudioRecorder panel ("🎙 Record your answer").

**Click:** "Start Recording" — speak a brief answer aloud (15–30 seconds).

**Click:** "Stop & Upload"

**Say:** "The backend sends this to faster-Whisper for transcription, then scores confidence, clarity, speaking rate, and pause count."

**Show:** The audio scores card appears in the sidebar:
- Transcript text
- Confidence and clarity pills
- Speaking rate indicator (slow / medium / fast)

**Click:** "Use as typed answer" to merge the transcript into the text box.

**Click:** "Submit Answer" and show the evaluation + audio scores together.

---

## Step 8 — Video / Webcam Demo (45 s)

**Say:** "Next, video intelligence. The platform analyses facial engagement, eye contact, posture, and stress indicators."

**Click:** "Enable Camera" in the video panel.

*(Allow camera permission in the browser prompt)*

**Show:** The live mirrored webcam preview.

**Click:** "Capture Frame" — the snapshot is uploaded instantly.

**Show:** The video scores card:
- Engagement, Eye Contact, Posture bars
- Stress indicator (Low / Medium / High)

**Say:** "For a longer recording, 'Record 15s' captures a 15-second clip and analyses multiple frames for better temporal accuracy."

---

## Step 9 — Adaptive Difficulty (20 s)

**Click:** "Next Question"

**Show:** The yellow **Adaptation Badge** above the new question:
- If the previous score was high: "⬆ Increasing difficulty — you're performing well"
- If low: "⬇ Lowering difficulty — let's consolidate the basics"

**Say:** "The orchestrator adjusts in real time — keeping the interview in the candidate's zone of proximal development."

---

## Step 10 — Final Feedback Report (60 s)

After 3+ questions, **click:** "Generate Final Report"

**Say:** "The feedback agent aggregates all signals — technical scores, audio behavioral data, and video engagement — into a comprehensive report."

**Show:**

1. **Behavioral mode badge** — "multimodal" (green) if both audio and video were recorded; "audio" or "video" for single-modality; "placeholder" if typed-only
2. **Radar chart** — 5-axis competency web (Technical, Communication, Confidence, Engagement, Role Fit)
3. **Bar chart** — per-question overall score showing progression and difficulty adaptation
4. **Overall score** — weighted formula: `tech×0.45 + comm×0.20 + conf×0.15 + eng×0.10 + role_fit×0.10`
5. **Score cards** — each of the 5 axes with value, mode label, and context tooltip
6. **Per-question breakdown** — collapsible cards with the question, answer summary, evaluation scores, and any audio/video metrics for that question
7. **Learning plan** — personalised recommendations per topic based on missing points across all answers
8. **Strengths & Improvement areas** — plain-language summary

---

## Closing Points (30 s)

**Say:** "A few things worth highlighting for judges:"

1. **Zero-setup fallbacks** — the app works with no MongoDB (in-memory store), no API key (rule-based agents), no Whisper (heuristic audio), and no OpenCV (heuristic video). Install any of those to unlock full capability.

2. **Fully containerised** — `docker compose up --build` brings up MongoDB, the FastAPI backend, and the React frontend in one command.

3. **Extensible agent architecture** — adding a new interview role is two lines: one in `role_agent.py`, one in `JobCard.jsx`.

4. **All data on-device** — no audio or video is sent to third-party cloud services unless Anthropic Claude is enabled.

---

## Troubleshooting During Demo

| Issue | Fix |
|-------|-----|
| Backend offline (red API status) | `cd backend && uvicorn main:app --reload --port 8000` |
| Camera permission denied | Reload page, allow camera in browser permissions |
| Audio upload fails | Check browser console; ensure `python-multipart` is installed |
| MongoDB not connecting | App silently uses in-memory store — no action needed |
| Scores all look the same | Whisper / OpenCV not installed — scores are heuristic (expected) |
