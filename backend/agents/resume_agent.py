"""
Resume analysis agent — improved section detection, project grouping,
certification extraction, achievement tracking, and domain inference.

Key fix: project fragmentation was caused by splitting on every line starting
with an uppercase letter, bullet, or digit.  The new _group_into_entries()
function only splits on actual entry headings, so bullet points and description
lines are correctly grouped under their parent project / role / certification.
"""

import re
from typing import Optional
from models.analysis import (
    ResumeAnalysis, Project, Certification, WorkExperience,
)

# ── Skill registry (unchanged) ────────────────────────────────────────────────

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
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "XGBoost", "LightGBM",
    "Pandas", "NumPy", "Matplotlib", "Seaborn",
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "OpenCV", "Hugging Face", "LangChain", "LLM",
    "MLflow", "Weights & Biases",
    # Data Engineering
    "Spark", "Hadoop", "Airflow", "Kafka", "dbt", "Snowflake", "Databricks",
    "BigQuery", "Redshift", "Tableau", "Power BI", "Looker", "R",
    # Mobile
    "iOS", "Android", "React Native", "Flutter", "Swift", "Kotlin", "Xamarin",
    # Testing
    "Jest", "Pytest", "JUnit", "Selenium", "Cypress", "Playwright", "Postman",
    # Security / Auth
    "OAuth", "JWT",
    # General
    "Git", "GitHub", "REST API", "GraphQL", "gRPC", "Microservices",
    "Agile", "Scrum", "JIRA", "Figma",
]

_SKILLS_MAP: dict[str, str] = {s.lower(): s for s in _SKILL_LIST}


# ── Section aliases ────────────────────────────────────────────────────────────
# Maps every heading variant → canonical section type.

_SECTION_ALIASES: dict[str, list[str]] = {
    "summary": [
        "summary", "professional summary", "objective", "career objective",
        "profile", "about", "about me", "professional profile", "overview",
        "career summary",
    ],
    "skills": [
        "skills", "technical skills", "core competencies", "technologies",
        "tech stack", "programming languages", "tools & technologies",
        "tools and technologies", "key skills", "areas of expertise",
        "technical expertise", "technical proficiencies", "tools",
    ],
    "experience": [
        "work experience", "experience", "employment", "professional experience",
        "work history", "career history", "employment history",
        "professional background", "work",
    ],
    "internships": [
        "internships", "internship experience", "intern experience",
        "training", "industrial training", "internship",
    ],
    "projects": [
        "projects", "personal projects", "key projects", "academic projects",
        "notable projects", "side projects", "portfolio", "project work",
        "technical projects", "selected projects", "project",
    ],
    "education": [
        "education", "academic background", "educational background",
        "academics", "qualifications", "educational qualifications",
        "academic qualifications", "academic details",
    ],
    "certifications": [
        "certifications", "certification", "certificates", "licenses",
        "credentials", "professional certifications", "licenses & certifications",
        "professional certificates",
    ],
    "achievements": [
        "achievements", "awards", "honors", "honours", "accomplishments",
        "recognition", "awards & achievements", "honors & awards",
        "activities", "extra-curricular", "extracurricular",
        "positions of responsibility",
    ],
    "hackathons": [
        "hackathons", "competitions", "contests", "coding competitions",
        "competitive programming", "hackathon experience", "hackathon",
    ],
    "coursework": [
        "coursework", "relevant coursework", "courses", "online training",
        "relevant courses", "professional development", "online courses",
        "courses completed",
    ],
    "research": [
        "research", "research experience", "publications", "papers",
        "research work", "research projects", "academic research",
        "research & publications",
    ],
    "volunteering": [
        "volunteering", "volunteer experience", "social work",
        "community service", "volunteer",
    ],
}

# Flat lookup: canonical-lower-alias → section type
_HEADER_LOOKUP: dict[str, str] = {
    alias.lower(): stype
    for stype, aliases in _SECTION_ALIASES.items()
    for alias in aliases
}

# Legacy regex kept for _extract_name
_SECTION_RE = re.compile(
    r"^(?:skills?|technical skills?|core competencies|technologies|"
    r"work experience|experience|employment|professional experience|"
    r"education|academic background|"
    r"projects?|personal projects?|key projects?|academic projects?|"
    r"summary|objective|profile|about(?: me)?|"
    r"certifications?|achievements?|awards?|publications?)[\s:]*$",
    re.IGNORECASE,
)

# ── Date pattern ───────────────────────────────────────────────────────────────

_DATE_PAT = re.compile(
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\.?\s*\d{4}"
    r"|(?:20\d{2}|19\d{2})\s*[-–—]\s*(?:20\d{2}|19\d{2}|[Pp]resent|[Cc]urrent|[Tt]oday)"
    r"|\d{1,2}/\d{4}",
    re.IGNORECASE,
)

# ── Description-starter verbs ──────────────────────────────────────────────────
# Lines starting with these are content lines, not entry headings.

