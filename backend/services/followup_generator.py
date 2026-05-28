"""
Template-based contextual follow-up generator.

Scans a candidate's answer for specific technologies, patterns, or concepts
and returns a targeted follow-up question — no LLM required.

Public API:
  generate_followup(answer, current_topic, resume_techs) → (question, reason, points) | None
"""

import re
from typing import List, Optional, Tuple

FollowupResult = Tuple[str, str, List[str]]  # (question, reason, expected_points)

# ── Technology-specific follow-up templates ────────────────────────────────────
# (regex_pattern_to_match_in_answer, follow_up_question, expected_points_list)
# Ordered: more specific patterns come first.

_TECH_FOLLOWUPS: List[Tuple[str, str, List[str]]] = [
    # ── State Management ──────────────────────────────────────────────────────
    (
        r"\bredux toolkit\b",
        "You specifically mentioned Redux Toolkit — why did you choose it over plain Redux or the Context API, and did you use RTK Query for data fetching?",
        [
            "Bundle size and boilerplate reduction with RTK",
            "Built-in Immer for immutable updates",
            "RTK Query for server state vs client state distinction",
            "When Context API would have been sufficient",
        ],
    ),
    (
        r"\bredux\b(?![\s-]toolkit)",
        "You used Redux — what was the key driver for global state management over React's built-in options, and how did you structure your slices?",
        [
            "Cross-component state that local state can't handle",
            "Redux DevTools for time-travel debugging",
            "Middleware (thunk/saga) for async action handling",
            "When Redux becomes over-engineering vs. when it's justified",
        ],
    ),
    (
        r"\bcontext api\b|\breact context\b",
        "You used the Context API — how did you prevent unnecessary re-renders from context value changes in larger component trees?",
        [
            "Splitting contexts by update frequency",
            "useReducer + context as a lightweight state solution",
            "React.memo to prevent child re-renders",
            "Limitations that would push you to Redux or Zustand",
        ],
    ),
    (
        r"\bzustand\b",
        "You chose Zustand — what made it a better fit than Redux or Context for your specific use case?",
        [
            "No provider wrapper — simpler setup",
            "Slice-based organization without actions boilerplate",
            "Shallow equality subscriptions for performance",
            "Comparison with Jotai or Recoil",
        ],
    ),
    # ── Auth ──────────────────────────────────────────────────────────────────
    (
        r"\bjwt\b",
        "You used JWT — since JWTs are stateless and can't be revoked server-side before expiry, how did you handle secure logout or compromised-token scenarios?",
        [
            "Short-lived access tokens (15 min) with refresh token rotation",
            "Token blocklist in Redis for immediate revocation",
            "HttpOnly cookie storage vs localStorage risks",
            "Absolute vs sliding expiration trade-offs",
        ],
    ),
    (
        r"\brefresh token\b",
        "You mentioned refresh tokens — walk me through your rotation strategy and how you detect and respond to token reuse attacks.",
        [
            "Rotate on every refresh call (one-time use)",
            "Token family tracking to detect reuse",
            "Revoke entire family on suspicious reuse detection",
            "HttpOnly Secure cookie to prevent JS access",
        ],
    ),
    (
        r"\boauth\b",
        "You mentioned OAuth — walk me through the authorization code flow with PKCE and why it's more secure than the implicit flow.",
        [
            "Authorization code via redirect URL (not directly exposed)",
            "Code-for-token exchange on server side prevents exposure",
            "PKCE code verifier/challenge for public clients",
            "Implicit flow's token exposure vulnerability in URL fragment",
        ],
    ),
    # ── Data Pipeline ─────────────────────────────────────────────────────────
    (
        r"\bairflow\b",
        "You used Airflow — how did you handle task failures mid-DAG, and what happened to downstream tasks when an upstream task failed?",
        [
            "Retry policies (retries, retry_delay, retry_exponential_backoff)",
            "on_failure_callback for alerting",
            "DAG trigger rules (all_success vs one_failed)",
            "Dead-letter handling and manual task clearing",
        ],
    ),
    (
        r"\bkafka\b",
        "You mentioned Kafka — how did you monitor consumer lag, and what was your strategy when lag spiked unexpectedly?",
        [
            "Consumer group offset monitoring via Kafka UI or JMX",
            "Lag alerting thresholds and SLO definition",
            "Partition rebalancing and its impact on processing",
            "Increasing consumer parallelism vs reprocessing strategy",
        ],
    ),
    (
        r"\bspark\b",
        "You used Spark — when you hit data skew in a join or aggregation, what partitioning techniques did you apply to rebalance the load?",
        [
            "Salting skewed keys to spread across partitions",
            "Broadcast join for small lookup tables (< 10 MB)",
            "repartition() vs coalesce() and their shuffle cost",
            "Spark UI stage analysis to pinpoint skewed partitions",
        ],
    ),
    (
        r"\bdbt\b",
        "You used dbt — how did you structure your model layers (staging, intermediate, mart), and what testing strategy did you apply to catch data quality issues?",
        [
            "Layered model architecture: staging → intermediate → mart",
            "dbt test types: unique, not_null, accepted_values, relationships",
            "Custom generic tests for business logic",
            "CI integration for test gates before merge",
        ],
    ),
    # ── Caching ───────────────────────────────────────────────────────────────
    (
        r"\bredis\b",
        "You used Redis — beyond simple caching, how did you handle cache invalidation to prevent stale reads, and did you use any of Redis's data structures beyond strings?",
        [
            "TTL vs event-driven invalidation strategies",
            "Cache-aside vs write-through vs write-behind patterns",
            "Redis Sorted Sets for leaderboards, Pub/Sub for real-time",
            "Redis cluster mode and consistency considerations",
        ],
    ),
    # ── DevOps ────────────────────────────────────────────────────────────────
    (
        r"\bhelm\b",
        "You used Helm — how did you manage environment-specific configurations across dev, staging, and production without duplicating chart logic?",
        [
            "Separate values.yaml files per environment",
            "Helm --set or --values overrides in CI pipeline",
            "Sealed Secrets or External Secrets Operator for sensitive values",
            "Chart versioning and upgrade rollback strategy",
        ],
    ),
    (
        r"\bterraform\b",
        "You used Terraform — how did you manage remote state and prevent state conflicts when multiple engineers ran plans concurrently?",
        [
            "Remote state backend (S3 + DynamoDB lock or Terraform Cloud)",
            "State locking to prevent concurrent modifications",
            "Workspace or directory isolation per environment",
            "Terraform import for brownfield resources",
        ],
    ),
    (
        r"\bkubernetes\b|\bk8s\b",
        "You used Kubernetes — how did you configure pod resource requests and limits, and what was the eviction behavior when a node ran low on memory?",
        [
            "requests vs limits: scheduling vs throttle/kill",
            "QoS classes: Guaranteed, Burstable, BestEffort — eviction order",
            "VPA vs HPA for right-sizing resources",
            "ResourceQuota at namespace level",
        ],
    ),
    (
        r"\bdocker\b",
        "You used Docker — how did you structure your Dockerfiles to minimize image size and maximize layer cache efficiency?",
        [
            "Multi-stage builds to separate build from runtime",
            "Ordering COPY/RUN to maximize cache reuse",
            "Using alpine or distroless base images",
            ".dockerignore to exclude unnecessary files",
        ],
    ),
    # ── Frontend ──────────────────────────────────────────────────────────────
    (
        r"\busecallback\b|\busememo\b",
        "You mentioned useCallback/useMemo — how do you decide when memoisation actually helps performance versus when it adds overhead without measurable benefit?",
        [
            "Profile with React DevTools Profiler before memoising",
            "useCallback only helps when passed to React.memo or useEffect deps",
            "useMemo for expensive computations — not just referential equality",
            "Over-memoisation can actually slow renders due to comparison cost",
        ],
    ),
    (
        r"\bserver.?side render|ssr\b|\bnext\.js\b",
        "You mentioned SSR or Next.js — what specific problems did it solve, and what new challenges did it introduce compared to a pure CSR approach?",
        [
            "SEO and time-to-first-byte improvements",
            "Hydration mismatch errors and how to debug them",
            "Server load vs CDN-cached static pages",
            "Data fetching strategy: getServerSideProps vs getStaticProps",
        ],
    ),
    (
        r"\breact query\b|\btanstack query\b",
        "You used React Query / TanStack Query — how did you handle cache synchronisation between optimistic updates and the server response?",
        [
            "onMutate → save snapshot, onError → rollback, onSettled → invalidate",
            "Cache time vs stale time configuration",
            "Query key structure for granular invalidation",
            "Conflict between optimistic state and stale server response",
        ],
    ),
    # ── ML ─────────────────────────────────────────────────────────────────────
    (
        r"\bfine.?tun",
        "You mentioned fine-tuning — how did you prevent catastrophic forgetting of the pre-trained model's general knowledge during domain adaptation?",
        [
            "Low learning rate (1e-5 to 5e-5) to make small updates",
            "LoRA / PEFT to freeze most parameters and train adapters only",
            "Rehearsal: mixing original training data into fine-tuning batches",
            "Evaluating on general benchmarks alongside domain tasks",
        ],
    ),
    (
        r"\bsmote\b",
        "You used SMOTE — how did you ensure the synthetic samples didn't leak into your test set and didn't introduce distribution artifacts?",
        [
            "Apply SMOTE only after train/test split — never on combined data",
            "Stratified k-fold to preserve class balance in every fold",
            "Monitoring decision boundary shift with PR-AUC vs ROC-AUC",
            "Comparing performance vs simple class-weight adjustment",
        ],
    ),
    (
        r"\bmlflow\b",
        "You used MLflow — how did you manage model registry transitions from staging to production, and what automated gates did you enforce?",
        [
            "Model registry stages: Staging → Production with manual approval",
            "Automated metric gates (min accuracy / AUC before promotion)",
            "Shadow mode deployment before full cutover",
            "Rollback strategy when production degradation is detected",
        ],
    ),
    (
        r"\blangchain\b",
        "You used LangChain — how did you handle prompt injection risks and ensure the LLM outputs were reliable enough for downstream processing?",
        [
            "Input sanitisation and output parsing with structured schemas",
            "Output parsers with retry logic for malformed responses",
            "Guardrails or content moderation layers",
            "Evaluation suite to track prompt regressions",
        ],
    ),
    # ── Async / Concurrency ───────────────────────────────────────────────────
    (
        r"\bcelery\b",
        "You used Celery — how did you monitor task queue health and catch tasks that silently failed without triggering retries?",
        [
            "Flower or Celery Insights for queue depth monitoring",
            "Task failure callbacks (on_failure) for alerting",
            "Result backend for task status persistence",
            "max_retries with exponential backoff and dead-letter handling",
        ],
    ),
    (
        r"\bwebsocket\b",
        "You used WebSockets — how did you handle connection drops and guarantee message delivery during reconnection periods?",
        [
            "Exponential backoff reconnection with jitter",
            "Message sequence numbers for ordering and deduplication",
            "Server-side buffer or message queue during disconnect window",
            "Heartbeat ping/pong to detect stale connections",
        ],
    ),
    # ── Architecture patterns ─────────────────────────────────────────────────
    (
        r"\bmicroservice",
        "You mentioned microservices — how did you handle distributed transaction consistency when a failure occurs mid-operation spanning multiple services?",
        [
            "Saga pattern with compensating transactions",
            "Outbox pattern for reliable event publishing",
            "Eventual consistency vs strong consistency trade-off",
            "Idempotency keys on consumers to handle duplicate events",
        ],
    ),
    (
        r"\bcircuit breaker\b",
        "You used the circuit breaker pattern — what were your open/closed/half-open state thresholds, and how did you test the transitions in staging?",
        [
            "Error rate threshold for opening the circuit",
            "Half-open state with probe requests before closing",
            "Timeout configuration per dependency",
            "Chaos engineering / fault injection to verify transitions",
        ],
    ),
    (
        r"\bstrangler\b|\bstrangler fig\b",
        "You used the strangler fig pattern — how did you decide where to draw the first service boundary, and how did you handle the shared database during migration?",
        [
            "Identifying high-churn or highest-value domains first",
            "Anti-corruption layer to translate between old and new models",
            "Shared database decomposition: separate schema first, then DB",
            "API gateway routing between old and new services",
        ],
    ),
]


