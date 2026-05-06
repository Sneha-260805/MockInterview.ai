"""Rule-based role recommendation from a ResumeAnalysis object."""

from models.analysis import ResumeAnalysis, RoleMatch, RoleRecommendationResponse

_ROLES = [
    {
        "role": "Frontend Developer",
        "core": ["javascript", "html", "css", "react", "typescript"],
        "bonus": ["next.js", "vue.js", "angular", "tailwind css", "tailwind", "redux", "webpack", "jest"],
        "focus_areas": ["Component architecture & state management", "CSS & responsive design", "Browser performance"],
        "probing": ["Unit / integration testing (Jest, RTL)", "Accessibility (WCAG)", "Bundle optimization"],
        "tpl": "Resume shows {matched} with a frontend-focused skill set.",
    },
    {
        "role": "Full Stack Developer",
        "core": ["javascript", "react", "python", "sql", "node.js"],
        "bonus": ["typescript", "docker", "postgresql", "mongodb", "redis", "aws", "fastapi", "django"],
        "focus_areas": ["React & component design", "REST API development", "Database modeling"],
        "probing": ["System design & scalability", "CI/CD pipelines", "Caching strategies"],
        "tpl": "Resume demonstrates {matched} spanning both frontend and backend layers.",
    },
    {
        "role": "Backend Developer",
        "core": ["python", "java", "node.js", "sql", "rest api"],
        "bonus": ["docker", "redis", "kafka", "postgresql", "mongodb", "microservices", "grpc"],
        "focus_areas": ["API design & REST principles", "Database query optimization", "Concurrency & threading"],
        "probing": ["Microservices architecture", "Message queues", "Auth & authorization patterns"],
        "tpl": "Resume highlights {matched} indicating strong server-side experience.",
    },
    {
        "role": "Data Scientist",
        "core": ["python", "pandas", "numpy", "machine learning", "sql"],
        "bonus": ["scikit-learn", "tensorflow", "pytorch", "r", "tableau", "spark"],
        "focus_areas": ["Statistical modeling & hypothesis testing", "Feature engineering", "Model evaluation"],
        "probing": ["Production model deployment", "Data pipeline design", "A/B testing methodology"],
        "tpl": "Resume shows {matched} aligned with data science workflows.",
    },
    {
        "role": "ML / AI Engineer",
        "core": ["python", "tensorflow", "pytorch", "machine learning", "deep learning"],
        "bonus": ["keras", "scikit-learn", "docker", "aws", "fastapi", "nlp", "computer vision", "llm"],
        "focus_areas": ["Model training & fine-tuning", "MLOps & experiment tracking", "Inference optimization"],
        "probing": ["Distributed training", "Model serving at scale", "Feature stores & data versioning"],
        "tpl": "Resume indicates {matched} reflecting ML/AI engineering capability.",
    },
    {
        "role": "DevOps / Cloud Engineer",
        "core": ["docker", "kubernetes", "aws", "linux", "ci/cd"],
        "bonus": ["terraform", "ansible", "prometheus", "grafana", "jenkins", "azure", "gcp", "bash"],
        "focus_areas": ["Infrastructure as Code", "Container orchestration", "Observability & alerting"],
        "probing": ["Cloud cost optimization", "Security hardening", "Disaster recovery planning"],
        "tpl": "Resume highlights {matched} pointing to cloud and infrastructure expertise.",
    },
    {
        "role": "Mobile Developer",
        "core": ["react native", "flutter", "ios", "android", "swift", "kotlin"],
        "bonus": ["typescript", "firebase", "redux", "rest api", "git"],
        "focus_areas": ["Mobile UI/UX implementation", "Platform-specific APIs", "Offline & sync patterns"],
        "probing": ["App performance profiling", "Push notifications", "App Store / Play Store deployment"],
        "tpl": "Resume shows {matched} relevant to mobile application development.",
    },
    {
        "role": "Data Engineer",
        "core": ["python", "sql", "spark", "airflow"],
        "bonus": ["kafka", "hadoop", "aws", "dbt", "snowflake", "databricks", "docker", "postgresql"],
        "focus_areas": ["Data pipeline design", "ETL / ELT processes", "Data warehouse modeling"],
        "probing": ["Stream processing", "Data quality & validation", "Pipeline orchestration patterns"],
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
    score = min(int(raw / max_pts * 100), 95) if max_pts else 0
    return score, core_hits[:3] + bonus_hits[:2]


def _display(matched_lower: list[str], skills: list[str]) -> list[str]:
    sl = {s.lower(): s for s in skills}
    return [sl.get(m, m.title()) for m in matched_lower]


def recommend(analysis: ResumeAnalysis) -> RoleRecommendationResponse:
    skills_lower = {s.lower() for s in analysis.skills}
    scored: list[RoleMatch] = []

    for rd in _ROLES:
        score, matched = _score(skills_lower, rd)
        if score < 10:
            continue
        disp = _display(matched, analysis.skills)
        reason = rd["tpl"].format(
            matched=", ".join(disp[:4]) if disp else "relevant technical skills"
        )
        scored.append(
            RoleMatch(
                role=rd["role"],
                match_score=score,
                reason=reason,
                focus_areas=rd["focus_areas"],
                weak_areas_to_probe=rd["probing"],
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
            )
        )

    return RoleRecommendationResponse(
        candidate_id=analysis.candidate_id,
        recommended_roles=scored[:5],
    )
