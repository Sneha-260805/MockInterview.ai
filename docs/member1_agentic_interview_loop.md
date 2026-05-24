# Member 1 — Agentic Interview Brain

## What was improved (Steps 1–6)

| Step | Capability |
|------|-----------|
| 1 | Decision-aware question generation — `generate_question()` receives the agent's decision type, missing concepts, confidence/communication/engagement scores, and previous Q&A context |
| 2 | Agentic topic and difficulty routing — `make_next_question_decision()` picks the next topic and difficulty based on live candidate state, not a fixed script |
| 3 | Primary-path follow-up generation — `followup_primary.resolve_primary_next_question()` tries the template-based `followup_generator` before falling back to `question_generator`; the orchestrator fallback is untouched |
| 4 | Judge-ready decision trace — every decision produces an `AgentDecisionTrace` with `observation`, `evidence`, `signal_scores`, `topic_rationale`, `difficulty_rationale`, `generation_mode`, and `followup_of_previous` |
| 5 | Improve-answer state consistency — `/improve-answer` uses `update_candidate_state_for_improvement()` which replaces scores (no double-counting), reduces concept gaps, and clears stale risk flags without incrementing the unique-question counter |
| 6 | Signal-driven behavioral probe — `behavioral_probe` fires only when a real signal exists (weak communication, declining confidence, strong technical performance, or role coverage gap); `answers_answered >= 2` is an eligibility gate, not a trigger |

---

## The Agentic Loop

```
Answer received
      │
      ▼
┌─────────────────────────────────────┐
│  OBSERVE                            │
│  update_candidate_state()           │
│  - Bayesian mastery update          │
│  - confidence/communication trend   │
│  - concept_gaps from missing_points │
│  - domain_performance history       │
│  - risk_flags (weak, repeated weak) │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  REASON + DECIDE                    │
│  make_next_question_decision()      │
│  Priority chain:                    │
│    repeated_weakness  → remediation │
│    low confidence     → recovery    │
│    vague claim        → verify      │
│    behavioral signal  → probe       │
│    high score         → escalate    │
│    partial score      → follow_up   │
│    weak score         → fundamentals│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  ACT                                │
│  resolve_primary_next_question()    │
│  1. followup_generator (template)   │
│  2. question_generator (LLM/det.)   │
│  3. orchestrator fallback (bank)    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  EXPLAIN                            │
│  AgentDecisionTrace (judge-ready)   │
│  - decision_type, next_topic/diff   │
│  - observation, detected_issue      │
│  - evidence[], signal_scores{}      │
│  - topic_rationale, diff_rationale  │
│  - generation_mode, followup_flag   │
└──────────────┬──────────────────────┘
               │
               ▼
         State persisted to DB
         (candidate_state updated in session)
```

---

## Demo Examples

### Weak Answer — Remediation / Fundamentals

**Question:** "How does database indexing improve query performance?"

**Candidate answer:** "Indexing makes search faster."

**Agent behavior:**
- Observes shallow answer (tech score ~30/100, depth score ~25/100)
- Detects missing concepts: query plan analysis, index selectivity, read/write trade-off
- Chooses `strengthen_fundamentals` (or `remediation` if previously weak)
- Stays on Database topic, lowers difficulty from medium → easy
- Generates a simpler practical question: "Can you walk me through what a B-tree index actually stores and why it speeds up a `WHERE email = ?` lookup?"
- Trace: `detected_issue` names the missing concepts; `difficulty_rationale` explains the step-down

**Trace example:**
```
decision_type:       "strengthen_fundamentals"
next_topic:          "Database"
next_difficulty:     "easy"
observation:         "Candidate gave a shallow answer on Database and missed query plan, index selectivity."
detected_issue:      "Answer on 'Database' showed significant gaps (30/100): missing query plan, index selectivity."
topic_rationale:     "Selected 'Database' because it is the weakest area (mastery 55/100) with repeated concept gaps."
difficulty_rationale:"Reduced difficulty from medium to easy to rebuild fundamentals before advancing."
```

---

### Strong Answer — Difficulty Escalation

**Question:** "How does database indexing improve query performance?"

**Candidate answer:** "Indexing creates a B-tree data structure on the indexed columns. For a login-by-email lookup I would index the email column, verify the plan with EXPLAIN ANALYZE, and factor in write overhead since each insert must update the index."

**Agent behavior:**
- Observes strong, structured answer (tech score ~88/100, depth score ~80/100)
- No missing rubric points
- Chooses `increase_difficulty`
- Stays on Database and raises difficulty to hard, OR advances to next plan topic if mastery is demonstrated
- Trace: `observation` acknowledges the technical depth; `detected_issue` explains the escalation

**Trace example:**
```
decision_type:       "increase_difficulty"
next_topic:          "Database"
next_difficulty:     "hard"
observation:         "Candidate gave a strong answer on Database with good depth (technical 88/100, depth 80/100)."
detected_issue:      "Strong performance (88/100) on 'Database'. Ready for increased challenge."
difficulty_rationale:"Increased difficulty from medium to hard after strong answer (technical 88/100, depth 80/100)."
```

---

### Vague Claim — Template Follow-up

**Candidate answer:** "I used Redis to improve API performance."