_DESC_STARTERS = frozenset({
    # Technical action verbs
    "developed", "built", "created", "designed", "implemented", "worked", "added",
    "responsible", "managed", "led", "collaborated", "participated",
    "contributed", "used", "utilized", "helped", "assisted", "performed",
    "conducted", "analyzed", "analysed", "maintained", "improved", "enhanced",
    "integrated", "deployed", "configured", "tested", "wrote", "researched",
    "investigated", "established", "reduced", "increased", "supported",
    "trained", "mentored", "coordinated", "delivered", "launched", "migrated",
    "refactored", "optimized", "optimised", "automated", "monitored",
    "architected", "scaled", "streamlined", "revamped",
    # Passive / outcome verbs
    "passed", "earned", "completed", "awarded", "received", "certified",
    "recognized", "selected", "chosen", "ranked", "scored", "secured",
    "placed", "participated",
    # Descriptive starters
    "covers", "includes", "focuses", "provides", "consists",
})

# ── Certification issuer map ───────────────────────────────────────────────────

_CERT_ISSUER_MAP: dict[str, str] = {
    "aws": "Amazon Web Services",
    "amazon": "Amazon Web Services",
    "azure": "Microsoft",
    "microsoft": "Microsoft",
    "google": "Google",
    "gcp": "Google",
    "cisco": "Cisco",
    "ccna": "Cisco",
    "ccnp": "Cisco",
    "comptia": "CompTIA",
    "a+": "CompTIA",
    "security+": "CompTIA",
    "network+": "CompTIA",
    "oracle": "Oracle",
    "meta": "Meta",
    "coursera": "Coursera",
    "udemy": "Udemy",
    "linkedin": "LinkedIn Learning",
    "databricks": "Databricks",
    "hashicorp": "HashiCorp",
    "terraform": "HashiCorp",
    "kubernetes": "CNCF",
    "cka": "CNCF",
    "ckad": "CNCF",
    "cks": "CNCF",
    "red hat": "Red Hat",
    "rhce": "Red Hat",
    "pmi": "PMI",
    "scrum": "Scrum Alliance",
    "tensorflow": "Google",
    "mongodb": "MongoDB Inc.",
    "elastic": "Elastic",
    "salesforce": "Salesforce",
    "github": "GitHub",
    "gitlab": "GitLab",
    "snowflake": "Snowflake",
    "tableau": "Tableau / Salesforce",
    "docker": "Docker Inc.",
    "nvidia": "NVIDIA",
    "deeplearning": "DeepLearning.AI",
    "deeplearning.ai": "DeepLearning.AI",
    "nptel": "NPTEL",
    "infosys": "Infosys Springboard",
    "ibm": "IBM",
    "redhat": "Red Hat",
}

# ── Certification validation ──────────────────────────────────────────────────
# Entries must match at least one of these signals to be treated as a cert.

_CERT_SIGNAL_RE = re.compile(
    r"(?i)\b(?:certif(?:ied|ication|icate)|credential|licensed|"
    r"aws|azure|gcp|google cloud|cisco|comptia|oracle|red hat|redhat|"
    r"microsoft|pmi|scrum|kubernetes|cka|ckad|cks|databricks|snowflake|"
    r"professional|associate|practitioner|architect|developer exam|"
    r"foundation|fundamentals|essentials|bootcamp|nanodegree|"
    r"coursera|udemy|linkedin learning|nptel|infosys|ibm|nvidia|deeplearning)\b"
)


def _looks_like_cert(name: str) -> bool:
    """Return True when the name looks like a real cert, not a list of coursework topics."""
    # Comma-separated topic lists (e.g. "LLMs, Big Data Analytics, NLP") are coursework
    if name.count(",") >= 2:
        return False
    if len(name) < 6:
        return False
    return bool(_CERT_SIGNAL_RE.search(name))


# ── Role-title detection for work experience grouping ─────────────────────────

_ROLE_TITLE_RE = re.compile(
    r"(?i)^(?:software|senior|junior|lead|staff|principal|associate|"
    r"assistant|chief|head|vp|vice\s+president|"
    r"engineer(?:ing)?|developer|analyst|architect|manager|director|intern(?:ship)?|"
    r"consultant|specialist|scientist|researcher|designer|"
    r"data|backend|frontend|full[- ]?stack|devops|cloud|sre|"
    r"machine learning|ml\b|ai\b)\b"
)


def _is_role_line(line: str) -> bool:
    """True if line looks like a standalone job-title line (no date, short, not a bullet)."""
    line = line.strip()
    if not line or len(line) > 80:
        return False
    if line[0] in "•-*◦▪▸→–—":
        return False
    if _DATE_PAT.search(line):
        return False
    return bool(_ROLE_TITLE_RE.match(line))


# ── Tech → domain keyword map ─────────────────────────────────────────────────

