"""
Phase 11 — Intelligence Engine

Core agentic logic that:
  1. Builds a personalised interview plan from the resume analysis
  2. Initialises live candidate state (skill mastery estimates)
  3. Updates candidate state after every answer
  4. Makes next-question decisions with a full decision trace

Pure Python — no external dependencies, no LLM required.
"""

import logging
from typing import Optional

from models.agent_state import (
    InterviewPlanItem,
    CandidateState,
    AgentDecisionTrace,
)

logger = logging.getLogger(__name__)

# ── Role curriculum (ordered topic flow per role) ─────────────────────────────
# Mirrors the curriculum in interview_orchestrator; kept here for plan building.

_ROLE_CURRICULUM: dict[str, list[str]] = {
    "Full Stack Developer":    ["Project Deep Dive", "REST Fundamentals", "Database Design",
                                "Authentication", "Performance Optimization", "System Design"],
    "Frontend Developer":      ["Project Deep Dive", "React Internals", "CSS Fundamentals",
                                "Rendering Strategies", "Performance Optimization", "Frontend Architecture"],
    "Backend Developer":       ["Project Deep Dive", "API Design", "Database",
                                "Concurrency", "Performance", "System Design"],
    "Data Scientist":          ["Project Deep Dive", "Model Selection", "Evaluation Metrics",
                                "Model Theory", "Practical ML", "Experimentation"],
    "ML / AI Engineer":        ["Project Deep Dive", "Transfer Learning", "Deep Learning",
                                "MLOps", "Model Serving", "Continual Learning"],
    "DevOps / Cloud Engineer": ["Project Deep Dive", "Container Fundamentals", "Kubernetes",
                                "Cloud Architecture", "Security", "Observability"],
    "Mobile Developer":        ["Project Deep Dive", "React Native Internals", "Platform APIs",
                                "Performance", "Offline Architecture"],
    "Data Engineer":           ["Project Deep Dive", "Processing Paradigms", "Pipeline Design",
                                "Data Quality", "Data Modelling", "Performance"],
}

# ── Skill → topic mapping for mastery initialisation ─────────────────────────

_SKILL_TOPIC_MAP: dict[str, str] = {
    # Full Stack
    "react": "React Internals", "vue": "Frontend Architecture", "angular": "Frontend Architecture",
    "css": "CSS Fundamentals", "html": "CSS Fundamentals", "tailwind": "CSS Fundamentals",
    "node": "API Design", "express": "API Design", "fastapi": "API Design",
    "django": "API Design", "flask": "API Design",
    "postgresql": "Database Design", "mongodb": "Database Design", "mysql": "Database Design",
    "redis": "Performance Optimization",
    "jwt": "Authentication", "oauth": "Authentication",
    "docker": "Container Fundamentals", "kubernetes": "Kubernetes", "aws": "Cloud Architecture",
    "python": "Concurrency", "javascript": "React Internals", "typescript": "Frontend Architecture",
    # ML/DS
    "scikit-learn": "Model Selection", "sklearn": "Model Selection",
    "pytorch": "Deep Learning", "tensorflow": "Deep Learning",
    "mlflow": "MLOps", "wandb": "MLOps",
    "pandas": "Practical ML", "numpy": "Practical ML",
    "spark": "Processing Paradigms", "kafka": "Pipeline Design",
    "hugging face": "Transfer Learning", "transformers": "Deep Learning",
    # DevOps
    "terraform": "Cloud Architecture", "helm": "Kubernetes",
    "prometheus": "Observability", "grafana": "Observability",
    # Mobile
    "react native": "React Native Internals", "flutter": "Platform APIs",
}


def _topic_jitter(topic: str, low: int, high: int) -> int:
    """
    Deterministic ±(high-low)//2 jitter based on topic name hash.
    Same topic always produces the same variation — reproducible across restarts.
    """
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(topic[:10]))
    span = max(high - low, 1)
    return low + (seed % span)


def _infer_level(analysis) -> str:
    if not analysis:
        return "mid"
    lvl = getattr(analysis, "experience_level", "mid")
    return lvl if lvl in ("junior", "mid", "senior") else "mid"


def _skill_to_topic(skill: str, role: str) -> str:
    """Map a resume skill to its most relevant curriculum topic."""
    sl = skill.lower()
    for key, topic in _SKILL_TOPIC_MAP.items():
        if key in sl:
            return topic
    # Fall back to second topic in role curriculum (after Project Deep Dive)
    curriculum = _ROLE_CURRICULUM.get(role, [])
    return curriculum[1] if len(curriculum) > 1 else "General"


def _initial_mastery_for_topic(topic: str, strong_skills: list[str],
                                weak_skills: list[str], level: str,
                                all_skills: list[str] | None = None) -> int:
    """
    Estimate prior mastery for a topic before any answers.

    Scoring tiers (before level offset + deterministic jitter):
      ≥2 resume skills map to this topic  → base 63   (clear evidence)
      1  resume skill maps to this topic  → base 55   (some evidence)
      Topic name in a weak_area string    → base 38   (explicit gap)
      No mapping found                    → base 47   (unknown)

    Level offset: senior +6, mid 0, junior −6.
    Jitter: ±4 deterministic hash — no two topics are identical.
    """
    level_offset = {"senior": 6, "mid": 0, "junior": -6}.get(level, 0)
    topic_lower = topic.lower()

    # Count resume skills that map to this topic via _SKILL_TOPIC_MAP
    skill_hits = 0
    if all_skills:
        for s in all_skills:
            sl = s.lower()
            for key, mapped_topic in _SKILL_TOPIC_MAP.items():
                if key in sl and mapped_topic.lower() == topic_lower:
                    skill_hits += 1
                    break

    # Also check direct name containment as fallback
    if skill_hits == 0:
        for s in (strong_skills or []):
            if topic_lower in s.lower() or s.lower() in topic_lower:
                skill_hits += 1

    # Check for explicit weak area designation
    is_weak = any(topic_lower in w.lower() or w.lower() in topic_lower for w in (weak_skills or []))

    if is_weak:
        base = 38
    elif skill_hits >= 2:
        base = 63
    elif skill_hits == 1:
        base = 55
    else:
        base = 47

    # Apply level offset then jitter (±4 deterministic)
    adjusted = base + level_offset
    jitter = _topic_jitter(topic, -4, 5)   # yields −4 to +4
    return max(10, min(95, adjusted + jitter))


# ── Public API ────────────────────────────────────────────────────────────────

