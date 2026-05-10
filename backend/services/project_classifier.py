"""
project_classifier.py — keyword-based project domain classification.

No embeddings, no vector DBs, no LLM calls.
Scores each project against 6 domain signal tables, then computes
how relevant that project is for a given interview role.

Public API
----------
classify_project(project)              -> ProjectDomain
project_role_relevance(project, role)  -> int  (0-100)
select_best_project(projects, role)    -> (Project | None, int, dict[str, int])
"""

from __future__ import annotations

# ── Domain signal tables ──────────────────────────────────────────────────────
# tech_names: appear in project.technologies  → +3 pts per match
# keywords:   appear anywhere in name + description text → +1 pt per match

_DOMAIN_SIGNALS: dict[str, dict[str, list[str]]] = {
    "ML / AI": {
        "tech_names": [
            "tensorflow", "pytorch", "keras", "scikit-learn", "xgboost",
            "lightgbm", "hugging face", "mlflow", "weights & biases",
            "opencv", "langchain", "llm", "machine learning", "deep learning",
            "nlp", "computer vision",
        ],
        "keywords": [
            "neural network", "natural language", "prediction", "classification",
            "regression", "clustering", "model training", "inference",
            "transformer", "embedding", "sentiment", "recommendation",
            "anomaly detection", "forecasting", "generative", "ai model",
            "predictive", "chatbot", "image recognition", "object detection",
            "feature engineering", "model accuracy", "precision recall",
        ],
    },
    "Data Engineering": {
        "tech_names": [
            "spark", "hadoop", "airflow", "kafka", "dbt", "snowflake",
            "databricks", "bigquery", "redshift", "hive", "flink",
        ],
        "keywords": [
            "pipeline", "etl", "data pipeline", "batch processing", "streaming",
            "data warehouse", "data lake", "ingestion", "data flow",
            "real-time processing", "orchestration", "data transformation",
            "data quality", "data catalog", "schema", "partitioning",
            "data integration", "event-driven",
        ],
    },
    "Web Frontend": {
        "tech_names": [
            "react", "angular", "vue.js", "vue", "next.js", "nuxt.js",
            "gatsby", "svelte", "tailwind css", "tailwind", "bootstrap",
            "material ui", "redux", "webpack", "vite",
        ],
        "keywords": [
            "user interface", "frontend", "front-end", "responsive design",
            "component", "dashboard ui", "web app", "browser",
            "single page app", "progressive web app", "ui ux", "design system",
            "accessibility", "animation", "client-side", "interactive",
        ],
    },
    "Backend": {
        "tech_names": [
            "django", "flask", "fastapi", "express.js", "express",
            "spring boot", "spring", "rails", "laravel", "node.js",
            "graphql", "grpc", "rest api", "postgresql", "mysql",
            "mongodb", "redis",
        ],
        "keywords": [
            "api", "microservice", "server", "backend", "back-end",
            "authentication", "authorization", "database integration",
            "endpoint", "crud", "web service", "middleware",
            "rate limiting", "caching", "message queue",
        ],
    },
    "DevOps / Cloud": {
        "tech_names": [
            "docker", "kubernetes", "jenkins", "github actions", "gitlab ci",
            "terraform", "ansible", "prometheus", "grafana", "nginx",
            "aws", "azure", "gcp", "google cloud",
        ],
        "keywords": [
            "deployment", "ci/cd", "devops", "infrastructure", "cloud",
            "container", "orchestration", "auto-scaling", "monitoring",
            "infrastructure as code", "helm chart", "cluster management",
            "load balancer", "auto deploy", "pipeline",
        ],
    },
    "Mobile": {
        "tech_names": [
            "react native", "flutter", "swift", "kotlin", "ios", "android",
            "xamarin",
        ],
        "keywords": [
            "mobile app", "ios app", "android app", "native app",
            "cross-platform mobile", "smartphone", "tablet application",
            "push notification", "offline-first", "mobile ui",
        ],
    },
}


# ── Role → domain affinity weights ───────────────────────────────────────────
# 0.0 = irrelevant project domain for this role
# 1.0 = core domain (highest priority for project selection)
# 12 interview roles × 6 domains

