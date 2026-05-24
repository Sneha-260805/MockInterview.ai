"""
Resume Intelligence Agent.
Rule-based analysis that produces interview-ready intelligence — not just a skill parser.
Works without any LLM key; LLM layer in llm_service.py can enhance the output further.
"""

import re
from models.analysis import ResumeAnalysis, Project, ClaimToVerify, ProjectDeepDive

# ── Skill registry ────────────────────────────────────────────────────────────

_SKILL_LIST = [
    # Frontend
    "React", "Angular", "Vue.js", "Vue", "Next.js", "Nuxt.js", "Gatsby",
    "JavaScript", "TypeScript", "HTML", "CSS", "SASS", "LESS",
    "Tailwind CSS", "Tailwind", "Bootstrap", "Material UI", "Redux",
    "Webpack", "Vite",
    # Backend
    "Node.js", "Express.js", "Express", "Django", "Flask", "FastAPI",
    "Spring Boot", "Spring", "ASP.NET", "Rails", "Laravel",
    "Python", "Java", "C#", "C++", "Go", "Rust", "Ruby", "PHP", "Scala", "Kotlin",
    # Database
    "MySQL", "PostgreSQL", "SQLite", "MongoDB", "Redis", "Elasticsearch",
    "DynamoDB", "Cassandra", "Oracle", "SQL", "NoSQL", "Firebase",
    # Cloud / DevOps
    "AWS", "Azure", "GCP", "Google Cloud",
    "Docker", "Kubernetes", "Jenkins", "GitHub Actions", "GitLab CI",
    "Terraform", "Ansible", "Prometheus", "Grafana", "Nginx",
    "CI/CD", "Linux", "Bash",
    # ML / AI (core frameworks)
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "XGBoost",
    "Pandas", "NumPy", "Matplotlib", "Seaborn",
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "OpenCV", "LangChain", "LLM",
    # ML / AI (modern LLM & NLP stack)
    "HuggingFace", "Hugging Face", "Transformers",
    "BERT", "DistilBERT", "Sentence Transformers",
    "RAG", "Retrieval Augmented Generation",
    "Gemini", "Llama", "LLaMA",
    "Groq API", "Agentic AI", "AI Agents",
    "MLflow", "Weights & Biases",
    # Data Engineering
    "Spark", "Hadoop", "Airflow", "Kafka", "dbt", "Snowflake", "Databricks",
    "Tableau", "Power BI", "Looker", "R",
    # Mobile
    "iOS", "Android", "React Native", "Flutter", "Swift", "Xamarin",
    # Testing
    "Jest", "Pytest", "JUnit", "Selenium", "Cypress", "Playwright",
    # General
    "Git", "GitHub", "REST API", "GraphQL", "gRPC", "Microservices",
    "Agile", "Scrum", "JIRA", "Figma",
]

_SKILLS_MAP: dict[str, str] = {s.lower(): s for s in _SKILL_LIST}

_SECTION_RE = re.compile(
    r"^(?:skills?|technical skills?|core competencies|technologies|"
    r"work experience|experience|employment|professional experience|"
    r"education|academic background|"
    r"projects?|personal projects?|key projects?|academic projects?|"
    r"summary|objective|profile|about(?: me)?|"
    r"certifications?|achievements?|awards?|publications?)[\s:]*$",
    re.IGNORECASE,
)

# ── Domain skill sets (for scoring) ──────────────────────────────────────────

_DOMAIN_SETS = {
    "frontend":  {"javascript", "react", "angular", "vue.js", "vue", "html", "css", "typescript", "next.js"},
    "backend":   {"python", "java", "node.js", "django", "fastapi", "flask", "spring", "express.js", "express", "c#", "go", "rust"},
    "ml":        {
        "tensorflow", "pytorch", "keras", "deep learning", "machine learning",
        "nlp", "computer vision", "huggingface", "hugging face", "transformers",
        "llm", "langchain", "bert", "distilbert", "rag", "sentence transformers",
        "gemini", "llama", "llama", "agentic ai",
    },
    "data":      {"pandas", "numpy", "scikit-learn", "r", "tableau", "statistics", "machine learning"},
    "devops":    {"docker", "kubernetes", "aws", "azure", "gcp", "google cloud", "ci/cd", "terraform", "jenkins"},
    "mobile":    {"ios", "android", "react native", "flutter", "swift", "kotlin"},
    "de":        {"spark", "hadoop", "airflow", "kafka", "dbt", "snowflake", "databricks"},
    "testing":   {"jest", "pytest", "junit", "selenium", "cypress", "playwright"},
    "db":        {"sql", "postgresql", "mysql", "mongodb", "redis"},
    "deployment":{"docker", "kubernetes", "aws", "azure", "gcp", "google cloud", "heroku", "netlify", "vercel"},
}