def build_interview_plan(resume_analysis, selected_role: str) -> list[InterviewPlanItem]:
    """
    Create a personalised 5-step interview plan from resume analysis and target role.

    Strategy:
    1. Always open with "Project Deep Dive" if projects exist.
    2. Include weak areas from the resume as explicit mid-session probe topics.
    3. Fill remaining steps from the role curriculum (ordered).
    4. Assign opening difficulty = easy; escalate as plan progresses.
    5. Attach real resume evidence to every step.
    """
    curriculum = _ROLE_CURRICULUM.get(selected_role, [])
    level = _infer_level(resume_analysis)

    skills = getattr(resume_analysis, "skills", []) if resume_analysis else []
    projects = getattr(resume_analysis, "projects", []) if resume_analysis else []
    strengths = getattr(resume_analysis, "strengths", []) if resume_analysis else []
    weak_areas = getattr(resume_analysis, "weak_areas", []) if resume_analysis else []
    domains = getattr(resume_analysis, "domains", []) if resume_analysis else []

    # Build topic list with intent
    plan_topics: list[dict] = []  # {topic, difficulty, reason, evidence, target_skill}

    # Step 1 — Project Deep Dive (always first if projects exist)
    # Select the project most relevant to the target role, not just projects[0]
    if projects and curriculum and curriculum[0] == "Project Deep Dive":
        proj = projects[0]  # safe default
        domain_label = ""
        try:
            from services.project_classifier import select_best_project
            best, relevance, _ = select_best_project(projects, selected_role)
            if best is not None:
                proj = best
                if getattr(getattr(proj, "domain", None), "primary_domain", ""):
                    domain_label = f" [{proj.domain.primary_domain}]"
        except Exception:
            pass

        techs = ", ".join(getattr(proj, "technologies", [])[:3]) or "your mentioned technologies"
        plan_topics.append({
            "topic": "Project Deep Dive",
            "difficulty": "easy",
            "reason": (
                f"Opening with a deep dive into your '{proj.name}'{domain_label} project built with {techs}. "
                "This personalises the session and reveals how you think about architecture and trade-offs."
            ),
            "evidence": [
                f"Project '{proj.name}'{domain_label} on resume",
                f"Technologies used: {techs}",
            ],
            "target_skill": "Technical Communication",
        })

    # Step 2 — Probe a weak area from resume (if any and not already in plan)
    weak_topics_added = 0
    for wa in weak_areas[:2]:  # max 2 weak-area probes
        # Find the matching curriculum topic
        matching = next(
            (t for t in curriculum if wa.lower() in t.lower() or t.lower() in wa.lower()),
            None
        )
        topic_to_add = matching or curriculum[1] if len(curriculum) > 1 else None
        if topic_to_add and not any(p["topic"] == topic_to_add for p in plan_topics):
            plan_topics.append({
                "topic": topic_to_add,
                "difficulty": "easy",   # start easy on weak areas
                "reason": (
                    f"Your resume flags '{wa}' as an area for growth. "
                    f"Testing foundational understanding of '{topic_to_add}' to identify exact gaps."
                ),
                "evidence": [f"Resume weak area: {wa}"],
                "target_skill": wa,
            })
            weak_topics_added += 1

    # Step 3 — Fill from curriculum (skip already-added topics)
    diff_sequence = ["easy", "medium", "medium", "hard", "hard"]
    for topic in curriculum:
        if len(plan_topics) >= 5:
            break
        if any(p["topic"] == topic for p in plan_topics):
            continue

        step_idx = len(plan_topics)
        difficulty = diff_sequence[min(step_idx, len(diff_sequence) - 1)]

        # Find resume evidence for this topic
        evidence: list[str] = []
        for s in skills[:8]:
            if topic.lower() in _skill_to_topic(s, selected_role).lower():
                evidence.append(f"Skill on resume: {s}")
        if strengths:
            for st in strengths:
                if topic.lower() in st.lower() or any(w in st.lower() for w in topic.lower().split()):
                    evidence.append(f"Resume strength: {st}")
        if not evidence:
            evidence = [f"Required skill for {selected_role} at {level} level"]

        plan_topics.append({
            "topic": topic,
            "difficulty": difficulty,
            "reason": (
                f"'{topic}' is a core competency for {selected_role}. "
                + (f"Your resume lists {evidence[0].replace('Skill on resume: ', '')} as a skill — "
                   "probing depth and real-world application."
                   if evidence and "Skill on resume:" in evidence[0]
                   else f"This is a required area for the {level}-level {selected_role} role.")
            ),
            "evidence": evidence[:3],
            "target_skill": topic,
        })

    # Ensure we have at least 3 items
    while len(plan_topics) < 3:
        fallback = curriculum[len(plan_topics)] if len(plan_topics) < len(curriculum) else "Problem Solving"
        plan_topics.append({
            "topic": fallback,
            "difficulty": "medium",
            "reason": f"Core coverage area for {selected_role}.",
            "evidence": [f"Required for {selected_role}"],
            "target_skill": fallback,
        })

    return [
        InterviewPlanItem(
            step=i + 1,
            topic=p["topic"],
            difficulty=p["difficulty"],
            reason=p["reason"],
            linked_resume_evidence=p["evidence"],
            target_skill=p["target_skill"],
        )
        for i, p in enumerate(plan_topics[:5])
    ]


def initialize_candidate_state(
    session_id: str,
    candidate_id: str,
    selected_role: str,
    resume_analysis,
    interview_plan: list[InterviewPlanItem],
) -> CandidateState:
    """
    Initialise a live candidate model from the resume before any questions are asked.
    Skill mastery is estimated from resume evidence, not observed performance.
    """
    level = _infer_level(resume_analysis)

    skills = getattr(resume_analysis, "skills", []) if resume_analysis else []
    strengths = getattr(resume_analysis, "strengths", []) if resume_analysis else []
    weak_areas = getattr(resume_analysis, "weak_areas", []) if resume_analysis else []
    projects = getattr(resume_analysis, "projects", []) if resume_analysis else []

    # Build strong/weak skill lists
    strong_skills: list[str] = []
    seen: set[str] = set()
    for s in (strengths + skills[:6]):
        k = s.lower()[:40]
        if k not in seen:
            seen.add(k)
            strong_skills.append(s)

    weak_skills: list[str] = weak_areas[:4]

    # Build initial skill mastery map (one entry per planned topic)
    skill_mastery: dict[str, int] = {}
    for item in interview_plan:
        skill_mastery[item.topic] = _initial_mastery_for_topic(
            item.topic, strong_skills, weak_skills, level, all_skills=skills
        )

    # Also initialise for any curriculum topic not in the plan
    curriculum = _ROLE_CURRICULUM.get(selected_role, [])
    for topic in curriculum:
        if topic not in skill_mastery:
            skill_mastery[topic] = _initial_mastery_for_topic(
                topic, strong_skills, weak_skills, level, all_skills=skills
            )

    next_action = interview_plan[0].topic if interview_plan else "Project Deep Dive"

    # Build agent summary
    proj_names = [getattr(p, "name", "") for p in projects[:2]]
    proj_text = f"projects ({', '.join(proj_names)})" if proj_names else "no listed projects"
    weak_text = ", ".join(weak_areas[:2]) if weak_areas else "no identified gaps"

    return CandidateState(
        session_id=session_id,
        candidate_id=candidate_id,
        selected_role=selected_role,
        inferred_level=level,
        strong_skills=strong_skills[:6],
        weak_skills=weak_skills,
        skill_mastery=skill_mastery,
        confidence_trend="unknown",
        communication_trend="unknown",
        risk_flags=[],
        last_decision="session_start",
        next_best_action=next_action,
    )


