"""
Interview session orchestrator.
Generates the first question using candidate profile + selected role.
Uses smart personalised static questions by default; upgrades to LLM when USE_LLM=true.
"""

import uuid
import logging
import json
import re
from datetime import datetime, timezone

from models.interview import Question, InterviewSession
from models.analysis import ResumeAnalysis

logger = logging.getLogger(__name__)

# ── Static question bank ──────────────────────────────────────────────────────
# Each role has three opening-question templates:
#   "project"  – references a specific project (used when candidate.projects is non-empty)
#   "skills"   – references detected skills
#   "general"  – safe fallback with no personalisation needed

_BANK: dict[str, dict[str, dict]] = {
    "Full Stack Developer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": (
                "I can see you worked on '{project}' using {techs}. "
                "Could you walk me through the overall architecture — how did you split responsibilities "
                "between the frontend and backend, and what was the trickiest problem you had to solve?"
            ),
            "expected_points": [
                "Describe the system architecture and data flow",
                "Explain the frontend/backend boundary and API design",
                "Share a specific technical challenge and how it was resolved",
                "Reflect on what you would change with hindsight",
            ],
        },
        "skills": {
            "topic": "Role Introduction",
            "question": (
                "Your resume shows experience with {skills}. "
                "How do you typically approach starting a new full-stack feature — "
                "from design all the way through to deployment?"
            ),
            "expected_points": [
                "Describe the end-to-end development workflow",
                "Explain API contract decisions (REST, GraphQL, etc.)",
                "Discuss state management and data fetching choices",
                "Mention testing and deployment practices",
            ],
        },
        "general": {
            "topic": "Role Introduction",
            "question": (
                "Tell me about a full-stack project you're most proud of. "
                "What was the problem it solved and how did you decide on the technology choices?"
            ),
            "expected_points": [
                "Articulate the problem being solved",
                "Justify the technology stack selected",
                "Describe the architecture at a high level",
                "Highlight personal contributions and learnings",
            ],
        },
    },
    "Frontend Developer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": (
                "I see you built '{project}' — can you walk me through how you structured the component hierarchy "
                "and how you managed state across the application?"
            ),
            "expected_points": [
                "Explain component decomposition strategy",
                "Describe state management approach (local, Context, Redux, etc.)",
                "Discuss performance considerations taken",
                "Share any accessibility or responsive design decisions",
            ],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": (
                "You've listed {skills} on your resume. "
                "How do you decide between local component state and a global state solution "
                "when building a new feature?"
            ),
            "expected_points": [
                "Explain criteria for local vs. global state",
                "Compare at least two state management strategies",
                "Discuss scalability and maintainability trade-offs",
                "Give a concrete example from experience",
            ],
        },
        "general": {
            "topic": "Role Introduction",
            "question": (
                "Walk me through how you approach building a new UI feature from design mockup to production. "
                "What does your typical process look like?"
            ),
            "expected_points": [
                "Describe how you interpret design specs",
                "Explain component planning before coding",
                "Mention cross-browser and responsive testing",
                "Discuss code review and deployment steps",
            ],
        },
    },
    "Backend Developer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": (
                "Tell me about the backend of '{project}'. "
                "How did you design the API layer, and what approach did you take to data storage with {techs}?"
            ),
            "expected_points": [
                "Explain API design decisions (REST, versioning, error handling)",
                "Describe the data model and database schema rationale",
                "Discuss authentication and security measures applied",
                "Share any performance or scalability considerations",
            ],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": (
                "Given your experience with {skills}, how do you approach designing a REST API from scratch — "
                "what are the key decisions you make before writing any code?"
            ),
            "expected_points": [
                "Explain resource modelling and URL structure",
                "Discuss HTTP method semantics and status codes",
                "Describe error handling strategy",
                "Mention authentication, rate limiting, and versioning",
            ],
        },
        "general": {
            "topic": "Role Introduction",
            "question": (
                "Describe a backend system you built that you're proud of. "
                "What were the main design decisions and what trade-offs did you make?"
            ),
            "expected_points": [
                "Articulate the system's purpose and scale",
                "Explain key architectural and tech-stack decisions",
                "Discuss trade-offs (e.g. SQL vs NoSQL, sync vs async)",
                "Reflect on what worked well and what you'd improve",
            ],
        },
    },
    "Data Scientist": {
        "project": {
            "topic": "Project Deep Dive",
            "question": (
                "I noticed '{project}' on your resume. Could you walk me through your end-to-end ML workflow — "
                "from raw data to the final model, including how you validated its performance?"
            ),
            "expected_points": [
                "Describe data collection and cleaning steps",
                "Explain feature engineering decisions",
                "Discuss model selection and evaluation metrics chosen",
                "Share how findings were communicated to stakeholders",
            ],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": (
                "You have experience with {skills}. "
                "How do you approach selecting the right model for a new prediction problem — "
                "what factors guide your decision?"
            ),
            "expected_points": [
                "Explain baseline model strategy",
                "Discuss bias-variance trade-off",
                "Describe cross-validation and metric selection",
                "Mention interpretability vs. performance considerations",
            ],
        },
        "general": {
            "topic": "Role Introduction",
            "question": (
                "Tell me about a data science project where the results surprised you. "
                "What did the data reveal, and how did that change your approach?"
            ),
            "expected_points": [
                "Describe the problem and initial hypothesis",
                "Explain what the data showed that was unexpected",
                "Discuss how the methodology was adjusted",
                "Share the final outcome and business impact",
            ],
        },
    },
    "ML / AI Engineer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": (
                "Tell me about '{project}'. How did you go from a trained model to something "
                "running reliably in production — what was your serving and monitoring strategy?"
            ),
            "expected_points": [
                "Describe the model training pipeline",
                "Explain the serving architecture (API, batch, streaming)",
                "Discuss monitoring for model drift and data quality",
                "Share challenges faced in the production environment",
            ],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": (
                "You've worked with {skills}. How do you decide between fine-tuning a pre-trained model "
                "versus training from scratch for a new ML task?"
            ),
            "expected_points": [
                "Discuss available data size and quality considerations",
                "Explain transfer learning trade-offs",
                "Describe compute budget and latency requirements",
                "Mention evaluation methodology for the comparison",
            ],
        },
        "general": {
            "topic": "Role Introduction",
            "question": (
                "Describe an ML system you built or contributed to significantly. "
                "How did you ensure it performed reliably once deployed?"
            ),
            "expected_points": [
                "Explain the problem the model solves",
                "Describe the training and evaluation process",
                "Discuss deployment architecture and monitoring",
                "Share lessons learned from production behaviour",
            ],
        },
    },
    "DevOps / Cloud Engineer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": (
                "Tell me about the infrastructure you set up for '{project}'. "
                "How did you handle deployment, scaling, and observability?"
            ),
            "expected_points": [
                "Describe the infrastructure topology (cloud provider, regions)",
                "Explain CI/CD pipeline design",
                "Discuss auto-scaling and reliability strategies",
                "Share monitoring, alerting, and incident-response setup",
            ],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": (
                "With your experience in {skills}, how would you design a CI/CD pipeline "
                "for a microservices application that needs zero-downtime deployments?"
            ),
            "expected_points": [
                "Outline pipeline stages (build, test, deploy)",
                "Explain blue/green or canary deployment strategy",
                "Discuss rollback mechanisms",
                "Mention secrets management and environment promotion",
            ],
        },
        "general": {
            "topic": "Role Introduction",
            "question": (
                "Walk me through the most complex infrastructure problem you've solved. "
                "What was the situation, what did you do, and what was the outcome?"
            ),
            "expected_points": [
                "Set the context and scale of the system",
                "Explain root cause diagnosis process",
                "Describe the solution implemented",
                "Share the measurable impact (uptime, cost, speed)",
            ],
        },
    },
    "Mobile Developer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": (
                "Tell me about '{project}'. How did you handle state management and "
                "keep the UI smooth while making network requests in the background?"
            ),
            "expected_points": [
                "Describe the state management approach chosen",
                "Explain async data fetching and loading state strategy",
                "Discuss UI thread concerns and optimisation techniques",
                "Share how you tested on different device sizes and OS versions",
            ],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": (
                "You've worked with {skills}. How do you approach optimising app startup time "
                "and ensuring a smooth 60 fps experience throughout?"
            ),
            "expected_points": [
                "Describe lazy loading and code splitting strategies",
                "Explain how to avoid blocking the main/UI thread",
                "Discuss profiling tools used to identify bottlenecks",
                "Mention image and asset optimisation techniques",
            ],
        },
        "general": {
            "topic": "Role Introduction",
            "question": (
                "Tell me about a mobile app you've shipped. "
                "What were the biggest technical challenges from development to App Store release?"
            ),
            "expected_points": [
                "Describe the app's core user problem",
                "Explain a significant technical challenge encountered",
                "Discuss testing strategy across devices",
                "Share the release process and any post-launch fixes",
            ],
        },
    },
    "Data Engineer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": (
                "Walk me through the data pipeline you built for '{project}'. "
                "How did you ensure reliability, handle late-arriving data, and monitor pipeline health?"
            ),
            "expected_points": [
                "Describe the pipeline architecture (sources, transformations, sinks)",
                "Explain idempotency and error recovery design",
                "Discuss handling of late or out-of-order data",
                "Share monitoring and alerting approach for pipeline failures",
            ],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": (
                "Given your experience with {skills}, how do you approach designing "
                "a data pipeline that needs to be both reliable and easy to extend?"
            ),
            "expected_points": [
                "Explain modularity and separation of concerns in pipeline design",
                "Discuss idempotency and exactly-once semantics",
                "Describe schema evolution strategy",
                "Mention testing and data quality validation approaches",
            ],
        },
        "general": {
            "topic": "Role Introduction",
            "question": (
                "Tell me about a data pipeline you built that you're particularly proud of. "
                "What problem did it solve and how did you ensure data quality end to end?"
            ),
            "expected_points": [
                "Describe the business problem and data sources involved",
                "Explain key architectural decisions made",
                "Discuss data quality checks implemented",
                "Share performance and reliability outcomes",
            ],
        },
    },
}

