"""
Phase 11 — Rubric-Based Evaluation Service

Scores answers across 5 weighted dimensions using synonym-aware matching.
Works entirely without LLM — no external dependencies required.

Dimension weights (total 100):
  conceptual_correctness    30  — factual/theoretical accuracy
  practical_application     25  — hands-on, real-world usage
  depth_and_tradeoffs       20  — nuance, trade-offs, alternatives
  communication_structure   15  — clarity, examples, logical flow
  resume_project_connection 10  — connecting answer to own projects/experience
"""

import re
import math
from typing import Dict, List, Tuple

# ── Synonym expansion ─────────────────────────────────────────────────────────
# Groups of interchangeable terms.  Any word in a group can match any other.

_SYNONYM_GROUPS: List[set] = [
    {"authentication", "auth", "login", "jwt", "token", "oauth", "session", "credential"},
    {"authorisation", "authorization", "permission", "rbac", "role", "access control", "privilege"},
    {"database", "db", "sql", "nosql", "mongo", "mongodb", "postgres", "mysql", "sqlite", "storage"},
    {"api", "rest", "endpoint", "route", "http", "request", "response", "interface"},
    {"performance", "speed", "latency", "throughput", "fast", "optimize", "optimise", "cache", "caching"},
    {"error", "exception", "fault", "try", "catch", "handle", "handling", "failure", "fallback"},
    {"security", "secure", "xss", "csrf", "injection", "sanitize", "sanitise", "validate", "validation"},
    {"scale", "scalability", "horizontal", "vertical", "distributed", "load", "traffic"},
    {"test", "testing", "unit test", "integration test", "qa", "assertion", "mock"},
    {"deploy", "deployment", "docker", "container", "kubernetes", "k8s", "ci", "cd", "pipeline"},
    {"index", "indexes", "indices", "indexing", "query performance", "search"},
    {"transaction", "acid", "commit", "rollback", "atomicity", "consistency", "isolation", "durability"},
    {"async", "asynchronous", "concurrency", "concurrent", "parallel", "thread", "coroutine", "await"},
    {"state", "stateful", "stateless", "session state", "redux", "store", "context"},
    {"component", "module", "service", "microservice", "monolith", "function"},
    {"logging", "log", "monitoring", "observability", "trace", "tracing", "metric", "alert"},
    {"pagination", "page", "cursor", "offset", "limit", "scroll", "infinite"},
    {"encryption", "encrypt", "decrypt", "hash", "hashing", "bcrypt", "ssl", "tls", "https"},
    {"webhook", "event", "message", "queue", "kafka", "rabbitmq", "pubsub", "notification"},
    {"memory", "ram", "heap", "garbage collection", "gc", "leak", "allocation"},
    {"machine learning", "ml", "model", "training", "inference", "prediction", "classifier"},
    {"feature", "feature engineering", "preprocessing", "normalisation", "normalisation", "scaling"},
    {"overfitting", "underfitting", "regularisation", "regularization", "dropout", "l1", "l2"},
    {"precision", "recall", "f1", "accuracy", "auc", "roc", "metric", "evaluation metric"},
    {"docker", "container", "image", "dockerfile", "compose", "build"},
    {"kubernetes", "pod", "deployment", "service", "ingress", "namespace", "helm"},
    {"cdn", "edge", "static", "asset", "bundle", "webpack", "vite", "build tool"},
    {"react", "vue", "angular", "jsx", "component", "hook", "props", "state"},
    {"virtual dom", "reconciliation", "diffing", "rendering", "repaint", "reflow"},
]

# Build a quick lookup: term → canonical set index
_TERM_TO_GROUP: Dict[str, int] = {}
for _gidx, _grp in enumerate(_SYNONYM_GROUPS):
    for _term in _grp:
        _TERM_TO_GROUP[_term] = _gidx


def _synonyms_of(term: str) -> set:
    """Return the full synonym group for a term (including itself)."""
    norm = term.lower().strip()
    gidx = _TERM_TO_GROUP.get(norm)
    if gidx is not None:
        return _SYNONYM_GROUPS[gidx]
    return {norm}


def _normalise(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text.lower())


def _extract_terms(phrase: str) -> List[str]:
    STOP = {"a", "an", "the", "and", "or", "of", "in", "to", "for", "with",
            "is", "be", "by", "on", "at", "as", "from", "it", "its", "use",
            "how", "what", "when", "where", "which", "that", "this", "are"}
    words = _normalise(phrase).split()
    return [w for w in words if w not in STOP and len(w) >= 3]


def _answer_contains(answer_lower: str, concept: str) -> bool:
    """
    Return True if the answer contains the concept or any of its synonyms.
    Supports prefix matching for terms ≥ 6 chars (catches plurals, conjugations).
    """
    all_terms = _synonyms_of(concept) | {concept.lower()}
    for term in all_terms:
        if term in answer_lower:
            return True
        terms_words = _extract_terms(term)
        for tw in terms_words:
            if tw in answer_lower:
                return True
            if len(tw) >= 6 and tw[:6] in answer_lower:
                return True
    return False


# ── Phase 3: Rubric profile weights (sum = 100 per profile) ──────────────────
# Each profile redistributes the 5 raw dimension scores by these weights.
# Dimension scores are first normalised to 0-100, then scaled by weight.

_PROFILE_WEIGHTS: Dict[str, Dict[str, int]] = {
    "technical_concept": {
        # Pure concept questions — project connection irrelevant
        "conceptual": 35, "practical": 30, "tradeoffs": 20,
        "communication": 15, "project": 0, "directness": 0,
    },
    "project_deep_dive": {
        # Ownership + implementation matter most
        "conceptual": 20, "practical": 25, "tradeoffs": 20,
        "communication": 10, "project": 25, "directness": 0,
    },
    "technical_follow_up": {
        # Phase 3.1: Technical depth and precision only — NO project ownership required.
        # Normal follow-ups (Redis invalidation, RAG chunking, JWT expiry, SQL debugging)
        # must not be penalised for missing first-person project language.
        "conceptual": 15, "practical": 30, "tradeoffs": 30,
        "communication": 10, "project": 0, "directness": 15,
    },
    "claim_verification": {
        # Phase 3.1: Resume/project ownership checks — rewards first-person detail,
        # ownership language, and concrete implementation specifics.
        "conceptual": 10, "practical": 25, "tradeoffs": 20,
        "communication": 5, "project": 20, "directness": 20,
    },
    # "behavioral" uses entirely different dimensions — handled in _score_behavioral_profile()
}