# ── Concept-level follow-up templates ─────────────────────────────────────────
# Triggered on broader concepts rather than specific tech names.

_CONCEPT_FOLLOWUPS: List[Tuple[str, str, List[str]]] = [
    (
        r"\bn\+1\b|n plus 1|n \+ 1",
        "You mentioned the N+1 problem — walk me through exactly how you detected it in your environment and which solution you settled on.",
        [
            "Query logging to count DB round-trips per request",
            "ORM eager loading (select_related / prefetch_related)",
            "DataLoader batching pattern for GraphQL or async contexts",
            "Monitoring APM traces to catch regressions",
        ],
    ),
    (
        r"\bcache invalidation\b|\bcache stampede\b",
        "You touched on cache invalidation — how did you prevent a cache stampede when a popular key expired and many requests hit the origin simultaneously?",
        [
            "Probabilistic early expiration to stagger cache misses",
            "Lock-based single-repopulation (only one request fills cache)",
            "Background refresh before TTL expires",
            "Circuit breaker fallback to stale value during origin overload",
        ],
    ),
    (
        r"\brate limit",
        "You mentioned rate limiting — how did you implement it in a distributed way so limits apply consistently across multiple API server instances?",
        [
            "Sliding window with Redis atomic INCR + EXPIRE",
            "Token bucket with Redis stored state",
            "Per-user vs per-IP vs global limits",
            "Returning 429 with Retry-After header",
        ],
    ),
    (
        r"\bload balanc",
        "You mentioned load balancing — how did you handle session affinity when your application maintained stateful WebSocket or server-sent event connections?",
        [
            "Sticky sessions via consistent hashing on client ID",
            "Moving all state to shared Redis to make servers stateless",
            "Connection draining before removing a node from rotation",
            "L4 vs L7 load balancing trade-offs",
        ],
    ),
    (
        r"\bindex(?:ing|es)?\b",
        "You mentioned indexes — how do you decide which columns to index, and what write-path trade-offs do you accept when adding a new index?",
        [
            "Query pattern analysis before creating indexes",
            "Cardinality: high-cardinality columns benefit most from B-tree indexes",
            "Write overhead: every INSERT/UPDATE must update all indexes",
            "Covering indexes to avoid table heap lookups",
        ],
    ),
    (
        r"\bsharding\b|\bdata partition",
        "You mentioned sharding — how did you choose the shard key, and how did you mitigate hot spots when certain keys received disproportionate traffic?",
        [
            "Cardinality and uniform distribution of the shard key",
            "Salting or compound shard keys to spread hot data",
            "Cross-shard query limitations and aggregation strategies",
            "Re-sharding plan as data volume grows",
        ],
    ),
    (
        r"\bevent.?driven\b|\bevent sourcing\b",
        "You mentioned event-driven architecture — how did you handle event ordering and ensure consumers processed events exactly once?",
        [
            "Partition keys to guarantee per-entity ordering",
            "Idempotency keys on consumer side",
            "Exactly-once vs at-least-once semantics trade-offs",
            "Event schema versioning for backward compatibility",
        ],
    ),
    (
        r"\boptimistic.?update\b|\boptimistic.?ui\b",
        "You mentioned optimistic updates — what was your rollback strategy when the server returned an error after the UI had already applied the change?",
        [
            "Save pre-mutation snapshot before applying optimistic state",
            "onError callback to restore previous state",
            "User notification that the operation failed",
            "Conflict resolution when server state diverged from optimistic state",
        ],
    ),
]