def update_candidate_state(
    candidate_state: CandidateState,
    answer_record: dict,
    audio_score: Optional[dict] = None,
    video_score: Optional[dict] = None,
) -> CandidateState:
    """
    Update the candidate's live model after a single answer.
    Called from the evaluate-answer route so state stays current.
    """
    state = candidate_state.model_copy(deep=True)

    # ── Extract answer data ───────────────────────────────────────────────────
    evaluation = answer_record.get("evaluation", {})
    tech_score = evaluation.get("technical_score", 50)
    depth = evaluation.get("depth_score", 50)
    answer_text = answer_record.get("answer_text", "")
    topic = answer_record.get("topic", "")

    # Determine topic from question if not directly on record
    if not topic:
        q = answer_record.get("question", "")
        # Try to infer from mastery map keys
        for key in state.skill_mastery:
            if key.lower() in q.lower():
                topic = key
                break

    # ── Increment answer counter ──────────────────────────────────────────────
    state.answers_answered = getattr(state, "answers_answered", 0) + 1

    # ── Update skill mastery ──────────────────────────────────────────────────
    # Bayesian-style update: blend prior with observed score.
    # Weight adjusts based on answer count to trust observed evidence more over time:
    #   Q1 answer: 60% prior / 40% observed
    #   Q3+ answer: 50% prior / 50% observed
    obs_weight = 0.45 if state.answers_answered >= 3 else 0.40
    prior_weight = 1.0 - obs_weight

    if topic and topic in state.skill_mastery:
        prior = state.skill_mastery[topic]
        updated = round(prior * prior_weight + tech_score * obs_weight)
        state.skill_mastery[topic] = max(5, min(100, updated))

    # Also update adjacent topics that are closely linked to the answered topic
    # (e.g. a strong Database answer also signals SQL/query knowledge)
    _ADJACENT_TOPICS: dict[str, list[str]] = {
        "Database Design":      ["Database", "Performance"],
        "REST Fundamentals":    ["API Design", "Authentication"],
        "React Internals":      ["Frontend Architecture", "Performance Optimization"],
        "Authentication":       ["Security", "REST Fundamentals"],
        "System Design":        ["Performance", "Cloud Architecture"],
        "Kubernetes":           ["Container Fundamentals", "Cloud Architecture"],
        "Deep Learning":        ["Transfer Learning", "MLOps"],
        "Pipeline Design":      ["Processing Paradigms", "Data Quality"],
    }
    for adj in _ADJACENT_TOPICS.get(topic, []):
        if adj in state.skill_mastery:
            adj_prior = state.skill_mastery[adj]
            # Weak signal from adjacency: 85% prior / 15% observed
            adj_updated = round(adj_prior * 0.85 + tech_score * 0.15)
            state.skill_mastery[adj] = max(5, min(100, adj_updated))

    # ── Confidence trend ──────────────────────────────────────────────────────
    # Collect all tech scores observed so far from risk flags analysis
    all_scores = [tech_score]  # simplified: track last few
    if audio_score:
        conf_from_audio = audio_score.get("confidence_score", 50)
        all_scores.append(conf_from_audio)

    # Use word count as proxy for confidence when no audio
    word_count = len(answer_text.split())

    prev_trend = state.confidence_trend
    if tech_score >= 75:
        new_trend = "improving"
    elif tech_score >= 55:
        new_trend = "stable"
    else:
        new_trend = "declining"

    # Smooth: don't flip from improving to declining in one step
    if prev_trend == "improving" and new_trend == "declining":
        new_trend = "stable"
    state.confidence_trend = new_trend

    # ── Communication trend ───────────────────────────────────────────────────
    if audio_score and audio_score.get("mode") in ("faster_whisper", "whisper"):
        clarity = audio_score.get("communication_clarity_score", 50)
        state.communication_trend = "good" if clarity >= 70 else "fair" if clarity >= 50 else "poor"
    else:
        # Word count proxy
        if word_count >= 100:
            state.communication_trend = "good"
        elif word_count >= 50:
            state.communication_trend = "fair"
        else:
            state.communication_trend = "poor"

    # ── Track concept gaps from missing_points ────────────────────────────────
    missing_points = answer_record.get("evaluation", {}).get("missing_points", [])
    concept_gaps = dict(getattr(state, "concept_gaps", {}) or {})
    for concept in missing_points:
        key = concept.lower()[:60]
        concept_gaps[key] = concept_gaps.get(key, 0) + 1
    state.concept_gaps = concept_gaps

    # ── Track per-domain performance history ──────────────────────────────────
    domain_performance = dict(getattr(state, "domain_performance", {}) or {})
    if topic:
        domain_key = topic
        history = list(domain_performance.get(domain_key, []))
        history.append(tech_score)
        domain_performance[domain_key] = history[-5:]  # keep last 5
    state.domain_performance = domain_performance

    # ── Risk flags ────────────────────────────────────────────────────────────
    flags = list(state.risk_flags)

    if tech_score < 50 and topic:
        flag = f"Weak performance on '{topic}' ({tech_score}/100)"
        # Check if this topic already flagged — mark as repeated
        repeated = any(f"'{topic}'" in f and "Repeated" not in f for f in flags)
        if repeated:
            # Upgrade to repeated
            flags = [f for f in flags if f"'{topic}'" not in f]
            flags.append(f"Repeated weakness on '{topic}' — needs remediation")
        elif flag not in flags:
            flags.append(flag)

    if word_count < 40:
        short_flag = "Very brief answer — insufficient depth signal"
        if short_flag not in flags:
            flags.append(short_flag)

    audio_conf = audio_score.get("confidence_score", 100) if audio_score else 100
    if audio_conf < 50:
        conf_flag = f"Low vocal confidence detected ({audio_conf}/100)"
        if not any("Low vocal confidence" in f for f in flags):
            flags.append(conf_flag)

    state.risk_flags = flags[-6:]  # keep latest 6

    # ── Next best action ──────────────────────────────────────────────────────
    # Find the weakest topic with highest curriculum importance
    if state.skill_mastery:
        weakest = min(state.skill_mastery, key=lambda t: state.skill_mastery[t])
        state.next_best_action = weakest

    state.last_decision = "post_answer_update"
    return state