# Maps question_type field values to rubric profile names.
# Phase 3.1: claim_verification and verify_resume_claim use the stricter
# claim_verification profile (ownership-aware), NOT technical_follow_up.
_QUESTION_TYPE_TO_PROFILE: Dict[str, str] = {
    "technical_concept":   "technical_concept",
    "project_deep_dive":   "project_deep_dive",
    "technical_follow_up": "technical_follow_up",
    "claim_verification":  "claim_verification",   # was "technical_follow_up" in Phase 3
    "behavioral":          "behavioral",
    "behavioral_probe":    "behavioral",
    "verify_resume_claim": "claim_verification",   # was "technical_follow_up" in Phase 3
    "final_synthesis":     "technical_concept",
}

# ── Rubric definitions ────────────────────────────────────────────────────────
# Each rubric has 4 concept lists, one per scorable dimension.
# communication_structure is scored separately from text signals.
# resume_project_connection is scored from first-person language patterns.

_RUBRICS: Dict[str, Dict[str, List[str]]] = {

    # ── Full Stack / REST ─────────────────────────────────────────────────────
    "REST Fundamentals": {
        "conceptual": ["stateless", "http verbs", "resource", "uniform interface", "status code",
                       "idempotent", "hateoas", "cacheable"],
        "practical":  ["get post put delete", "endpoint", "json", "request response",
                       "versioning", "authentication", "error handling"],
        "tradeoffs":  ["rest vs graphql", "rest vs grpc", "versioning trade-off",
                       "stateless limitation", "over-fetching", "under-fetching"],
    },
    "API Design": {
        "conceptual": ["idempotency", "http method", "resource model", "status code",
                       "contract", "openapi", "swagger"],
        "practical":  ["endpoint design", "error response", "pagination", "rate limiting",
                       "versioning", "authentication"],
        "tradeoffs":  ["rest vs graphql", "sync vs async", "backward compatibility",
                       "versioning strategy"],
    },

    # ── Database ──────────────────────────────────────────────────────────────
    "Database Design": {
        "conceptual": ["normalisation", "acid", "index", "schema", "relational", "primary key",
                       "foreign key", "join", "query"],
        "practical":  ["postgres", "mongodb", "sql", "nosql", "migration", "orm",
                       "connection pool"],
        "tradeoffs":  ["sql vs nosql", "index trade-off", "denormalisation", "consistency vs availability",
                       "cap theorem"],
    },
    "Database": {
        "conceptual": ["transaction", "isolation level", "acid", "index", "query plan",
                       "lock", "deadlock"],
        "practical":  ["sql", "query optimisation", "explain", "connection pool",
                       "migration", "backup"],
        "tradeoffs":  ["isolation level trade-off", "index overhead", "read vs write",
                       "sql vs nosql"],
    },

    # ── Authentication / Security ─────────────────────────────────────────────
    "Authentication": {
        "conceptual": ["jwt", "oauth", "token", "session", "stateless auth", "expiry",
                       "refresh token", "signature", "payload"],
        "practical":  ["login", "protected route", "httponly cookie", "token storage",
                       "refresh", "logout"],
        "tradeoffs":  ["jwt vs session", "cookie vs localstorage", "refresh token risk",
                       "stateless vs stateful"],
    },
    "Security": {
        "conceptual": ["xss", "csrf", "sql injection", "cors", "csp", "input validation",
                       "owasp", "sanitisation"],
        "practical":  ["parameterised query", "output encoding", "samesite cookie",
                       "rate limiting", "https", "helmet"],
        "tradeoffs":  ["security vs usability", "allowlist vs denylist",
                       "defence in depth"],
    },

    # ── Performance ───────────────────────────────────────────────────────────
    "Performance Optimization": {
        "conceptual": ["caching", "cdn", "lazy loading", "code splitting", "profiling",
                       "bottleneck", "latency", "throughput"],
        "practical":  ["redis", "browser cache", "bundle size", "webpack", "lighthouse",
                       "devtools", "n+1"],
        "tradeoffs":  ["cache invalidation", "premature optimisation", "caching vs freshness",
                       "monolith vs microservice performance"],
    },
    "Performance": {
        "conceptual": ["caching", "index", "async", "connection pool", "profiling",
                       "bottleneck", "queue"],
        "practical":  ["redis", "query optimisation", "load test", "profiler",
                       "batch processing"],
        "tradeoffs":  ["consistency vs performance", "cache invalidation",
                       "trade-off in index"],
    },

    # ── System Design ─────────────────────────────────────────────────────────
    "System Design": {
        "conceptual": ["scalability", "availability", "consistency", "partition tolerance",
                       "cap theorem", "load balancer", "microservice", "message queue"],
        "practical":  ["horizontal scaling", "cdn", "database sharding", "kafka",
                       "redis", "api gateway"],
        "tradeoffs":  ["cap theorem", "consistency vs availability", "sql vs nosql",
                       "monolith vs microservice", "sync vs async"],
    },

    # ── Frontend ──────────────────────────────────────────────────────────────
    "React Internals": {
        "conceptual": ["virtual dom", "reconciliation", "diffing", "fiber", "hook",
                       "component lifecycle", "state", "props"],
        "practical":  ["usecallback", "usememo", "useeffect", "react.memo",
                       "key prop", "profiler"],
        "tradeoffs":  ["over-memoisation", "context re-render", "pure component trade-off",
                       "hook dependency"],
    },
    "Frontend Architecture": {
        "conceptual": ["component design", "state management", "separation of concerns",
                       "single responsibility", "composition"],
        "practical":  ["redux", "context api", "zustand", "react query",
                       "module federation"],
        "tradeoffs":  ["local vs global state", "over-engineering", "redux vs context",
                       "ssr vs csr"],
    },
    "CSS Fundamentals": {
        "conceptual": ["cascade", "specificity", "inheritance", "box model",
                       "flexbox", "grid", "custom property"],
        "practical":  ["bem", "css modules", "tailwind", "media query", "animation"],
        "tradeoffs":  ["css-in-js trade-off", "specificity war", "global vs scoped"],
    },
    "Rendering Strategies": {
        "conceptual": ["csr", "ssr", "ssg", "isr", "hydration", "time to first byte",
                       "seo"],
        "practical":  ["next.js", "react", "gatsby", "streaming ssr"],
        "tradeoffs":  ["seo vs interactivity", "build time vs request time",
                       "cache staleness"],
    },
    "Accessibility": {
        "conceptual": ["aria", "wcag", "semantic html", "keyboard navigation",
                       "screen reader", "focus management"],
        "practical":  ["axe", "role attribute", "alt text", "tab index", "skip link"],
        "tradeoffs":  ["accessibility vs design", "automation vs manual testing"],
    },

    # ── Backend specific ──────────────────────────────────────────────────────
    "Concurrency": {
        "conceptual": ["gil", "thread", "process", "async", "event loop",
                       "coroutine", "asyncio", "blocking"],
        "practical":  ["asyncio", "multiprocessing", "celery", "threadpool",
                       "await", "aiohttp"],
        "tradeoffs":  ["thread vs process", "gil limitation", "io vs cpu bound",
                       "complexity vs performance"],
    },
    "Observability": {
        "conceptual": ["trace", "log", "metric", "span", "correlation id",
                       "slo", "sli", "error budget"],
        "practical":  ["prometheus", "grafana", "opentelemetry", "jaeger",
                       "elk", "structured logging"],
        "tradeoffs":  ["sampling strategy", "storage cost", "cardinality",
                       "push vs pull metrics"],
    },

    # ── DevOps ────────────────────────────────────────────────────────────────
    "Container Fundamentals": {
        "conceptual": ["namespace", "cgroup", "union filesystem", "oci", "image layer",
                       "overlay", "runtime"],
        "practical":  ["docker", "dockerfile", "compose", "build", "run", "containerd"],
        "tradeoffs":  ["vm vs container", "image size", "build cache trade-off"],
    },
    "Kubernetes": {
        "conceptual": ["pod", "deployment", "service", "scheduler", "kubelet",
                       "controller", "node", "cluster"],
        "practical":  ["kubectl", "helm", "statefulset", "ingress", "configmap",
                       "rolling update"],
        "tradeoffs":  ["stateful vs stateless", "rolling vs blue-green",
                       "resource limit"],
    },
    "Cloud Architecture": {
        "conceptual": ["multi-region", "availability zone", "rto", "rpo", "failover",
                       "replication", "eventual consistency"],
        "practical":  ["aws", "route53", "s3", "rds", "lambda", "cloudfront"],
        "tradeoffs":  ["cost vs availability", "active-active vs active-passive",
                       "consistency vs availability"],
    },

    # ── Data Science / ML ─────────────────────────────────────────────────────
    "Model Selection": {
        "conceptual": ["bias", "variance", "overfitting", "underfitting", "baseline",
                       "complexity", "interpretability"],
        "practical":  ["logistic regression", "decision tree", "gradient boost",
                       "xgboost", "cross validation"],
        "tradeoffs":  ["accuracy vs interpretability", "model complexity trade-off",
                       "training time vs performance"],
    },
    "Model Theory": {
        "conceptual": ["bias variance trade-off", "regularisation", "l1", "l2",
                       "overfitting", "generalisation", "loss function"],
        "practical":  ["sklearn", "cross-validation", "hyperparameter tuning",
                       "grid search"],
        "tradeoffs":  ["lasso vs ridge", "regularisation strength", "model capacity"],
    },
    "Practical ML": {
        "conceptual": ["class imbalance", "smote", "oversampling", "undersampling",
                       "precision", "recall", "f1", "threshold"],
        "practical":  ["sklearn", "imbalanced-learn", "cost sensitive",
                       "stratified split"],
        "tradeoffs":  ["precision vs recall trade-off", "synthetic data risk",
                       "threshold selection"],
    },
    "Experimentation": {
        "conceptual": ["a/b test", "hypothesis", "significance", "power", "p-value",
                       "sample size", "randomisation"],
        "practical":  ["split test", "treatment control", "metric definition",
                       "guardrail metric"],
        "tradeoffs":  ["novelty effect", "multiple testing", "practical vs statistical significance"],
    },
    "Evaluation Metrics": {
        "conceptual": ["precision", "recall", "f1", "auc", "roc", "accuracy",
                       "confusion matrix", "mse", "mae"],
        "practical":  ["sklearn metrics", "threshold tuning", "calibration"],
        "tradeoffs":  ["precision vs recall", "auc vs accuracy", "metric choice by domain"],
    },
    "MLOps": {
        "conceptual": ["model versioning", "data drift", "concept drift", "pipeline",
                       "experiment tracking", "registry"],
        "practical":  ["mlflow", "wandb", "dvc", "airflow", "bentoml", "sagemaker"],
        "tradeoffs":  ["retraining strategy", "batch vs online learning",
                       "monitoring overhead"],
    },

    # ── ML Engineering ────────────────────────────────────────────────────────
    "Transfer Learning": {
        "conceptual": ["pretrained", "fine-tuning", "feature extraction", "peft",
                       "lora", "catastrophic forgetting", "downstream task"],
        "practical":  ["hugging face", "bert", "gpt", "lora", "adapter"],
        "tradeoffs":  ["fine-tune vs scratch", "data size threshold",
                       "domain adaptation"],
    },
    "Deep Learning": {
        "conceptual": ["attention", "transformer", "self-attention", "positional encoding",
                       "backpropagation", "gradient", "activation"],
        "practical":  ["pytorch", "tensorflow", "hugging face", "cuda", "batch size"],
        "tradeoffs":  ["model size vs inference speed", "attention complexity",
                       "rnn vs transformer"],
    },
    "Model Serving": {
        "conceptual": ["inference", "batching", "quantisation", "latency slo",
                       "throughput", "kv cache", "horizontal scaling"],
        "practical":  ["vllm", "triton", "torchserve", "bentoml", "onnx",
                       "tensorrt"],
        "tradeoffs":  ["latency vs throughput", "quantisation quality trade-off",
                       "batch size trade-off"],
    },
    "Continual Learning": {
        "conceptual": ["catastrophic forgetting", "elastic weight", "replay buffer",
                       "task incremental", "domain incremental"],
        "practical":  ["ewc", "progressive network", "rehearsal", "avalanche"],
        "tradeoffs":  ["stability vs plasticity", "memory overhead", "retraining vs continual"],
    },

    # ── Data Engineering ──────────────────────────────────────────────────────
    "Processing Paradigms": {
        "conceptual": ["batch", "streaming", "lambda architecture", "kappa architecture",
                       "latency", "throughput", "watermark"],
        "practical":  ["spark", "flink", "kafka", "airflow", "dbt"],
        "tradeoffs":  ["batch vs stream", "lambda vs kappa", "cost vs latency"],
    },
    "Pipeline Design": {
        "conceptual": ["idempotency", "exactly-once", "at-least-once", "checkpoint",
                       "fault tolerance", "watermark", "late data"],
        "practical":  ["flink", "kafka streams", "airflow dag", "dead letter queue"],
        "tradeoffs":  ["exactly-once overhead", "late data vs completeness",
                       "complexity vs reliability"],
    },
    "Data Quality": {
        "conceptual": ["schema validation", "null check", "anomaly detection",
                       "data contract", "quarantine", "sla"],
        "practical":  ["great expectations", "dbt test", "z-score", "profiling"],
        "tradeoffs":  ["validation overhead", "strictness vs flexibility",
                       "fail fast vs quarantine"],
    },
    "Data Modelling": {
        "conceptual": ["star schema", "fact table", "dimension table", "scd",
                       "grain", "slowly changing dimension", "normalisation"],
        "practical":  ["kimball", "dbt", "snowflake", "bigquery", "partitioning"],
        "tradeoffs":  ["normalised vs denormalised", "query cost vs storage",
                       "scd type trade-off"],
    },

    # ── Mobile ────────────────────────────────────────────────────────────────
    "React Native Internals": {
        "conceptual": ["bridge", "jsi", "fabric", "turbomodule", "js thread",
                       "native thread", "serialisation"],
        "practical":  ["react native", "reanimated", "new architecture", "native module"],
        "tradeoffs":  ["bridge overhead", "new vs old architecture", "js vs native"],
    },
    "Offline Architecture": {
        "conceptual": ["offline first", "local storage", "sync", "conflict resolution",
                       "queue", "optimistic update"],
        "practical":  ["sqlite", "realm", "watermelon", "async storage", "background fetch"],
        "tradeoffs":  ["conflict resolution strategy", "storage limit", "sync complexity"],
    },
    "Platform APIs": {
        "conceptual": ["apns", "fcm", "push notification", "device token",
                       "background mode", "permission"],
        "practical":  ["expo", "notifee", "firebase", "apple push", "google fcm"],
        "tradeoffs":  ["ios vs android", "background vs foreground", "silent vs visible"],
    },

    # ── Universal ────────────────────────────────────────────────────────────
    "Project Deep Dive": {
        "conceptual": ["architecture", "design decision", "trade-off", "problem",
                       "solution", "technology choice"],
        "practical":  ["built", "implemented", "deployed", "used", "developed",
                       "created", "shipped"],
        "tradeoffs":  ["what i would change", "lesson learned", "alternative approach",
                       "limitation"],
    },
    "Error Handling": {
        "conceptual": ["exception", "error boundary", "circuit breaker", "retry",
                       "fallback", "graceful degradation"],
        "practical":  ["try catch", "error middleware", "status code", "logging"],
        "tradeoffs":  ["fail fast vs graceful", "retry vs circuit breaker",
                       "error detail vs security"],
    },
}

