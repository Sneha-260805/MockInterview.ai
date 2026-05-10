"""
Multi-dimensional, evidence-driven role recommendation engine.

Root causes fixed vs previous version:
  • Binary matching → ratio-based coverage scoring per skill tier
  • Projects ignored → project evidence scan adds up to 18 pts
  • No cross-domain → key skills appear in MULTIPLE role definitions
    (e.g. Spark counts for Data Engineer AND ML Engineer AND Data Scientist)
  • Template reasons → dynamic 2-sentence explanation per candidate
  • No experience modifier → level_affinities per role (−5 to +6)
  • Scores 0-95 → calibrated to believable 65-91 band with deterministic ±3 jitter
  • No missing-skill recommendations → computed from next_skills gap

Scoring pipeline (per role):
  1. Core skill coverage    → 0–55  (matched_core / total_core × 55)
  2. Bonus skill coverage   → 0–20  (matched_bonus / total_bonus × 20)
  3. Project evidence scan  → 0–18  (+≤3 per project capped at 18 total)
  4. Experience affinity    → −5..+6
  5. Breadth bonus          → 0 / 3 / 6  (≥40 % / ≥65 % of all role skills)
  ──────────────────────────────────────────────────────────────────────────
  Raw max ≈ 104 pts  (>100 intentionally to give calibration headroom)

Calibration:
  ratio      = min(raw / 93, 1.0)
  calibrated = round(65 + ratio × 26)            → 65–91
  jitter     = deterministic ±3 (candidate+role hash)
  final      = clamp(calibrated + jitter, 65, 91)
"""

import re
import logging

from models.analysis import ResumeAnalysis, RoleMatch, RoleRecommendationResponse

logger = logging.getLogger(__name__)

# ── Role definitions ──────────────────────────────────────────────────────────
# Cross-domain skills appear in MULTIPLE roles intentionally so that e.g.
# Spark earns credit toward Data Engineer, ML Engineer, AND Data Scientist.