def update_candidate_state_for_improvement(
    candidate_state: CandidateState,
    answer_record: dict,
    previous_evaluation: dict,
    audio_score: Optional[dict] = None,
    video_score: Optional[dict] = None,
) -> CandidateState:
    """
    Update candidate state after /improve-answer — NOT a new unique question.

    Key differences from update_candidate_state():
    - answers_answered is NOT incremented (same question retried, not a new Q)
    - domain_performance REPLACES the last score for this topic (no double entry)
    - concept_gaps are REDUCED for concepts now covered that were previously missing
    - risk_flags for this topic are refreshed (stale weak flags cleared if score improved)

    previous_evaluation: the EvaluationResult dict from the original weak attempt,
    used to correctly reduce concept_gap counts for newly-covered concepts.
    """
    state = candidate_state.model_copy(deep=True)

    evaluation = answer_record.get("evaluation", {})
    tech_score = evaluation.get("technical_score", 50)
    depth = evaluation.get("depth_score", 50)
    answer_text = answer_record.get("answer_text", "")
    topic = answer_record.get("topic", "")

    if not topic:
        q = answer_record.get("question", "")
        for key in state.skill_mastery:
            if key.lower() in q.lower():
                topic = key
                break

    # ── answers_answered: NOT incremented — same unique question ─────────────
    # (no change to state.answers_answered)

    # ── Update skill mastery with improved score ──────────────────────────────
    obs_weight = 0.45 if state.answers_answered >= 3 else 0.40
    prior_weight = 1.0 - obs_weight

    if topic and topic in state.skill_mastery:
        prior = state.skill_mastery[topic]
        updated = round(prior * prior_weight + tech_score * obs_weight)
        state.skill_mastery[topic] = max(5, min(100, updated))

    # Adjacent topic propagation (same as normal update)
    _ADJACENT_TOPICS: dict[str, list[str]] = {
        "Database Design":      ["Database", "Performance"],
        "REST Fundamentals":    ["API Design", "Authentication"],
        "React Internals":      ["Frontend Architecture", "Performance Optimization"],
        "Authentication":       ["Security", "REST Fundamentals"],
        "System Design":        ["Performance", "Cloud Architecture"],
        "Kubernetes":           ["Container Fundamentals", "Cloud Architecture"],
        "Deep Learning":        ["Transfer Learning", "MLOps"],
        "Pipeline Design":      ["Processing Paradigms", "Data Quality"],
    }
    for adj in _ADJACENT_TOPICS.get(topic, []):
        if adj in state.skill_mastery:
            adj_prior = state.skill_mastery[adj]
            adj_updated = round(adj_prior * 0.85 + tech_score * 0.15)
            state.skill_mastery[adj] = max(5, min(100, adj_updated))

    # ── Confidence trend ──────────────────────────────────────────────────────
    word_count = len(answer_text.split())
    prev_trend = state.confidence_trend
    if tech_score >= 75:
        new_trend = "improving"
    elif tech_score >= 55:
        new_trend = "stable"
    else:
        new_trend = "declining"

    if prev_trend == "improving" and new_trend == "declining":
        new_trend = "stable"
    state.confidence_trend = new_trend

    # ── Communication trend ───────────────────────────────────────────────────
    if audio_score and audio_score.get("mode") in ("faster_whisper", "whisper"):
        clarity = audio_score.get("communication_clarity_score", 50)
        state.communication_trend = "good" if clarity >= 70 else "fair" if clarity >= 50 else "poor"
    else:
        if word_count >= 100:
            state.communication_trend = "good"
        elif word_count >= 50:
            state.communication_trend = "fair"
        else:
            state.communication_trend = "poor"

    # ── concept_gaps: reduce counts for newly-covered concepts ────────────────
    # A concept that was missing in the original answer but is now covered
    # should have its miss count decremented (down to 0, then removed).
    prev_missing = {p.lower()[:60] for p in previous_evaluation.get("missing_points", [])}
    new_covered = {p.lower()[:60] for p in evaluation.get("covered_points", [])}
    newly_resolved = prev_missing & new_covered   # concepts that were missing, now covered

    concept_gaps = dict(getattr(state, "concept_gaps", {}) or {})
    for concept in newly_resolved:
        if concept in concept_gaps:
            new_count = concept_gaps[concept] - 1
            if new_count <= 0:
                del concept_gaps[concept]
            else:
                concept_gaps[concept] = new_count

    # Add any concepts still missing in the improved answer (genuinely unresolved)
    new_missing = evaluation.get("missing_points", [])
    for concept in new_missing:
        key = concept.lower()[:60]
        # Only count if not already tracked from a previous question's miss
        if key not in concept_gaps:
            concept_gaps[key] = 1
    state.concept_gaps = concept_gaps

    # ── domain_performance: REPLACE last score, not append ────────────────────
    # Appending would create two data points for the same question and falsely
    # trigger persistent_weak checks (avg of [40, 48] < 50 = remediation).
    domain_performance = dict(getattr(state, "domain_performance", {}) or {})
    if topic:
        history = list(domain_performance.get(topic, []))
        if history:
            history[-1] = tech_score   # replace the score from the original attempt
        else:
            history = [tech_score]
        domain_performance[topic] = history[-5:]
    state.domain_performance = domain_performance

    # ── risk_flags: refresh for this topic ────────────────────────────────────
    # Remove stale weak flags for this topic if the improved score cleared the bar.
    flags = list(state.risk_flags)
    if topic and tech_score >= 50:
        flags = [f for f in flags if f"'{topic}'" not in f]

    # If still weak after improvement, update the flag to reflect new score
    if topic and tech_score < 50:
        stale = [f for f in flags if f"'{topic}'" in f]
        flags = [f for f in flags if f"'{topic}'" not in f]
        new_flag = f"Weak performance on '{topic}' ({tech_score}/100)"
        flags.append(new_flag)

    # Clear stale "Very brief answer" flag if the improved answer is longer
    if word_count >= 40:
        flags = [f for f in flags if "Very brief answer" not in f]

    state.risk_flags = flags[-6:]

    # ── Next best action ──────────────────────────────────────────────────────
    if state.skill_mastery:
        weakest = min(state.skill_mastery, key=lambda t: state.skill_mastery[t])
        state.next_best_action = weakest

    state.last_decision = "improvement_update"
    return state


# ── Next-question routing helpers ─────────────────────────────────────────────

_DIFF_UP = {"easy": "medium", "medium": "hard", "hard": "hard"}
_DIFF_DOWN = {"hard": "medium", "medium": "easy", "easy": "easy"}


def _normalize_topic(topic: str) -> str:
    """Strip follow-up prefix so routing stays on the underlying topic."""
    if topic.startswith("Follow-Up:"):
        return topic.split(":", 1)[1].strip()
    return topic


def _covered_topics(session_history: list[dict], current_topic: str) -> set[str]:
    covered = {_normalize_topic(h.get("question", {}).get("topic", "")) for h in session_history}
    covered.discard("")
    if current_topic:
        covered.add(_normalize_topic(current_topic))
    return covered


def _plan_topics(interview_plan: list[InterviewPlanItem]) -> list[str]:
    return [item.topic for item in interview_plan]


def _next_uncovered_plan_topic(plan_topics: list[str], covered: set[str]) -> Optional[str]:
    for topic in plan_topics:
        if topic not in covered:
            return topic
    return None


def _next_advance_topic(
    plan_topics: list[str],
    covered: set[str],
    current_topic: str,
) -> Optional[str]:
    """Prefer the next uncovered plan topic after the current one in curriculum order."""
    normalized_current = _normalize_topic(current_topic)
    if normalized_current in plan_topics:
        start_idx = plan_topics.index(normalized_current) + 1
        for topic in plan_topics[start_idx:]:
            if topic not in covered:
                return topic
    for topic in plan_topics:
        if topic not in covered and topic != normalized_current:
            return topic
    return None


def _weakest_mastery_topic(
    candidate_state: CandidateState,
    candidates: Optional[list[str]] = None,
) -> str:
    mastery = candidate_state.skill_mastery or {}
    pool = candidates or list(mastery.keys())
    scored = {t: mastery[t] for t in pool if t in mastery}
    if not scored:
        return candidate_state.next_best_action or (pool[0] if pool else "")
    return min(scored, key=lambda t: scored[t])


def _strongest_mastery_topic(
    candidate_state: CandidateState,
    plan_topics: list[str],
) -> str:
    mastery = candidate_state.skill_mastery or {}
    scored = {t: mastery[t] for t in plan_topics if t in mastery}
    if not scored:
        return plan_topics[0] if plan_topics else candidate_state.next_best_action
    return max(scored, key=lambda t: scored[t])