# ── Dimension keywords for all topics not explicitly defined ──────────────────

_FALLBACK_RUBRIC: Dict[str, List[str]] = {
    "conceptual": ["concept", "principle", "theory", "understand", "definition",
                   "mechanism", "process", "algorithm"],
    "practical":  ["implement", "use", "build", "deploy", "run", "configure",
                   "example", "tool"],
    "tradeoffs":  ["trade-off", "however", "alternative", "advantage", "disadvantage",
                   "but", "versus", "compared"],
}


def _get_rubric(topic: str) -> Dict[str, List[str]]:
    # Exact match first, then fuzzy
    if topic in _RUBRICS:
        return _RUBRICS[topic]
    topic_lower = topic.lower()
    for key, val in _RUBRICS.items():
        if key.lower() in topic_lower or topic_lower in key.lower():
            return val
    return _FALLBACK_RUBRIC


def _score_dimension(answer_lower: str, keywords: List[str], max_score: int) -> Tuple[int, List[str]]:
    """
    Score one dimension by checking keyword/synonym presence.
    Returns (score, list_of_matched_terms).

    Uses a sqrt curve with a 12% floor so that partial coverage is rewarded fairly:
      score = floor + sqrt(ratio) × (max_score − floor)

    Examples with max_score=30, floor=3 (10%):
      0 matches  → 3   (not 0 — a little credit for attempting)
      25% match  → 3 + sqrt(0.25)×27 = 3 + 13.5 ≈ 17  (vs linear 7.5 — much fairer)
      50% match  → 3 + sqrt(0.50)×27 ≈ 22              (vs linear 15)
      100% match → 30
    """
    matched: List[str] = []
    for kw in keywords:
        if _answer_contains(answer_lower, kw):
            matched.append(kw)

    if not keywords:
        return 0, []

    ratio = len(matched) / len(keywords)
    floor = max(1, round(max_score * 0.10))   # 10% floor
    score = floor + math.sqrt(ratio) * (max_score - floor)
    return round(min(max_score, score)), matched