_TECH_DOMAIN_MAP: dict[str, str] = {
    # Cloud / DevOps
    "aws": "Cloud / DevOps", "azure": "Cloud / DevOps", "gcp": "Cloud / DevOps",
    "google cloud": "Cloud / DevOps", "docker": "Cloud / DevOps",
    "kubernetes": "Cloud / DevOps", "terraform": "Cloud / DevOps",
    "jenkins": "Cloud / DevOps", "ci/cd": "Cloud / DevOps",
    "ansible": "Cloud / DevOps", "github actions": "Cloud / DevOps",
    # Frontend
    "react": "Web Frontend", "angular": "Web Frontend", "vue": "Web Frontend",
    "next.js": "Web Frontend", "svelte": "Web Frontend",
    "javascript": "Web Frontend", "typescript": "Web Frontend",
    # Backend
    "django": "Web Backend", "flask": "Web Backend", "fastapi": "Web Backend",
    "node.js": "Web Backend", "spring": "Web Backend", "express": "Web Backend",
    "rails": "Web Backend", "laravel": "Web Backend",
    # ML / AI
    "tensorflow": "Machine Learning / AI", "pytorch": "Machine Learning / AI",
    "keras": "Machine Learning / AI", "machine learning": "Machine Learning / AI",
    "deep learning": "Machine Learning / AI", "nlp": "Machine Learning / AI",
    "computer vision": "Machine Learning / AI", "scikit-learn": "Machine Learning / AI",
    "hugging face": "Machine Learning / AI", "langchain": "Machine Learning / AI",
    # Data Engineering
    "spark": "Data Engineering", "airflow": "Data Engineering",
    "kafka": "Data Engineering", "databricks": "Data Engineering",
    "dbt": "Data Engineering", "snowflake": "Data Engineering",
    "hadoop": "Data Engineering",
    # Mobile
    "flutter": "Mobile Development", "react native": "Mobile Development",
    "android": "Mobile Development", "ios": "Mobile Development",
    "swift": "Mobile Development", "kotlin": "Mobile Development",
    # Networking
    "cisco": "Networking", "ccna": "Networking", "ccnp": "Networking",
    # Data Science
    "pandas": "Data Science", "numpy": "Data Science",
    "tableau": "Data Science", "power bi": "Data Science",
}


# ── Section parsing ────────────────────────────────────────────────────────────