def _topic_from_gaps(
    candidate_state: CandidateState,
    missing: list[str],
    plan_topics: list[str],
) -> Optional[str]:
    """Pick a plan topic aligned with repeated concept gaps or missing rubric points."""
    gap_keys = list((candidate_state.concept_gaps or {}).keys())
    gap_keys.extend(m.lower()[:60] for m in missing)

    best_topic: Optional[str] = None
    best_hits = 0
    for topic in plan_topics:
        tl = topic.lower()
        hits = sum(1 for g in gap_keys if tl in g or g in tl or any(w in g for w in tl.split()))
        if hits > best_hits:
            best_hits = hits
            best_topic = topic

    if best_topic:
        return best_topic
    return _weakest_mastery_topic(candidate_state, plan_topics) or None


def _demonstrated_deep_mastery(
    tech_score: int,
    depth_score: int,
    missing: list[str],
    topic_count: int,
) -> bool:
    """True when the candidate is ready to leave the current topic."""
    if len(missing) > 1:
        return False
    if topic_count >= 1 and tech_score >= 80 and depth_score >= 70 and not missing:
        return True
    if topic_count >= 2 and tech_score >= 78 and depth_score >= 68 and not missing:
        return True
    if tech_score >= 90 and depth_score >= 85 and not missing:
        return True
    return False


def _should_verify_resume_claim(
    current_topic: str,
    tech_score: int,
    missing: list[str],
    risk_flags: list[str],
) -> bool:
    normalized = _normalize_topic(current_topic)
    if "deep dive" not in normalized.lower() and normalized != "Project Deep Dive":
        return False
    if tech_score >= 78:
        return False
    if any("brief" in f.lower() for f in risk_flags) and missing:
        return True
    return bool(missing) and 45 <= tech_score < 72


def _build_signal_bundle(
    tech_score: int,
    depth_score: int,
    audio_score: Optional[dict],
    video_score: Optional[dict],
    combined_score: int,
) -> tuple[dict, bool, bool, bool, int, int, int, str]:
    """
    Build judge-ready signal scores with availability flags.

    Returns:
      signal_scores, confidence_available, communication_available,
      engagement_available, audio_conf_internal, audio_clarity_internal,
      video_engagement_internal, confidence_note
    """
    confidence_available = bool(
        audio_score is not None and audio_score.get("confidence_score") is not None
    )
    communication_available = bool(
        audio_score is not None and audio_score.get("communication_clarity_score") is not None
    )
    engagement_available = bool(
        video_score is not None and video_score.get("engagement_score") is not None
    )

    audio_conf_internal = int(audio_score.get("confidence_score", 100)) if confidence_available else 100
    audio_clarity_internal = (
        int(audio_score.get("communication_clarity_score", 100)) if communication_available else 100
    )
    video_engagement_internal = (
        int(video_score.get("engagement_score", 100)) if engagement_available else 100
    )

    notes: list[str] = []
    if not confidence_available:
        notes.append("No audio confidence signal was available.")
    if not communication_available:
        notes.append("No communication clarity signal was available.")
    if not engagement_available:
        notes.append("No video engagement signal was available.")
    confidence_note = " ".join(notes)

    signal_scores: dict = {
        "technical": tech_score,
        "depth": depth_score,
        "confidence": int(audio_score["confidence_score"]) if confidence_available else None,
        "communication": (
            int(audio_score["communication_clarity_score"]) if communication_available else None
        ),
        "engagement": int(video_score["engagement_score"]) if engagement_available else None,
        "combined": combined_score,
    }
    return (
        signal_scores,
        confidence_available,
        communication_available,
        engagement_available,
        audio_conf_internal,
        audio_clarity_internal,
        video_engagement_internal,
        confidence_note,
    )


def _build_observation(
    decision_type: str,
    current_topic: str,
    tech_score: int,
    depth_score: int,
    missing: list[str],
    confidence_available: bool,
    audio_conf_internal: int,
    has_confidence_flag: bool,
) -> str:
    """Plain-English summary of what the agent observed."""
    missing_text = ""
    if missing:
        missing_text = f" and missed {', '.join(missing[:2])}"

    if decision_type in ("remediation", "strengthen_fundamentals") or tech_score < 50:
        quality = "shallow" if tech_score < 55 else "weak"
        return (
            f"Candidate gave a {quality} answer on {current_topic}{missing_text}."
        )

    if decision_type == "confidence_recovery":
        if confidence_available:
            return (
                f"Candidate's technical score was moderate ({tech_score}/100), but the "
                f"confidence signal was low ({audio_conf_internal}/100), so the agent "
                "chose a supportive next question."
            )
        return (
            f"Candidate's technical score was moderate ({tech_score}/100), and other "
            "uncertainty cues were present, so the agent chose a supportive next question."
        )

    if decision_type in ("deeper_follow_up", "verify_resume_claim"):
        return (
            f"Candidate showed partial understanding on '{current_topic}'"
            f"{missing_text}. A targeted follow-up is needed to probe remaining depth."
        )

    if decision_type == "increase_difficulty" or tech_score >= 80:
        return (
            f"Candidate gave a strong answer on {current_topic} with good depth "
            f"(technical {tech_score}/100, depth {depth_score}/100)."
        )

    if decision_type == "behavioral_probe":
        if has_confidence_flag:
            return (
                f"Candidate answered technical questions but confidence signals were low. "
                "Shifting to a behavioral probe to assess communication and ownership."
            )
        if tech_score >= 75:
            return (
                f"Candidate showed strong technical performance ({tech_score}/100). "
                "Now assessing communication, ownership, and soft skills through a behavioral question."
            )
        return (
            f"Candidate has answered technical questions (last score: {tech_score}/100). "
            "Now validating communication clarity and ownership through a behavioral probe."
        )

    if decision_type == "switch_topic":
        return (
            f"Candidate demonstrated solid understanding of '{current_topic}' "
            f"({tech_score}/100) with no major gaps remaining."
        )

    if has_confidence_flag and confidence_available:
        return (
            f"Candidate answered '{current_topic}' with technical score {tech_score}/100, "
            f"but confidence signals were low ({audio_conf_internal}/100)."
        )

    return (
        f"Candidate answered on '{current_topic}' with technical score {tech_score}/100 "
        f"and depth {depth_score}/100{missing_text}."
    )


_BEHAVIORAL_TOPIC = "Behavioral & Communication"


def _behavioral_trigger_label(
    candidate_state: CandidateState,
    tech_score: int,
    n: int,
) -> str:
    """Return a short human-readable label for whichever trigger fired."""
    if candidate_state.communication_trend in ("poor", "fair"):
        return f"weak communication trend ('{candidate_state.communication_trend}')"
    if candidate_state.confidence_trend == "declining":
        return "declining confidence trend"
    if tech_score >= 75:
        return f"strong technical performance ({tech_score}/100)"
    if n >= 4:
        return "late-interview coverage gap — behavioral dimension not yet assessed"
    if n >= 3:
        return f"adequate technical coverage after {n} questions; role requires soft-skill validation"
    return "behavioral assessment due"


