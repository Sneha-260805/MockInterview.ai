# MockInterview.ai — Demo Script

> **Hackathon Demo Guide** — Follow this step-by-step for a polished, judge-ready presentation.  
> Total time: ~8–10 minutes.

---

## Setup Before Demo

1. Backend running: `uvicorn main:app --reload --port 8000` (with `USE_LLM=true` and `ANTHROPIC_API_KEY` set in `.env`)
2. Frontend running: `npm run dev` → open `http://localhost:5173`
3. Sample resume ready: `sample_data/sample_resume.txt`
4. Browser window maximised, devtools closed
5. Open the app on the **Home** page

---

## Step 1 — Upload Resume (60 seconds)

**Say:** "The system starts with a resume. We support PDF and plain text. Let me upload our sample candidate."

**Action:** Navigate to `/upload` → click the upload zone → select `sample_data/sample_resume.txt`.

**Click "Extract Resume Text"** → point to the word count in the preview.

**Say:** "The backend extracts raw text immediately — no manual parsing needed."

---

## Step 2 — Resume Intelligence (90 seconds)

**Click "Analyse Resume & Recommend Roles"**

**Wait for the panel to load, then point to each section:**

### Strongest Skills
> "The system does not just list all skills — it identifies the most **marketable** ones. These are the skills the interview agent will focus on."

### Project Deep-Dive Candidates
> "For each project, the agent determines **why** it was selected for deep-dive and what topics it will probe. This is personalised to this resume — not a generic list."

### Claims to Verify
> "This is a key intelligence feature. The agent identifies **claims that cannot be verified from the resume alone** and generates a probe question for each one."

**Show one claim, e.g.:**
```
Claim: "Built a MERN stack project"
Why verify: Resume does not mention authentication, deployment, or database design
Probe question: Walk me through the architecture — how did you handle user 
authentication and data flow?
```

### Interview Risk Signals
> "These are red flags the agent detected — common expectations for this role that are missing from the resume."

---

## Step 3 — Role Recommendations (60 seconds)

**Click "View Role Recommendations →"**

**Point to the top card:**

- **Score ring** → "84/100 — calculated from skill overlap with the role's core and bonus requirements"
- **Realistic Fit badge** → "Roles are classified as Realistic, Stretch, or Aspirational — honest guidance"
- **Click "Show resume evidence & gaps":**
  - **Resume Evidence**: "Specific lines from the resume that justify this recommendation"
  - **Gaps to Address**: "Missing skills the candidate needs to develop"
- **"Why this role?" section**: "A plain-language explanation derived from the actual skill overlap — not a template"

---

## Step 4 — Job Recommendations (60 seconds)

**Click "View Recommended Jobs"**

**Point to the stats banner:** "X jobs matched from Y positions scanned."

**Point to a job card:**
- **"Live Posting" / "Sample Job" badge** → "We are transparent about whether jobs are live from Adzuna or from our curated fallback — no false claims"
- **Match score** → "Calculated from skill overlap, not keyword guessing"
- **"Why this job fits"** → "Personalised explanation using the candidate's actual matched skills"
- **"Recommended preparation"** → "Specific prep advice before applying"
- **"Apply Now" button** → shown when live Adzuna jobs are fetched with a redirect URL

---

## Step 5 — Start Interview (30 seconds)

**Go back to `/roles`** → **Click "Start Interview"** on the top-matched role

**Say:** "The first question is personalised — it references the candidate's actual project from the resume. This is not a static bank."

**Point to the question panel** — show topic and difficulty badge.

---

## Step 6 — Submit a STRONG Answer (90 seconds)

**Type or paste this strong answer:**

```
Indexing improves read performance by creating a B-tree data structure on selected 
columns, allowing the database engine to find rows without a full table scan. 
For a login lookup, I would index the email column since it is queried on every 
authentication attempt. I would verify the index is used with EXPLAIN ANALYZE, 
and monitor write overhead since indexes slow INSERT and UPDATE operations. 
For a high-volume auth system, I would also consider a partial index on active users 
to reduce index size.
```

**Click "Submit Answer"**

**Point to scores:** "Technical: ~85, Depth: ~78, Correctness: ~82 — strong performance."

**Click "Next Question"** — wait for the system to fetch the next question.

**Point to the Agent Decision Trace panel:**

> "This is the key differentiator. The system shows its **full reasoning chain**:"
> - **Agent Observed**: 'Strong answer — candidate shows confident mastery'
> - **Evidence**: score numbers + no missing concepts
> - **Agent Decision**: 'Ask an advanced question on System Design'
> - **Why**: 'Excellent performance (85/100) — escalating to hard difficulty'
> - **Next Action**: 'Generate a challenging advanced question on System Design'

