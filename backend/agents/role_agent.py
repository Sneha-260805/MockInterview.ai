"""
Role recommendation agent.
Rule-based scoring with evidence-backed, explainable output.
Works without an LLM key; LLM layer can enhance further via llm_service.py.
"""

from models.analysis import ResumeAnalysis, RoleMatch, RoleRecommendationResponse

_ROLES = [
    {
        "role": "Frontend Developer",
        "core": ["javascript", "html", "css", "react", "typescript"],
        "bonus": ["next.js", "vue.js", "angular", "tailwind css", "tailwind", "redux", "webpack", "jest"],
        "focus_areas": ["Component architecture & state management", "CSS & responsive design", "Browser performance"],
        "probing": ["Unit / integration testing (Jest, RTL)", "Accessibility (WCAG)", "Bundle optimization"],
        "evidence_signals": {
            "skills": ["React", "JavaScript", "TypeScript", "CSS", "HTML", "Next.js", "Redux"],
            "keywords": ["component", "frontend", "ui", "interface", "responsive", "css", "dom"],
        },
        "gap_checks": [
            ("jest", "cypress", "playwright", "Unit/integration testing not mentioned"),
            ("typescript",),                                        # single-tuple = single skill
            ("docker", "kubernetes", "aws", "azure", "gcp"),
        ],
        "gap_labels": [
            "Testing frameworks (Jest, Cypress) not mentioned",
            "TypeScript not listed — increasingly required",
            "No deployment/cloud experience visible",
        ],
        "tpl": "Resume shows {matched} with a frontend-focused skill set.",
    },
    {
        "role": "Full Stack Developer",
        "core": ["javascript", "react", "python", "sql", "node.js"],
        "bonus": ["typescript", "docker", "postgresql", "mongodb", "redis", "aws", "fastapi", "django"],
        "focus_areas": ["React & component design", "REST API development", "Database modeling"],
        "probing": ["System design & scalability", "CI/CD pipelines", "Caching strategies"],
        "evidence_signals": {
            "skills": ["React", "Node.js", "Python", "SQL", "MongoDB", "PostgreSQL", "JavaScript"],
            "keywords": ["full stack", "fullstack", "mern", "mean", "frontend", "backend", "api"],
        },
        "gap_checks": [
            ("docker", "kubernetes"),
            ("jest", "pytest", "cypress"),
            ("aws", "azure", "gcp", "google cloud"),
        ],
        "gap_labels": [
            "Containerisation (Docker/Kubernetes) not mentioned",
            "No testing framework listed",
            "Cloud deployment experience not visible",
        ],
        "tpl": "Resume demonstrates {matched} spanning both frontend and backend layers.",
    },
    {
        "role": "Backend Developer",
        "core": ["python", "java", "node.js", "sql", "rest api"],
        "bonus": ["docker", "redis", "kafka", "postgresql", "mongodb", "microservices", "grpc"],
        "focus_areas": ["API design & REST principles", "Database query optimization", "Concurrency & threading"],
        "probing": ["Microservices architecture", "Message queues", "Auth & authorization patterns"],
        "evidence_signals": {
            "skills": ["Python", "Java", "Node.js", "SQL", "PostgreSQL", "MongoDB", "REST API"],
            "keywords": ["api", "server", "backend", "database", "endpoint", "rest", "service"],
        },
        "gap_checks": [
            ("docker", "kubernetes"),
            ("redis", "kafka", "rabbitmq"),
            ("jest", "pytest", "junit"),
        ],
        "gap_labels": [
            "Containerisation (Docker/Kubernetes) not mentioned",
            "Caching / message queue experience not visible",
            "No testing framework listed",
        ],
        "tpl": "Resume highlights {matched} indicating strong server-side experience.",
    },
    {
        "role": "Data Scientist",
        "core": ["python", "pandas", "numpy", "machine learning", "sql"],
        "bonus": ["scikit-learn", "tensorflow", "pytorch", "r", "tableau", "spark"],
        "focus_areas": ["Statistical modeling & hypothesis testing", "Feature engineering", "Model evaluation"],
        "probing": ["Production model deployment", "Data pipeline design", "A/B testing methodology"],
        "evidence_signals": {
            "skills": ["Python", "Pandas", "NumPy", "Scikit-learn", "Machine Learning", "SQL", "R"],
            "keywords": ["model", "dataset", "analysis", "prediction", "classification", "regression"],
        },
        "gap_checks": [
            ("docker", "mlflow", "airflow"),
            ("tensorflow", "pytorch"),
            ("tableau", "power bi", "looker"),
        ],
        "gap_labels": [
            "MLOps / model deployment tooling not visible",
            "Deep learning framework (TensorFlow/PyTorch) not listed",
            "Data visualisation tools not mentioned",
        ],
        "tpl": "Resume shows {matched} aligned with data science workflows.",
    },
    {
        "role": "ML / AI Engineer",
        "core": ["python", "tensorflow", "pytorch", "machine learning", "deep learning"],
        "bonus": ["keras", "scikit-learn", "docker", "aws", "fastapi", "nlp", "computer vision", "llm"],
        "focus_areas": ["Model training & fine-tuning", "MLOps & experiment tracking", "Inference optimization"],
        "probing": ["Distributed training", "Model serving at scale", "Feature stores & data versioning"],
        "evidence_signals": {
            "skills": ["TensorFlow", "PyTorch", "Machine Learning", "Deep Learning", "NLP", "LLM"],
            "keywords": ["neural network", "training", "inference", "model", "gpu", "fine-tuning"],
        },
        "gap_checks": [
            ("docker", "kubernetes"),
            ("mlflow", "wandb", "airflow"),
            ("fastapi", "flask", "django"),
        ],
        "gap_labels": [
            "Container/orchestration experience not visible",
            "Experiment tracking (MLflow/W&B) not mentioned",
            "Model serving API framework not listed",
        ],
        "tpl": "Resume indicates {matched} reflecting ML/AI engineering capability.",
    },
    {
        "role": "DevOps / Cloud Engineer",
        "core": ["docker", "kubernetes", "aws", "linux", "ci/cd"],
        "bonus": ["terraform", "ansible", "prometheus", "grafana", "jenkins", "azure", "gcp", "bash"],
        "focus_areas": ["Infrastructure as Code", "Container orchestration", "Observability & alerting"],
        "probing": ["Cloud cost optimization", "Security hardening", "Disaster recovery planning"],
        "evidence_signals": {
            "skills": ["Docker", "Kubernetes", "AWS", "Azure", "GCP", "Terraform", "Jenkins", "Linux"],
            "keywords": ["pipeline", "deployment", "infrastructure", "ci", "cd", "devops", "cloud"],
        },
        "gap_checks": [
            ("terraform", "ansible", "pulumi"),
            ("prometheus", "grafana", "datadog"),
            ("python", "bash", "go"),
        ],
        "gap_labels": [
            "Infrastructure as Code tooling (Terraform/Ansible) not listed",
            "Observability tools (Prometheus/Grafana) not mentioned",
            "Scripting language for automation not visible",
        ],
        "tpl": "Resume highlights {matched} pointing to cloud and infrastructure expertise.",
    },
    {
        "role": "Mobile Developer",
        "core": ["react native", "flutter", "ios", "android", "swift", "kotlin"],
        "bonus": ["typescript", "firebase", "redux", "rest api", "git"],
        "focus_areas": ["Mobile UI/UX implementation", "Platform-specific APIs", "Offline & sync patterns"],
        "probing": ["App performance profiling", "Push notifications", "App Store / Play Store deployment"],
        "evidence_signals": {
            "skills": ["React Native", "Flutter", "iOS", "Android", "Swift", "Kotlin"],
            "keywords": ["mobile", "app", "ios", "android", "native", "flutter"],
        },
        "gap_checks": [
            ("jest", "detox", "espresso"),
            ("firebase", "aws", "gcp"),
            ("typescript",),
        ],
        "gap_labels": [
            "Mobile testing framework not mentioned",
            "Backend/cloud integration experience not listed",
            "TypeScript not listed for React Native",
        ],
        "tpl": "Resume shows {matched} relevant to mobile application development.",
    },
    {
        "role": "Data Engineer",
        "core": ["python", "sql", "spark", "airflow"],
        "bonus": ["kafka", "hadoop", "aws", "dbt", "snowflake", "databricks", "docker", "postgresql"],
        "focus_areas": ["Data pipeline design", "ETL / ELT processes", "Data warehouse modeling"],
        "probing": ["Stream processing", "Data quality & validation", "Pipeline orchestration patterns"],
        "evidence_signals": {
            "skills": ["Python", "SQL", "Spark", "Airflow", "Kafka", "dbt", "Snowflake"],
            "keywords": ["pipeline", "etl", "data warehouse", "batch", "stream", "ingestion"],
        },
        "gap_checks": [
            ("kafka", "kinesis", "pubsub"),
            ("dbt", "great expectations"),
            ("docker", "kubernetes"),
        ],
        "gap_labels": [
            "Stream processing tools (Kafka/Kinesis) not listed",
            "Data quality tooling (dbt, Great Expectations) not mentioned",
            "Containerisation not visible",
        ],
        "tpl": "Resume demonstrates {matched} suited for data engineering roles.",
    },
]