_ROLES = [
    {
        "role": "Frontend Developer",
        "core":  ["javascript", "html", "css", "react", "typescript"],
        "bonus": ["next.js", "vue.js", "angular", "tailwind css", "tailwind",
                  "redux", "webpack", "vite", "jest", "graphql", "figma",
                  "nuxt.js", "gatsby", "sass"],
        "project_signals": [
            "ui", "interface", "component", "responsive", "web app",
            "dashboard", "landing page", "frontend", "user experience",
            "accessibility", "animation", "spa", "design system", "layout",
            "pixel", "figma", "tailwind", "react", "css", "styled",
        ],
        "next_skills": [
            "Server-side rendering (Next.js / Nuxt)",
            "Component testing (Jest + RTL)",
            "Web performance (Core Web Vitals)",
            "Accessibility auditing (WCAG)",
            "Storybook for design systems",
        ],
        "level_affinities": {"junior": 4, "mid": 2, "senior": 1},
        "focus_areas": ["Component architecture & state management", "CSS & responsive design", "Browser performance"],
        "probing": ["Unit / integration testing (Jest, RTL)", "Accessibility (WCAG)", "Bundle optimization"],
    },
    {
        "role": "Full Stack Developer",
        "core":  ["javascript", "react", "python", "sql", "node.js"],
        "bonus": ["typescript", "docker", "postgresql", "mongodb", "redis",
                  "aws", "fastapi", "django", "graphql", "rest api",
                  "next.js", "tailwind css", "tailwind", "express.js", "express"],
        "project_signals": [
            "full stack", "web application", "rest api", "backend", "frontend",
            "database", "authentication", "user", "crud", "api",
            "deployment", "cloud", "react", "node", "express",
            "login", "dashboard", "realtime", "websocket",
        ],
        "next_skills": [
            "System design & scalability patterns",
            "Redis caching strategies",
            "CI/CD pipelines (GitHub Actions)",
            "GraphQL API design",
            "Microservices decomposition",
        ],
        "level_affinities": {"junior": 1, "mid": 5, "senior": 3},
        "focus_areas": ["React & component design", "REST API development", "Database modeling"],
        "probing": ["System design & scalability", "CI/CD pipelines", "Caching strategies"],
    },
    {
        "role": "Backend Developer",
        "core":  ["python", "java", "node.js", "sql", "rest api"],
        "bonus": ["docker", "redis", "kafka", "postgresql", "mongodb",
                  "microservices", "grpc", "fastapi", "django", "spring boot",
                  "aws", "linux", "typescript", "go", "rust"],
        "project_signals": [
            "api", "backend", "server", "microservice", "database", "query",
            "authentication", "authorization", "rest", "endpoint", "service",
            "async", "concurrency", "cache", "queue", "event-driven",
            "oauth", "jwt", "middleware", "scheduler",
        ],
        "next_skills": [
            "Message queues (Kafka / RabbitMQ)",
            "gRPC for internal services",
            "Kubernetes deployment",
            "OpenAPI / Swagger documentation",
            "Database query optimization & indexing",
        ],
        "level_affinities": {"junior": 0, "mid": 3, "senior": 5},
        "focus_areas": ["API design & REST principles", "Database query optimization", "Concurrency & threading"],
        "probing": ["Microservices architecture", "Message queues", "Auth & authorization patterns"],
    },
    {
        "role": "Data Scientist",
        "core":  ["python", "pandas", "numpy", "machine learning", "sql",
                  "scikit-learn"],
        "bonus": ["tensorflow", "pytorch", "xgboost", "lightgbm", "r",
                  "tableau", "spark", "matplotlib", "seaborn", "jupyter",
                  "mlflow", "weights & biases", "deep learning", "nlp"],
        "project_signals": [
            "model", "prediction", "classification", "regression", "clustering",
            "analysis", "insight", "exploratory", "eda", "correlation", "feature",
            "accuracy", "precision", "recall", "f1", "roc", "dataset", "training",
            "evaluation", "hypothesis", "statistical", "visualization", "notebook",
            "experiment", "forecast", "anomaly",
        ],
        "next_skills": [
            "Experiment tracking (MLflow / W&B)",
            "Model deployment via FastAPI / Flask",
            "Cloud ML platforms (SageMaker / Vertex AI)",
            "A/B testing framework design",
            "Feature stores & data versioning (DVC)",
        ],
        "level_affinities": {"junior": 0, "mid": 3, "senior": 4},
        "focus_areas": ["Statistical modeling & hypothesis testing", "Feature engineering", "Model evaluation metrics"],
        "probing": ["Production model deployment", "Data pipeline design", "A/B testing methodology"],
    },
    {
        "role": "ML / AI Engineer",
        "core":  ["python", "machine learning", "deep learning", "tensorflow",
                  "pytorch", "scikit-learn"],
        "bonus": ["keras", "xgboost", "lightgbm", "docker", "aws", "fastapi",
                  "spark", "airflow", "nlp", "computer vision", "llm",
                  "hugging face", "mlflow", "weights & biases", "kubernetes",
                  "langchain"],
        "project_signals": [
            "model", "training", "neural", "inference", "classification",
            "detection", "nlp", "sentiment", "deep learning", "fine-tuning",
            "accuracy", "f1", "pipeline", "feature engineering", "experiment",
            "embedding", "transformer", "llm", "prediction", "benchmark",
            "hyperparameter", "optimization", "generative", "diffusion",
            "computer vision", "object detection", "segmentation",
        ],
        "next_skills": [
            "Experiment tracking (MLflow / Weights & Biases)",
            "Model serving (TorchServe / Triton)",
            "Distributed training (Ray / Horovod)",
            "ONNX / TensorRT for inference optimization",
            "Cloud ML platforms (SageMaker, Vertex AI, Azure ML)",
        ],
        "level_affinities": {"junior": -3, "mid": 3, "senior": 6},
        "focus_areas": ["Model training & fine-tuning", "MLOps & experiment tracking", "Inference optimization"],
        "probing": ["Distributed training strategies", "Model serving at scale", "Feature stores & data versioning"],
    },
    {
        "role": "MLOps / AI Platform Engineer",
        "core":  ["python", "docker", "kubernetes", "machine learning", "ci/cd"],
        "bonus": ["airflow", "mlflow", "aws", "gcp", "azure", "terraform",
                  "spark", "kafka", "fastapi", "prometheus", "grafana",
                  "linux", "bash", "weights & biases"],
        "project_signals": [
            "pipeline", "deployment", "model serving", "monitoring", "mlops",
            "experiment", "versioning", "orchestration", "infrastructure",
            "reproducible", "automation", "containerize", "model registry",
            "feature store", "canary", "rollout", "drift", "observability",
            "ci/cd", "github actions", "jenkins",
        ],
        "next_skills": [
            "Kubeflow / Argo Workflows for ML pipelines",
            "Model monitoring (Evidently AI / Arize)",
            "Feature stores (Feast / Tecton)",
            "Data versioning (DVC / LakeFS)",
            "Seldon Core / BentoML for model serving",
        ],
        "level_affinities": {"junior": -5, "mid": 2, "senior": 6},
        "focus_areas": ["Model deployment & serving", "Pipeline orchestration", "Infrastructure as Code for ML"],
        "probing": ["Model drift detection & retraining triggers", "Online vs batch serving trade-offs", "Rollback & blue-green deployment"],
    },
    {
        "role": "DevOps / Cloud Engineer",
        "core":  ["docker", "kubernetes", "aws", "linux", "ci/cd"],
        "bonus": ["terraform", "ansible", "prometheus", "grafana", "jenkins",
                  "azure", "gcp", "bash", "python", "helm", "nginx",
                  "kafka", "github actions", "gitlab ci"],
        "project_signals": [
            "deploy", "infrastructure", "pipeline", "automation", "container",
            "cloud", "cluster", "scaling", "monitoring", "alerting", "log",
            "helm chart", "terraform", "ci/cd", "github actions", "jenkins",
            "security", "networking", "load balanc", "high availability",
            "kubernetes", "docker", "ansible",
        ],
        "next_skills": [
            "Infrastructure as Code (Terraform / Pulumi)",
            "Service mesh (Istio / Linkerd)",
            "Cloud cost optimization & FinOps",
            "Security hardening & RBAC",
            "Multi-cloud & hybrid strategy",
        ],
        "level_affinities": {"junior": -3, "mid": 3, "senior": 6},
        "focus_areas": ["Infrastructure as Code", "Container orchestration", "Observability & alerting"],
        "probing": ["Cloud cost optimization", "Security hardening", "Disaster recovery planning"],
    },
    {
        "role": "Data Engineer",
        "core":  ["python", "sql", "spark", "airflow"],
        "bonus": ["kafka", "hadoop", "aws", "dbt", "snowflake", "databricks",
                  "docker", "postgresql", "bigquery", "redshift",
                  "pandas", "scala", "gcp", "azure"],
        "project_signals": [
            "pipeline", "etl", "ingestion", "warehouse", "lake", "batch",
            "streaming", "transform", "orchestrate", "schedule", "data flow",
            "partitioning", "schema", "migration", "dbt", "snowflake",
            "databricks", "kafka", "spark", "large-scale", "terabyte",
            "airflow", "dag", "incremental",
        ],
        "next_skills": [
            "dbt (data build tool) for transformations",
            "Databricks / Delta Lake table format",
            "Stream processing (Kafka Streams / Flink)",
            "Data quality (Great Expectations / Soda)",
            "Iceberg / Hudi open table formats",
        ],
        "level_affinities": {"junior": -3, "mid": 3, "senior": 5},
        "focus_areas": ["Data pipeline design", "ETL / ELT processes", "Data warehouse modeling"],
        "probing": ["Stream processing trade-offs", "Data quality & validation", "Pipeline orchestration patterns"],
    },
    {
        "role": "Analytics Engineer",
        "core":  ["sql", "python", "dbt", "snowflake"],
        "bonus": ["bigquery", "redshift", "tableau", "looker", "power bi",
                  "pandas", "airflow", "postgresql", "spark", "aws",
                  "databricks", "r"],
        "project_signals": [
            "analytics", "reporting", "dashboard", "metrics", "kpi", "insight",
            "business intelligence", "data model", "transformation", "dbt",
            "dimension", "fact table", "star schema", "warehouse", "visualization",
            "stakeholder", "product analytics", "funnel", "retention", "cohort",
        ],
        "next_skills": [
            "dbt advanced patterns (tests, macros, packages)",
            "Semantic layer tools (Cube.js / MetricFlow)",
            "LookML for Looker dashboards",
            "Reverse ETL (Census / Hightouch)",
            "Experimentation platform design",
        ],
        "level_affinities": {"junior": 0, "mid": 5, "senior": 3},
        "focus_areas": ["Data modeling & transformation", "SQL performance & optimization", "Business metrics definition"],
        "probing": ["Slowly changing dimensions (SCD)", "Metric consistency across teams", "Semantic layer trade-offs"],
    },
    {
        "role": "Mobile Developer",
        "core":  ["react native", "flutter", "ios", "android", "swift", "kotlin"],
        "bonus": ["typescript", "firebase", "redux", "rest api", "git",
                  "javascript", "graphql", "aws"],
        "project_signals": [
            "mobile", "app", "ios", "android", "native", "flutter", "react native",
            "push notification", "offline", "sync", "store", "play store",
            "gesture", "animation", "navigation", "background", "widget",
            "biometric", "camera", "location",
        ],
        "next_skills": [
            "Advanced animations (React Native Reanimated / Lottie)",
            "CI/CD for mobile (Fastlane / Bitrise)",
            "Native module bridging (iOS + Android)",
            "App performance profiling (Flipper)",
            "State management (Zustand / Jotai / TanStack Query)",
        ],
        "level_affinities": {"junior": 3, "mid": 3, "senior": 2},
        "focus_areas": ["Mobile UI/UX implementation", "Platform-specific APIs", "Offline & sync patterns"],
        "probing": ["App performance profiling", "Push notifications & background processing", "App Store / Play Store deployment"],
    },
    {
        "role": "QA / SDET Engineer",
        "core":  ["selenium", "python", "jest", "cypress"],
        "bonus": ["playwright", "pytest", "junit", "postman", "rest api",
                  "docker", "ci/cd", "javascript", "typescript", "java",
                  "git", "sql"],
        "project_signals": [
            "test", "qa", "quality", "automation", "end-to-end", "e2e",
            "unit test", "integration test", "load test", "performance test",
            "selenium", "cypress", "playwright", "coverage", "regression",
            "bug", "defect", "test plan", "test suite", "mocking",
        ],
        "next_skills": [
            "Playwright for modern E2E testing",
            "Contract testing (Pact)",
            "Load & performance testing (k6 / Locust)",
            "Test observability & flaky test tracking",
            "Shift-left security testing (DAST/SAST)",
        ],
        "level_affinities": {"junior": 3, "mid": 3, "senior": 2},
        "focus_areas": ["Test strategy & pyramid", "API & E2E automation frameworks", "Performance & load testing"],
        "probing": ["Test coverage philosophy", "Flaky test management", "Shift-left testing practices"],
    },
    {
        "role": "Security Engineer",
        "core":  ["python", "linux", "oauth", "jwt", "docker"],
        "bonus": ["aws", "kubernetes", "selenium", "postman", "rest api",
                  "docker", "ci/cd", "git", "bash", "postgresql"],
        "project_signals": [
            "security", "vulnerability", "penetration", "audit", "compliance",
            "encryption", "authentication", "authorization", "oauth", "jwt",
            "threat", "firewall", "hardening", "incident", "forensic",
            "secure", "hashing", "token", "access control", "rbac",
            "ssl", "tls", "certificate",
        ],
        "next_skills": [
            "SIEM platforms (Splunk / Elastic SIEM)",
            "Cloud security posture (AWS GuardDuty / Security Hub)",
            "Threat modeling (STRIDE methodology)",
            "Container security (Falco / Trivy)",
            "Bug bounty & responsible disclosure practice",
        ],
        "level_affinities": {"junior": -3, "mid": 2, "senior": 6},
        "focus_areas": ["Threat modeling & risk assessment", "Secure SDLC practices", "Identity & access management"],
        "probing": ["Zero-trust architecture design", "Incident response playbooks", "Secure API design patterns"],
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _display_skill(skill_lower: str, original_skills: list[str]) -> str:
    """Return original-cased skill name if available, else title-case."""
    lookup = {s.lower(): s for s in original_skills}
    return lookup.get(skill_lower, skill_lower.title())


def _score_role(
    skills_lower: set[str],
    role_def: dict,
    analysis: ResumeAnalysis,
) -> tuple[int, list[str], list[str], int]:
    """
    Multi-dimensional score.
    Returns: (raw_score, core_hits, bonus_hits, project_bonus)
    """
    # 1. Core coverage (0–55)
    core_hits = [c for c in role_def["core"] if c in skills_lower]
    core_score = round((len(core_hits) / max(len(role_def["core"]), 1)) * 55)

    # 2. Bonus coverage (0–20)
    bonus_hits = [b for b in role_def["bonus"] if b in skills_lower]
    bonus_score = round((len(bonus_hits) / max(len(role_def["bonus"]), 1)) * 20)

    # 3. Project evidence (0–18: up to 3 pts per project, capped)
    signals = role_def.get("project_signals", [])
    project_bonus = 0
    if signals and analysis.projects:
        for proj in analysis.projects:
            proj_text = " ".join([
                proj.name,
                " ".join(proj.technologies),
                proj.summary,
                " ".join(proj.description) if proj.description else "",
            ]).lower()
            hits = sum(1 for sig in signals if sig in proj_text)
            project_bonus += min(hits, 3) * 3   # max +9 per project
        project_bonus = min(project_bonus, 18)

    # 4. Experience affinity (−5..+6)
    affinities = role_def.get("level_affinities", {"junior": 0, "mid": 2, "senior": 3})
    exp_bonus = affinities.get(analysis.experience_level, 0)

    # 5. Skill breadth bonus (0 / 3 / 6)
    total_defined = len(role_def["core"]) + len(role_def["bonus"])
    total_matched = len(core_hits) + len(bonus_hits)
    breadth = total_matched / max(total_defined, 1)
    breadth_bonus = 6 if breadth >= 0.65 else (3 if breadth >= 0.40 else 0)

    raw = core_score + bonus_score + project_bonus + exp_bonus + breadth_bonus
    return raw, core_hits, bonus_hits, project_bonus


def _calibrate(raw: int, candidate_id: str, role_name: str) -> int:
    """
    Map raw 0–~104 to believable 65–91 range.
    Deterministic ±3 jitter so identical skills give varied scores across roles.
    """
    ratio = min(raw / 93.0, 1.0)
    base = round(65 + ratio * 26)
    seed_str = (candidate_id + role_name)[:14]
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(seed_str))
    jitter = (seed % 7) - 3   # −3 to +3
    return max(65, min(91, base + jitter))


def _relevant_projects(role_def: dict, analysis: ResumeAnalysis) -> list[str]:
    """Return names of projects with ≥1 signal match for this role."""
    signals = role_def.get("project_signals", [])
    names = []
    for proj in analysis.projects:
        text = (proj.name + " " + " ".join(proj.technologies) + " " + proj.summary).lower()
        if any(sig in text for sig in signals[:20]):
            names.append(proj.name)
    return names


def _build_evidence(
    role_def: dict,
    core_hits: list[str],
    bonus_hits: list[str],
    analysis: ResumeAnalysis,
    exp_bonus: int,
    project_bonus: int,
) -> list[str]:
    """Build 3–5 specific evidence bullet points."""
    evidence = []

    # Core skill match
    if core_hits:
        disp = [_display_skill(c, analysis.skills) for c in core_hits[:4]]
        coverage_pct = round(len(core_hits) / len(role_def["core"]) * 100)
        evidence.append(
            f"Core skills: {', '.join(disp)}"
            + (f" ({coverage_pct}% coverage)" if coverage_pct < 100 else " (full coverage)")
        )

    # Supporting / bonus skills
    if len(bonus_hits) >= 2:
        disp = [_display_skill(b, analysis.skills) for b in bonus_hits[:3]]
        evidence.append(f"Ecosystem depth: {', '.join(disp)}")

    # Project evidence
    if project_bonus >= 6:
        proj_names = _relevant_projects(role_def, analysis)
        if proj_names:
            joined = ", ".join(f'"{n}"' for n in proj_names[:2])
            evidence.append(f"Project evidence: {joined} demonstrates applied {role_def['role']} work")

    # Experience level
    if exp_bonus >= 4:
        evidence.append(
            f"{analysis.experience_level.title()} experience level aligns with this role's seniority demands"
        )
    elif exp_bonus <= -3:
        evidence.append(
            f"Growth opportunity — this role typically expects more seniority than {analysis.experience_level}"
        )

    # Breadth signal
    total_matched = len(core_hits) + len(bonus_hits)
    total_defined = len(role_def["core"]) + len(role_def["bonus"])
    if total_matched >= 0.65 * total_defined and len(evidence) < 4:
        evidence.append("Broad skill coverage across the full role skill profile")

    return evidence[:5]


def _build_reason(
    role_def: dict,
    core_hits: list[str],
    bonus_hits: list[str],
    analysis: ResumeAnalysis,
    project_bonus: int,
) -> str:
    """Generate a 2-sentence dynamic, evidence-based reason."""
    role = role_def["role"]

    if not core_hits:
        ns = role_def["next_skills"][0] if role_def.get("next_skills") else "core skills"
        return (
            f"Your background has transferable elements relevant to {role}, though "
            f"core technical skills still need development. "
            f"Building {ns} would be the highest-impact next step."
        )

    # Sentence 1 — core match quality
    core_disp = [_display_skill(c, analysis.skills) for c in core_hits[:3]]
    coverage = len(core_hits) / len(role_def["core"])
    if coverage >= 0.80:
        s1 = (
            f"Excellent core-skill alignment with {', '.join(core_disp)}"
            f" — covering {round(coverage * 100)}% of the fundamental {role} skill set."
        )
    else:
        s1 = (
            f"Solid foundation in {', '.join(core_disp)}"
            f" provides a strong entry point for {role} roles."
        )

    # Sentence 2 — project / bonus / gap evidence
    proj_names = _relevant_projects(role_def, analysis)
    if project_bonus >= 9 and proj_names:
        s2 = (
            f"Project work on '{proj_names[0]}' demonstrates hands-on experience "
            f"directly relevant to {role} responsibilities."
        )
    elif len(bonus_hits) >= 2:
        bonus_disp = [_display_skill(b, analysis.skills) for b in bonus_hits[:2]]
        s2 = (
            f"Supporting experience with {', '.join(bonus_disp)} "
            f"further strengthens the fit for this role."
        )
    elif role_def.get("next_skills"):
        ns = role_def["next_skills"][0]
        s2 = (
            f"Adding {ns} experience would meaningfully close the gap "
            f"to a highly competitive {role} profile."
        )
    else:
        s2 = f"Continuing to build domain depth will sharpen this {role} profile."

    return f"{s1} {s2}"


def _build_boosted_by(
    role_def: dict,
    core_hits: list[str],
    bonus_hits: list[str],
    analysis: ResumeAnalysis,
    project_bonus: int,
    exp_bonus: int,
) -> list[str]:
    """Up to 4 specific signals that raised the score."""
    boosted = []

    if len(core_hits) >= len(role_def["core"]) * 0.6:
        boosted.append(
            f"{len(core_hits)}/{len(role_def['core'])} core skills matched"
        )
    if bonus_hits:
        top = [_display_skill(b, analysis.skills) for b in bonus_hits[:3]]
        boosted.append(f"{', '.join(top)}")
    if project_bonus >= 9:
        proj_names = _relevant_projects(role_def, analysis)
        if proj_names:
            boosted.append(f"Project: {proj_names[0]}")
    if exp_bonus >= 4:
        boosted.append(f"{analysis.experience_level.title()}-level experience")
    if analysis.certifications:
        cert = analysis.certifications[0].name
        boosted.append(f"Certification: {cert[:40]}")

    return boosted[:4]


def _build_reduced_by(
    role_def: dict,
    core_hits: list[str],
    analysis: ResumeAnalysis,
    exp_bonus: int,
) -> list[str]:
    """Up to 3 factors that limited the score."""
    reduced = []

    core_missing = [c for c in role_def["core"] if c not in set(core_hits)]
    if len(core_missing) >= 2:
        miss_disp = [c.title() for c in core_missing[:2]]
        reduced.append(f"Missing core skills: {', '.join(miss_disp)}")
    elif len(core_missing) == 1:
        reduced.append(f"Missing core skill: {core_missing[0].title()}")

    if not analysis.projects:
        reduced.append("No project portfolio to evidence practical application")

    if exp_bonus <= -3:
        reduced.append(
            f"{analysis.experience_level.title()} level — role typically expects more seniority"
        )

    return reduced[:3]


def _build_missing_skills(role_def: dict, skills_lower: set[str]) -> list[str]:
    """
    Return next_skills entries the candidate likely doesn't already have.
    Checks by scanning key words (≥ 5 chars) from each suggestion against
    the candidate's skill set.
    """
    missing = []
    for ns in role_def.get("next_skills", []):
        words = re.sub(r"[^\w\s\.\-]", " ", ns.lower()).split()
        key_words = [w for w in words if len(w) >= 5]
        covered = any(
            any(kw[:6] in sk or sk[:6] in kw for sk in skills_lower)
            for kw in key_words
        )
        if not covered:
            missing.append(ns)
        if len(missing) >= 4:
            break
    return missing


# ── Public API ────────────────────────────────────────────────────────────────

def recommend(analysis: ResumeAnalysis) -> RoleRecommendationResponse:
    """
    Score all 12 role definitions, calibrate, attach evidence, return top 5.
    """
    skills_lower = {s.lower() for s in analysis.skills}
    scored: list[RoleMatch] = []

    for rd in _ROLES:
        raw, core_hits, bonus_hits, project_bonus = _score_role(
            skills_lower, rd, analysis
        )

        # Minimum threshold: at least one core skill OR strong project evidence
        if not core_hits and project_bonus < 9:
            continue
        if raw < 10:
            continue

        score = _calibrate(raw, analysis.candidate_id, rd["role"])

        level = analysis.experience_level
        exp_bonus = rd.get("level_affinities", {}).get(level, 0)

        evidence = _build_evidence(rd, core_hits, bonus_hits, analysis, exp_bonus, project_bonus)
        reason   = _build_reason(rd, core_hits, bonus_hits, analysis, project_bonus)
        boosted  = _build_boosted_by(rd, core_hits, bonus_hits, analysis, project_bonus, exp_bonus)
        reduced  = _build_reduced_by(rd, core_hits, analysis, exp_bonus)
        missing  = _build_missing_skills(rd, skills_lower)

        # Build project deep-dive areas for interview use
        project_areas = []
        for p in analysis.projects[:2]:
            techs = ", ".join(p.technologies[:4]) if p.technologies else "architecture and trade-offs"
            project_areas.append(f"{p.name}: probe {techs}")

        scored.append(RoleMatch(
            role=rd["role"],
            match_score=score,
            confidence=score,
            reason=reason,
            focus_areas=rd["focus_areas"],
            weak_areas_to_probe=rd["probing"],
            interview_focus_areas=rd["focus_areas"],
            project_deep_dive_areas=project_areas,
            evidence=evidence,
            boosted_by=boosted,
            reduced_by=reduced,
            missing_skills=missing,
        ))

    scored.sort(key=lambda r: r.match_score, reverse=True)

    # Assign 1-based ranks
    for i, r in enumerate(scored):
        r.rank = i + 1

    # Guarantee at least 2 results (edge case: very thin or unusual resume)
    if len(scored) == 0:
        scored.append(RoleMatch(
            role="Software Developer",
            match_score=68,
            confidence=68,
            reason=(
                "General software development aptitude detected across the resume. "
                "Focusing on a specialisation — frontend, backend, data, or ML — "
                "would unlock more precise role recommendations."
            ),
            focus_areas=["Problem solving & clean code", "Algorithm fundamentals", "Version control & collaboration"],
            interview_focus_areas=["Problem solving & clean code", "Algorithm fundamentals", "Version control & collaboration"],
            project_deep_dive_areas=[],
            weak_areas_to_probe=["System design basics", "Testing strategy", "Cloud platform awareness"],
            evidence=["Technical background present"],
            boosted_by=[],
            reduced_by=["No dominant technical domain cluster found"],
            missing_skills=["Choose a specialisation: frontend, backend, data, or ML/AI"],
            rank=1,
        ))
    if len(scored) == 1:
        scored.append(RoleMatch(
            role="Technical Support Engineer",
            match_score=65,
            confidence=65,
            reason=(
                "Technical background is well-suited for debugging, documentation, "
                "and customer-facing engineering support roles."
            ),
            focus_areas=["Debugging & root-cause analysis", "Technical documentation", "Customer empathy"],
            interview_focus_areas=["Debugging & root-cause analysis", "Technical documentation", "Customer empathy"],
            project_deep_dive_areas=[],
            weak_areas_to_probe=["Automation scripting", "Network fundamentals", "Cloud service basics"],
            evidence=["Technical aptitude inferred from resume"],
            boosted_by=[],
            reduced_by=[],
            missing_skills=["Scripting automation (Python / Bash)", "ITIL / SRE fundamentals", "Monitoring tools (Datadog / PagerDuty)"],
            rank=2,
        ))

    return RoleRecommendationResponse(
        candidate_id=analysis.candidate_id,
        recommended_roles=scored[:5],
    )