_ROLE_DOMAIN_AFFINITY: dict[str, dict[str, float]] = {
    "Full Stack Developer": {
        "Web Frontend": 0.95, "Backend": 0.90,
        "DevOps / Cloud": 0.30, "ML / AI": 0.10, "Data Engineering": 0.05,
        "Mobile": 0.10,
    },
    "Frontend Developer": {
        "Web Frontend": 1.00, "Backend": 0.25, "Mobile": 0.20,
        "DevOps / Cloud": 0.10, "ML / AI": 0.05, "Data Engineering": 0.05,
    },
    "Backend Developer": {
        "Backend": 1.00, "Web Frontend": 0.20, "DevOps / Cloud": 0.40,
        "Data Engineering": 0.20, "ML / AI": 0.10, "Mobile": 0.05,
    },
    "Data Scientist": {
        "ML / AI": 1.00, "Data Engineering": 0.55, "Backend": 0.15,
        "Web Frontend": 0.05, "DevOps / Cloud": 0.10, "Mobile": 0.0,
    },
    "Machine Learning Engineer": {
        "ML / AI": 1.00, "Data Engineering": 0.60, "DevOps / Cloud": 0.40,
        "Backend": 0.25, "Web Frontend": 0.05, "Mobile": 0.0,
    },
    "Data Engineer": {
        "Data Engineering": 1.00, "Backend": 0.40, "DevOps / Cloud": 0.35,
        "ML / AI": 0.25, "Web Frontend": 0.05, "Mobile": 0.0,
    },
    "DevOps / SRE Engineer": {
        "DevOps / Cloud": 1.00, "Backend": 0.40, "Data Engineering": 0.20,
        "Web Frontend": 0.10, "ML / AI": 0.10, "Mobile": 0.05,
    },
    "MLOps / AI Platform Engineer": {
        "DevOps / Cloud": 0.90, "ML / AI": 0.85, "Data Engineering": 0.55,
        "Backend": 0.25, "Web Frontend": 0.05, "Mobile": 0.0,
    },
    "Mobile Developer": {
        "Mobile": 1.00, "Backend": 0.30, "Web Frontend": 0.20,
        "DevOps / Cloud": 0.10, "ML / AI": 0.05, "Data Engineering": 0.0,
    },
    "Analytics Engineer": {
        "Data Engineering": 0.85, "ML / AI": 0.45, "Backend": 0.25,
        "Web Frontend": 0.20, "DevOps / Cloud": 0.15, "Mobile": 0.0,
    },
    "QA / SDET Engineer": {
        "Backend": 0.55, "Web Frontend": 0.55, "DevOps / Cloud": 0.45,
        "Mobile": 0.40, "ML / AI": 0.10, "Data Engineering": 0.10,
    },
    "Security Engineer": {
        "Backend": 0.60, "DevOps / Cloud": 0.70, "Web Frontend": 0.25,
        "Data Engineering": 0.15, "ML / AI": 0.10, "Mobile": 0.10,
    },
}


# ── classify_project ──────────────────────────────────────────────────────────