def _score_communication(answer: str) -> Tuple[int, List[str]]:
    """
    Score communication_structure from text structure signals (15 pts max).
    """
    al = answer.lower()
    signals: List[str] = []

    checks = [
        (r"\b(first|second|third|finally|lastly|additionally|furthermore)\b", "logical sequence"),
        (r"\b(for example|such as|specifically|in particular|like|to illustrate)\b", "concrete example"),
        (r"\b(because|therefore|since|as a result|which means|this means)\b", "reasoning chain"),
        (r"\b(trade.?off|however|although|on the other hand|but|alternatively)\b", "nuanced view"),
        (r"\d+", "quantitative data"),
        (r"\b(i built|i implemented|i used|i chose|we decided|i designed|i worked)\b", "personal experience"),
    ]

    for pattern, label in checks:
        if re.search(pattern, al):
            signals.append(label)

    word_count = len(answer.split())
    if word_count >= 120:
        signals.append("comprehensive length")
    elif word_count >= 60:
        signals.append("adequate length")

    score = min(round(len(signals) / len(checks) * 15), 15)
    return score, signals


def _score_project_connection(answer: str) -> Tuple[int, List[str]]:
    """
    Score resume_project_connection — 10 pts max.
    Looks for first-person project/experience language across 8 signal categories.
    """
    al = answer.lower()
    patterns = [
        # Category 1 — explicit project reference
        (r"\b(my project|my app|my application|my system|my service|my api|our (app|system|platform|service))\b",
         "project reference"),
        # Category 2 — direct build/ship experience
        (r"\b(i (built|developed|created|implemented|shipped|deployed|wrote|designed|architected|set up))\b",
         "direct build experience"),
        # Category 3 — team / company context
        (r"\b(at my (previous|current|last|former)|in my (previous|current|last|former)|at (work|my company|my team))\b",
         "company context"),
        # Category 4 — team collaboration signals
        (r"\b(we (used|built|deployed|implemented|decided|switched|migrated|chose|went with|ran into|faced|found))\b",
         "team experience"),
        # Category 5 — production / real-world context
        (r"\b(in production|production environment|real.world|live system|customer.facing|end users?)\b",
         "production context"),
        # Category 6 — personal experimentation / debugging
        (r"\b(i (experimented|observed|traced|debugged|profiled|investigated|discovered|noticed|encountered|ran into))\b",
         "personal debugging"),
        # Category 7 — codebase references
        (r"\b(in our codebase|our codebase|our repo|our (database|schema|pipeline|stack)|the codebase)\b",
         "codebase reference"),
        # Category 8 — quantified outcomes
        (r"\b\d+\s*%\s*(improvement|reduction|faster|slower|drop|increase|decrease|gain|saving)\b"
         r"|\b(reduced|improved|increased|cut|saved|optimised|optimized).{0,30}\b\d+",
         "quantified outcome"),
    ]

    matched: List[str] = []
    for pattern, label in patterns:
        if re.search(pattern, al):
            matched.append(label)

    # 2 pts per signal, capped at 10
    score = min(len(matched) * 2, 10)
    return score, matched