# ── Vague-claim follow-ups (light answers that need probing) ─────────────────

_VAGUE_CLAIM_FOLLOWUPS: List[Tuple[str, str, List[str]]] = [
    (
        r"\b(?:worked on|implemented|handled|built|used|did)\s+(?:auth(?:entication)?|login|sign[\s-]?in)\b|\bauthentication\b",
        "What authentication method did you use, and how did you protect routes or APIs from unauthorized access?",
        [
            "JWT/session/OAuth choice and trade-offs",
            "Authorization vs authentication separation",
            "Route or API protection strategy",
            "Token validation and security hardening",
        ],
    ),
    (
        r"\bbuilt (?:the )?backend\b|\bbackend apis?\b|\bbuilt apis?\b|\bdesigned apis?\b",
        "Can you walk me through one API you designed, including request validation, error handling, and database interaction?",
        [
            "API design and resource modelling",
            "Request validation approach",
            "Consistent error handling",
            "Database interaction and query patterns",
        ],
    ),
    (
        r"\b(?:built|developed|worked on|shipped)\s+(?:a |an |the )?(?:project|app|application|platform|system)\b",
        "Can you walk me through the architecture of that project — what were the main components, and what was the hardest technical decision you made?",
        [
            "System architecture and component boundaries",
            "Key technology choices with rationale",
            "Hardest technical decision or trade-off",
            "Personal contribution vs team responsibilities",
        ],
    ),
]


