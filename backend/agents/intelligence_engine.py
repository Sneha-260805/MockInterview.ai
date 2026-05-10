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
    current_topic = current_question.get("topic", "")
    current_diff = current_question.get("difficulty", "medium")

    # Detect how many times current_topic appeared in history
    topic_count = sum(1 for h in session_history if h.get("question", {}).get("topic") == current_topic)

    # ── Determine decision type ────────────────────────────────────────────────
    audio_conf = int(audio_score.get("confidence_score", 100)) if audio_score else 100
    audio_clarity = int(audio_score.get("communication_clarity_score", 100)) if audio_score else 100
    video_engagement = int(video_score.get("engagement_score", 100)) if video_score else 100
    visual_stress = (video_score or {}).get("stress_indicator") or (video_score or {}).get("stress_nervousness_indicator")
    combined_score = int(multimodal_score.get("combined_score", tech_score)) if multimodal_score else tech_score
    risk_flags = candidate_state.risk_flags
    has_confidence_flag = (
        any("Low vocal confidence" in f for f in risk_flags)
        or audio_conf < 50
        or audio_clarity < 45
        or video_engagement < 45
        or visual_stress == "high"
    )
    has_repeated_weakness = any("Repeated weakness" in f and current_topic in f for f in risk_flags)

    # Check for persistent domain weakness via domain_performance history
    domain_perf = getattr(candidate_state, "domain_performance", {}) or {}
    topic_history = domain_perf.get(current_topic, [])
    persistent_weak = len(topic_history) >= 2 and (sum(topic_history[-2:]) / 2) < 50

    if has_repeated_weakness or persistent_weak:
        decision_type = "remediation"
        detail = (
            f"last two scores avg {round(sum(topic_history[-2:])/max(len(topic_history[-2:]),1))}/100"
            if topic_history else
            "repeated weakness flag present"
        )
        detected_issue = (
            f"'{current_topic}' has been flagged as weak more than once ({detail}). "
            "The candidate needs reinforcement on fundamentals before advancing."
        )
    elif has_confidence_flag:
        decision_type = "confidence_recovery"
        detected_issue = (
            "Low vocal confidence detected via audio analysis. "
            "Easing to a more accessible question to rebuild momentum."
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
    elif 60 <= tech_score < 80 and len(missing) <= 1:
        decision_type = "deeper_follow_up"
        detected_issue = (
            f"Good performance ({tech_score}/100) with minor gaps on '{current_topic}'. "
            "A follow-up can probe the remaining depth."
        )
    elif 50 <= tech_score < 60:
        decision_type = "deeper_follow_up"
        detected_issue = (
            f"Partial understanding of '{current_topic}' ({tech_score}/100). "
            "Testing a related area at the same difficulty."
        )
    else:
        decision_type = "strengthen_fundamentals"
        detected_issue = (
            f"Answer on '{current_topic}' showed significant gaps ({tech_score}/100): "
            + (f"missing {', '.join(missing[:2])}" if missing else "unclear fundamentals")
            + ". Returning to foundational concepts."
        )

    # ── Determine next topic ───────────────────────────────────────────────────
    covered_topics = {h.get("question", {}).get("topic", "") for h in session_history}
    covered_topics.add(current_topic)

    # Use interview plan as the preferred order
    plan_topics_in_order = [item.topic for item in interview_plan]

    next_planned = next(
        (t for t in plan_topics_in_order if t not in covered_topics),
        None,
    )

    # Fallback: use weakest untested topic from mastery map
    if not next_planned:
        mastery = candidate_state.skill_mastery
        untested = {t: v for t, v in mastery.items() if t not in covered_topics}
        if untested:
            next_planned = min(untested, key=lambda t: untested[t])

    if not next_planned:
        # All topics covered — synthesis question
        decision_type = "final_synthesis"
        detected_issue = "All planned topics have been covered."
        next_planned = current_topic

    # ── Determine next difficulty ──────────────────────────────────────────────
    if decision_type == "increase_difficulty":
        diff_map = {"easy": "medium", "medium": "hard", "hard": "hard"}
        next_diff = diff_map.get(current_diff, "medium")
    elif decision_type in ("strengthen_fundamentals", "confidence_recovery", "remediation"):
        diff_map = {"hard": "medium", "medium": "easy", "easy": "easy"}
        next_diff = diff_map.get(current_diff, "easy")
    elif decision_type == "domain_pivot":
        next_diff = "medium"   # reset difficulty on topic pivot
    else:
        next_diff = current_diff  # keep same difficulty for follow-up

    # ── Build human-readable reason ────────────────────────────────────────────
    reason_templates = {
        "aggressive_escalation": (
            f"Impressive — {tech_score}/100 with strong depth on '{current_topic}'. "
            f"Jumping straight to '{next_planned}' at hard difficulty to find your ceiling."
        ),
        "increase_difficulty": (
            f"You scored {tech_score}/100 on '{current_topic}' — excellent. "
            f"Moving to '{next_planned}' at {next_diff} difficulty to continue stretching your knowledge."
        ),
        "deeper_follow_up": (
            f"Good understanding of '{current_topic}' ({tech_score}/100). "
            f"Exploring '{next_planned}' to check related depth across the {candidate_state.selected_role} skill set."
        ),
        "strengthen_fundamentals": (
            f"The answer on '{current_topic}' ({tech_score}/100) had gaps in key concepts. "
            f"Stepping back to '{next_planned}' at {next_diff} difficulty to check the foundation."
        ),
        "confidence_recovery": (
            f"Sensing some uncertainty — switching to a more structured question on '{next_planned}' "
            "to help you build momentum and demonstrate what you know."
        ),
        "remediation": (
            f"'{current_topic}' has appeared weak more than once. "
            f"Probing '{next_planned}' to check if this is a systematic gap or a specific knowledge hole."
        ),
        "domain_pivot": (
            f"Shifting focus from '{current_topic}' to '{next_planned}' at medium difficulty. "
            "Seeing your performance across different domains gives a more complete picture."
        ),
        "final_synthesis": (
            f"You've covered all the planned areas for {candidate_state.selected_role}. "
            "This final question asks you to synthesise your experience at a high level."
        ),
    }
    reason = reason_templates.get(decision_type, f"Moving to '{next_planned}'.")

    # ── Evidence bullets ───────────────────────────────────────────────────────
    evidence: list[str] = []
    evidence.append(f"Technical score on Q: {tech_score}/100")
    evidence.append(f"Depth score: {depth_score}/100")
    if audio_score:
        evidence.append(f"Audio confidence: {audio_conf}/100; clarity: {audio_clarity}/100")
    if video_score:
        stress_label = visual_stress or "not flagged"
        evidence.append(f"Video engagement: {video_engagement}/100; stress proxy: {stress_label}")
    if multimodal_score:
        evidence.append(f"Combined multimodal score: {combined_score}/100")
    if covered:
        evidence.append(f"Covered: {', '.join(covered[:2])}")
    if missing:
        evidence.append(f"Missing: {', '.join(missing[:2])}")
    if candidate_state.confidence_trend != "unknown":
        evidence.append(f"Confidence trend: {candidate_state.confidence_trend}")
    mastery_val = candidate_state.skill_mastery.get(next_planned)
    if mastery_val is not None:
        evidence.append(f"Prior mastery estimate for '{next_planned}': {mastery_val}/100")
    # Include rubric improvement hint if available
    improvement_hint = last_evaluation.get("improvement_hint", "")
    if improvement_hint:
        evidence.append(f"Coaching hint: {improvement_hint[:80]}")

    return AgentDecisionTrace(
        decision_type=decision_type,
        previous_topic=current_topic,
        previous_score=tech_score,
        detected_issue=detected_issue,
        next_topic=next_planned,
        next_difficulty=next_diff,
        reason_for_adaptation=reason,
        evidence=evidence,
    )