# ── Phase 3.1: Follow-up directness scoring ──────────────────────────────────

def _score_followup_directness(answer: str) -> Tuple[int, List[str]]:
    """
    Phase 3.1: Score directness and technical precision for follow-up answers (0-100).

    Rewards answers that:
      • Start with a clear, specific claim ("The reason is...", "Specifically...")
      • Explain the underlying mechanism ("works by", "because", "under the hood")
      • Use concrete technical values or domain-specific terms (TTL, chunk size, 15 ms)
      • Frame a trade-off or comparison specific to the follow-up question

    No floor — a vague answer contributes 0 to this dimension.
    """
    al = answer.lower()
    checks = [
        # Direct answer markers
        (r"\b(the reason (is|why|for)|specifically[,\s]|the (key|main|core) (point|difference"
         r"|reason|issue)|in short|to (answer|clarify)|that means|the answer is)\b",
         "direct assertion"),
        # Mechanism / how-it-works explanation
        (r"\b(works by|because|under the hood|internally|the mechanism|this (happens|occurs) when"
         r"|the way (it|this|that) works|how (it|this) works)\b",
         "mechanism explanation"),
        # Concrete technical values or domain-specific terms
        (r"\b(ttl|timeout|expiry|threshold|chunk( size)?|shard|replica|partition|cursor"
         r"|retry|circuit.?breaker|backoff|batch( size)?|page( size)?|buffer|embedding|vector"
         r"|token (limit|budget)|overlap)\b"
         r"|\b\d+\s*(ms|seconds?|minutes?|kb|mb|gb|tokens?|chunks?|records?|requests?|%)\b",
         "concrete technical detail"),
        # Comparative / trade-off framing specific to the follow-up
        (r"\b(trade.?off|compared to|whereas|unlike|in contrast|the difference (is|between)"
         r"|on the other hand)\b|\bvs\b",
         "comparative framing"),
    ]
    signals = [label for pattern, label in checks if re.search(pattern, al)]
    return round(len(signals) / len(checks) * 100), signals


# ── Phase 3: Behavioral scoring helpers ──────────────────────────────────────