def _normalize_topic_label(topic: str) -> str:
    if topic.startswith("Follow-Up:"):
        return topic.split(":", 1)[1].strip()
    return topic.strip()


def _remediation_followup(
    missing_concepts: List[str],
    current_topic: str,
) -> Optional[FollowupResult]:
    """
    Build a deliberately simpler, foundational follow-up for remediation
    and strengthen_fundamentals decisions.

    This is intentionally easier than _missing_concept_followup — it asks
    the candidate to define and give a basic example rather than handle a
    production scenario.  Used when the agent detects the candidate's
    understanding is weak and needs to probe fundamentals before advancing.

    Example: if a candidate fumbles XGBoost vs Random Forest, BAD would be
    asking about quantization/pruning — GOOD is "explain the main training
    difference between Random Forest and XGBoost in your own words."
    """
    if not missing_concepts:
        return None
    concept = missing_concepts[0]
    topic_label = _normalize_topic_label(current_topic) or "this topic"
    question = (
        f"Let's step back to basics on {topic_label}. "
        f"In your own words, can you explain what '{concept}' means "
        f"and give me a simple, concrete example of it?"
    )
    reason = (
        f"Returning to fundamentals on '{concept}' to build conceptual "
        "understanding before progressing to harder material."
    )
    points = [
        f"Clear definition of {concept}",
        "Simple concrete example or analogy",
        "Basic use case or when you would apply it",
    ] + [c for c in missing_concepts[1:3] if c != concept]
    return question, reason, points[:5]