_CORE_W = 15
_BONUS_W = 7


def _score(skills_lower: set[str], role_def: dict) -> tuple[int, list[str]]:
    core_hits = [c for c in role_def["core"] if c in skills_lower]
    bonus_hits = [b for b in role_def["bonus"] if b in skills_lower]
    max_pts = len(role_def["core"]) * _CORE_W + len(role_def["bonus"]) * _BONUS_W
    raw = len(core_hits) * _CORE_W + len(bonus_hits) * _BONUS_W
    score = min(int(raw / max_pts * 100), 100) if max_pts else 0
    return score, core_hits[:3] + bonus_hits[:2]


def _display(matched_lower: list[str], skills: list[str]) -> list[str]:
    sl = {s.lower(): s for s in skills}
    return [sl.get(m, m.title()) for m in matched_lower]


def _determine_role_type(score: int) -> str:
    if score >= 60:
        return "realistic"
    if score >= 35:
        return "stretch"
    return "aspirational"


def _build_resume_evidence(
    role_def: dict, skills: list[str], projects: list, text_lower: str
) -> list[str]:
    """Extract specific resume evidence that supports this role recommendation."""
    evidence: list[str] = []
    skills_lower = {s.lower() for s in skills}

    # Matched high-value skills
    matched_signals = [
        s for s in role_def["evidence_signals"]["skills"]
        if s.lower() in skills_lower
    ]
    for skill in matched_signals[:3]:
        evidence.append(f"{skill} listed in skills")

    # Keyword evidence from resume text
    for kw in role_def["evidence_signals"]["keywords"]:
        if kw in text_lower:
            evidence.append(f'Resume mentions "{kw}"')
            break  # one keyword evidence is enough

    # Project evidence
    for project in projects[:2]:
        p_techs_lower = {t.lower() for t in project.technologies}
        role_core_lower = set(role_def["core"]) | set(role_def["bonus"])
        overlap = p_techs_lower & role_core_lower
        if overlap:
            evidence.append(f"{project.name} project uses {', '.join(list(overlap)[:2])}")

    return evidence[:5] if evidence else ["General technical skills aligned with role requirements"]