def _score_behavioral_situation_task(answer: str) -> Tuple[int, List[str]]:
    """STAR: Situation / Task — clarity of context (20 pts max)."""
    al = answer.lower()
    checks = [
        (r"\b(when|the situation|at the time|the problem was|context|background)\b", "context setting"),
        (r"\b(i was (asked|tasked|responsible for|working on)|my (task|goal|objective|role) was)\b",
         "task clarity"),
        (r"\b(the (team|project|company|client) (needed|wanted|was|had|faced))\b", "team context"),
        (r"\b(in order to|the challenge was|we were (trying|working|facing)|the goal)\b",
         "challenge framing"),
    ]
    signals = [label for pattern, label in checks if re.search(pattern, al)]
    return min(round(len(signals) / len(checks) * 20), 20), signals


def _score_behavioral_action_ownership(answer: str) -> Tuple[int, List[str]]:
    """STAR: Action / Ownership — first-person initiative (30 pts max)."""
    al = answer.lower()
    checks = [
        (r"\b(i decided|i chose|i led|i took|i was responsible|i owned|my decision)\b",
         "decision ownership"),
        (r"\b(i (implemented|built|designed|created|wrote|fixed|solved|initiated|started))\b",
         "implementation action"),
        # "coordinating with" is a natural form of "I coordinated" mid-sentence
        (r"\b(i (coordinated|managed|communicated|collaborated|worked with|partnered))"
         r"|(coordinating with|managing the)\b",
         "coordination action"),
        # Accept both "I proposed" and compound form "... and proposed" with prior "I"
        (r"\b(i (proposed|suggested|recommended|pushed for|advocated|raised))\b"
         r"|\band proposed\b|\band suggested\b",
         "initiative"),
        (r"\b(i (prioritised|prioritized|focused|identified|analysed|analyzed|evaluated))\b",
         "analysis action"),
    ]
    signals = [label for pattern, label in checks if re.search(pattern, al)]
    return min(round(len(signals) / len(checks) * 30), 30), signals


def _score_behavioral_result_impact(answer: str) -> Tuple[int, List[str]]:
    """STAR: Result / Impact — quantified or qualitative outcome (20 pts max)."""
    al = answer.lower()
    checks = [
        (r"\b(as a result|the outcome was|this led to|which meant|consequently)\b", "outcome stated"),
        (r"\b\d+\s*%|\b\d+x\b|\b\d+\s*(seconds?|minutes?|hours?|days?|weeks?)\b", "quantified impact"),
        (r"\b(improved|reduced|increased|saved|delivered|shipped|launched|achieved)\b", "achievement verb"),
        (r"\b(the team|stakeholders|users|customers|clients) (was|were|could|got|received|saw)\b",
         "stakeholder impact"),
    ]
    signals = [label for pattern, label in checks if re.search(pattern, al)]
    return min(round(len(signals) / len(checks) * 20), 20), signals


def _score_behavioral_reflection(answer: str) -> Tuple[int, List[str]]:
    """STAR: Reflection / Learning — retrospective insight (15 pts max)."""
    al = answer.lower()
    checks = [
        (r"\b(i (learned|learnt)|key (takeaway|lesson|insight)|in retrospect)\b", "explicit learning"),
        # Catch "I would have done", "I would do differently", "if I did it again"
        (r"\b(i would (have|do|change)|what i would (do|change)|if i did it again"
         r"|do it differently|next time i)\b", "retrospective"),
        (r"\b(this (taught|showed|reminded) me|it made me (realise|realize|understand)"
         r"|i (realised|realized))\b", "insight"),
    ]
    signals = [label for pattern, label in checks if re.search(pattern, al)]
    return min(round(len(signals) / len(checks) * 15), 15), signals