def _missing_concept_followup(
    missing_concepts: List[str],
    current_topic: str,
    answer: str,
) -> Optional[FollowupResult]:
    """Build a gap-targeted follow-up when rubric concepts were missed."""
    if not missing_concepts:
        return None
    concept = missing_concepts[0]
    topic_label = _normalize_topic_label(current_topic) or "this topic"
    question = (
        f"On {topic_label}, your answer didn't fully address '{concept}'. "
        f"Can you explain how you would handle {concept} in a real production scenario?"
    )
    reason = (
        f"Prior answer on '{topic_label}' missed '{concept}' — "
        "staying on topic to close the implementation gap."
    )
    points = missing_concepts[:4] + [
        "Concrete production example",
        "Trade-offs considered",
    ]
    return question, reason, points[:5]


def _resume_tech_followup(tech: str) -> FollowupResult:
    return (
        f"You mentioned {tech}, which is also listed on your resume. "
        f"Can you walk me through a specific production challenge you encountered with {tech} "
        f"and exactly how you diagnosed and resolved it?",
        f"You referenced {tech} from your background — probing depth of real-world implementation.",
        [
            f"Describe a concrete, specific problem encountered with {tech}",
            "Explain your debugging or diagnosis process step by step",
            "Share the solution and any trade-offs you accepted",
            "Reflect on what you'd design differently with hindsight",
        ],
    )