def _should_do_behavioral_probe(
    candidate_state: CandidateState,
    covered_topics: set[str],
    tech_score: int,
    session_history: list[dict],
) -> bool:
    """
    Returns True when the primary path should ask a behavioral question.

    Eligibility gate (all must pass):
      - "Behavioral & Communication" not yet in covered topics
      - No previous question had question_type=="behavioral" or behavioral topic
      - candidate_state.answers_answered >= 2 (unique questions, NOT retries)

    answers_answered >= 2 alone does NOT trigger — it only opens eligibility.

    Triggers (at least one must fire):
      1. communication_trend is "poor" or "fair"   — communication signal
      2. confidence_trend is "declining"            — confidence signal
      3. tech_score >= 75                           — strong technical → validate soft skills
      4. n >= 3 and role is set                     — role coverage gap (all roles need soft skills;
                                                       by Q4 we have adequate technical signal)
      5. n >= 4                                     — late-interview urgency
    """
    # Guard 1: topic not already covered
    if _BEHAVIORAL_TOPIC in covered_topics:
        return False

    # Guard 2: no previous behavioral question in history (catches custom topics)
    for entry in session_history:
        q = entry.get("question", {})
        q_topic = (q.get("topic") or "").lower()
        q_type = (q.get("question_type") or "")
        if q_type == "behavioral" or "behavioral" in q_topic or "communication" in q_topic:
            return False

    # Eligibility gate — answers_answered >= 2 is necessary but not sufficient
    n = candidate_state.answers_answered
    if n < 2:
        return False

    # Trigger 1: communication concern (fires at n >= 2)
    if candidate_state.communication_trend in ("poor", "fair"):
        return True

    # Trigger 2: confidence declining (fires at n >= 2; works without audio)
    if candidate_state.confidence_trend == "declining":
        return True

    # Trigger 3: strong technical performance → soft-skill validation needed
    if tech_score >= 75:
        return True

    # Trigger 4: adequate technical coverage — by Q4 (n >= 3) enough signal
    # exists to justify pivoting to assess communication, ownership, reflection.
    if n >= 3 and candidate_state.selected_role:
        return True

    # Trigger 5: late-interview urgency — n >= 4 means we're near the end
    # without having assessed the behavioral dimension at all.
    if n >= 4:
        return True

    return False