def _build_gaps(role_def: dict, skills_lower: set[str]) -> list[str]:
    """Return human-readable gaps for this role."""
    gaps: list[str] = []
    checks = role_def.get("gap_checks", [])
    labels = role_def.get("gap_labels", [])

    for i, check in enumerate(checks):
        if not any(c in skills_lower for c in check):
            label = labels[i] if i < len(labels) else f"Missing: {', '.join(check)}"
            gaps.append(label)

    return gaps[:3]


def _build_why_fit(role: str, matched_display: list[str], score: int, level: str) -> str:
    """Plain-language explanation of why this role fits the candidate."""
    skill_str = ", ".join(matched_display[:4]) if matched_display else "relevant technical skills"
    level_adj = {"junior": "entry-level", "mid": "mid-level", "senior": "senior"}.get(level, "")
    level_clause = f" as a {level_adj} candidate" if level_adj else ""

    if score >= 80:
        return (
            f"Strong match for {role}{level_clause}. "
            f"Candidate demonstrates {skill_str} — covering the core requirements directly. "
            f"Interview should focus on depth and system design."
        )
    if score >= 60:
        return (
            f"Good match for {role}{level_clause}. "
            f"Key skills {skill_str} align well with the role. "
            f"Some gaps exist but the foundational competency is present."
        )
    if score >= 35:
        return (
            f"Stretch opportunity for {role}{level_clause}. "
            f"{skill_str} provides a starting point, but significant gaps remain. "
            f"Targeted upskilling would make this role achievable."
        )
    return (
        f"Aspirational goal for {role}{level_clause}. "
        f"Current skills show limited overlap with core requirements. "
        f"A structured learning plan is recommended before targeting this role."
    )