# ── Private helpers ───────────────────────────────────────────────────────────

def _extract_name(lines: list[str]) -> str:
    email_re = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    phone_re = re.compile(r"[\+\d][\d\s\-().]{7,}")
    url_re = re.compile(r"https?://|www\.", re.IGNORECASE)
    for line in lines[:8]:
        if not line:
            continue
        if email_re.search(line) or phone_re.search(line) or url_re.search(line):
            continue
        if _SECTION_RE.match(line):
            continue
        words = line.split()
        if 1 <= len(words) <= 5 and all(re.match(r"[A-Za-z'\-\.]+$", w) for w in words):
            return line.strip()
    return ""


def _extract_email(text: str) -> str:
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    return m.group(0) if m else ""


def _extract_phone(text: str) -> str:
    m = re.search(r"(\+?1?\s*[\-.]?\s*\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})", text)
    return m.group(0).strip() if m else ""


def _extract_skills(text: str) -> list[str]:
    text_lower = text.lower()
    found: dict[str, str] = {}
    for kw_lower, kw_display in _SKILLS_MAP.items():
        if re.search(r"\b" + re.escape(kw_lower) + r"\b", text_lower):
            found[kw_lower] = kw_display
    return list(found.values())


# Verbs that start resume bullet descriptions — never project titles
_DESC_START_RE = re.compile(
    r"^(built|created|developed|implemented|designed|supervised|fine[\s\-]?tuned|"
    r"benchmarked|used|performed|analyzed|analysed|trained|deployed|integrated|"
    r"optimized|optimised|conducted|applied|worked|led|managed|collaborated|"
    r"researched|engineered|architected|contributed|wrote|generated|evaluated|"
    r"tested|validated|utilized|utilised|leveraged|produced|multi[\s\-]stage|"
    r"composite|achieved|improved|reduced|increased|automated|migrated|"
    r"established|responsible|explored|demonstrated|extracted|preprocessed|"
    r"curated|collected|transformed|predicted|classified|focused|combined|"
    r"enabled|introduced|extended|gathered|processed|compared|evaluated|"
    r"constructed|formulated|proposed|proposed|simulated|calculated|"
    r"tools?\s*:|tech(?:nologies)?\s*:|stack\s*:|languages?\s*:)",
    re.IGNORECASE,
)


def _looks_like_title(line: str) -> bool:
    """Return True if this line looks like a project title rather than a description."""
    words = line.split()
    if not words:
        return False
    # Very long lines are descriptions, not titles
    if len(line) > 120:
        return False
    # Lines with 2+ commas are technology/skill lists → description
    if line.count(",") >= 2:
        return False
    # Action verbs → description (caught earlier, but double-check)
    if _DESC_START_RE.match(line):
        return False
    # Starts with lowercase → description
    if line[0].islower():
        return False
    # Title-case check: >50% of words must start with uppercase
    cap_count = sum(1 for w in words if w and w[0].isupper())
    return (cap_count / len(words)) >= 0.5