def _score_behavioral_profile(answer: str, topic: str) -> Dict:
    """Score a behavioral answer using the STAR-method rubric (total 100 pts)."""
    if not answer.strip():
        return {
            "rubric_scores": {
                "situation_task_clarity": 0, "action_ownership": 0,
                "result_impact": 0, "reflection_learning": 0, "communication_structure": 0,
            },
            "rubric_total": 0,
            "evidence": [],
            "rubric_profile": "behavioral",
            "improvement_hint": (
                "Use the STAR method: describe the Situation, your Task, "
                "the Actions you took, and the Results achieved."
            ),
            "interviewer_diagnosis": f"No answer was provided for '{topic}'.",
        }

    sit_score,  sit_sigs  = _score_behavioral_situation_task(answer)
    act_score,  act_sigs  = _score_behavioral_action_ownership(answer)
    res_score,  res_sigs  = _score_behavioral_result_impact(answer)
    ref_score,  ref_sigs  = _score_behavioral_reflection(answer)
    comm_score, comm_sigs = _score_communication(answer)

    rubric_total = min(sit_score + act_score + res_score + ref_score + comm_score, 100)

    dims = [
        ("Situation/task clarity", sit_score,  20),
        ("Action and ownership",   act_score,  30),
        ("Result and impact",      res_score,  20),
        ("Reflection and learning", ref_score, 15),
        ("Communication structure", comm_score, 15),
    ]
    worst = min(dims, key=lambda d: d[1] / d[2])

    hint_map = {
        "Situation/task clarity": (
            "Open with more context: set the scene (when, what project/team) "
            "and clarify what specifically you were asked to do."
        ),
        "Action and ownership": (
            "Use first-person language to show what YOU did — 'I decided', 'I led', 'I implemented'. "
            "Avoid 'we' without specifying your personal contribution."
        ),
        "Result and impact": (
            "Close with the outcome: what specifically changed, "
            "and ideally quantify it (e.g. reduced errors by 30%, shipped on time)."
        ),
        "Reflection and learning": (
            "Add a brief reflection: what you learned, what you'd do differently, "
            "or what insight the experience gave you."
        ),
        "Communication structure": (
            "Structure your answer: set context → describe actions → state result → reflect. "
            "Transition words like 'as a result' or 'in retrospect' help."
        ),
    }
    improvement_hint = hint_map.get(
        worst[0], "Structure your answer using the STAR method for maximum clarity."
    )

    if rubric_total >= 75:
        diagnosis = f"Strong behavioral answer on '{topic}' — clear ownership, context, and impact."
    elif rubric_total >= 55:
        diagnosis = f"Good behavioral answer on '{topic}'. {worst[0]} could be strengthened."
    else:
        diagnosis = f"The answer needs more STAR structure — particularly {worst[0].lower()}."

    return {
        "rubric_scores": {
            "situation_task_clarity": sit_score,
            "action_ownership":       act_score,
            "result_impact":          res_score,
            "reflection_learning":    ref_score,
            "communication_structure": comm_score,
        },
        "rubric_total":          rubric_total,
        "evidence":              (sit_sigs + act_sigs + res_sigs + ref_sigs)[:10],
        "rubric_profile":        "behavioral",
        "improvement_hint":      improvement_hint,
        "interviewer_diagnosis": diagnosis,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def score_with_rubric(
    answer: str,
    topic: str,
    expected_points: List[str],
) -> Dict:
    """
    Score an answer with the 5-dimension rubric.

    Returns a dict with:
      rubric_scores: {dimension: score}
      rubric_total: 0-100
      evidence: list of matched concepts
      improvement_hint: targeted coaching based on lowest-scoring dimensions
      interviewer_diagnosis: 1-sentence diagnostic
    """
    if not answer.strip():
        return {
            "rubric_scores": {
                "conceptual_correctness": 0,
                "practical_application": 0,
                "depth_and_tradeoffs": 0,
                "communication_structure": 0,
                "resume_project_connection": 0,
            },
            "rubric_total": 0,
            "evidence": [],
            "improvement_hint": "Provide a substantive answer with at least one concrete concept, example, and trade-off.",
            "interviewer_diagnosis": f"No answer was provided for '{topic}', so the rubric has no evidence to score.",
        }

    al = _normalise(answer)
    rubric = _get_rubric(topic)

    # Dimension 1 — Conceptual correctness (30 pts)
    conc_score, conc_matched = _score_dimension(al, rubric.get("conceptual", []), 30)

    # Dimension 2 — Practical application (25 pts)
    prac_score, prac_matched = _score_dimension(al, rubric.get("practical", []), 25)

    # Dimension 3 — Depth and trade-offs (20 pts)
    depth_score, depth_matched = _score_dimension(al, rubric.get("tradeoffs", []), 20)

    # Dimension 4 — Communication structure (15 pts)
    comm_score, comm_signals = _score_communication(answer)

    # Dimension 5 — Resume/project connection (10 pts)
    proj_score, proj_signals = _score_project_connection(answer)

    rubric_total = conc_score + prac_score + depth_score + comm_score + proj_score
    rubric_total = min(rubric_total, 100)

    all_evidence: List[str] = conc_matched + prac_matched + depth_matched

    # ── Improvement hint ──────────────────────────────────────────────────────
    dims = [
        ("Conceptual understanding", conc_score, 30),
        ("Practical application",    prac_score, 25),
        ("Trade-off depth",          depth_score, 20),
        ("Communication structure",  comm_score,  15),
        ("Project connection",       proj_score,  10),
    ]
    # Find the dimension with the biggest gap
    worst = min(dims, key=lambda d: d[1] / d[2])
    worst_ratio = worst[1] / worst[2]

    hint_map = {
        "Conceptual understanding": (
            f"To go deeper on '{topic}': name the key mechanisms by name, "
            "briefly define what they do, and explain why they exist — "
            "that three-step pattern (name → define → why) is what strong answers look like."
        ),
        "Practical application": (
            f"Ground the answer in '{topic}' with a specific tool or step you've actually used. "
            "Even one sentence like 'In practice I used X to do Y' makes a big difference."
        ),
        "Trade-off depth": (
            "The answer would be stronger with one explicit trade-off: "
            "what does this approach give up, and when would you pick an alternative? "
            "Interviewers are specifically listening for that kind of nuance."
        ),
        "Communication structure": (
            "Try a simple structure: one sentence of context, one concrete example, "
            "one trade-off or caveat. Transition words like 'however' or 'specifically' "
            "signal that kind of structured thinking immediately."
        ),
        "Project connection": (
            "Tie the answer to something you actually built or observed. "
            "Starting with 'In a project I worked on, we...' or 'I ran into this when...' "
            "immediately makes the answer more credible and memorable."
        ),
    }
    improvement_hint = hint_map.get(
        worst[0],
        "Add one concrete example and one trade-off — those two additions consistently raise scores the most."
    )

    # ── Interviewer diagnosis ─────────────────────────────────────────────────
    if rubric_total >= 80:
        diagnosis = f"Strong answer on '{topic}' — conceptual grounding and practical depth are both clearly there."
    elif rubric_total >= 65:
        diagnosis = f"Good answer on '{topic}'. Solid foundation; {worst[0].lower()} could go a bit further."
    elif rubric_total >= 45:
        diagnosis = (
            f"Decent start on '{topic}'. The candidate shows awareness of the area, "
            f"but {worst[0].lower()} would benefit from more specificity."
        )
    else:
        diagnosis = (
            f"The answer on '{topic}' establishes a starting point, "
            f"but needs more depth — particularly on {worst[0].lower()}."
        )

    return {
        "rubric_scores": {
            "conceptual_correctness":    conc_score,
            "practical_application":     prac_score,
            "depth_and_tradeoffs":       depth_score,
            "communication_structure":   comm_score,
            "resume_project_connection": proj_score,
        },
        "rubric_total":         rubric_total,
        "evidence":             all_evidence[:12],  # cap for readability
        "improvement_hint":     improvement_hint,
        "interviewer_diagnosis": diagnosis,
    }


def score_with_rubric_profile(
    answer: str,
    topic: str,
    expected_points: List[str],
    rubric_profile: str | None = None,
) -> Dict:
    """
    Phase 3: Profile-aware rubric scoring.

    When rubric_profile is None or unrecognised, falls back to score_with_rubric()
    (fully backward compatible).

    For non-behavioral profiles:
      Each of the 5 raw dimensions is scored on a normalised 0-100 scale, then
      scaled by the profile's weight for that dimension.  This means a concept
      answer is never penalised for missing project-language when the profile
      weight for that dimension is 0.

    For the behavioral profile, STAR-method scoring is used instead.
    """
    if rubric_profile == "behavioral":
        return _score_behavioral_profile(answer, topic)

    if not rubric_profile or rubric_profile not in _PROFILE_WEIGHTS:
        return score_with_rubric(answer, topic, expected_points)

    if not answer.strip():
        empty = score_with_rubric("", topic, expected_points)
        empty["rubric_profile"] = rubric_profile
        return empty

    al = _normalise(answer)
    rubric = _get_rubric(topic)
    w = _PROFILE_WEIGHTS[rubric_profile]

    # Score each dimension normalised to 0-100 (then scale by weight)
    conc_norm,  conc_matched  = _score_dimension(al, rubric.get("conceptual", []), 100)
    prac_norm,  prac_matched  = _score_dimension(al, rubric.get("practical",  []), 100)
    depth_norm, depth_matched = _score_dimension(al, rubric.get("tradeoffs",  []), 100)

    comm_raw,  comm_signals = _score_communication(answer)       # 0-15
    comm_norm = round(comm_raw / 15 * 100)

    proj_raw,  proj_signals = _score_project_connection(answer)  # 0-10
    proj_norm = round(proj_raw / 10 * 100) if proj_raw else 0

    # Phase 3.1: directness dimension (technical_follow_up + claim_verification only)
    dir_weight = w.get("directness", 0)
    if dir_weight > 0:
        dir_norm, dir_signals = _score_followup_directness(answer)
    else:
        dir_norm, dir_signals = 0, []

    rubric_total = round(
        conc_norm  * w["conceptual"]      / 100 +
        prac_norm  * w["practical"]       / 100 +
        depth_norm * w["tradeoffs"]       / 100 +
        comm_norm  * w["communication"]   / 100 +
        proj_norm  * w["project"]         / 100 +
        dir_norm   * dir_weight           / 100
    )
    rubric_total = min(rubric_total, 100)

    rubric_scores: Dict[str, int] = {
        "conceptual_correctness":    round(conc_norm  * w["conceptual"]    / 100),
        "practical_application":     round(prac_norm  * w["practical"]     / 100),
        "depth_and_tradeoffs":       round(depth_norm * w["tradeoffs"]     / 100),
        "communication_structure":   round(comm_norm  * w["communication"] / 100),
        "resume_project_connection": round(proj_norm  * w["project"]       / 100),
    }
    if dir_weight > 0:
        rubric_scores["direct_answer_to_followup"] = round(dir_norm * dir_weight / 100)

    all_evidence = (conc_matched + prac_matched + depth_matched + dir_signals)[:12]

    # Improvement hint — find worst active dimension (by fill ratio)
    dim_info = [
        ("Conceptual understanding", w["conceptual"],    conc_norm),
        ("Practical application",    w["practical"],     prac_norm),
        ("Trade-off depth",          w["tradeoffs"],     depth_norm),
        ("Communication structure",  w["communication"], comm_norm),
    ]
    if w["project"] > 0:
        label = "Project ownership" if rubric_profile == "project_deep_dive" else "Ownership detail"
        dim_info.append((label, w["project"], proj_norm))
    if dir_weight > 0:
        dim_info.append(("Answer directness", dir_weight, dir_norm))

    active = [(name, weight, norm) for name, weight, norm in dim_info if weight > 0]
    worst = min(active, key=lambda d: d[2]) if active else ("Communication structure", 15, 50)
    worst_name = worst[0]

    hint_map = {
        "Conceptual understanding": (
            f"To go deeper on '{topic}': name the key mechanisms, briefly define what they do, "
            "and explain why they exist — that three-step pattern (name → define → why) "
            "is what strong answers look like."
        ),
        "Practical application": (
            f"Ground the answer in '{topic}' with a specific tool or step you've used. "
            "Even one sentence like 'In practice I used X to do Y' makes a big difference."
        ),
        "Trade-off depth": (
            "The answer would be stronger with one explicit trade-off: "
            "what does this approach give up, and when would you pick an alternative?"
        ),
        "Communication structure": (
            "Try: one sentence of context, one concrete example, one trade-off or caveat. "
            "Transition words like 'however' or 'specifically' signal structured thinking."
        ),
        "Project ownership": (
            "Describe the project in first person: what YOU decided, built, and owned. "
            "Include at least one concrete architectural decision and its rationale."
        ),
        "Ownership detail": (
            "Show ownership: what specifically did you build, decide, or observe? "
            "Starting with 'I implemented', 'I chose', or 'In my team we...' "
            "makes the answer far more credible for claim verification."
        ),
        "Answer directness": (
            "Start with a direct, specific answer: 'The reason is...', 'Specifically...' "
            "or name the concrete mechanism at play. "
            "Concrete values (TTL=30s, chunk size 512 tokens) and "
            "comparative framing ('compared to X, Y is better when...') signal technical precision."
        ),
    }
    improvement_hint = hint_map.get(
        worst_name,
        "Add one concrete example and one trade-off — these two additions raise scores the most."
    )

    if rubric_total >= 80:
        diagnosis = f"Strong answer on '{topic}' — conceptual grounding and practical depth are both clearly there."
    elif rubric_total >= 65:
        diagnosis = f"Good answer on '{topic}'. Solid foundation; {worst_name.lower()} could go a bit further."
    elif rubric_total >= 45:
        diagnosis = (
            f"Decent start on '{topic}'. The candidate shows awareness of the area, "
            f"but {worst_name.lower()} would benefit from more specificity."
        )
    else:
        diagnosis = (
            f"The answer on '{topic}' establishes a starting point, "
            f"but needs more depth — particularly on {worst_name.lower()}."
        )

    return {
        "rubric_scores":          rubric_scores,
        "rubric_total":           rubric_total,
        "evidence":               all_evidence,
        "rubric_profile":         rubric_profile,
        "improvement_hint":       improvement_hint,
        "interviewer_diagnosis":  diagnosis,
    }
