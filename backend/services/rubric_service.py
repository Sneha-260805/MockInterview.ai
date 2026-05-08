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
    """
    matched: List[str] = []
    for kw in keywords:
        if _answer_contains(answer_lower, kw):
            matched.append(kw)

    ratio = len(matched) / max(len(keywords), 1)
    score = round(ratio * max_score)
    return score, matched


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
    Looks for first-person project/experience language.
    """
    al = answer.lower()
    patterns = [
        (r"\b(my project|my app|my application|my system|my service|my api)\b", "project reference"),
        (r"\b(i built|i developed|i created|i implemented|i shipped|i deployed)\b", "direct experience"),
        (r"\b(at my (previous|current|last)|in my (previous|current|last))\b", "company context"),
        (r"\b(we (used|built|deployed|implemented|decided))\b", "team experience"),
        (r"\b(in production|production environment|real-world)\b", "production context"),
    ]

    matched: List[str] = []
    for pattern, label in patterns:
        if re.search(pattern, al):
            matched.append(label)

    score = min(len(matched) * 3, 10)
    return score, matched


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
            f"Strengthen the theoretical foundation for '{topic}'. "
            "Name the key concepts, define them, and explain the underlying mechanism."
        ),
        "Practical application": (
            f"Add concrete implementation details for '{topic}'. "
            "Mention specific tools, libraries, or steps you've used in practice."
        ),
        "Trade-off depth": (
            "Discuss the trade-offs explicitly. "
            "What are the pros and cons? When would you choose an alternative?"
        ),
        "Communication structure": (
            "Structure your answer more clearly. "
            "Use numbered steps or signal words (first, then, however, because). "
            "Include at least one concrete example."
        ),
        "Project connection": (
            "Connect your answer to real experience. "
            "Say 'In my project X, I used Y because...' to show practical grounding."
        ),
    }
    improvement_hint = hint_map.get(worst[0], "Deepen the answer with specific examples and trade-off discussion.")

    # ── Interviewer diagnosis ─────────────────────────────────────────────────
    if rubric_total >= 80:
        diagnosis = f"Strong answer on '{topic}' — conceptual grounding and practical depth both evident."
    elif rubric_total >= 60:
        diagnosis = f"Solid foundation on '{topic}', but {worst[0].lower()} needs more depth."
    elif rubric_total >= 40:
        diagnosis = f"Partial understanding of '{topic}' — key {worst[0].lower()} is underdeveloped."
    else:
        diagnosis = f"Answer on '{topic}' lacks sufficient depth; needs significant work on core concepts."

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
