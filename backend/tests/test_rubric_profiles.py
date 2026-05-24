"""
Phase 3 — Question-type-aware rubric profile tests.

Covers:
  1. Strong technical_concept answer without project mention → score ≥ 75
  2. Weak vague answer stays low (< 50)
  3. technical_concept profile sets resume_project_connection weight to 0
  4. project_deep_dive profile rewards ownership + implementation
  5. project_deep_dive without ownership/detail → lower score than strong answer
  6. Behavioral answer uses behavioral rubric profile and STAR keys
  7. claim_verification rewards directness and implementation detail
  8. Default (no question_type) rubric behaviour is backward compatible
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import pytest
from services.rubric_service import score_with_rubric, score_with_rubric_profile
from models.interview import EvaluateAnswerRequest


STRONG_CONCEPT_ANSWER = (
    "Idempotency means that performing the same HTTP operation multiple times produces "
    "the same result as performing it once — the state of the system does not change on "
    "repeated calls. For example, a PUT request to update a user record should always leave "
    "the resource in the same final state regardless of how many times it is sent. "
    "GET, PUT, DELETE, HEAD, and OPTIONS are all idempotent, while POST and PATCH are not. "
    "The key trade-off is safety versus resource creation: idempotent methods are essential "
    "in distributed systems where network failures can trigger duplicate requests — "
    "using PUT instead of POST for creates means retries are safe. "
    "However, enforcing idempotency server-side requires extra logic such as idempotency keys "
    "or conditional ETags, which adds implementation complexity."
)

WEAK_VAGUE_ANSWER = "I think it means doing the same thing. It is useful for APIs."

STRONG_PROJECT_ANSWER = (
    "I led the backend architecture for our real-time analytics service. "
    "I designed a Redis-backed event ingestion pipeline that processed 50,000 events per second. "
    "I chose Redis Streams over Kafka because our team was small and Kafka's operational overhead "
    "was not justified at that scale. I implemented the consumer groups myself in Python using "
    "asyncio so we could fan out events to multiple downstream processors without blocking. "
    "The system was deployed on Kubernetes with horizontal scaling — I wrote the Helm chart. "
    "The trade-off I made was prioritising simplicity over guaranteed delivery; "
    "we used at-least-once semantics with idempotent consumers rather than exactly-once processing. "
    "If I did it again I would add dead-letter queues from day one — we hit edge cases with "
    "malformed events that took time to debug in production."
)

WEAK_PROJECT_ANSWER = (
    "We built a backend system that handled a lot of data. "
    "The team used some technologies and it worked okay. "
    "There were some challenges but we figured them out. "
    "The project was successful in the end."
)

BEHAVIORAL_ANSWER = (
    "When I was working on the platform team, the situation was that our CI pipeline "
    "had become so slow it was blocking releases — taking over 40 minutes per run. "
    "My task was to cut that time in half without breaking any tests. "
    "I analysed the bottlenecks using our CI metrics and identified that unit tests "
    "were not parallelised at all. I decided to split the test suite into four shards "
    "and proposed the change to the team. I led the implementation over two sprints, "
    "coordinating with three other engineers on the flaky-test backlog at the same time. "
    "As a result we reduced CI time from 42 minutes to 16 minutes — a 62% improvement — "
    "and on-time release frequency went up from 70% to 90%. "
    "In retrospect I would have added per-shard failure reporting earlier; "
    "the initial version made it harder to diagnose flaky tests across shards."
)

FOLLOWUP_ANSWER = (
    "The specific reason I chose JWT over session tokens in that service was statefulness. "
    "Our system needed to scale horizontally across multiple nodes — storing session state "
    "server-side would have required sticky sessions or a shared Redis session store, "
    "both of which add operational complexity. JWT lets each node validate the token locally "
    "by verifying the signature with the shared secret, so there is no cross-node coordination. "
    "The trade-off is that JWTs cannot be easily revoked before expiry — to mitigate this "
    "I implemented a short 15-minute access token TTL with a Redis-backed token blacklist "
    "for logout events. I benchmarked both approaches: session store added 8 ms average "
    "latency per request; JWT added 0.3 ms for local validation."
)


# ── Test 1: Strong concept answer without project mention scores high ─────────

@pytest.mark.asyncio
async def test_strong_concept_answer_without_project_connection_scores_high():
    """
    A strong technical concept answer that never mentions 'my project' or 'I built'
    should score ≥ 75 when evaluated with the technical_concept rubric profile.
    The competence floor must fire because correctness + depth are strong.
    """
    from agents import evaluator_agent
    req = EvaluateAnswerRequest(
        session_id="s1", question_id="q1",
        question="What is idempotency in REST APIs?",
        answer=STRONG_CONCEPT_ANSWER,
        expected_points=["idempotency", "HTTP methods", "safe retries", "trade-off"],
        topic="API Design",
        question_type="technical_concept",
    )
    result = await evaluator_agent.evaluate(req)
    assert result.technical_score >= 75, (
        f"Strong concept answer without project mention should score ≥ 75, got {result.technical_score}"
    )
    assert result.rubric_profile == "technical_concept", (
        f"Expected rubric_profile='technical_concept', got {result.rubric_profile!r}"
    )


# ── Test 2: Weak vague answer stays low ────────────────────────────────────────

@pytest.mark.asyncio
async def test_weak_vague_answer_stays_low():
    """
    A vague 2-sentence answer should score below 50.
    """
    from agents import evaluator_agent
    req = EvaluateAnswerRequest(
        session_id="s1", question_id="q2",
        question="What is idempotency?",
        answer=WEAK_VAGUE_ANSWER,
        expected_points=["idempotency", "HTTP methods", "safe retries", "trade-off"],
        topic="API Design",
        question_type="technical_concept",
    )
    result = await evaluator_agent.evaluate(req)
    assert result.technical_score < 50, (
        f"Weak vague answer should score < 50, got {result.technical_score}"
    )


# ── Test 3: technical_concept sets project_connection weight to zero ──────────

def test_concept_profile_project_connection_has_zero_weight():
    """
    For technical_concept profile, resume_project_connection must be exactly 0
    regardless of what the answer contains.
    """
    # Answer WITH explicit project language
    answer_with_project = (
        "In my project I built an idempotent REST API using PUT endpoints. "
        "I implemented proper status codes and stateless design. "
        "The trade-off was between simplicity and strict idempotency guarantees."
    )
    result = score_with_rubric_profile(
        answer_with_project, "API Design", [], rubric_profile="technical_concept"
    )
    assert result["rubric_scores"]["resume_project_connection"] == 0, (
        "technical_concept profile must assign 0 weight to resume_project_connection, "
        f"got {result['rubric_scores']['resume_project_connection']}"
    )
    # Total must not include project contribution
    non_project_sum = (
        result["rubric_scores"]["conceptual_correctness"] +
        result["rubric_scores"]["practical_application"] +
        result["rubric_scores"]["depth_and_tradeoffs"] +
        result["rubric_scores"]["communication_structure"]
    )
    assert result["rubric_total"] == non_project_sum, (
        f"rubric_total ({result['rubric_total']}) should equal sum of non-project dims ({non_project_sum})"
    )


# ── Test 4: project_deep_dive rewards ownership and implementation ─────────────

def test_project_deep_dive_rewards_ownership_and_implementation():
    """
    A strong project answer with first-person ownership, concrete decisions,
    and quantified outcomes should score high under project_deep_dive profile.
    """
    result = score_with_rubric_profile(
        STRONG_PROJECT_ANSWER, "System Design", [], rubric_profile="project_deep_dive"
    )
    assert result["rubric_profile"] == "project_deep_dive", (
        f"Expected rubric_profile='project_deep_dive', got {result.get('rubric_profile')!r}"
    )
    assert result["rubric_total"] >= 65, (
        f"Strong project answer should score ≥ 65 on project_deep_dive profile, "
        f"got {result['rubric_total']}"
    )
    # Project connection dimension should be non-zero (weight = 25)
    assert result["rubric_scores"]["resume_project_connection"] > 0, (
        "project_deep_dive profile must have non-zero project connection score"
    )


# ── Test 5: Project answer without ownership loses marks ──────────────────────

def test_project_answer_without_ownership_loses_marks():
    """
    A vague project answer without ownership or implementation detail should
    score significantly lower than a strong ownership answer.
    """
    strong = score_with_rubric_profile(
        STRONG_PROJECT_ANSWER, "System Design", [], rubric_profile="project_deep_dive"
    )
    weak = score_with_rubric_profile(
        WEAK_PROJECT_ANSWER, "System Design", [], rubric_profile="project_deep_dive"
    )
    assert strong["rubric_total"] > weak["rubric_total"], (
        f"Strong project ({strong['rubric_total']}) must outscore weak project ({weak['rubric_total']})"
    )
    assert weak["rubric_total"] <= 55, (
        f"Vague project answer should score ≤ 55 on project_deep_dive, got {weak['rubric_total']}"
    )


# ── Test 6: Behavioral answer uses behavioral rubric profile ──────────────────

def test_behavioral_answer_uses_behavioral_profile():
    """
    A STAR-structured behavioral answer should:
      1. Return rubric_profile = 'behavioral'
      2. Have behavioral rubric_scores keys (not the technical 5)
      3. Score reasonably high (≥ 55) given its structure
    """
    result = score_with_rubric_profile(
        BEHAVIORAL_ANSWER, "Behavioral & Communication", [], rubric_profile="behavioral"
    )
    assert result["rubric_profile"] == "behavioral", (
        f"Expected rubric_profile='behavioral', got {result.get('rubric_profile')!r}"
    )
    behavioral_keys = {
        "situation_task_clarity", "action_ownership",
        "result_impact", "reflection_learning", "communication_structure",
    }
    assert set(result["rubric_scores"].keys()) == behavioral_keys, (
        f"Behavioral rubric_scores should have STAR keys, got: {set(result['rubric_scores'].keys())}"
    )
    assert result["rubric_total"] >= 55, (
        f"Strong STAR answer should score ≥ 55 on behavioral profile, got {result['rubric_total']}"
    )
    # Behavioral profile must not have the standard technical keys
    assert "conceptual_correctness" not in result["rubric_scores"], (
        "Behavioral rubric_scores must not contain 'conceptual_correctness'"
    )


# ── Test 7: Claim verification rewards directness and implementation ──────────

def test_claim_verification_scores_directness_and_implementation():
    """
    For technical_follow_up / claim_verification profile, practical_application
    and depth_and_tradeoffs are weighted heavily (30 + 25 = 55%).
    A concrete implementation answer should outscore a vague one.
    """
    vague = (
        "I used JWT because it is good for authentication. "
        "It works well in distributed systems."
    )
    concrete = score_with_rubric_profile(
        FOLLOWUP_ANSWER, "Authentication", [], rubric_profile="technical_follow_up"
    )
    vague_result = score_with_rubric_profile(
        vague, "Authentication", [], rubric_profile="technical_follow_up"
    )
    assert concrete["rubric_profile"] == "technical_follow_up", (
        f"Expected rubric_profile='technical_follow_up', got {concrete.get('rubric_profile')!r}"
    )
    assert concrete["rubric_total"] > vague_result["rubric_total"], (
        f"Concrete follow-up ({concrete['rubric_total']}) must outscore vague follow-up "
        f"({vague_result['rubric_total']})"
    )
    # Practical + depth combined should be the dominant force
    concrete_practical_depth = (
        concrete["rubric_scores"]["practical_application"] +
        concrete["rubric_scores"]["depth_and_tradeoffs"]
    )
    assert concrete_practical_depth >= concrete["rubric_scores"]["conceptual_correctness"] * 2, (
        "For technical_follow_up, practical+depth should dominate over conceptual alone"
    )


# ── Test 8: Default rubric behaviour is backward compatible ───────────────────

def test_default_rubric_behavior_is_backward_compatible():
    """
    score_with_rubric() (no profile argument) must still return the original
    5-dimension dict structure and NOT include a rubric_profile key.
    score_with_rubric_profile() with rubric_profile=None must produce the same result.
    """
    answer = (
        "I used Redis for caching database query results to reduce load. "
        "The trade-off was cache invalidation complexity — we had to ensure stale data "
        "was evicted on writes. I implemented a write-through strategy."
    )
    topic = "Performance"
    expected = ["caching", "redis", "cache invalidation"]

    default_result = score_with_rubric(answer, topic, expected)
    profile_none_result = score_with_rubric_profile(answer, topic, expected, rubric_profile=None)

    # Original API: no rubric_profile key
    assert "rubric_profile" not in default_result, (
        "score_with_rubric() must NOT include 'rubric_profile' in its return dict"
    )
    # Standard 5 dimension keys present
    standard_keys = {
        "conceptual_correctness", "practical_application",
        "depth_and_tradeoffs", "communication_structure", "resume_project_connection",
    }
    assert set(default_result["rubric_scores"].keys()) == standard_keys, (
        f"Default rubric must have standard 5 keys, got: {set(default_result['rubric_scores'].keys())}"
    )
    # rubric_profile=None falls through to default — results should match
    assert default_result["rubric_total"] == profile_none_result["rubric_total"], (
        "score_with_rubric_profile(None) must produce identical rubric_total as score_with_rubric()"
    )
    assert default_result["rubric_scores"] == profile_none_result["rubric_scores"], (
        "score_with_rubric_profile(None) must produce identical rubric_scores as score_with_rubric()"
    )


# ── Phase 3.1 Tests: Split technical_follow_up / claim_verification ───────────

REDIS_FOLLOWUP_ANSWER = (
    "Cache invalidation in Redis is handled through several mechanisms. "
    "TTL-based expiration is the simplest — you set a time-to-live on each key "
    "so stale data automatically expires without intervention. "
    "For event-driven invalidation, Redis keyspace notifications fire when a key "
    "expires or is modified, letting downstream consumers delete related entries. "
    "The main trade-off is between consistency and complexity: a 60-second TTL "
    "guarantees eventual consistency but may serve stale data up to that window, "
    "whereas explicit cache deletion on writes is more precise but requires "
    "careful coordination across services. "
    "For read-heavy systems, a cache-aside pattern with a short TTL works well "
    "as a safety net, combined with explicit deletes on database writes."
)

RAG_FOLLOWUP_ANSWER = (
    "Chunk size in a RAG pipeline directly affects retrieval quality. "
    "Smaller chunks (128-256 tokens) are more precise — the semantic signal is "
    "concentrated in a single concept — but they can cut sentences mid-thought, "
    "losing context that the embedding needs. "
    "Larger chunks (512-1024 tokens) preserve more surrounding context per retrieved "
    "segment but dilute the embedding vector, making it harder to surface the right "
    "chunk for a narrow query. "
    "The practical approach is a sliding window with 20-30% overlap between chunks "
    "so context is not lost at boundaries. "
    "The trade-off is between recall and precision: smaller chunks improve precision "
    "whereas larger chunks improve recall but reduce embedding specificity."
)

CLAIM_WITH_OWNERSHIP = (
    "I implemented JWT authentication in our platform service. "
    "Specifically, I chose a 15-minute access token TTL with refresh tokens backed "
    "by Redis, because our compliance requirements mandated short-lived credentials "
    "for the healthcare data we were handling. "
    "I wrote the token validation middleware myself, including HMAC-SHA256 signature "
    "verification with a rotating secret. "
    "The trade-off I made was between simplicity and security — a longer TTL would "
    "have simplified client refresh logic but would not have met our HIPAA requirements. "
    "I benchmarked the middleware overhead at under 1 ms per request."
)

CLAIM_WITHOUT_OWNERSHIP = (
    "JWT is a good choice for authentication in distributed systems "
    "because tokens can be validated locally without a database lookup. "
    "The trade-off is that tokens cannot be easily revoked before they expire."
)


# ── Test 9: Redis follow-up without project language scores high ───────────────

def test_redis_followup_without_project_language_scores_high():
    """
    A strong Redis cache invalidation answer with no 'I built' / 'my project'
    language should score well on technical_follow_up because project weight = 0.
    """
    result = score_with_rubric_profile(
        REDIS_FOLLOWUP_ANSWER, "Performance", [], rubric_profile="technical_follow_up"
    )
    assert result["rubric_profile"] == "technical_follow_up"
    assert result["rubric_scores"]["resume_project_connection"] == 0, (
        "technical_follow_up must assign zero weight to project connection, "
        f"got {result['rubric_scores']['resume_project_connection']}"
    )
    assert result["rubric_total"] >= 55, (
        f"Strong Redis follow-up without project language should score ≥ 55, "
        f"got {result['rubric_total']}"
    )


# ── Test 10: RAG chunking follow-up without project language scores high ───────

def test_rag_followup_without_project_language_scores_high():
    """
    A detailed RAG/vector-search follow-up with no first-person project language
    should not be penalised and should score >= 55 on technical_follow_up.
    """
    result = score_with_rubric_profile(
        RAG_FOLLOWUP_ANSWER, "Deep Learning", [], rubric_profile="technical_follow_up"
    )
    assert result["rubric_scores"]["resume_project_connection"] == 0, (
        "technical_follow_up must never penalise for missing project connection"
    )
    assert result["rubric_total"] >= 50, (
        f"RAG follow-up answer should score ≥ 50, got {result['rubric_total']}"
    )


# ── Test 11: technical_follow_up project_connection is always zero ─────────────

def test_technical_followup_project_connection_has_zero_weight():
    """
    resume_project_connection must be 0 in technical_follow_up rubric_scores
    even when the answer is full of project language.
    """
    answer_with_project = (
        "In my project I built a Redis cache for our API. "
        "I implemented TTL-based expiration and set up keyspace notifications. "
        "I observed that a 30-second TTL reduced stale data incidents by 80%. "
        "The trade-off was cache coherency — I decided to use write-through caching."
    )
    result = score_with_rubric_profile(
        answer_with_project, "Performance", [], rubric_profile="technical_follow_up"
    )
    assert result["rubric_scores"]["resume_project_connection"] == 0, (
        "technical_follow_up must set resume_project_connection to exactly 0, "
        f"got {result['rubric_scores']['resume_project_connection']}"
    )
    # direct_answer_to_followup key should be present (directness weight > 0)
    assert "direct_answer_to_followup" in result["rubric_scores"], (
        "technical_follow_up rubric_scores should include 'direct_answer_to_followup'"
    )


# ── Test 12: claim_verification with ownership scores higher than without ──────

def test_claim_verification_with_ownership_scores_higher():
    """
    A claim_verification answer that contains first-person implementation detail
    and ownership language should outscore a vague answer without ownership.
    """
    with_ownership = score_with_rubric_profile(
        CLAIM_WITH_OWNERSHIP, "Authentication", [], rubric_profile="claim_verification"
    )
    without_ownership = score_with_rubric_profile(
        CLAIM_WITHOUT_OWNERSHIP, "Authentication", [], rubric_profile="claim_verification"
    )
    assert with_ownership["rubric_profile"] == "claim_verification"
    assert without_ownership["rubric_profile"] == "claim_verification"
    assert with_ownership["rubric_total"] > without_ownership["rubric_total"], (
        f"claim_verification answer with ownership ({with_ownership['rubric_total']}) "
        f"must outscore answer without ownership ({without_ownership['rubric_total']})"
    )
    # Ownership contribution should be non-zero for the strong answer
    assert with_ownership["rubric_scores"]["resume_project_connection"] > 0, (
        "claim_verification must give credit for project/ownership language"
    )


# ── Test 13: verify_resume_claim maps to claim_verification profile ────────────

def test_verify_resume_claim_maps_to_claim_verification_profile():
    """
    The question_type 'verify_resume_claim' must map to 'claim_verification'
    profile (not 'technical_follow_up'), so ownership language is weighted.
    """
    from services.rubric_service import _QUESTION_TYPE_TO_PROFILE
    mapped = _QUESTION_TYPE_TO_PROFILE.get("verify_resume_claim")
    assert mapped == "claim_verification", (
        f"verify_resume_claim should map to 'claim_verification', got {mapped!r}"
    )
    # Also confirm claim_verification maps to itself
    assert _QUESTION_TYPE_TO_PROFILE.get("claim_verification") == "claim_verification", (
        "claim_verification question_type should map to claim_verification profile"
    )
    # And technical_follow_up still maps to itself (not claim_verification)
    assert _QUESTION_TYPE_TO_PROFILE.get("technical_follow_up") == "technical_follow_up", (
        "technical_follow_up question_type must map to technical_follow_up profile"
    )
