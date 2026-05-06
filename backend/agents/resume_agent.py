"""Rule-based resume analysis. Works without any LLM key."""

import re
from models.analysis import ResumeAnalysis, Project

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
    # ML / AI
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "XGBoost",
    "Pandas", "NumPy", "Matplotlib", "Seaborn",
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "OpenCV", "Hugging Face", "LangChain", "LLM",
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


def _extract_projects(text: str) -> list[Project]:
    m = re.search(
        r"(?:projects?|personal projects?|key projects?)[:\s\n]+(.*?)"
        r"(?=\n(?:education|experience|skills?|certifications?|awards?)|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []

    blocks = re.split(r"\n(?=[A-Z•\-*\d])", m.group(1))
    projects: list[Project] = []

    for block in blocks[:6]:
        block = block.strip()
        if len(block) < 10:
            continue
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue

        name = re.sub(r"^[\d\.\-•*\s]+", "", lines[0]).strip()
        if not name:
            continue

        description = " ".join(lines[1:]) if len(lines) > 1 else ""
        block_lower = block.lower()
        techs = [
            _SKILLS_MAP[k]
            for k in _SKILLS_MAP
            if re.search(r"\b" + re.escape(k) + r"\b", block_lower)
        ]
        projects.append(
            Project(
                name=name,
                technologies=techs[:8],
                summary=(description[:200] if description else "No description available."),
            )
        )

    return projects


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

    fe = len(s & {"javascript", "react", "angular", "vue.js", "vue", "html", "css", "typescript", "next.js"})
    be = len(s & {"python", "java", "node.js", "django", "fastapi", "flask", "spring", "express.js", "express", "c#", "go", "rust"})
    ml = len(s & {"tensorflow", "pytorch", "keras", "deep learning", "machine learning", "nlp", "computer vision"})
    ds = len(s & {"pandas", "numpy", "scikit-learn", "r", "tableau", "statistics", "machine learning"})
    do = len(s & {"docker", "kubernetes", "aws", "azure", "gcp", "google cloud", "ci/cd", "terraform", "jenkins"})
    mob = len(s & {"ios", "android", "react native", "flutter", "swift", "kotlin"})
    de = len(s & {"spark", "hadoop", "airflow", "kafka", "dbt", "snowflake", "databricks"})

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


# ── Public API ────────────────────────────────────────────────────────────────

def analyze(raw_text: str, candidate_id: str) -> ResumeAnalysis:
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    skills = _extract_skills(raw_text)
    projects = _extract_projects(raw_text)
    exp_level = _extract_experience_level(raw_text)
    domains = _infer_domains(skills)

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
        weak_areas=_infer_weak_areas(skills, domains),
    )