def classify_project(project) -> "ProjectDomain":
    """
    Classify a project's primary and secondary domains using keyword signals.

    Scoring per domain:
      +3  for each matching tech_name found in project.technologies
      +1  for each keyword found in project name + description text

    Returns a ProjectDomain model instance.
    """
    from models.analysis import ProjectDomain  # deferred to avoid circular import

    # Build sets for efficient matching
    tech_set = {t.lower() for t in (getattr(project, "technologies", None) or [])}

    # Full text: name + summary + all description bullets
    desc_lines = getattr(project, "description", None) or []
    summary    = getattr(project, "summary", None) or ""
    full_text  = " ".join([
        (getattr(project, "name", "") or "").lower(),
        summary.lower(),
        " ".join(b.lower() for b in desc_lines),
    ])

    # Score each domain
    scores: dict[str, int] = {}
    for domain, signals in _DOMAIN_SIGNALS.items():
        score = 0
        for tech_name in signals["tech_names"]:
            if tech_name in tech_set:
                score += 3
        for kw in signals["keywords"]:
            if kw in full_text:
                score += 1
        scores[domain] = score

    best_score = max(scores.values()) if scores else 0

    if best_score == 0:
        # No signals at all — general project
        return ProjectDomain(
            primary_domain="General Software",
            secondary_domains=[],
            supporting_technologies=list((getattr(project, "technologies", None) or [])[:3]),
            confidence=0,
        )

    # Sort domains by score descending
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary_domain = ranked[0][0]
    primary_score  = ranked[0][1]

    # Secondary: score >= 30% of primary AND score > 0
    secondary_domains = [
        d for d, s in ranked[1:]
        if s > 0 and s >= 0.30 * primary_score
    ]

    # Supporting technologies: techs that signal NON-primary domains
    supporting: list[str] = []
    for tech in (getattr(project, "technologies", None) or []):
        tech_lower = tech.lower()
        for domain, signals in _DOMAIN_SIGNALS.items():
            if domain != primary_domain and tech_lower in signals["tech_names"]:
                if tech not in supporting:
                    supporting.append(tech)
                break  # one domain match per tech is enough

    # Confidence: ratio of actual score to theoretical max for this domain
    max_possible = (
        len(_DOMAIN_SIGNALS[primary_domain]["tech_names"]) * 3
        + len(_DOMAIN_SIGNALS[primary_domain]["keywords"])
    )
    confidence = min(100, round((primary_score / max(max_possible, 1)) * 100))

    return ProjectDomain(
        primary_domain=primary_domain,
        secondary_domains=secondary_domains,
        supporting_technologies=supporting[:5],
        confidence=confidence,
    )


# ── project_role_relevance ────────────────────────────────────────────────────

def project_role_relevance(project, target_role: str) -> int:
    """
    Return 0-100 relevance of a project for a given interview role.

    Formula:
      primary_affinity  × 80
      + best_secondary_affinity × 15
      + supporting_tech bonus   (up to +5)

    Falls back to 50 if domain is unknown or role has no affinity table.
    """
    domain = getattr(project, "domain", None)
    if domain is None:
        return 50

    affinity = _ROLE_DOMAIN_AFFINITY.get(target_role)
    if not affinity:
        return 50

    primary_weight = affinity.get(getattr(domain, "primary_domain", ""), 0.0)

    secondary_domains = getattr(domain, "secondary_domains", []) or []
    secondary_max = max(
        (affinity.get(d, 0.0) for d in secondary_domains),
        default=0.0,
    )

    # Small bonus for supporting technologies that align with the role
    supporting_technologies = getattr(domain, "supporting_technologies", []) or []
    supporting_bonus = 0
    for tech in supporting_technologies:
        tech_lower = tech.lower()
        for dom, signals in _DOMAIN_SIGNALS.items():
            if dom != getattr(domain, "primary_domain", ""):
                if tech_lower in signals["tech_names"] and affinity.get(dom, 0.0) > 0:
                    supporting_bonus += 1
                    break
    supporting_bonus = min(supporting_bonus, 5)

    score = (
        primary_weight * 80.0
        + secondary_max * 15.0
        + supporting_bonus
    )
    return min(100, round(score))


# ── select_best_project ───────────────────────────────────────────────────────

def select_best_project(
    projects,
    target_role: str,
) -> tuple:
    """
    Select the most role-relevant project from a list.

    Returns:
        (best_project, best_relevance_score, {name: score, ...})

    Falls back to first project when no projects exist or all scores tie at 0.
    Returns (None, 0, {}) when the list is empty.
    """
    if not projects:
        return None, 0, {}

    if len(projects) == 1:
        score = project_role_relevance(projects[0], target_role)
        return projects[0], score, {getattr(projects[0], "name", "project"): score}

    all_scores = {
        getattr(p, "name", f"project_{i}"): project_role_relevance(p, target_role)
        for i, p in enumerate(projects)
    }

    best = max(projects, key=lambda p: all_scores.get(getattr(p, "name", ""), 0))
    best_score = all_scores.get(getattr(best, "name", ""), 0)

    # If everything scored 0 (no domain info), fall back to first project
    if best_score == 0:
        first = projects[0]
        return first, 0, all_scores

    return best, best_score, all_scores