def _identify_section_header(line: str) -> Optional[str]:
    """
    Return canonical section type if `line` is a section heading, else None.
    Accepts: exact alias matches (case-insensitive), with optional trailing
    punctuation (colon, dash, underscores), and decorative wrappers like
    "--- PROJECTS ---".
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 65:
        return None
    if stripped[0] in "•-*◦▪▸→–—":
        return None
    # Strip trailing / leading punctuation and whitespace
    clean = re.sub(r"[\s:\-_=\|]+$", "", stripped).strip()
    clean = re.sub(r"^[\-=_ ]+|[\-=_ ]+$", "", clean).strip()
    return _HEADER_LOOKUP.get(clean.lower())


def _parse_sections(text: str) -> dict[str, str]:
    """
    Scan resume text line-by-line and group content by section heading.
    Returns {section_type: content_text}.  Unknown pre-header lines → "header".
    """
    lines = text.split("\n")
    current = "header"
    buf: dict[str, list[str]] = {}

    for line in lines:
        stype = _identify_section_header(line)
        if stype:
            current = stype
        else:
            buf.setdefault(current, []).append(line)

    return {k: "\n".join(v) for k, v in buf.items()}


def _split_inline_section_header(text: str) -> str:
    """
    PDF extraction sometimes returns a section title and the first item on the
    same visual line, e.g. "PROJECTS Interview Agent". Split those lines so the
    normal section parser can still find the Projects block.
    """
    out: list[str] = []
    header_words = sorted(_HEADER_LOOKUP.keys(), key=len, reverse=True)

    for raw in text.split("\n"):
        line = raw.strip()
        lowered = line.lower()
        matched = False
        for header in header_words:
            if not lowered.startswith(header + " "):
                continue
            prefix = line[:len(header)]
            rest = line[len(header):].strip(" :-|")
            if rest and prefix.isupper():
                out.append(prefix)
                out.append(rest)
                matched = True
                break
        if not matched:
            out.append(raw)

    return "\n".join(out)


# ── Entry heading detection ────────────────────────────────────────────────────

_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.|github\.com/|gitlab\.com/|bitbucket\.org/)\S+")
_LINK_LABEL_RE = re.compile(
    r"(?i)^\s*(?:github|gitlab|bitbucket|repo(?:sitory)?|source\s*code|code|demo|live\s*demo|link|url)\s*[:\-|]"
)


def _is_entry_heading(line: str) -> bool:
    """
    Heuristic: is this line the first line of a new entry (project title,
    company name, certification name, achievement title)?

    Heading signals  (+):  short, starts with capital/digit, not a bullet
    Non-heading signals (−): starts with action verb, is a pure date,
                             is a long sentence, starts with bullet,
                             is a technology-label line
    """
    line = line.strip()
    if not line or len(line) < 3:
        return False
    if _URL_RE.search(line) or _LINK_LABEL_RE.match(line):
        return False
    # Bullet characters → content line
    if line[0] in "•-*◦▪▸→–—":
        return False
    # Explicit technology-label lines (e.g. "Technologies: React, Django")
    if re.match(
        r"(?i)^(?:technologies?|tech(?:\s+stack)?|tools?|stack|built with"
        r"|frameworks?|languages?|skills?)\s*[:\|]",
        line,
    ):
        return False
    # Line that IS purely a date → not a heading
    if _DATE_PAT.fullmatch(line):
        return False
    date_m = _DATE_PAT.match(line)
    if date_m and (len(line) - date_m.end()) < 5:
        return False  # line is almost entirely a date
    # Long sentence ending with period → description text
    if len(line) > 70 and line.rstrip().endswith("."):
        return False
    # Very long lines → not headings
    if len(line) > 100:
        return False
    # Must start with uppercase letter or a digit
    if not (line[0].isupper() or line[0].isdigit()):
        return False
    # Action-verb first word → this is a description / responsibility line
    first_word = re.split(r"[\s\W]", line)[0].lower()
    if first_word in _DESC_STARTERS:
        return False
    return True


def _group_into_entries(section_text: str) -> list[list[str]]:
    """
    Split section content into grouped entries.

    Each entry = [heading_line, content_line, content_line, …]

    Lines before the first heading are discarded.
    If NO heading is detected at all (e.g. bullet-only lists), every
    non-empty line becomes its own single-line entry — this handles
    certifications / achievements formatted as plain bullet lists.
    """
    lines = [l for l in section_text.split("\n") if l.strip()]
    entries: list[list[str]] = []
    current: list[str] = []
    heading_found = False

    for line in lines:
        stripped = line.strip()
        if _is_entry_heading(stripped):
            heading_found = True
            if current:
                entries.append(current)
            current = [stripped]
        else:
            if current:
                current.append(stripped)
            # else: pre-heading noise — discard

    if current:
        entries.append(current)

    # No headings found → each line is its own entry (bullet lists, etc.)
    if not heading_found and lines:
        entries = [[l.strip()] for l in lines if l.strip()]

    return entries


def _group_project_entries(section_text: str) -> list[list[str]]:
    """
    Project sections need a softer fallback than certification sections. If a
    PDF strips title styling and leaves only bullets, grouping every bullet as a
    separate project is worse than keeping the block together as one project.
    """
    entries = _group_into_entries(section_text)
    lines = [l.strip() for l in section_text.split("\n") if l.strip()]
    if not lines:
        return []

    heading_count = sum(1 for line in lines if _is_entry_heading(line))
    if heading_count == 0:
        return [lines]

    return entries


# ── Date extraction helper ─────────────────────────────────────────────────────

def _pull_date(text: str) -> str:
    """Return first date-like string found in text, or ''."""
    m = _DATE_PAT.search(text)
    return m.group(0).strip() if m else ""


def _strip_date(text: str) -> str:
    """Remove all date-like strings from text."""
    return _DATE_PAT.sub("", text).strip().rstrip("|-–— ").strip()


# ── Contact extraction (unchanged) ────────────────────────────────────────────

def _extract_name(lines: list[str]) -> str:
    email_re = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    phone_re = re.compile(r"[\+\d][\d\s\-().]{7,}")
    url_re   = re.compile(r"https?://|www\.", re.IGNORECASE)
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


# ── Skill extraction (unchanged) ──────────────────────────────────────────────

def _extract_skills(text: str) -> list[str]:
    text_lower = text.lower()
    found: dict[str, str] = {}
    for kw_lower, kw_display in _SKILLS_MAP.items():
        if re.search(r"\b" + re.escape(kw_lower) + r"\b", text_lower):
            found[kw_lower] = kw_display
    return list(found.values())


def _skills_in_block(block: str) -> list[str]:
    """Extract skills mentioned in an arbitrary text block."""
    block_lower = block.lower()
    return [
        _SKILLS_MAP[k]
        for k in _SKILLS_MAP
        if re.search(r"\b" + re.escape(k) + r"\b", block_lower)
    ]


# ── Education (updated to use section map) ────────────────────────────────────

def _extract_education(text: str, sections: dict) -> str:
    edu_text = sections.get("education", "")
    if edu_text:
        lines = [l.strip() for l in edu_text.split("\n") if l.strip()][:4]
        if lines:
            return " | ".join(lines)
    # Fallback: original regex
    m = re.search(
        r"(?:education|academic)[:\s\n]+(.*?)"
        r"(?=\n(?:experience|projects?|skills?|certifications?)|$)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if m:
        lines = [l.strip() for l in m.group(1).split("\n") if l.strip()][:3]
        return " | ".join(lines)
    degree_m = re.search(
        r"(B\.?S\.?|B\.?E\.?|B\.?Tech\.?|M\.?S\.?|M\.?Tech\.?|Bachelor|Master|Ph\.?D\.?)"
        r"[^\n]{0,150}",
        text, re.IGNORECASE,
    )
    return degree_m.group(0).strip() if degree_m else ""


# ── Project extraction (FIXED) ────────────────────────────────────────────────

def _extract_projects(text: str, sections: dict) -> list[Project]:
    """
    Improved project extraction.

    Old bug: re.split(r"\\n(?=[A-Z•\\-*\\d])", section) split on every bullet,
    turning N description lines into N fake projects.

    Fix: _group_into_entries() only starts a new entry at lines that pass
    _is_entry_heading(), so bullets / descriptions stay grouped under their
    project title.
    """
    section_text = sections.get("projects", "")
    if not section_text:
        # Fallback regex for resumes where section headers don't match aliases
        m = re.search(
            r"(?:projects?|personal projects?|key projects?)[:\s\n]+(.*?)"
            r"(?=\n(?:education|experience|skills?|certifications?|awards?)|$)",
            text, re.IGNORECASE | re.DOTALL,
        )
        section_text = m.group(1) if m else ""
    if not section_text:
        return []

    entries = _group_project_entries(section_text)
    projects: list[Project] = []

    for entry_lines in entries[:8]:
        if not entry_lines:
            continue

        title_line = entry_lines[0]
        if _URL_RE.search(title_line) or _LINK_LABEL_RE.match(title_line):
            if projects:
                link_line = re.sub(r"^[â€¢\-*â—¦â–ªâ–¸â†’â€“â€”]\s*", "", title_line).strip()
                if link_line and link_line not in projects[-1].description:
                    projects[-1].description.append(link_line)
                    projects[-1].summary = " ".join(projects[-1].description[:3])[:300]
            continue

        # Extract date from title line
        duration = _pull_date(title_line)
        title    = _strip_date(title_line)
        title    = re.sub(r"^[\d\.\-•*\s]+", "", title).strip()

        # No date on title line → check the second line
        if not duration and len(entry_lines) > 1:
            duration = _pull_date(entry_lines[1])

        if not title or len(title) < 2:
            continue

        description:    list[str] = []
        techs_explicit: list[str] = []

        for raw_line in entry_lines[1:]:
            stripped = raw_line.strip()
            if not stripped:
                continue

            # Technology-label line  (e.g. "Technologies: React, Django, AWS")
            tech_m = re.match(
                r"(?i)^(?:technologies?|tech(?:\s+stack)?|tools?|stack"
                r"|built with|frameworks?|languages?)\s*[:\|]\s*(.+)",
                stripped,
            )
            if tech_m:
                for tok in re.split(r"[,|;/]", tech_m.group(1)):
                    t = tok.strip()
                    if t:
                        techs_explicit.append(t)
                continue

            # Standalone date → already captured, skip
            if _DATE_PAT.fullmatch(stripped) or (
                _pull_date(stripped) and len(stripped) < 45
                and not re.search(r"[A-Za-z]{3,}", _strip_date(stripped))
            ):
                continue

            # Bullet / description line
            clean = re.sub(r"^[•\-*◦▪▸→–—]\s*", "", stripped)
            if clean and len(clean) > 5:
                description.append(clean)

        # Technology merge: prefer explicit label, augment from skill-map scan
        detected = _skills_in_block("\n".join(entry_lines))
        if techs_explicit:
            label_lower = {t.lower() for t in techs_explicit}
            extra = [t for t in detected if t.lower() not in label_lower]
            all_techs = techs_explicit[:6] + extra[:3]
        else:
            all_techs = detected[:8]

        summary = " ".join(description[:3])[:300] if description else "No description available."

        projects.append(Project(
            name=title,
            technologies=all_techs[:8],
            summary=summary,
            duration=duration,
            description=description[:6],
        ))

    return projects


# ── Certification extraction (new) ───────────────────────────────────────────

def _extract_certifications(sections: dict) -> list[Certification]:
    """
    Extract structured certifications from the certifications section only.
    Coursework topics are deliberately excluded — they land in sections["coursework"]
    after the _SECTION_ALIASES fix and are NOT merged here.

    Each extracted name is validated by _looks_like_cert() to reject
    comma-separated coursework topic lists mistakenly placed under a cert heading.
    """
    cert_text = sections.get("certifications", "")
    if not cert_text.strip():
        return []

    entries  = _group_into_entries(cert_text)
    certs: list[Certification] = []

    for entry_lines in entries[:15]:
        if not entry_lines:
            continue
        full_text = " ".join(entry_lines)

        date      = _pull_date(full_text)
        name_raw  = entry_lines[0]
        name      = _strip_date(name_raw)
        name      = re.sub(r"^[\d\.\-•*\s]+", "", name).strip()

        if not name or len(name) < 4:
            continue

        # Reject coursework-style topic lists
        if not _looks_like_cert(name):
            continue

        # Infer issuer from keywords in the entire entry block
        full_lower = full_text.lower()
        issuer = ""
        for keyword, org in _CERT_ISSUER_MAP.items():
            if re.search(r"\b" + re.escape(keyword) + r"\b", full_lower):
                issuer = org
                break

        certs.append(Certification(name=name, issuer=issuer, date=date))

    return certs


# ── Achievement extraction (new) ──────────────────────────────────────────────

def _extract_achievements(sections: dict) -> list[str]:
    """
    Collect achievements, awards, hackathons, and research entries as strings.
    """
    results: list[str] = []
    for stype in ("achievements", "hackathons", "research", "volunteering"):
        block = sections.get(stype, "")
        if not block:
            continue
        for line in block.split("\n"):
            clean = re.sub(r"^[•\-*◦▪▸→–—]\s*", "", line.strip())
            if clean and len(clean) > 5 and clean not in results:
                results.append(clean)
    return results[:10]


# ── Work experience grouping (date-anchored) ─────────────────────────────────

def _group_experience_entries(section_text: str) -> list[list[str]]:
    """
    Date-anchored entry grouping for work experience sections.

    Unlike _group_into_entries(), this does NOT split on every _is_entry_heading
    line.  Role-title lines ("Software Engineer", "Data Analyst") commonly appear
    on the line just before OR just after the company/date line and must stay
    attached to their entry.

    Algorithm:
      1. Find every line that carries a date and is not a bullet (= date anchor).
      2. For each anchor, check whether the immediately preceding line is a
         standalone heading (company name or role title without a date); if so,
         include it in the same entry.
      3. Slice the full line list by the resolved entry-start indices.
    Fallback: if no date anchors exist, delegate to _group_into_entries().
    """
    lines = [l.strip() for l in section_text.split("\n") if l.strip()]
    if not lines:
        return []

    # Step 1 — locate date-anchor lines
    date_anchor_idx: list[int] = []
    for i, line in enumerate(lines):
        if line[0] in "•-*◦▪▸→–—":
            continue
        if len(line) > 120:
            continue
        if _DATE_PAT.search(line):
            date_anchor_idx.append(i)

    if not date_anchor_idx:
        return _group_into_entries(section_text)

    # Step 2 — for each anchor, look one line back for a pre-anchor heading
    entry_starts: list[int] = []
    claimed: set[int] = set()
    for anchor_i in date_anchor_idx:
        prev_i = anchor_i - 1
        if (
            prev_i >= 0
            and prev_i not in claimed
            and prev_i not in date_anchor_idx
        ):
            prev = lines[prev_i]
            if (
                _is_entry_heading(prev)
                and not _DATE_PAT.search(prev)
                and len(prev) <= 80
            ):
                entry_starts.append(prev_i)
                claimed.add(prev_i)
                continue
        entry_starts.append(anchor_i)

    entry_starts = sorted(set(entry_starts))

    # Step 3 — slice
    entries: list[list[str]] = []
    for j, start in enumerate(entry_starts):
        end = entry_starts[j + 1] if j + 1 < len(entry_starts) else len(lines)
        entry = [lines[k] for k in range(start, end) if lines[k]]
        if entry:
            entries.append(entry)

    return entries or _group_into_entries(section_text)


# ── Work experience extraction (new) ─────────────────────────────────────────

def _extract_work_experience(sections: dict) -> list[WorkExperience]:
    """
    Extract structured work experience and internship entries.
    Groups company, role, duration, and bullet-point responsibilities.

    Handles the most common single-line format:
        "Company Name | Role | Jan 2023 – Dec 2023"
    and the two-line format:
        "Company Name                Jan 2023 – Present"
        "Software Engineer"
    """
    combined = "\n".join(filter(None, [
        sections.get("experience", ""),
        sections.get("internships", ""),
    ]))
    if not combined.strip():
        return []

    entries      = _group_experience_entries(combined)
    experiences: list[WorkExperience] = []

    for entry_lines in entries[:8]:
        if not entry_lines:
            continue

        first_line = entry_lines[0].strip()
        duration   = _pull_date(first_line)
        header     = _strip_date(first_line)

        # Parse "Company | Role" / "Company – Role" / "Company, Role"
        company, role = header, ""
        for sep in (" | ", " – ", " — ", " - ", ", "):
            if sep in header:
                parts   = header.split(sep, 1)
                company = parts[0].strip()
                role    = parts[1].strip()
                role    = _strip_date(role)
                break

        # Look through next 2 lines for role / date if not found on first line
        for extra_line in entry_lines[1:3]:
            extra = extra_line.strip()
            if not extra or extra[0] in "•-*◦▪▸→–—":
                break
            if not duration:
                duration = _pull_date(extra)
            if not role and (
                not _DATE_PAT.fullmatch(extra)
                and len(extra) < 70
                and not re.match(r"(?i)^(?:technologies?|tools?)", extra)
            ):
                role = _strip_date(extra)

        if not company or len(company) < 2:
            continue

        # Collect bullet-point responsibilities
        responsibilities: list[str] = []
        for raw in entry_lines[1:]:
            stripped = raw.strip()
            clean    = re.sub(r"^[•\-*◦▪▸→–—]\s*", "", stripped)
            if (
                clean
                and len(clean) > 10
                and not _DATE_PAT.fullmatch(clean)
                and clean != role
            ):
                responsibilities.append(clean)

        experiences.append(WorkExperience(
            company=company,
            role=role,
            duration=duration,
            responsibilities=responsibilities[:6],
        ))

    return experiences


# ── Experience level (uses structured work_exp count if available) ────────────

def _extract_experience_level(text: str, work_exp: list = None) -> str:
    t = text.lower()
    if re.search(r"\b(senior|lead|principal|staff|architect|head of|vp|director)\b", t):
        return "senior"
    if re.search(r"\b(junior|entry.?level|fresher|trainee|graduate)\b", t):
        return "junior"
    m = re.search(r"(\d+)\+?\s*years?\s*(?:of\s*)?(?:experience|exp)", t)
    if m:
        yrs = int(m.group(1))
        return "senior" if yrs >= 5 else ("mid" if yrs >= 2 else "junior")
    if work_exp:
        n = len(work_exp)
        return "senior" if n >= 3 else ("mid" if n >= 1 else "junior")
    jobs = len(re.findall(r"\b(?:20\d{2})\s*[-–]\s*(?:20\d{2}|present|current)", t))
    return "senior" if jobs >= 3 else ("mid" if jobs >= 1 else "junior")


# ── Domain inference (enhanced: certifications + project techs) ───────────────

def _infer_domains(
    skills:         list[str],
    certifications: list = None,
    projects:       list = None,
) -> list[str]:
    s = {sk.lower() for sk in skills}

    fe  = len(s & {"javascript", "react", "angular", "vue.js", "vue", "html", "css", "typescript", "next.js"})
    be  = len(s & {"python", "java", "node.js", "django", "fastapi", "flask", "spring", "express.js", "express", "c#", "go", "rust"})
    ml  = len(s & {"tensorflow", "pytorch", "keras", "deep learning", "machine learning", "nlp", "computer vision"})
    ds  = len(s & {"pandas", "numpy", "scikit-learn", "r", "tableau", "statistics", "machine learning"})
    do  = len(s & {"docker", "kubernetes", "aws", "azure", "gcp", "google cloud", "ci/cd", "terraform", "jenkins"})
    mob = len(s & {"ios", "android", "react native", "flutter", "swift", "kotlin"})
    de  = len(s & {"spark", "hadoop", "airflow", "kafka", "dbt", "snowflake", "databricks"})
    net = len(s & {"cisco", "ccna", "ccnp", "wireshark"})

    # Boost from certifications (each cert counts as +1 for its domain)
    if certifications:
        for cert in certifications:
            cert_text = (cert.name + " " + cert.issuer).lower()
            for kw, domain in _TECH_DOMAIN_MAP.items():
                if kw in cert_text:
                    dl = domain.lower()
                    if "cloud" in dl or "devops" in dl:     do  += 1
                    elif "network" in dl:                    net += 1
                    elif "machine learning" in dl:           ml  += 1
                    elif "data engineering" in dl:           de  += 1
                    elif "data science" in dl:               ds  += 1
                    elif "frontend" in dl:                   fe  += 1
                    elif "backend" in dl:                    be  += 1
                    elif "mobile" in dl:                     mob += 1
                    break  # one domain per cert

    # Boost from project technologies (fractional, so one project doesn't dominate)
    if projects:
        for proj in projects:
            for tech in proj.technologies:
                domain = _TECH_DOMAIN_MAP.get(tech.lower(), "")
                dl = domain.lower()
                if "cloud" in dl or "devops" in dl:     do  += 0.5
                elif "machine learning" in dl:           ml  += 0.5
                elif "data engineering" in dl:           de  += 0.5
                elif "frontend" in dl:                   fe  += 0.5
                elif "backend" in dl:                    be  += 0.5

    domains: list[str] = []
    if fe >= 2 and be >= 2: domains.append("Full Stack Web")
    elif fe >= 2:            domains.append("Web Frontend")
    elif be >= 2:            domains.append("Web Backend")
    if ml >= 2:              domains.append("Machine Learning / AI")
    if ds >= 3:              domains.append("Data Science")
    if do >= 2:              domains.append("Cloud / DevOps")
    if mob >= 1:             domains.append("Mobile Development")
    if de >= 2:              domains.append("Data Engineering")
    if net >= 1:             domains.append("Networking")

    return domains or ["General Software Development"]


# ── Strengths (updated to recognize certifications + work experience) ──────────

def _infer_strengths(
    skills:         list[str],
    projects:       list,
    level:          str,
    certifications: list = None,
    work_exp:       list = None,
) -> list[str]:
    s   = {sk.lower() for sk in skills}
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
    elif work_exp and len(work_exp) >= 1:
        out.append("Professional work / internship experience")
    if certifications and len(certifications) >= 1:
        out.append(f"Industry-recognised certification ({certifications[0].name})")
    if {"git", "github", "agile", "scrum"} & s:
        out.append("Collaborative development practices")

    return out[:5] or ["Technical proficiency demonstrated through projects"]


# ── Weak areas (domain-driven) ────────────────────────────────────────────────

# Each entry: (skill_set_that_covers_the_gap, human-readable label)
# If the candidate's skills have NO intersection with the skill_set, the gap is flagged.
_DOMAIN_WEAK_RULES: dict[str, list[tuple]] = {
    "Web Frontend": [
        ({"jest", "cypress", "playwright", "testing-library"}, "Frontend testing (Jest / Cypress)"),
        ({"typescript"},                                        "TypeScript adoption"),
        ({"docker", "kubernetes", "aws", "azure", "gcp"},      "Cloud / deployment knowledge"),
        ({"webpack", "vite", "rollup"},                         "Build-tooling familiarity"),
    ],
    "Web Backend": [
        ({"docker", "kubernetes"},                              "Containerization (Docker / Kubernetes)"),
        ({"redis", "kafka", "rabbitmq", "celery"},              "Caching and message queues"),
        ({"pytest", "junit", "jest"},                           "Automated testing practices"),
        ({"aws", "azure", "gcp", "google cloud"},               "Cloud platform experience"),
    ],
    "Full Stack Web": [
        ({"jest", "cypress", "playwright", "pytest"},           "End-to-end / unit testing"),
        ({"docker", "kubernetes"},                              "Containerization (Docker / Kubernetes)"),
        ({"redis", "kafka"},                                    "Caching and async messaging"),
        ({"aws", "azure", "gcp", "google cloud"},               "Cloud deployment experience"),
    ],
    "Machine Learning / AI": [
        ({"docker", "kubernetes", "mlflow", "kubeflow"},        "MLOps / model deployment"),
        ({"spark", "kafka", "airflow"},                         "Large-scale data pipelines"),
        ({"sql", "postgresql", "mysql"},                        "Structured-data / SQL proficiency"),
        ({"git", "github", "gitlab"},                           "Version-control discipline"),
    ],
    "Data Science": [
        ({"spark", "hadoop", "dbt"},                            "Big-data processing skills"),
        ({"docker", "aws", "gcp", "azure"},                     "Cloud and deployment awareness"),
        ({"pytorch", "tensorflow", "keras"},                    "Deep-learning exposure"),
        ({"sql", "postgresql", "mysql"},                        "Advanced SQL proficiency"),
    ],
    "Cloud / DevOps": [
        ({"python", "go", "bash", "rust"},                      "Scripting / automation language"),
        ({"prometheus", "grafana", "datadog"},                  "Monitoring and observability"),
        ({"terraform", "ansible", "pulumi"},                    "Infrastructure-as-code"),
        ({"kubernetes"},                                        "Container orchestration (Kubernetes)"),
    ],
    "Data Engineering": [
        ({"docker", "kubernetes"},                              "Containerized pipeline deployment"),
        ({"tensorflow", "pytorch", "scikit-learn"},             "ML integration knowledge"),
        ({"aws", "azure", "gcp"},                               "Cloud data platform experience"),
        ({"sql", "postgresql"},                                 "Advanced SQL / query optimisation"),
    ],
    "Mobile Development": [
        ({"jest", "xctest", "espresso"},                        "Mobile testing frameworks"),
        ({"docker", "aws", "firebase"},                         "Backend / cloud integration"),
        ({"typescript", "swift", "kotlin"},                     "Strongly-typed language depth"),
        ({"figma", "sketch"},                                   "UI/UX design-tool exposure"),
    ],
    "Networking": [
        ({"python", "bash", "go"},                              "Network scripting / automation"),
        ({"docker", "kubernetes"},                              "Container networking knowledge"),
        ({"aws", "azure", "gcp"},                               "Cloud networking services"),
        ({"prometheus", "grafana", "wireshark"},                "Network monitoring tools"),
    ],
    "General Software Development": [
        ({"aws", "azure", "gcp", "google cloud"},               "Cloud platform experience"),
        ({"docker", "kubernetes"},                              "Containerization skills"),
        ({"jest", "pytest", "junit"},                           "Automated testing practices"),
        ({"typescript"},                                        "TypeScript / static typing"),
    ],
}


def _infer_weak_areas(skills: list[str], domains: list[str]) -> list[str]:
    s = {sk.lower() for sk in skills}
    seen: set[str] = set()
    weak: list[str] = []

    for domain in domains:
        rules = _DOMAIN_WEAK_RULES.get(
            domain,
            _DOMAIN_WEAK_RULES["General Software Development"],
        )
        for skill_set, label in rules:
            if not (skill_set & s) and label not in seen:
                seen.add(label)
                weak.append(label)

    return weak[:4]


# ── Public API ─────────────────────────────────────────────────────────────────

def analyze(raw_text: str, candidate_id: str) -> ResumeAnalysis:
    raw_text = _split_inline_section_header(raw_text)
    lines          = [l.strip() for l in raw_text.split("\n") if l.strip()]

    # Parse sections first — all extractors use this dict
    sections       = _parse_sections(raw_text)

    skills         = _extract_skills(raw_text)
    projects       = _extract_projects(raw_text, sections)

    # Classify each project's primary domain for role-aware selection later
    try:
        from services.project_classifier import classify_project
        for proj in projects:
            proj.domain = classify_project(proj)
    except Exception:
        pass  # domain stays None; selection falls back to projects[0]

    certifications = _extract_certifications(sections)
    achievements   = _extract_achievements(sections)
    work_exp       = _extract_work_experience(sections)
    exp_level      = _extract_experience_level(raw_text, work_exp)
    domains        = _infer_domains(skills, certifications, projects)

    return ResumeAnalysis(
        candidate_id=candidate_id,
        candidate_name=_extract_name(lines),
        email=_extract_email(raw_text),
        phone=_extract_phone(raw_text),
        skills=skills,
        projects=projects,
        education=_extract_education(raw_text, sections),
        experience_level=exp_level,
        domains=domains,
        strengths=_infer_strengths(skills, projects, exp_level, certifications, work_exp),
        weak_areas=_infer_weak_areas(skills, domains),
        certifications=certifications,
        achievements=achievements,
        work_experience=work_exp,
    )