**Agent behavior:**
- `followup_generator` scans the answer and matches the `\bredis\b` pattern
- Does not call the LLM — uses a pre-validated template question
- Returns: "You used Redis — beyond simple caching, how did you handle cache invalidation to prevent stale reads, and did you use any of Redis's data structures beyond strings?"
- `generation_mode` = `"followup_generator"`, `followup_of_previous` = `True`
- Trace evidence includes: "Follow-up generated from candidate answer: You specifically mentioned redis in your answer."

**Trace example:**
```
generation_mode:    "followup_generator"
followup_of_previous: true
question_type:      "follow_up"
expected_points:    [
  "TTL vs event-driven invalidation strategies",
  "Cache-aside vs write-through vs write-behind patterns",
  "Redis Sorted Sets for leaderboards, Pub/Sub for real-time",
  "Redis cluster mode and consistency considerations"
]
```

---

### Improved Answer — State Replaced, Not Doubled

**Original (weak) answer:** "I use connection pooling." → tech score 38/100
- State: `answers_answered=1`, `concept_gaps={query optimization, index strategy}`, `domain_performance={Database: [38]}`

**Improved answer:** "I use connection pooling, analyze slow queries with EXPLAIN, and add indexes on high-cardinality columns." → tech score 74/100

**Agent behavior:**
- `/improve-answer` calls `update_candidate_state_for_improvement()` — NOT `update_candidate_state()`
- `answers_answered` stays at **1** (same unique question, not a new question)
- `domain_performance["Database"]` becomes `[74]` — the score is **replaced**, not appended to `[38, 74]`
- `concept_gaps` for `"query optimization"` and `"index strategy"` are **removed** (now covered)
- Stale `"Weak performance on 'Database' (38/100)"` risk flag is **cleared**
- Next-question decision runs on the improved state → no longer triggers remediation

**Why this matters:** Appending would create `[38, 74]` → average 56, safe. But if the improvement was `[38, 48]` (still weak), appending creates average 43 → `persistent_weak = True` → wrongly triggers remediation. Replacing prevents this false positive.

---

### Behavioral Probe — Signal-Driven

**Condition:** Candidate has answered 2 technical questions. `communication_trend = "poor"` (short, hesitant answers).

**Agent behavior:**
- `_should_do_behavioral_probe()` checks eligibility: `answers_answered >= 2` ✓
- Checks triggers: `communication_trend == "poor"` → **fires**
- Selects `next_topic = "Behavioral & Communication"`, `next_difficulty = "medium"`
- Generates a role-aware behavioral question: "Tell me about a time you had to take ownership of a difficult problem outside your immediate scope as a Backend Developer..."
- Trace names the trigger: `"trigger: weak communication trend ('poor')"`

**What does NOT fire behavioral_probe:**
- `answers_answered == 2` alone with good communication and stable confidence
- The agent does not ask behavioral questions on a fixed Q3 schedule

**Trace example:**
```
decision_type:          "behavioral_probe"
next_topic:             "Behavioral & Communication"
next_difficulty:        "medium"
next_question_strategy: "behavioral_communication_probe"
detected_issue:         "Candidate is eligible for behavioral assessment after 2 technical question(s); trigger: weak communication trend ('poor'). Now validating communication, ownership, and soft skills."
topic_rationale:        "Selecting a behavioral question to assess communication, ownership, and reflection — essential soft skills for the Backend Developer role. Communication trend is currently 'poor'."
```

---

## What to Say to Judges

> "Our interview brain is agentic because after every answer it updates candidate state, evaluates technical depth and behavioural signals, decides the next best action, generates an adaptive question, and records a transparent decision trace explaining why that action was chosen."

The key properties that make this genuinely agentic rather than scripted:
- **Live state**: `CandidateState` is updated after every answer and persists across the session
- **Signal-driven routing**: the decision chain reads skill mastery, concept gaps, confidence trend, communication trend, and risk flags — not just the raw score
- **Explainability**: every decision ships a `AgentDecisionTrace` with human-readable rationale, evidence bullets, and signal availability flags
- **Idempotent retries**: `/improve-answer` updates state without corrupting session counters or falsely triggering remediation
- **Preserved safety net**: the orchestrator fallback bank remains fully intact if the primary path fails

---

## Test Results

**Command:**
```bash
cd backend
python -m pytest \
  tests/test_improve_answer_state_drift.py \
  tests/test_decision_trace.py \
  tests/test_followup_primary_path.py \
  tests/test_intelligence_engine.py \
  tests/test_question_generator_decision_context.py \
  tests/test_agentic_interview_loop_integration.py \
  -q
```

**Result: 101 passed, 0 failed, 1 warning (Pydantic v2 deprecation — not our code)**

| Test file | Tests | Coverage |
|-----------|-------|----------|
| `test_improve_answer_state_drift.py` | 13 | Step 5: improve-answer state correctness |
| `test_decision_trace.py` | varies | Step 4: AgentDecisionTrace fields |
| `test_followup_primary_path.py` | varies | Step 3: primary-path follow-up routing |
| `test_intelligence_engine.py` | varies | Steps 2 & 6: routing logic, behavioral probe |
| `test_question_generator_decision_context.py` | varies | Step 1: decision context in question generation |
| `test_agentic_interview_loop_integration.py` | **27** | Step 7: full loop integration |

**No production bugs were found or fixed during integration testing.** All behaviors exercised by the integration tests were already correct in the production code, confirming that Steps 1–6 were implemented consistently.