def make_next_question_decision(
    candidate_state: CandidateState,
    last_evaluation: dict,
    current_question: dict,
    interview_plan: list[InterviewPlanItem],
    session_history: list[dict],
    audio_score: Optional[dict] = None,
    video_score: Optional[dict] = None,
    multimodal_score: Optional[dict] = None,
) -> AgentDecisionTrace:
    """
    Decide what to do next based on candidate state, not just the raw score.
    Returns a full decision trace explaining the reasoning.
    """
    tech_score = last_evaluation.get("technical_score", 50)
    depth_score = last_evaluation.get("depth_score", 50)
    missing = last_evaluation.get("missing_points", [])
    covered = last_evaluation.get("covered_points", [])
    current_topic = _normalize_topic(current_question.get("topic", ""))
    current_diff = current_question.get("difficulty", "medium")

    topic_count = sum(
        1 for h in session_history
        if _normalize_topic(h.get("question", {}).get("topic", "")) == current_topic
    )

    audio_conf = int(audio_score.get("confidence_score", 100)) if audio_score else 100
    audio_clarity = int(audio_score.get("communication_clarity_score", 100)) if audio_score else 100
    video_engagement = int(video_score.get("engagement_score", 100)) if video_score else 100
    visual_stress = (video_score or {}).get("stress_indicator") or (video_score or {}).get("stress_nervousness_indicator")
    combined_score = int(multimodal_score.get("combined_score", tech_score)) if multimodal_score else tech_score
    multimodal_signal = (multimodal_score or {}).get("multimodal_signal", "average_performance")
    (
        signal_scores,
        confidence_available,
        communication_available,
        engagement_available,
        audio_conf,
        audio_clarity,
        video_engagement,
        confidence_note,
    ) = _build_signal_bundle(
        tech_score, depth_score, audio_score, video_score, combined_score,
    )

    risk_flags = candidate_state.risk_flags
    has_confidence_flag = (
        any("Low vocal confidence" in f for f in risk_flags)
        or audio_conf < 50
        or audio_clarity < 45
        or video_engagement < 45
        or visual_stress == "high"
    )
    has_repeated_weakness = any("Repeated weakness" in f and current_topic in f for f in risk_flags)

    domain_perf = getattr(candidate_state, "domain_performance", {}) or {}
    topic_history = domain_perf.get(current_topic, [])
    persistent_weak = len(topic_history) >= 2 and (sum(topic_history[-2:]) / 2) < 50

    plan_topics = _plan_topics(interview_plan)
    covered_topics = _covered_topics(session_history, current_topic)

    # ── Determine decision type ────────────────────────────────────────────────
    if has_repeated_weakness or persistent_weak:
        decision_type = "remediation"
        detail = (
            f"last two scores avg {round(sum(topic_history[-2:]) / max(len(topic_history[-2:]), 1))}/100"
            if topic_history else "repeated weakness flag present"
        )
        detected_issue = (
            f"'{current_topic}' has been flagged as weak more than once ({detail}). "
            "The candidate needs reinforcement on fundamentals before advancing."
        )
    elif has_confidence_flag:
        decision_type = "confidence_recovery"
        detected_issue = (
            "Low vocal confidence detected via audio/video analysis. "
            "Easing to a more accessible question to rebuild momentum."
        )
    elif _should_verify_resume_claim(current_topic, tech_score, missing, risk_flags):
        decision_type = "verify_resume_claim"
        detected_issue = (
            f"The answer on '{current_topic}' lacked concrete resume-backed detail "
            + (f"(missing: {', '.join(missing[:2])})." if missing else ".")
            + " Verifying ownership of claimed project experience."
        )
    elif _should_do_behavioral_probe(candidate_state, covered_topics, tech_score, session_history):
        decision_type = "behavioral_probe"
        _trigger_label = _behavioral_trigger_label(candidate_state, tech_score, candidate_state.answers_answered)
        detected_issue = (
            f"Candidate is eligible for behavioral assessment after "
            f"{candidate_state.answers_answered} technical question(s); "
            f"trigger: {_trigger_label}. "
            "Now validating communication, ownership, and soft skills."
        )
    elif tech_score >= 85 and depth_score >= 65:
        decision_type = "increase_difficulty"
        detected_issue = (
            f"Exceptional performance ({tech_score}/100, depth {depth_score}/100) on '{current_topic}'. "
            "Increasing difficulty to test the ceiling."
        )
    elif tech_score >= 80:
        decision_type = "increase_difficulty"
        detected_issue = (
            f"Strong performance ({tech_score}/100) on '{current_topic}'. "
            "Ready for increased challenge."
        )
    elif (
        tech_score >= 72
        and depth_score >= 60
        and not missing
        and topic_count >= 1
    ):
        decision_type = "switch_topic"
        detected_issue = (
            f"Solid grasp of '{current_topic}' ({tech_score}/100) with no remaining gaps. "
            "Moving to the next role-critical area."
        )
    elif 60 <= tech_score < 80 and len(missing) <= 2:
        decision_type = "deeper_follow_up"
        detected_issue = (
            f"Good performance ({tech_score}/100) with gaps on '{current_topic}'. "
            "A follow-up can probe the remaining depth."
        )
    elif 50 <= tech_score < 60:
        decision_type = "deeper_follow_up"
        detected_issue = (
            f"Partial understanding of '{current_topic}' ({tech_score}/100). "
            "Staying on topic to probe implementation details."
        )
    else:
        decision_type = "strengthen_fundamentals"
        detected_issue = (
            f"Answer on '{current_topic}' showed significant gaps ({tech_score}/100): "
            + (f"missing {', '.join(missing[:2])}" if missing else "unclear fundamentals")
            + ". Returning to foundational concepts."
        )

    if multimodal_signal == "strong_technical_low_confidence":
        if decision_type == "deeper_follow_up":
            decision_type = "confidence_recovery"
            detected_issue = (
                f"Strong technical answer ({tech_score}/100) but low vocal confidence detected. "
                "Keeping difficulty and adding encouragement to help the candidate relax."
            )
    elif multimodal_signal == "weak_technical_low_confidence":
        if decision_type not in ("remediation", "strengthen_fundamentals"):
            decision_type = "strengthen_fundamentals"
            detected_issue = (
                f"Low technical score ({tech_score}/100) combined with low behavioural confidence. "
                "Stepping back to accessible fundamentals to rebuild understanding and composure."
            )
    elif multimodal_signal == "weak_technical_needs_coaching":
        if decision_type not in ("remediation", "strengthen_fundamentals", "confidence_recovery"):
            decision_type = "confidence_recovery"
            detected_issue = (
                f"Technical gaps ({tech_score}/100) paired with low confidence signal. "
                "Choosing a more structured, accessible question to build momentum."
            )
    elif multimodal_signal == "strong_candidate":
        if decision_type != "increase_difficulty":
            decision_type = "increase_difficulty"
            detected_issue = (
                f"Strong candidate signal - technical ({tech_score}/100), confidence, and communication "
                "are all above threshold. Increasing challenge."
            )
    elif multimodal_signal == "confidence_and_engagement_low":
        if decision_type not in ("confidence_recovery", "remediation"):
            decision_type = "confidence_recovery"
            detected_issue = (
                "Both confidence and engagement signals are low. "
                "Switching to a more accessible question with positive framing."
            )

    # TODO(behavioral_probe): inject a behavioral question when len(session_history) >= 2
    # and no behavioral topic has been covered — defer to orchestrator fallback for now.

    # ── Agentic topic + difficulty selection ───────────────────────────────────
    next_topic = current_topic
    next_diff = current_diff
    topic_rationale = ""
    difficulty_rationale = ""
    next_question_strategy = ""

    if decision_type == "deeper_follow_up":
        next_topic = current_topic
        if depth_score >= 70 and tech_score >= 72 and current_diff != "hard":
            next_diff = _DIFF_UP.get(current_diff, current_diff)
            difficulty_rationale = (
                f"Raised difficulty from {current_diff} to {next_diff} because the candidate "
                "showed partial understanding and can handle a slightly deeper probe."
            )
        else:
            next_diff = current_diff
            difficulty_rationale = (
                f"Keeping {current_diff} difficulty while closing gaps before escalating further."
            )
        gap_hint = f" Missing: {', '.join(missing[:2])}." if missing else ""
        topic_rationale = (
            f"Staying on '{current_topic}' for a deeper follow-up — "
            f"candidate showed partial understanding ({tech_score}/100).{gap_hint}"
        )
        next_question_strategy = "same_topic_depth_probe"

    elif decision_type in ("remediation", "strengthen_fundamentals"):
        gap_topic = _topic_from_gaps(candidate_state, missing, plan_topics)
        weak_topic = _weakest_mastery_topic(candidate_state, plan_topics or None)
        next_topic = gap_topic or weak_topic or current_topic
        current_mastery = candidate_state.skill_mastery.get(current_topic, 100)
        chosen_mastery = candidate_state.skill_mastery.get(next_topic, 100)
        if current_mastery <= chosen_mastery:
            next_topic = current_topic
        next_diff = _DIFF_DOWN.get(current_diff, "easy")
        topic_rationale = (
            f"Selected '{next_topic}' because it is the weakest or most gap-heavy area "
            f"(mastery estimate {candidate_state.skill_mastery.get(next_topic, 'unknown')}/100)"
            + (" with repeated concept gaps." if candidate_state.concept_gaps else ".")
        )
        difficulty_rationale = (
            f"Reduced difficulty from {current_diff} to {next_diff} to rebuild fundamentals "
            "before advancing the interview plan."
        )
        next_question_strategy = "remediation_weakest_or_gap_topic"

    elif decision_type == "confidence_recovery":
        strong_topic = _strongest_mastery_topic(candidate_state, plan_topics)
        current_mastery = candidate_state.skill_mastery.get(current_topic, 50)
        strong_mastery = candidate_state.skill_mastery.get(strong_topic, 50)
        if current_mastery >= strong_mastery:
            next_topic = current_topic
            topic_rationale = (
                f"Staying on '{current_topic}' at an easier difficulty to rebuild confidence "
                f"(audio/visual confidence signals were low: {audio_conf}/100)."
            )
        else:
            next_topic = strong_topic
            topic_rationale = (
                f"Switching to '{strong_topic}' where prior mastery is stronger "
                f"({strong_mastery}/100) to rebuild confidence with a supportive question."
            )
        next_diff = _DIFF_DOWN.get(current_diff, "easy")
        difficulty_rationale = (
            f"Lowered difficulty from {current_diff} to {next_diff} for confidence recovery — "
            "avoiding a hard pivot while momentum is fragile."
        )
        next_question_strategy = "confidence_recovery_easier"

    elif decision_type == "increase_difficulty":
        deep_mastery = _demonstrated_deep_mastery(tech_score, depth_score, missing, topic_count)
        if deep_mastery:
            uncovered = _next_advance_topic(plan_topics, covered_topics, current_topic)
            if uncovered and uncovered != current_topic:
                next_topic = uncovered
                topic_rationale = (
                    f"Deep mastery demonstrated on '{current_topic}' ({tech_score}/100, depth {depth_score}/100); "
                    f"advancing to uncovered plan topic '{next_topic}'."
                )
                next_question_strategy = "advance_uncovered_topic"
            else:
                next_topic = current_topic
                topic_rationale = (
                    f"Deep mastery on '{current_topic}' but no new plan topics remain — "
                    "staying on topic with maximum difficulty."
                )
                next_question_strategy = "deepen_same_topic_hard"
        else:
            next_topic = current_topic
            topic_rationale = (
                f"Strong performance ({tech_score}/100) but not yet deep mastery on '{current_topic}' — "
                "staying on topic with increased difficulty."
            )
            next_question_strategy = "increase_difficulty_same_topic"
        next_diff = _DIFF_UP.get(current_diff, "medium")
        difficulty_rationale = (
            f"Increased difficulty from {current_diff} to {next_diff} after strong answer "
            f"(technical {tech_score}/100, depth {depth_score}/100)."
        )

    elif decision_type == "switch_topic":
        next_topic = _next_advance_topic(plan_topics, covered_topics, current_topic)
        if not next_topic:
            next_topic = _next_uncovered_plan_topic(plan_topics, covered_topics)
        if not next_topic:
            next_topic = _weakest_mastery_topic(
                candidate_state,
                [t for t in plan_topics if t not in covered_topics] or plan_topics,
            )
        next_diff = "medium"
        topic_rationale = (
            f"Moving from '{current_topic}' to uncovered role-critical topic '{next_topic}' — "
            "prior topic showed solid understanding with no remaining gaps."
        )
        difficulty_rationale = "Reset to medium difficulty when entering a new topic area."
        next_question_strategy = "switch_uncovered_topic"

    elif decision_type == "verify_resume_claim":
        next_topic = current_topic or "Project Deep Dive"
        next_diff = current_diff if current_diff == "easy" else _DIFF_DOWN.get(current_diff, "medium")
        topic_rationale = (
            f"Staying on '{next_topic}' to verify resume/project claims — "
            "the prior answer lacked concrete, resume-backed detail."
        )
        difficulty_rationale = (
            f"Using manageable ({next_diff}) difficulty while probing for specific ownership evidence."
        )
        next_question_strategy = "verify_resume_claim"

    elif decision_type == "behavioral_probe":
        next_topic = _BEHAVIORAL_TOPIC
        next_diff = "medium"
        comm_context = (
            f" Communication trend is currently '{candidate_state.communication_trend}'."
            if candidate_state.communication_trend not in ("unknown", "good") else ""
        )
        topic_rationale = (
            "Selecting a behavioral question to assess communication, ownership, and "
            f"reflection — essential soft skills for the {candidate_state.selected_role} role."
            f"{comm_context}"
        )
        difficulty_rationale = (
            "Medium difficulty for a behavioral question — the goal is clarity and "
            "self-reflection, not technical depth. STAR-style framing is expected."
        )
        next_question_strategy = "behavioral_communication_probe"

    elif decision_type == "final_synthesis":
        next_topic = current_topic or (plan_topics[0] if plan_topics else "Synthesis")
        next_diff = "hard" if current_diff != "easy" else "medium"
        topic_rationale = "All planned topics covered — synthesis question across experience."
        difficulty_rationale = "Final synthesis at elevated difficulty."
        next_question_strategy = "final_synthesis"

    else:
        next_topic = _next_uncovered_plan_topic(plan_topics, covered_topics) or current_topic
        topic_rationale = f"Default advance to '{next_topic}'."
        difficulty_rationale = f"Maintaining {next_diff} difficulty."
        next_question_strategy = "default_advance"

    # All topics covered → synthesis override (unless already remediating)
    all_plan_covered = (
        len(plan_topics) > 0
        and all(t in covered_topics for t in plan_topics)
    )
    if (
        decision_type not in (
            "remediation", "strengthen_fundamentals", "confidence_recovery",
            "behavioral_probe", "final_synthesis",
        )
        and all_plan_covered
    ):
        decision_type = "final_synthesis"
        detected_issue = "All planned topics have been covered."
        next_topic = current_topic or plan_topics[-1]
        next_diff = "hard" if current_diff != "easy" else "medium"
        topic_rationale = "All planned topics covered — synthesis question across experience."
        difficulty_rationale = "Final synthesis at elevated difficulty."
        next_question_strategy = "final_synthesis"

    # ── Build human-readable reason ────────────────────────────────────────────
    reason_templates = {
        "increase_difficulty": (
            f"You scored {tech_score}/100 on '{current_topic}' — excellent. "
            f"{'Staying on' if next_topic == current_topic else 'Moving to'} '{next_topic}' "
            f"at {next_diff} difficulty to continue stretching your knowledge."
        ),
        "deeper_follow_up": (
            f"Good understanding of '{current_topic}' ({tech_score}/100). "
            f"Staying on '{next_topic}' to probe remaining depth"
            + (f" around {', '.join(missing[:2])}." if missing else ".")
        ),
        "strengthen_fundamentals": (
            f"The answer on '{current_topic}' ({tech_score}/100) had gaps in key concepts. "
            f"Stepping back to '{next_topic}' at {next_diff} difficulty to check the foundation."
        ),
        "confidence_recovery": (
            f"Sensing some uncertainty — a more structured question on '{next_topic}' "
            f"at {next_diff} difficulty to help rebuild momentum."
        ),
        "remediation": (
            f"'{current_topic}' has appeared weak more than once. "
            f"Remediating on '{next_topic}' at {next_diff} difficulty to close systematic gaps."
        ),
        "switch_topic": (
            f"Solid work on '{current_topic}' ({tech_score}/100). "
            f"Moving to '{next_topic}' to cover another important {candidate_state.selected_role} area."
        ),
        "verify_resume_claim": (
            f"Your answer on '{current_topic}' was light on concrete project detail. "
            f"Let's verify the specifics on '{next_topic}'."
        ),
        "behavioral_probe": (
            "You've built up solid technical signal across the interview. "
            "Shifting to a behavioral question to evaluate how you communicate, make trade-offs, "
            f"and take ownership — skills that matter for the {candidate_state.selected_role} role."
        ),
        "final_synthesis": (
            f"You've covered the planned areas for {candidate_state.selected_role}. "
            "This final question asks you to synthesise your experience at a high level."
        ),
    }
    reason = reason_templates.get(
        decision_type,
        f"Moving to '{next_topic}' at {next_diff} difficulty.",
    )

    # ── Evidence bullets ───────────────────────────────────────────────────────
    evidence: list[str] = []
    evidence.append(f"Technical score on Q: {tech_score}/100")
    evidence.append(f"Depth score: {depth_score}/100")
    if audio_score:
        if confidence_available:
            evidence.append(f"Audio confidence: {audio_conf}/100")
        else:
            evidence.append("Audio confidence: not available")
        if communication_available:
            evidence.append(f"Communication clarity: {audio_clarity}/100")
        else:
            evidence.append("Communication clarity: not available")
    if video_score:
        stress_label = visual_stress or "not flagged"
        if engagement_available:
            evidence.append(f"Video engagement: {video_engagement}/100; stress proxy: {stress_label}")
        else:
            evidence.append(f"Video engagement: not available; stress proxy: {stress_label}")
    if multimodal_score:
        evidence.append(f"Combined multimodal score: {combined_score}/100")
        if multimodal_signal and multimodal_signal != "average_performance":
            evidence.append(f"Multimodal signal: {multimodal_signal.replace('_', ' ')}")
    if covered:
        evidence.append(f"Covered: {', '.join(covered[:2])}")
    if missing:
        evidence.append(f"Missing: {', '.join(missing[:2])}")
    if candidate_state.confidence_trend != "unknown":
        evidence.append(f"Confidence trend: {candidate_state.confidence_trend}")
    mastery_val = candidate_state.skill_mastery.get(next_topic)
    if mastery_val is not None:
        evidence.append(f"Prior mastery estimate for '{next_topic}': {mastery_val}/100")
    improvement_hint = last_evaluation.get("improvement_hint", "")
    if improvement_hint:
        evidence.append(f"Coaching hint: {improvement_hint[:80]}")
    if topic_rationale:
        evidence.append(f"Topic rationale: {topic_rationale[:120]}")
    if difficulty_rationale:
        evidence.append(f"Difficulty rationale: {difficulty_rationale[:120]}")

    observation = _build_observation(
        decision_type,
        current_topic,
        tech_score,
        depth_score,
        missing,
        confidence_available,
        audio_conf,
        has_confidence_flag,
    )

    return AgentDecisionTrace(
        decision_type=decision_type,
        previous_topic=current_topic,
        previous_score=tech_score,
        detected_issue=detected_issue,
        next_topic=next_topic,
        next_difficulty=next_diff,
        reason_for_adaptation=reason,
        evidence=evidence,
        observation=observation,
        signal_scores=signal_scores,
        topic_rationale=topic_rationale,
        difficulty_rationale=difficulty_rationale,
        next_question_strategy=next_question_strategy,
        generation_mode="pending",
        confidence_available=confidence_available,
        communication_available=communication_available,
        engagement_available=engagement_available,
        confidence_note=confidence_note,
    )