**Say:** "The agent does not follow a script — it reads the scores and confidence signals to decide what to ask next."

---

## Step 7 — Submit a WEAK Answer (90 seconds)

**For the next question, type or paste this weak answer:**

```
Indexing makes database faster. It helps search quickly.
```

**Click "Submit Answer"**

**Point to scores:** "Technical: ~28, Depth: ~22, Correctness: ~35 — weak performance."

**Click "Next Question"**

**Point to the Agent Decision Trace panel:**

> - **Agent Observed**: 'Weak answer — fundamental concepts not articulated'
> - **Evidence**: low scores + missing concepts list (B-tree, query plan, write overhead)
> - **Agent Decision**: 'Ask a simpler foundational question'
> - **Why**: 'Score dropped to ~28 — stepping back to check foundational knowledge'
> - **Next Action**: 'Generate an easier foundational question to rebuild confidence'

**Say:** "The system detected the drop and adapted — asking a simpler question rather than continuing to escalate. This is real-time adaptive intelligence."

---

## Step 8 — Audio & Video Intelligence (30 seconds)

**Point to the sidebar during the interview:**

- **Audio Scores** (if audio was recorded): "Confidence, clarity, speaking pace, and pause count — derived from Whisper speech-to-text transcription"
- **Video Scores** (if webcam was enabled): "Engagement indicator, eye-contact proxy, posture proxy, and stress indicator — derived from OpenCV and MediaPipe face detection"

**Say:** "We are honest about what these scores are — they are explainable behavioural signals, not claimed emotion detection. The problem statement permits heuristics-based scoring, and we label everything clearly."

---

## Step 9 — Final Feedback Report (60 seconds)

**After 3+ questions, click "Generate Final Report"**

**Point to:**
- **Radar chart** → "Overall performance profile across all scoring dimensions"
- **Per-question breakdown** → "Each answer's scores and the agent's feedback"
- **Adaptation reason in history** → "The reason the agent selected each question is preserved and visible"
- **Learning plan** → "Personalised next steps based on weak areas detected"

---

## Step 10 — Closing Statement (20 seconds)

> "MockInterview.ai is not a chatbot. It is a **resume-aware, role-aware, adaptive interview coach** that:
> - Reads your resume to understand actual skills and gaps
> - Recommends roles and jobs with evidence-backed explanations
> - Generates personalised interview questions — not from a static bank
> - Adapts difficulty in real time based on answers and confidence signals
> - Shows its reasoning at every step — explainable AI, not a black box"

---

## Sample Answers Reference

### Weak Answer — Triggers Difficulty Drop
```
Indexing makes database faster. It helps search quickly.
```
**Expected agent behaviour:**
- Technical score: ~25–35
- Missing concepts flagged: B-tree structure, query plan, write overhead
- Agent selects easier foundational question on the same topic
- Adaptation reason: "Answer lacked depth — stepping back to foundational knowledge"

### Strong Answer — Triggers Difficulty Escalation
```
Indexing improves read performance by creating a B-tree data structure on selected 
columns. For login lookup I index email, verify with EXPLAIN ANALYZE, and monitor 
write overhead since indexes slow INSERT/UPDATE. For high volume I would consider 
a partial index on active users only.
```
**Expected agent behaviour:**
- Technical score: ~80–90
- No missing concepts flagged (or minimal)
- Agent escalates to harder question (system design, trade-offs, scale)
- Adaptation reason: "Excellent performance — escalating to hard difficulty"

### Second Strong Answer — System Design
```
For a distributed caching layer I would use Redis with a cache-aside pattern. 
The application checks Redis first, falls back to the database on miss, then 
writes the result back to Redis with a TTL. For invalidation I would use 
event-driven invalidation via a message queue when underlying data changes. 
For high-read systems, read replicas on the database reduce load further.
```

---

## Troubleshooting During Demo

| Problem | Fix |
|---------|-----|
| Backend not starting | Verify `USE_LLM=true` and `ANTHROPIC_API_KEY` in `.env` |
| No live job results | Adzuna credentials optional — sample jobs appear as fallback with "Sample Job" badge |
| First question not personalised | LLM key needed — static personalised template used as fallback |
| Agent trace not showing | Only visible from Q2 onward (requires a previous answer in history) |
| Audio scores missing | Record audio using the mic button before submitting the answer |
| Video scores missing | Allow webcam access when prompted by the browser |