def recommend(analysis: ResumeAnalysis, raw_text: str = "") -> RoleRecommendationResponse:
    skills_lower = {s.lower() for s in analysis.skills}
    text_lower = raw_text.lower() if raw_text else " ".join(analysis.skills).lower()
    scored: list[RoleMatch] = []

    for rd in _ROLES:
        score, matched = _score(skills_lower, rd)
        if score < 10:
            continue
        disp = _display(matched, analysis.skills)
        reason = rd["tpl"].format(
            matched=", ".join(disp[:4]) if disp else "relevant technical skills"
        )
        role_type = _determine_role_type(score)
        why_fit = _build_why_fit(rd["role"], disp, score, analysis.experience_level)
        resume_evidence = _build_resume_evidence(rd, analysis.skills, analysis.projects, text_lower)
        gaps = _build_gaps(rd, skills_lower)

        scored.append(
            RoleMatch(
                role=rd["role"],
                match_score=score,
                reason=reason,
                focus_areas=rd["focus_areas"],
                weak_areas_to_probe=rd["probing"],
                role_type=role_type,
                why_fit=why_fit,
                resume_evidence=resume_evidence,
                gaps=gaps,
            )
        )

    scored.sort(key=lambda r: r.match_score, reverse=True)

    # Guarantee at least 2 results
    if len(scored) == 0:
        scored.append(
            RoleMatch(
                role="Software Developer",
                match_score=50,
                reason="General software development skills detected across the resume.",
                focus_areas=["Problem solving", "Clean code practices", "Algorithm fundamentals"],
                weak_areas_to_probe=["System design", "Testing strategy", "Cloud platform basics"],
                role_type="realistic",
                why_fit="Candidate has general software development skills. A broader skill assessment will be needed to identify a specific specialisation.",
                resume_evidence=["Technical skills present in resume"],
                gaps=["Specialised domain skills not clearly demonstrated", "Project evidence limited"],
            )
        )
    if len(scored) == 1:
        scored.append(
            RoleMatch(
                role="Technical Support Engineer",
                match_score=40,
                reason="Technical background is well-suited for support, debugging, and documentation roles.",
                focus_areas=["Debugging & root-cause analysis", "Technical documentation", "Customer empathy"],
                weak_areas_to_probe=["Automation scripting", "Network fundamentals", "Cloud service basics"],
                role_type="stretch",
                why_fit="Technical background provides a foundation for support engineering, though hands-on product development experience would strengthen the candidacy.",
                resume_evidence=["Technical skills visible in resume"],
                gaps=["Customer-facing experience not mentioned", "Support tooling not listed"],
            )
        )

    return RoleRecommendationResponse(
        candidate_id=analysis.candidate_id,
        recommended_roles=scored[:5],
    )