_GENERIC_OPENING = {
    "topic": "Role Introduction",
    "question": (
        "Tell me about yourself and what drew you to this role. "
        "Which project or achievement from your background are you most proud of, and why?"
    ),
    "expected_points": [
        "Give a concise professional summary",
        "Connect past experience to this role",
        "Highlight a specific achievement with measurable impact",
        "Express genuine motivation for the position",
    ],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _qid() -> str:
    return "Q" + str(uuid.uuid4()).replace("-", "")[:8].upper()


def _fill(template: str, project_name: str, techs: str, skills: str) -> str:
    return (
        template
        .replace("{project}", project_name)
        .replace("{techs}", techs)
        .replace("{skills}", skills)
    )


def _build_static(analysis: ResumeAnalysis, role: str) -> Question:
    bank = _BANK.get(role, {})

    skill_str = ", ".join(analysis.skills[:5]) if analysis.skills else "your listed technologies"

    if analysis.projects and "project" in bank:
        p = analysis.projects[0]
        tech_str = ", ".join(p.technologies[:3]) if p.technologies else skill_str
        tmpl = bank["project"]
        return Question(
            question_id=_qid(),
            question=_fill(tmpl["question"], p.name, tech_str, skill_str),
            difficulty="easy",
            topic=tmpl["topic"],
            expected_points=tmpl["expected_points"],
        )

    if analysis.skills and "skills" in bank:
        tmpl = bank["skills"]
        return Question(
            question_id=_qid(),
            question=_fill(tmpl["question"], "", "", skill_str),
            difficulty="easy",
            topic=tmpl["topic"],
            expected_points=tmpl["expected_points"],
        )

    if "general" in bank:
        tmpl = bank["general"]
        return Question(
            question_id=_qid(),
            question=tmpl["question"],
            difficulty="easy",
            topic=tmpl["topic"],
            expected_points=tmpl["expected_points"],
        )

    return Question(
        question_id=_qid(),
        question=_GENERIC_OPENING["question"],
        difficulty="easy",
        topic=_GENERIC_OPENING["topic"],
        expected_points=_GENERIC_OPENING["expected_points"],
    )


async def _generate_with_llm(analysis: ResumeAnalysis, role: str) -> Question | None:
    from config import get_settings
    settings = get_settings()
    if not settings.use_llm or not settings.anthropic_api_key:
        return None

    try:
        import anthropic

        project_line = ""
        if analysis.projects:
            p = analysis.projects[0]
            techs = ", ".join(p.technologies[:3])
            project_line = f"Most prominent project: '{p.name}' using {techs}."

        prompt = (
            f"You are a warm, senior technical interviewer opening a mock interview.\n\n"
            f"Role: {role}\n"
            f"Candidate skills: {', '.join(analysis.skills[:12])}\n"
            f"Experience level: {analysis.experience_level}\n"
            f"{project_line}\n\n"
            "Generate the FIRST interview question. Rules:\n"
            "- Difficulty must be 'easy' — don't intimidate the candidate at the start\n"
            "- If a project is listed, reference it by name\n"
            "- Be specific, conversational, and open-ended\n"
            "- topic must be 'Project Deep Dive' or 'Role Introduction'\n\n"
            "Return ONLY valid JSON — no prose, no markdown:\n"
            '{"question": "...", "topic": "...", "expected_points": ["...", "...", "...", "..."]}'
        )

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            return Question(
                question_id=_qid(),
                question=data["question"],
                difficulty="easy",
                topic=data.get("topic", "Role Introduction"),
                expected_points=data.get("expected_points", []),
            )
    except Exception as exc:
        logger.warning("LLM question generation failed, using static fallback: %s", exc)

    return None


# ── Public API ────────────────────────────────────────────────────────────────

async def start_session(
    candidate_id: str,
    selected_role: str,
    analysis: ResumeAnalysis | None,
) -> tuple[InterviewSession, Question]:
    session_id = "INT-" + str(uuid.uuid4()).replace("-", "")[:10].upper()

    # Try LLM first, fall back to smart static
    first_q: Question | None = None
    if analysis:
        first_q = await _generate_with_llm(analysis, selected_role)
    if first_q is None:
        first_q = _build_static(analysis or ResumeAnalysis(
            candidate_id=candidate_id, candidate_name="", email="", phone="",
            skills=[], projects=[], education="", experience_level="mid",
            domains=[], strengths=[], weak_areas=[],
        ), selected_role)

    session = InterviewSession(
        session_id=session_id,
        candidate_id=candidate_id,
        selected_role=selected_role,
        status="active",
        created_at=datetime.now(timezone.utc),
        questions_asked=[first_q],
        current_question=first_q,
    )

    return session, first_q