def _find_resume_mentions(answer: str, resume_techs: List[str]) -> List[str]:
    """Return resume technologies explicitly mentioned in the answer (longest match first)."""
    al = answer.lower()
    hits = []
    for tech in resume_techs:
        if len(tech) >= 3:
            pattern = r"\b" + re.escape(tech.lower()) + r"\b"
            if re.search(pattern, al):
                hits.append(tech)
    # Longest match first to prefer "Redux Toolkit" over "Redux"
    return sorted(hits, key=len, reverse=True)[:2]


# ── Public API ────────────────────────────────────────────────────────────────

def generate_followup(
    answer: str,
    current_topic: str = "",
    resume_techs: Optional[List[str]] = None,
    *,
    missing_concepts: Optional[List[str]] = None,
    covered_concepts: Optional[List[str]] = None,
    previous_question: str = "",
    selected_role: str = "",
    decision_type: str = "",
    decision_reason: str = "",
) -> Optional[FollowupResult]:
    """
    Scan the candidate's answer for specific technologies or concepts.
    Return a targeted (question, reason, expected_points) tuple, or None.

    Priority:
      1. Specific tech pattern  (Redux Toolkit, Airflow, Redis, etc.)
      2. Vague claim pattern    (authentication, backend APIs, project ownership)
      3. Concept pattern        (N+1, cache stampede, etc.)
      4. Resume-tech mention    (generic "you mentioned X from your resume")
      5. Missing rubric concept (when decision context requests gap closure)
    """
    if not answer or not answer.strip():
        return None

    al = answer.lower()

    # ── Remediation / strengthen_fundamentals: bypass deep-tech probes ────────
    # When the agent decides the candidate needs foundational help, do NOT scan
    # the answer for technology patterns — those templates ask harder follow-ups
    # (e.g., JWT revocation strategy, Kafka lag monitoring).  Instead generate a
    # deliberately simpler question that targets the missed concept.
    #
    # BAD:  candidate fumbles XGBoost → system sees "model" in answer → asks
    #       about quantization or pruning (harder, different sub-topic).
    # GOOD: step back, ask "explain the main training difference between Random
    #       Forest and XGBoost in your own words."
    if decision_type in ("remediation", "strengthen_fundamentals"):
        if missing_concepts:
            return _remediation_followup(missing_concepts, current_topic)
        # No missing concepts — let question_generator handle it via the normal path
        return None

    for pattern, question, points in _TECH_FOLLOWUPS:
        m = re.search(pattern, al)
        if m:
            matched_term = m.group(0).strip()
            reason = (
                f"You specifically mentioned {matched_term} in your answer. "
                "Probing deeper into that implementation and the design decisions behind it."
            )
            if decision_reason:
                reason = f"{reason} Agent decision: {decision_reason[:120]}"
            return question, reason, points

    for pattern, question, points in _VAGUE_CLAIM_FOLLOWUPS:
        if re.search(pattern, al):
            reason = (
                "Your answer referenced this area at a high level. "
                "Probing for concrete implementation and ownership detail."
            )
            if decision_type == "verify_resume_claim":
                reason = (
                    "Follow-up generated from candidate claim — verifying resume/project "
                    "ownership with a specifics-focused question."
                )
            elif decision_reason:
                reason = f"{reason} {decision_reason[:120]}"
            return question, reason, points

    for pattern, question, points in _CONCEPT_FOLLOWUPS:
        if re.search(pattern, al):
            reason = (
                "Your answer touched on an important engineering pattern. "
                "Exploring the practical implementation details and trade-offs."
            )
            return question, reason, points

    if resume_techs:
        mentioned = _find_resume_mentions(answer, resume_techs)
        if mentioned:
            return _resume_tech_followup(mentioned[0])

    if missing_concepts and decision_type in (
        "deeper_follow_up",
        "ask_deeper_followup",
        "verify_resume_claim",
        "claim_verification",
    ):
        gap_followup = _missing_concept_followup(missing_concepts, current_topic, answer)
        if gap_followup:
            return gap_followup

    return None