def _extract_projects(text: str) -> list[Project]:
    m = re.search(
        r"(?:projects?|personal projects?|key projects?|academic projects?)[:\s\n]+(.*?)"
        r"(?=\n\s*(?:education|experience|skills?|certifications?|awards?|achievements?)\b|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []

    projects: list[Project] = []
    current_name: str | None = None
    current_desc: list[str] = []

    def _flush() -> None:
        nonlocal current_name, current_desc
        if not current_name:
            return
        description = " ".join(current_desc)
        full_lower = (current_name + " " + description).lower()
        techs = [
            _SKILLS_MAP[k]
            for k in _SKILLS_MAP
            if re.search(r"\b" + re.escape(k) + r"\b", full_lower)
        ]
        projects.append(Project(
            name=current_name,
            technologies=techs[:8],
            summary=description[:200] if description else "No description available.",
        ))
        current_name = None
        current_desc = []

    for raw in m.group(1).split("\n"):
        line = raw.strip()
        if not line:
            continue

        # Strip leading bullet/dash markers that PDF extraction may or may not preserve
        clean = re.sub(r"^[•●▪\*]\s*", "", line).strip()
        clean = re.sub(r"^[-–]\s+", "", clean).strip()

        if not clean:
            continue

        # Hyphenation fragment: very short, starts lowercase → merge into last desc line
        if len(clean) < 20 and clean[0].islower():
            if current_desc:
                current_desc[-1] = current_desc[-1].rstrip("-") + clean
            continue

        # Description line: starts with a known action verb or "Tools:"
        # (PDF extraction often strips dashes/indentation so we rely on content)
        if _DESC_START_RE.match(clean):
            if current_name:
                entry = re.sub(r"^[Tt]ools?\s*:\s*", "Tools: ", clean)
                current_desc.append(entry)
            continue

        # Also treat lines that were originally indented/dashed in the raw text as desc
        if re.match(r"^[-–]\s+", line) or re.match(r"^\s{2,}", raw):
            if current_name:
                current_desc.append(clean)
            continue

        # If we already have an open project and this line doesn't look like a
        # new project title, treat it as description (catches tech lists, result
        # sentences, and any verbs not in _DESC_START_RE)
        if current_name and not _looks_like_title(clean):
            current_desc.append(clean)
            continue

        # Remaining lines are new project titles — flush the previous project first
        _flush()
        title = re.sub(r"\s*(https?://\S+|github\.com/\S+|www\.\S+)", "", clean).strip()
        if len(title) > 3:
            current_name = title

    _flush()
    return projects[:6]


def _extract_education(text: str) -> str:
    m = re.search(
        r"(?:education|academic)[:\s\n]+(.*?)"
        r"(?=\n(?:experience|projects?|skills?|certifications?)|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        lines = [l.strip() for l in m.group(1).split("\n") if l.strip()][:3]
        return " | ".join(lines)

    degree_m = re.search(
        r"(B\.?S\.?|B\.?E\.?|B\.?Tech\.?|M\.?S\.?|M\.?Tech\.?|Bachelor|Master|Ph\.?D\.?)[^\n]{0,150}",
        text,
        re.IGNORECASE,
    )
    return degree_m.group(0).strip() if degree_m else ""


def _extract_experience_level(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(senior|lead|principal|staff|architect|head of|vp|director)\b", t):
        return "senior"
    if re.search(r"\b(junior|entry.?level|fresher|trainee|intern|graduate)\b", t):
        return "junior"
    m = re.search(r"(\d+)\+?\s*years?\s*(?:of\s*)?(?:experience|exp)", t)
    if m:
        yrs = int(m.group(1))
        return "senior" if yrs >= 5 else ("mid" if yrs >= 2 else "junior")
    jobs = len(re.findall(r"\b(?:20\d{2})\s*[-–]\s*(?:20\d{2}|present|current)", t))
    return "senior" if jobs >= 3 else ("mid" if jobs >= 1 else "junior")


def _infer_domains(skills: list[str]) -> list[str]:
    s = {sk.lower() for sk in skills}

    fe = len(s & _DOMAIN_SETS["frontend"])
    be = len(s & _DOMAIN_SETS["backend"])
    ml = len(s & _DOMAIN_SETS["ml"])
    ds = len(s & _DOMAIN_SETS["data"])
    do = len(s & _DOMAIN_SETS["devops"])
    mob = len(s & _DOMAIN_SETS["mobile"])
    de = len(s & _DOMAIN_SETS["de"])

    domains: list[str] = []
    if fe >= 2 and be >= 2:
        domains.append("Full Stack Web")
    elif fe >= 2:
        domains.append("Web Frontend")
    elif be >= 2:
        domains.append("Web Backend")
    if ml >= 2:
        domains.append("Machine Learning / AI")
    if ds >= 3:
        domains.append("Data Science")
    if do >= 2:
        domains.append("Cloud / DevOps")
    if mob >= 1:
        domains.append("Mobile Development")
    if de >= 2:
        domains.append("Data Engineering")

    return domains or ["General Software Development"]


def _infer_strengths(skills: list[str], projects: list[Project], level: str) -> list[str]:
    s = {sk.lower() for sk in skills}
    out: list[str] = []

    if len(skills) >= 10:
        out.append("Broad technical skill set")
    if len(projects) >= 3:
        out.append("Strong project portfolio")
    elif len(projects) >= 2:
        out.append("Demonstrated project experience")
    if {"react", "node.js"} & s and {"python", "django", "fastapi", "flask"} & s:
        out.append("Full-stack development capability")
    if {"docker", "kubernetes", "aws", "azure", "ci/cd"} & s:
        out.append("DevOps and cloud awareness")
    if {"tensorflow", "pytorch", "scikit-learn", "machine learning"} & s:
        out.append("Machine learning proficiency")
    if {"sql", "postgresql", "mysql", "mongodb"} & s:
        out.append("Database management experience")
    if level == "senior":
        out.append("Senior-level industry experience")
    if {"git", "github", "agile", "scrum"} & s:
        out.append("Collaborative development practices")

    return out[:5] or ["Technical proficiency demonstrated through projects"]


def _infer_weak_areas(skills: list[str], domains: list[str]) -> list[str]:
    s = {sk.lower() for sk in skills}
    weak: list[str] = []

    if any("frontend" in d.lower() or "full stack" in d.lower() for d in domains):
        if not ({"jest", "cypress", "playwright"} & s):
            weak.append("Frontend testing (Jest, Cypress)")
        if "typescript" not in s:
            weak.append("TypeScript adoption")

    if any("backend" in d.lower() or "full stack" in d.lower() for d in domains):
        if not ({"docker", "kubernetes"} & s):
            weak.append("Containerization (Docker / Kubernetes)")
        if not ({"redis", "kafka", "rabbitmq"} & s):
            weak.append("Caching and message queues")

    if not ({"aws", "azure", "gcp", "google cloud"} & s):
        weak.append("Cloud platform experience")

    return weak[:3]


# ── Intelligence functions ────────────────────────────────────────────────────

def _extract_strong_skills(skills: list[str], domains: list[str]) -> list[str]:
    """Return the candidate's top 5 most marketable skills given their domain."""
    s_lower = {sk.lower() for sk in skills}
    priority: list[str] = []

    # High-value domain-specific skills (ordered by market demand)
    high_value_order = [
        "React", "TypeScript", "Node.js", "Python", "FastAPI", "Django",
        "Docker", "Kubernetes", "AWS", "GCP", "Azure",
        "TensorFlow", "PyTorch", "Machine Learning", "Deep Learning",
        "PostgreSQL", "MongoDB", "Redis", "Kafka",
        "Spark", "Airflow", "Flutter", "React Native",
        "Next.js", "GraphQL", "Microservices", "Go",
    ]
    for skill in high_value_order:
        if skill.lower() in s_lower:
            priority.append(skill)
        if len(priority) >= 5:
            break

    # Fall back to any skills if priority list is short
    if len(priority) < 3:
        for skill in skills:
            if skill not in priority:
                priority.append(skill)
            if len(priority) >= 5:
                break

    return priority


def _extract_role_signals(skills: list[str], projects: list[Project], domains: list[str]) -> list[str]:
    """Infer explicit role signals from the resume content."""
    s = {sk.lower() for sk in skills}
    signals: list[str] = []

    fe = len(s & _DOMAIN_SETS["frontend"])
    be = len(s & _DOMAIN_SETS["backend"])
    ml = len(s & _DOMAIN_SETS["ml"])
    do = len(s & _DOMAIN_SETS["devops"])
    mob = len(s & _DOMAIN_SETS["mobile"])
    de = len(s & _DOMAIN_SETS["de"])

    if fe >= 3 and be >= 2:
        signals.append("Full-stack signals: strong frontend and backend skills present")
    elif fe >= 3:
        signals.append("Frontend signals: multiple UI/component framework skills")
    elif be >= 3:
        signals.append("Backend signals: server-side and data-layer skills present")
    if ml >= 2:
        signals.append("ML/AI signals: model training frameworks detected")
    if do >= 2:
        signals.append("DevOps signals: container and cloud tooling present")
    if mob >= 1:
        signals.append("Mobile signals: cross-platform or native mobile skills")
    if de >= 2:
        signals.append("Data engineering signals: pipeline and warehouse tools detected")
    if len(projects) >= 2:
        signals.append(f"Project evidence: {len(projects)} projects demonstrate hands-on experience")
    if not ({"jest", "pytest", "cypress", "junit"} & s):
        signals.append("No testing framework mentioned — gap signal")
    if not (_DOMAIN_SETS["deployment"] & s):
        signals.append("No deployment/cloud tools mentioned — gap signal")

    return signals[:6]


def _extract_claims_to_verify(skills: list[str], projects: list[Project], text: str) -> list[ClaimToVerify]:
    """Generate verifiable claims from the resume — things to probe in an interview."""
    s = {sk.lower() for sk in skills}
    claims: list[ClaimToVerify] = []
    text_lower = text.lower()

    # Each project is a claim — verify depth
    for project in projects[:3]:
        p_lower = project.name.lower()
        techs = ", ".join(project.technologies[:3]) if project.technologies else "various technologies"
        missing_aspects: list[str] = []

        # Check what is implied by the project but not mentioned
        if "auth" not in text_lower and "login" not in text_lower and "jwt" not in text_lower:
            missing_aspects.append("authentication")
        if "deploy" not in text_lower and "hosting" not in text_lower:
            missing_aspects.append("deployment")
        if "test" not in text_lower:
            missing_aspects.append("testing")
        if "database" not in text_lower and "db" not in text_lower and not ({"sql", "mongodb", "postgresql"} & s):
            missing_aspects.append("database design")

        why = (
            f"Resume lists {project.name} using {techs}, but "
            + (f"does not mention {', '.join(missing_aspects[:2])}" if missing_aspects else "depth of implementation is unclear")
        )
        probe = (
            f"Walk me through the architecture of {project.name} — "
            f"how did you handle " + (f"{missing_aspects[0]} and data flow?" if missing_aspects else "the most complex technical challenge?")
        )
        claims.append(ClaimToVerify(
            claim=f"Built {project.name} using {techs}",
            why_verify=why,
            probe_question=probe,
        ))

    # Skill-claim verifications
    if "machine learning" in s or "deep learning" in s:
        if "tensorflow" not in s and "pytorch" not in s and "scikit-learn" not in s:
            claims.append(ClaimToVerify(
                claim="Machine Learning / Deep Learning expertise",
                why_verify="Resume mentions ML/DL but no specific framework (TensorFlow, PyTorch, Scikit-learn) is listed",
                probe_question="Which ML frameworks have you used in practice and what kind of models did you train?",
            ))

    if "microservices" in s or "microservices" in text_lower:
        if not ({"docker", "kubernetes", "kafka"} & s):
            claims.append(ClaimToVerify(
                claim="Microservices architecture experience",
                why_verify="Microservices mentioned but no container or orchestration tooling found (Docker, Kubernetes, Kafka)",
                probe_question="How did you handle service discovery, inter-service communication, and deployment in your microservices setup?",
            ))

    if "aws" in s or "azure" in s or "gcp" in s or "google cloud" in s:
        cloud_services = [x for x in ["EC2", "S3", "Lambda", "RDS", "ECS"] if x.lower() in text_lower]
        if not cloud_services:
            claims.append(ClaimToVerify(
                claim="Cloud platform (AWS/Azure/GCP) experience",
                why_verify="Cloud provider mentioned but no specific services are listed in the resume",
                probe_question="Which specific cloud services did you use and what did you build with them?",
            ))

    return claims[:4]


def _extract_project_deep_dives(projects: list[Project], domains: list[str]) -> list[ProjectDeepDive]:
    """Select best projects for interview deep-dives and suggest probe topics."""
    if not projects:
        return []

    dives: list[ProjectDeepDive] = []

    for i, project in enumerate(projects[:3]):
        techs_lower = {t.lower() for t in project.technologies}

        # Determine why this project was selected
        if i == 0:
            why = f"Most prominent project on resume — best evidence of technical capability"
        elif len(project.technologies) >= 4:
            why = f"Demonstrates breadth across {len(project.technologies)} technologies"
        else:
            why = f"Shows experience with {', '.join(project.technologies[:2])}"

        # Generate probe topics based on tech stack
        probe_topics: list[str] = []
        if techs_lower & {"react", "vue.js", "angular", "next.js"}:
            probe_topics += ["component architecture", "state management", "API integration"]
        if techs_lower & {"node.js", "express", "django", "fastapi", "flask"}:
            probe_topics += ["API design", "authentication", "error handling"]
        if techs_lower & {"mongodb", "postgresql", "mysql", "sqlite"}:
            probe_topics += ["database schema design", "query optimisation"]
        if techs_lower & {"docker", "kubernetes", "aws"}:
            probe_topics += ["deployment strategy", "scalability"]
        if techs_lower & {"tensorflow", "pytorch", "scikit-learn"}:
            probe_topics += ["model selection", "training pipeline", "evaluation metrics"]
        if not probe_topics:
            probe_topics = ["architecture decisions", "biggest technical challenge", "what you would improve"]

        dives.append(ProjectDeepDive(
            project=project.name,
            why_selected=why,
            probe_topics=probe_topics[:4],
        ))

    return dives


def _extract_interview_risks(skills: list[str], projects: list[Project], level: str, text: str) -> list[str]:
    """Identify resume signals that may indicate interview risks."""
    s = {sk.lower() for sk in skills}
    risks: list[str] = []
    text_lower = text.lower()

    if not ({"jest", "pytest", "junit", "selenium", "cypress"} & s) and "test" not in text_lower:
        risks.append("No testing mentioned — may struggle with questions on test strategy")

    if not (_DOMAIN_SETS["deployment"] & s) and "deploy" not in text_lower:
        risks.append("No deployment experience visible — cloud/infra questions may be weak")

    if level == "junior" and len(projects) == 0:
        risks.append("No projects listed — insufficient evidence of hands-on skill")

    if len(skills) < 5:
        risks.append("Very few skills listed — breadth of technical knowledge may be limited")

    if not ({"git", "github"} & s):
        risks.append("Version control not mentioned — basic collaboration practice unclear")

    if "system design" in text_lower or level == "senior":
        if not ({"microservices", "kafka", "redis", "docker", "kubernetes"} & s):
            risks.append("Senior/system design claims but limited distributed systems tooling visible")

    return risks[:4]


def _extract_suggested_probes(claims: list[ClaimToVerify], weak_areas: list[str]) -> list[str]:
    """Combine claim probes and weak-area probes into a flat probe list."""
    probes: list[str] = [c.probe_question for c in claims[:2]]
    for w in weak_areas[:2]:
        probes.append(f"Describe your experience with {w} — what have you learned or built?")
    return probes[:4]


# ── Public API ────────────────────────────────────────────────────────────────

def analyze(raw_text: str, candidate_id: str) -> ResumeAnalysis:
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    skills = _extract_skills(raw_text)
    projects = _extract_projects(raw_text)
    exp_level = _extract_experience_level(raw_text)
    domains = _infer_domains(skills)
    weak_areas = _infer_weak_areas(skills, domains)

    strong_skills = _extract_strong_skills(skills, domains)
    role_signals = _extract_role_signals(skills, projects, domains)
    claims = _extract_claims_to_verify(skills, projects, raw_text)
    deep_dives = _extract_project_deep_dives(projects, domains)
    interview_risks = _extract_interview_risks(skills, projects, exp_level, raw_text)
    suggested_probes = _extract_suggested_probes(claims, weak_areas)

    return ResumeAnalysis(
        candidate_id=candidate_id,
        candidate_name=_extract_name(lines),
        email=_extract_email(raw_text),
        phone=_extract_phone(raw_text),
        skills=skills,
        projects=projects,
        education=_extract_education(raw_text),
        experience_level=exp_level,
        domains=domains,
        strengths=_infer_strengths(skills, projects, exp_level),
        weak_areas=weak_areas,
        strong_skills=strong_skills,
        role_signals=role_signals,
        claims_to_verify=claims,
        project_deep_dives=deep_dives,
        interview_risks=interview_risks,
        suggested_probes=suggested_probes,
    )
