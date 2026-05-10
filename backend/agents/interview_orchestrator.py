"""
Interview session orchestrator.
Phase 3 — first question from personalised static bank or LLM.
Phase 5 — adaptive next-question selection with difficulty escalation/de-escalation.
"""

import uuid
import logging
import json
import re
from datetime import datetime, timezone

from models.interview import Question, InterviewSession, NextQuestionRequest, NextQuestionResponse
from models.analysis import ResumeAnalysis

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 5

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


# ── Adaptive question bank (multi-role, multi-difficulty, multi-topic) ────────
# Each entry: question, difficulty, topic, expected_points

_ADAPTIVE_BANK: dict[str, list[dict]] = {
    "Full Stack Developer": [
        # REST Fundamentals
        {
            "q": "What makes an API RESTful? Walk me through the key principles and how you apply them in practice.",
            "d": "easy", "t": "REST Fundamentals",
            "p": ["Stateless client-server model", "Uniform interface with HTTP verbs", "Resource-based URLs", "HTTP status codes used correctly", "HATEOAS or hypermedia awareness"],
        },
        {
            "q": "How do you handle API versioning when multiple clients are on different versions simultaneously?",
            "d": "medium", "t": "REST Fundamentals",
            "p": ["URL vs header versioning trade-offs", "Backward compatibility guarantees", "Deprecation timeline and sunset headers", "API gateway routing strategy", "Consumer-driven contract testing"],
        },
        {
            "q": "Design a rate-limiting system for a public REST API that needs to handle 50,000 requests per second fairly.",
            "d": "hard", "t": "REST Fundamentals",
            "p": ["Token bucket or sliding window algorithm", "Distributed counter using Redis", "Per-user vs global limits", "Returning 429 with Retry-After", "Bypass for internal services"],
        },
        # Database Design
        {
            "q": "When would you choose PostgreSQL over MongoDB, and when would you choose MongoDB over PostgreSQL?",
            "d": "easy", "t": "Database Design",
            "p": ["ACID transactions for financial/relational data", "Flexible schema for evolving documents", "Join complexity considerations", "Scalability and sharding differences", "Indexing and query pattern alignment"],
        },
        {
            "q": "How would you design a database schema for a multi-tenant SaaS platform where each tenant must have strict data isolation?",
            "d": "medium", "t": "Database Design",
            "p": ["Shared schema with tenant_id column approach", "Schema-per-tenant approach", "Row-level security policies", "Index design for tenant-scoped queries", "Migration strategy across tenants"],
        },
        {
            "q": "Explain N+1 query problem. How do you detect it and what are the different strategies to resolve it?",
            "d": "easy", "t": "Database Design",
            "p": ["Definition with concrete example", "Detection using query logging", "Eager loading / JOIN solution", "DataLoader or batch fetching pattern", "ORM-specific solutions"],
        },
        # Authentication & Security
        {
            "q": "Walk me through how JWT authentication works end-to-end, from login to accessing a protected resource.",
            "d": "easy", "t": "Authentication",
            "p": ["Token structure: header, payload, signature", "Login endpoint and token issuance", "Client storage options and risks", "Server-side signature verification", "Token expiration and renewal"],
        },
        {
            "q": "How would you implement a secure refresh token rotation system to prevent token theft while maintaining good UX?",
            "d": "medium", "t": "Authentication",
            "p": ["HttpOnly cookie for refresh token storage", "Rotation on every refresh call", "Token family tracking for reuse detection", "Revocation on suspicious reuse", "Absolute vs sliding expiration"],
        },
        {
            "q": "What are the most critical web security vulnerabilities and how do you defend against each one in a Node.js/React stack?",
            "d": "medium", "t": "Security",
            "p": ["SQL injection via parameterized queries", "XSS via output sanitization and CSP", "CSRF via SameSite cookies", "CORS misconfiguration risks", "Rate limiting and input validation"],
        },
        # Performance
        {
            "q": "A full-stack page loads in 8 seconds. Walk me through your systematic process for diagnosing and fixing the bottleneck.",
            "d": "medium", "t": "Performance Optimization",
            "p": ["Separating network vs backend vs frontend time", "Profiling DB queries for N+1 and slow queries", "Caching strategy with Redis or CDN", "Frontend bundle size and lazy loading", "Async operations and background jobs"],
        },
        # System Design
        {
            "q": "Design the backend for a real-time collaborative document editor. Focus on how you handle concurrent edits.",
            "d": "hard", "t": "System Design",
            "p": ["Operational Transformation or CRDT for conflict resolution", "WebSocket connection management", "Presence awareness and cursor sync", "Persistence and recovery strategy", "Horizontal scaling approach"],
        },
        {
            "q": "How would you architect a notification system that needs to handle millions of push, email, and in-app notifications daily?",
            "d": "hard", "t": "System Design",
            "p": ["Message queue (Kafka or RabbitMQ) for async delivery", "Template rendering service", "Delivery tracking and retry logic", "User preference and opt-out system", "Fan-out strategy for large recipient lists"],
        },
        # Error Handling
        {
            "q": "How do you design a consistent error handling strategy across a full-stack app — both on the API and the React frontend?",
            "d": "easy", "t": "Error Handling",
            "p": ["Centralised error middleware in Express/FastAPI", "Problem+JSON or consistent error response schema", "React Error Boundaries for component failures", "Correlation IDs for tracing errors across services", "User-friendly error messaging vs logging detail"],
        },
        # Frontend Architecture
        {
            "q": "When would you use local component state vs React Context vs a global store like Redux? Walk through your decision process.",
            "d": "medium", "t": "Frontend Architecture",
            "p": ["Local state for isolated component concerns", "Context for low-frequency shared state", "Redux/Zustand for complex cross-cutting state", "Performance implications of Context re-renders", "Server state vs client state distinction"],
        },
    ],

    "Frontend Developer": [
        {
            "q": "Explain how the React reconciliation algorithm (Virtual DOM diffing) works and why it matters for performance.",
            "d": "easy", "t": "React Internals",
            "p": ["Virtual DOM as in-memory representation", "Diffing algorithm and heuristics", "Key prop importance for lists", "Component identity across renders", "Why unnecessary re-renders happen"],
        },
        {
            "q": "How do you decide when to use useCallback, useMemo, and React.memo? Give me a concrete example of each.",
            "d": "medium", "t": "React Internals",
            "p": ["useCallback for stable function references", "useMemo for expensive computed values", "React.memo for pure component memoization", "When over-memoisation hurts performance", "Profiler to verify optimisation impact"],
        },
        {
            "q": "Design a component library that needs to support theming, accessibility, and be consumed by multiple React applications.",
            "d": "hard", "t": "Frontend Architecture",
            "p": ["CSS-in-JS vs CSS variables for theming", "Compound component pattern", "ARIA roles and keyboard navigation", "Package distribution strategy (monorepo)", "Storybook for documentation and testing"],
        },
        {
            "q": "What is the difference between client-side rendering, server-side rendering, and static site generation? When do you choose each?",
            "d": "easy", "t": "Rendering Strategies",
            "p": ["CSR: bundle sent, rendered in browser", "SSR: rendered on server per request", "SSG: pre-rendered at build time", "SEO and Time-to-First-Byte trade-offs", "Next.js hybrid rendering approach"],
        },
        {
            "q": "How do you approach code splitting and lazy loading in a large React SPA to improve initial load time?",
            "d": "medium", "t": "Performance Optimization",
            "p": ["React.lazy and Suspense for route-level splitting", "Dynamic import() for component libraries", "Webpack bundle analyser to identify bloat", "Preloading critical resources", "Cache-control headers and chunk hashing"],
        },
        {
            "q": "How do you ensure a complex web application meets WCAG accessibility standards? What is your testing process?",
            "d": "medium", "t": "Accessibility",
            "p": ["Semantic HTML as the foundation", "ARIA labels for dynamic content", "Keyboard navigation and focus management", "Color contrast and text sizing", "axe-core and screen reader testing"],
        },
        {
            "q": "Explain the CSS cascade, specificity, and inheritance. How do you structure CSS in large applications to avoid specificity wars?",
            "d": "easy", "t": "CSS Fundamentals",
            "p": ["Cascade order: browser → author → inline", "Specificity calculation (0,0,0,0)", "BEM naming methodology", "CSS Modules or CSS-in-JS for scoping", "Custom properties for theming"],
        },
        {
            "q": "How would you implement an infinite scroll feed that remains performant with 10,000+ items?",
            "d": "hard", "t": "Performance Optimization",
            "p": ["Virtual list / windowing with react-window", "IntersectionObserver for scroll detection", "Server-side cursor pagination", "Placeholder skeletons for loading states", "Memory management and DOM node recycling"],
        },
    ],

    "Backend Developer": [
        {
            "q": "What is idempotency? Which HTTP methods must be idempotent and why does it matter for distributed systems?",
            "d": "easy", "t": "API Design",
            "p": ["Idempotency definition with example", "GET, PUT, DELETE must be idempotent", "POST is not inherently idempotent", "Idempotency keys for payment APIs", "At-least-once delivery and deduplication"],
        },
        {
            "q": "How would you design a webhook delivery system that guarantees at-least-once delivery with ordered processing?",
            "d": "medium", "t": "API Design",
            "p": ["Durable queue (SQS, RabbitMQ) for delivery", "Retry with exponential backoff", "Dead-letter queue for failures", "Idempotency on consumer side", "Ordering via partition key or FIFO queue"],
        },
        {
            "q": "Explain database transactions and isolation levels. When would you use SERIALIZABLE vs READ COMMITTED?",
            "d": "medium", "t": "Database",
            "p": ["ACID properties", "READ COMMITTED prevents dirty reads", "REPEATABLE READ prevents non-repeatable reads", "SERIALIZABLE prevents phantom reads", "Performance trade-offs of higher isolation"],
        },
        {
            "q": "How do you design a caching strategy that avoids cache stampede and stale data issues?",
            "d": "medium", "t": "Performance",
            "p": ["Cache-aside vs write-through vs write-behind", "TTL selection and cache warming", "Probabilistic early expiration to prevent stampede", "Cache invalidation strategies", "Distributed cache consistency (Redis Cluster)"],
        },
        {
            "q": "Walk me through how you would migrate a monolith to microservices without downtime.",
            "d": "hard", "t": "System Design",
            "p": ["Strangler fig pattern", "Identifying service boundaries by domain", "Shared database decomposition strategy", "API gateway for routing during migration", "Feature flags and canary releases"],
        },
        {
            "q": "How does Python's GIL affect concurrency? What strategies do you use to achieve true parallelism in Python services?",
            "d": "easy", "t": "Concurrency",
            "p": ["GIL prevents true thread parallelism for CPU tasks", "asyncio for I/O-bound concurrency", "multiprocessing for CPU-bound tasks", "Celery for distributed task execution", "When threads are still useful (I/O-bound)"],
        },
        {
            "q": "Describe how you would implement distributed tracing across microservices for debugging production issues.",
            "d": "hard", "t": "Observability",
            "p": ["Trace ID propagation via headers", "Span creation for each service hop", "OpenTelemetry as the collection standard", "Jaeger or Tempo for trace visualisation", "Sampling strategy to manage volume"],
        },
    ],

    "Data Scientist": [
        {
            "q": "When would you choose logistic regression over a gradient-boosted tree for a classification problem?",
            "d": "easy", "t": "Model Selection",
            "p": ["Logistic regression: interpretability and fast training", "GBT: non-linear patterns, higher accuracy", "Data size and feature engineering cost", "Regulatory interpretability requirements", "Baseline model strategy"],
        },
        {
            "q": "Explain the bias-variance trade-off and how regularisation techniques address it.",
            "d": "medium", "t": "Model Theory",
            "p": ["Bias: underfitting from oversimplified model", "Variance: overfitting from too-complex model", "L1 regularisation drives sparsity (Lasso)", "L2 regularisation shrinks weights (Ridge)", "Cross-validation to detect the trade-off"],
        },
        {
            "q": "How would you design an A/B test to determine if a new recommendation algorithm improves conversion rate?",
            "d": "medium", "t": "Experimentation",
            "p": ["Define primary and guardrail metrics", "Sample size calculation from power analysis", "Randomisation unit (user vs session)", "Checking for novelty effect and seasonality", "Statistical significance vs practical significance"],
        },
        {
            "q": "Walk me through how you handle class imbalance in a fraud detection model (1 fraud per 10,000 transactions).",
            "d": "medium", "t": "Practical ML",
            "p": ["SMOTE or undersampling strategies", "Precision-recall curve over ROC-AUC", "Class weight adjustment in the loss function", "Threshold tuning for business requirements", "Cost-sensitive learning"],
        },
        {
            "q": "How do you deploy a machine learning model to production and monitor it for data drift and performance degradation?",
            "d": "hard", "t": "MLOps",
            "p": ["Model serialisation and versioning (MLflow)", "REST API or batch scoring deployment", "Feature distribution monitoring (PSI, KS test)", "Prediction drift vs concept drift", "Automated retraining triggers"],
        },
        {
            "q": "Explain the difference between precision and recall. Give a real example where you would optimise for one over the other.",
            "d": "easy", "t": "Evaluation Metrics",
            "p": ["Precision: of predicted positives, how many are true", "Recall: of actual positives, how many were caught", "Medical screening: high recall priority", "Spam filter: high precision priority", "F1 score as a harmonic mean"],
        },
    ],

    "ML / AI Engineer": [
        {
            "q": "What is the difference between fine-tuning a pre-trained model and training from scratch? When would you choose each?",
            "d": "easy", "t": "Transfer Learning",
            "p": ["Pre-training captures general representations", "Fine-tuning adapts to domain-specific patterns", "Data size threshold for each approach", "Catastrophic forgetting risk in fine-tuning", "PEFT techniques: LoRA, prefix tuning"],
        },
        {
            "q": "Explain how attention mechanisms in transformers work, and why they replaced recurrent architectures for NLP.",
            "d": "medium", "t": "Deep Learning",
            "p": ["Self-attention computes pairwise token relationships", "Multi-head attention for different representation subspaces", "O(n²) complexity challenge for long sequences", "Parallelism advantage over sequential RNNs", "Positional encoding for sequence order"],
        },
        {
            "q": "How would you serve a large language model that needs to handle 1000 concurrent inference requests with < 200ms latency?",
            "d": "hard", "t": "Model Serving",
            "p": ["Continuous batching for GPU utilisation", "KV cache management", "Quantisation (INT8, INT4) for throughput", "Horizontal scaling with load balancer", "TensorRT or vLLM optimisation frameworks"],
        },
        {
            "q": "What is catastrophic forgetting and how do you mitigate it when continually training a model on new data?",
            "d": "medium", "t": "Continual Learning",
            "p": ["Definition: new training overwrites old knowledge", "Elastic weight consolidation (EWC)", "Replay buffer with old task examples", "Progressive neural networks", "Evaluation on old tasks during training"],
        },
        {
            "q": "Describe how you would build an MLOps pipeline from model training to production monitoring.",
            "d": "medium", "t": "MLOps",
            "p": ["Experiment tracking with MLflow or W&B", "Model registry and versioning", "CI/CD for model validation before promotion", "Feature store for consistent training/serving features", "Monitoring for data drift and prediction shift"],
        },
    ],

    "DevOps / Cloud Engineer": [
        {
            "q": "Explain how Kubernetes manages container scheduling and what happens when a node fails.",
            "d": "easy", "t": "Kubernetes",
            "p": ["Scheduler assigns pods to nodes based on resources", "Kubelet reports node health via heartbeats", "Controller manager detects failed node", "Pods rescheduled to healthy nodes", "Pod Disruption Budgets for graceful handling"],
        },
        {
            "q": "How would you design a zero-downtime deployment strategy for a stateful application on Kubernetes?",
            "d": "medium", "t": "Kubernetes",
            "p": ["Rolling update with maxSurge and maxUnavailable", "StatefulSet vs Deployment for stateful apps", "PodDisruptionBudget to preserve quorum", "Pre-upgrade and post-upgrade health checks", "Helm hooks for migration ordering"],
        },
        {
            "q": "Design a multi-region active-active architecture on AWS that can survive a full region failure.",
            "d": "hard", "t": "Cloud Architecture",
            "p": ["Route 53 health checks and latency routing", "DynamoDB Global Tables or Aurora Global Database", "S3 Cross-Region Replication", "RTO/RPO targets driving design decisions", "Chaos engineering to validate failover"],
        },
        {
            "q": "How do you manage secrets in a Kubernetes cluster across development, staging, and production environments?",
            "d": "medium", "t": "Security",
            "p": ["External Secrets Operator with Vault or AWS SSM", "Kubernetes Secrets encryption at rest", "RBAC to restrict secret access by namespace", "Secret rotation without pod restart", "Audit logging for secret access"],
        },
        {
            "q": "Describe how you would implement comprehensive observability (metrics, logs, traces) for a microservices system.",
            "d": "medium", "t": "Observability",
            "p": ["Prometheus + Grafana for metrics", "ELK or Loki for log aggregation", "OpenTelemetry for distributed tracing", "SLIs, SLOs, and error budgets", "Alert routing and escalation policies"],
        },
        {
            "q": "How does a container runtime like containerd differ from Docker, and what actually happens when you run a container?",
            "d": "easy", "t": "Container Fundamentals",
            "p": ["Docker as a higher-level UX over containerd/runc", "OCI image and runtime specs", "Linux namespaces for isolation", "cgroups for resource limits", "Union filesystem layers (overlay2)"],
        },
    ],

    "Mobile Developer": [
        {
            "q": "Explain the React Native bridge and how it handles communication between JavaScript and native code.",
            "d": "easy", "t": "React Native Internals",
            "p": ["JS thread and native thread separation", "Serialised messages over the bridge", "Performance impact of bridge crossings", "New architecture: JSI and Fabric renderer", "TurboModules for synchronous native calls"],
        },
        {
            "q": "How do you optimise a React Native app that shows dropped frames during long list scrolling?",
            "d": "medium", "t": "Performance",
            "p": ["FlatList vs ScrollView and windowSize prop", "getItemLayout to avoid dynamic measurement", "keyExtractor for stable item identity", "Image caching and resizing", "InteractionManager for deferred heavy work"],
        },
        {
            "q": "How do you manage offline-first data synchronisation in a mobile app that must work without internet?",
            "d": "hard", "t": "Offline Architecture",
            "p": ["SQLite or Realm for local storage", "Conflict resolution strategy (last-write-wins vs CRDT)", "Queue of pending mutations for sync", "Optimistic UI updates with rollback", "Background sync on connectivity restore"],
        },
        {
            "q": "Explain the difference between push notifications on iOS and Android. What are the key implementation challenges?",
            "d": "easy", "t": "Platform APIs",
            "p": ["APNs for iOS vs FCM for Android", "Device token registration and server storage", "Background vs foreground notification handling", "Rich notifications with images and actions", "Notification permission request best practices"],
        },
    ],

    "Data Engineer": [
        {
            "q": "Explain the difference between batch processing and stream processing. When would you choose one over the other?",
            "d": "easy", "t": "Processing Paradigms",
            "p": ["Batch: high throughput, higher latency (Spark)", "Stream: low latency, continuous processing (Flink, Kafka Streams)", "Lambda vs Kappa architecture", "Use case: reporting vs real-time alerts", "Cost and operational complexity trade-offs"],
        },
        {
            "q": "How do you design a data pipeline that handles late-arriving data and ensures exactly-once processing?",
            "d": "medium", "t": "Pipeline Design",
            "p": ["Watermarks for tracking event time progress", "Allowed lateness windows in Flink/Spark", "Idempotent writes for exactly-once semantics", "Checkpointing for fault tolerance", "Dead-letter queue for unprocessable events"],
        },
        {
            "q": "Describe your approach to data quality validation across an end-to-end ETL pipeline.",
            "d": "medium", "t": "Data Quality",
            "p": ["Schema validation at ingestion boundary", "Row count and null checks per stage", "Statistical anomaly detection (Z-score)", "Great Expectations or dbt tests", "Quarantine pattern for failed records"],
        },
        {
            "q": "How would you design a data warehouse schema for an e-commerce platform's analytics team?",
            "d": "medium", "t": "Data Modelling",
            "p": ["Star schema: fact and dimension tables", "Slowly changing dimensions (SCD Type 2)", "Grain definition for the fact table", "Aggregate tables for common query patterns", "Partitioning and clustering for query cost"],
        },
        {
            "q": "How do you approach optimising a slow Spark job that is processing 10TB of data?",
            "d": "hard", "t": "Performance",
            "p": ["Identify stage with highest shuffle/spill in Spark UI", "Partitioning strategy to avoid data skew", "Broadcast join for small lookup tables", "Caching intermediate results", "Predicate pushdown and column pruning with Parquet"],
        },
    ],
}

# ── Curriculum (ordered topic flow per role) ──────────────────────────────────
# The orchestrator follows this order; within each topic it adjusts difficulty.

_CURRICULUM: dict[str, list[str]] = {
    "Full Stack Developer":   ["Project Deep Dive", "REST Fundamentals", "Database Design", "Authentication", "Performance Optimization", "System Design"],
    "Frontend Developer":     ["Project Deep Dive", "React Internals", "CSS Fundamentals", "Rendering Strategies", "Performance Optimization", "Frontend Architecture"],
    "Backend Developer":      ["Project Deep Dive", "API Design", "Database", "Concurrency", "Performance", "System Design"],
    "Data Scientist":         ["Project Deep Dive", "Model Selection", "Evaluation Metrics", "Model Theory", "Practical ML", "Experimentation"],
    "ML / AI Engineer":       ["Project Deep Dive", "Transfer Learning", "Deep Learning", "MLOps", "Model Serving", "Continual Learning"],
    "DevOps / Cloud Engineer":["Project Deep Dive", "Container Fundamentals", "Kubernetes", "Cloud Architecture", "Security", "Observability"],
    "Mobile Developer":       ["Project Deep Dive", "React Native Internals", "Platform APIs", "Performance", "Offline Architecture"],
    "Data Engineer":          ["Project Deep Dive", "Processing Paradigms", "Pipeline Design", "Data Quality", "Data Modelling", "Performance"],
}

# ── Opening question bank (Phase 3 personalised templates) ───────────────────

_OPENING_BANK: dict[str, dict[str, dict]] = {
    "Full Stack Developer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": "I can see you worked on '{project}' using {techs}. Could you walk me through the overall architecture — how did you split responsibilities between the frontend and backend, and what was the trickiest problem you had to solve?",
            "expected_points": ["Describe the system architecture and data flow", "Explain the frontend/backend boundary and API design", "Share a specific technical challenge and how it was resolved", "Reflect on what you would change with hindsight"],
        },
        "skills": {
            "topic": "Role Introduction",
            "question": "Your resume shows experience with {skills}. How do you typically approach starting a new full-stack feature — from design all the way through to deployment?",
            "expected_points": ["Describe the end-to-end development workflow", "Explain API contract decisions", "Discuss state management and data fetching choices", "Mention testing and deployment practices"],
        },
        "general": {
            "topic": "Role Introduction",
            "question": "Tell me about a full-stack project you're most proud of. What was the problem it solved and how did you decide on the technology choices?",
            "expected_points": ["Articulate the problem being solved", "Justify the technology stack selected", "Describe the architecture at a high level", "Highlight personal contributions and learnings"],
        },
    },
    "Frontend Developer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": "I see you built '{project}' — can you walk me through how you structured the component hierarchy and how you managed state across the application?",
            "expected_points": ["Explain component decomposition strategy", "Describe state management approach", "Discuss performance considerations", "Share accessibility or responsive design decisions"],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": "You've listed {skills} on your resume. How do you decide between local component state and a global state solution when building a new feature?",
            "expected_points": ["Explain criteria for local vs global state", "Compare at least two state management strategies", "Discuss scalability trade-offs", "Give a concrete example"],
        },
        "general": {
            "topic": "Role Introduction",
            "question": "Walk me through how you approach building a new UI feature from design mockup to production. What does your typical process look like?",
            "expected_points": ["Describe how you interpret design specs", "Explain component planning before coding", "Mention cross-browser and responsive testing", "Discuss code review and deployment steps"],
        },
    },
    "Backend Developer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": "Tell me about the backend of '{project}'. How did you design the API layer, and what approach did you take to data storage with {techs}?",
            "expected_points": ["Explain API design decisions", "Describe the data model and schema rationale", "Discuss authentication and security measures", "Share performance or scalability considerations"],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": "Given your experience with {skills}, how do you approach designing a REST API from scratch — what are the key decisions you make before writing any code?",
            "expected_points": ["Explain resource modelling and URL structure", "Discuss HTTP method semantics and status codes", "Describe error handling strategy", "Mention authentication and versioning"],
        },
        "general": {
            "topic": "Role Introduction",
            "question": "Describe a backend system you built that you're proud of. What were the main design decisions and what trade-offs did you make?",
            "expected_points": ["Articulate the system's purpose", "Explain key architectural decisions", "Discuss trade-offs made", "Reflect on what worked and what you'd improve"],
        },
    },
    "Data Scientist": {
        "project": {
            "topic": "Project Deep Dive",
            "question": "I noticed '{project}' on your resume. Could you walk me through your end-to-end ML workflow — from raw data to the final model, including how you validated its performance?",
            "expected_points": ["Describe data collection and cleaning", "Explain feature engineering decisions", "Discuss model selection and evaluation metrics", "Share how findings were communicated"],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": "You have experience with {skills}. How do you approach selecting the right model for a new prediction problem?",
            "expected_points": ["Explain baseline model strategy", "Discuss bias-variance trade-off", "Describe cross-validation and metric selection", "Mention interpretability considerations"],
        },
        "general": {
            "topic": "Role Introduction",
            "question": "Tell me about a data science project where the results surprised you. What did the data reveal, and how did that change your approach?",
            "expected_points": ["Describe the problem and initial hypothesis", "Explain what the data showed unexpectedly", "Discuss how methodology was adjusted", "Share the final outcome"],
        },
    },
    "ML / AI Engineer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": "Tell me about '{project}'. How did you go from a trained model to something running reliably in production — what was your serving and monitoring strategy?",
            "expected_points": ["Describe the model training pipeline", "Explain the serving architecture", "Discuss monitoring for drift", "Share production challenges"],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": "You've worked with {skills}. How do you decide between fine-tuning a pre-trained model versus training from scratch for a new ML task?",
            "expected_points": ["Data size considerations", "Transfer learning trade-offs", "Compute budget constraints", "Evaluation methodology"],
        },
        "general": {
            "topic": "Role Introduction",
            "question": "Describe an ML system you built or contributed to significantly. How did you ensure it performed reliably once deployed?",
            "expected_points": ["Explain the problem the model solves", "Describe training and evaluation", "Discuss deployment architecture", "Share production lessons"],
        },
    },
    "DevOps / Cloud Engineer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": "Tell me about the infrastructure you set up for '{project}'. How did you handle deployment, scaling, and observability?",
            "expected_points": ["Describe infrastructure topology", "Explain CI/CD pipeline design", "Discuss auto-scaling strategy", "Share monitoring and alerting setup"],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": "With your experience in {skills}, how would you design a CI/CD pipeline for a microservices application that needs zero-downtime deployments?",
            "expected_points": ["Outline pipeline stages", "Explain blue/green or canary strategy", "Discuss rollback mechanisms", "Mention secrets management"],
        },
        "general": {
            "topic": "Role Introduction",
            "question": "Walk me through the most complex infrastructure problem you've solved. What was the situation and what did you do?",
            "expected_points": ["Set context and scale", "Explain root cause diagnosis", "Describe the solution", "Share measurable impact"],
        },
    },
    "Mobile Developer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": "Tell me about '{project}'. How did you handle state management and keep the UI smooth while making network requests in the background?",
            "expected_points": ["Describe state management approach", "Explain async data fetching strategy", "Discuss UI thread concerns", "Share testing approach"],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": "You've worked with {skills}. How do you approach optimising app startup time and ensuring a smooth 60 fps experience?",
            "expected_points": ["Lazy loading and code splitting", "Avoid blocking the main thread", "Profiling tools used", "Image and asset optimisation"],
        },
        "general": {
            "topic": "Role Introduction",
            "question": "Tell me about a mobile app you've shipped. What were the biggest technical challenges from development to App Store release?",
            "expected_points": ["Describe the app's core problem", "Explain a significant technical challenge", "Discuss testing across devices", "Share the release process"],
        },
    },
    "Data Engineer": {
        "project": {
            "topic": "Project Deep Dive",
            "question": "Walk me through the data pipeline you built for '{project}'. How did you ensure reliability and monitor pipeline health?",
            "expected_points": ["Describe pipeline architecture", "Explain error recovery design", "Discuss late data handling", "Share monitoring approach"],
        },
        "skills": {
            "topic": "Technical Foundations",
            "question": "Given your experience with {skills}, how do you approach designing a data pipeline that needs to be both reliable and easy to extend?",
            "expected_points": ["Modularity and separation of concerns", "Idempotency design", "Schema evolution strategy", "Data quality validation"],
        },
        "general": {
            "topic": "Role Introduction",
            "question": "Tell me about a data pipeline you built that you're particularly proud of. What problem did it solve and how did you ensure data quality?",
            "expected_points": ["Describe the business problem", "Explain architectural decisions", "Discuss data quality checks", "Share performance outcomes"],
        },
    },
}

# ── Behavioral question bank (role-agnostic, injected at Q3) ─────────────────

_BEHAVIORAL_BANK: list[dict] = [
    {
        "q": "Tell me about a time you had to debug a critical production issue with users affected. Walk me through exactly what you did, step by step.",
        "d": "medium", "t": "Behavioral & Communication",
        "p": ["Describes the incident context clearly", "Explains systematic diagnosis approach", "Discusses how they communicated under pressure", "Shares the resolution and what was learned"],
    },
    {
        "q": "Describe a situation where you disagreed with a technical decision your team or manager made. How did you handle it, and what was the outcome?",
        "d": "medium", "t": "Behavioral & Communication",
        "p": ["States the disagreement clearly and professionally", "Explains how they raised their concern", "Shows respect for the final decision", "Reflects on what they learned from the experience"],
    },
    {
        "q": "Tell me about a project where requirements changed significantly mid-way through. How did you adapt, and what would you do differently now?",
        "d": "medium", "t": "Behavioral & Communication",
        "p": ["Describes the scope change with specifics", "Explains how they reprioritised and communicated", "Discusses impact on timeline and quality", "Reflects on process improvements they'd make"],
    },
    {
        "q": "Describe a time you had to learn a completely new technology or framework quickly to deliver a project. What was your approach, and how did it go?",
        "d": "easy", "t": "Behavioral & Communication",
        "p": ["Names the technology and explains the context", "Describes a structured learning strategy", "Discusses how they validated their understanding", "Shares the outcome and any shortcuts taken"],
    },
    {
        "q": "Tell me about a meaningful mistake you made on a project. What happened, and more importantly, what did you change as a result?",
        "d": "easy", "t": "Behavioral & Communication",
        "p": ["Describes the mistake honestly without deflecting", "Explains the immediate impact", "Discusses concrete changes made to prevent recurrence", "Shows self-awareness and growth mindset"],
    },
    {
        "q": "Describe a time you had to collaborate closely with someone whose working style was very different from yours. How did you make it work?",
        "d": "easy", "t": "Behavioral & Communication",
        "p": ["Describes the style differences specifically", "Explains how they adapted their communication", "Shows empathy and flexibility", "Shares the outcome and what they took from it"],
    },
]


_GENERIC_OPENING = {
    "topic": "Role Introduction",
    "question": "Tell me about yourself and what drew you to this role. Which project or achievement from your background are you most proud of, and why?",
    "expected_points": ["Give a concise professional summary", "Connect past experience to this role", "Highlight a specific achievement with measurable impact", "Express genuine motivation"],
}


# ── Opening question generation (Phase 3) ────────────────────────────────────

def _build_static(analysis: ResumeAnalysis, role: str) -> Question:
    bank = _OPENING_BANK.get(role, {})
    skill_str = ", ".join(analysis.skills[:5]) if analysis.skills else "your listed technologies"

    if analysis.projects and "project" in bank:
        # Select project most relevant to the target role
        p = analysis.projects[0]
        try:
            from services.project_classifier import select_best_project
            best, _score, _all = select_best_project(analysis.projects, role)
            if best is not None:
                p = best
        except Exception:
            pass
        tech_str = ", ".join(p.technologies[:3]) if p.technologies else skill_str
        tmpl = bank["project"]
        return Question(
            question_id=_qid(),
            question=_fill(tmpl["question"], p.name, tech_str, skill_str),
            difficulty="easy", topic=tmpl["topic"], expected_points=tmpl["expected_points"],
        )
    if analysis.skills and "skills" in bank:
        tmpl = bank["skills"]
        return Question(
            question_id=_qid(),
            question=_fill(tmpl["question"], "", "", skill_str),
            difficulty="easy", topic=tmpl["topic"], expected_points=tmpl["expected_points"],
        )
    if "general" in bank:
        tmpl = bank["general"]
        return Question(
            question_id=_qid(), question=tmpl["question"],
            difficulty="easy", topic=tmpl["topic"], expected_points=tmpl["expected_points"],
        )
    return Question(
        question_id=_qid(), question=_GENERIC_OPENING["question"],
        difficulty="easy", topic=_GENERIC_OPENING["topic"], expected_points=_GENERIC_OPENING["expected_points"],
    )


async def _generate_first_with_llm(analysis: ResumeAnalysis, role: str) -> Question | None:
    from config import get_settings
    settings = get_settings()
    if not settings.has_llm_configured:
        return None
    try:
        from services.llm_client import call_llm, extract_json
        p_line = ""
        domain_focus = ""
        avoid_domains = ""
        if analysis.projects:
            # Pick the project most relevant to the target role
            p = analysis.projects[0]
            try:
                from services.project_classifier import select_best_project, _ROLE_DOMAIN_AFFINITY
                best, _score, _all = select_best_project(analysis.projects, role)
                if best is not None:
                    p = best
            except Exception:
                pass

            tech_str = ", ".join(p.technologies[:3]) if p.technologies else ""
            p_line = f"Most relevant project for this role: '{p.name}' using {tech_str}."

            # Add domain-focus hints so the LLM doesn't ask off-topic questions
            proj_domain = getattr(getattr(p, "domain", None), "primary_domain", "")
            if proj_domain and proj_domain != "General Software":
                domain_focus = f"Project primary domain: {proj_domain}."
                affinity = {}
                try:
                    from services.project_classifier import _ROLE_DOMAIN_AFFINITY
                    affinity = _ROLE_DOMAIN_AFFINITY.get(role, {})
                except Exception:
                    pass
                irrelevant = [d for d, w in affinity.items() if w < 0.20 and d != proj_domain]
                if irrelevant:
                    avoid_domains = (
                        f"IMPORTANT: Focus on {role} aspects of this project. "
                        f"Do NOT ask questions about {', '.join(irrelevant[:3])} — "
                        f"those are not relevant to this interview role."
                    )

        prompt = (
            f"You are a warm senior technical interviewer opening a mock interview.\n\n"
            f"Role: {role}\nSkills: {', '.join(analysis.skills[:12])}\nLevel: {analysis.experience_level}\n"
            f"{p_line}\n{domain_focus}\n{avoid_domains}\n\n"
            "Generate the FIRST interview question. Rules: difficulty='easy', reference project if listed, open-ended.\n"
            'Return ONLY JSON (no markdown, no prose): '
            '{"question":"...","topic":"...","expected_points":["...","...","...","..."]}'
        )
        raw = await call_llm(prompt, max_tokens=512)
        if raw is None:
            return None

        data = extract_json(raw)
        if not data:
            logger.warning("LLM first-question: could not parse JSON from response (len=%d)", len(raw))
            return None

        question_text = data.get("question", "").strip()
        if not question_text:
            logger.warning("LLM first-question: parsed JSON missing 'question' key. data=%s", data)
            return None

        return Question(
            question_id=_qid(),
            question=question_text,
            difficulty="easy",
            topic=data.get("topic", "Role Introduction") or "Role Introduction",
            expected_points=data.get("expected_points") or [],
        )
    except Exception as exc:
        logger.warning("LLM first-question failed: %s: %s", type(exc).__name__, exc)
    return None


async def start_session(
    candidate_id: str, selected_role: str, analysis: ResumeAnalysis | None,
) -> tuple[InterviewSession, Question]:
    session_id = "INT-" + str(uuid.uuid4()).replace("-", "")[:10].upper()
    first_q = None
    if analysis:
        first_q = await _generate_first_with_llm(analysis, selected_role)
    if first_q is None:
        logger.info("First interview question source: static_fallback.")
        first_q = _build_static(
            analysis or ResumeAnalysis(
                candidate_id=candidate_id, candidate_name="", email="", phone="",
                skills=[], projects=[], education="", experience_level="mid",
                domains=[], strengths=[], weak_areas=[],
            ),
            selected_role,
        )
    else:
        from config import get_settings
        logger.info("First interview question source: llm:%s.", get_settings().llm_provider.lower())
    session = InterviewSession(
        session_id=session_id, candidate_id=candidate_id, selected_role=selected_role,
        status="active", created_at=datetime.now(timezone.utc),
        questions_asked=[first_q], current_question=first_q,
    )
    return session, first_q


# ── Adaptive next question (Phase 5) ─────────────────────────────────────────

def _next_difficulty(current: str, tech: int, confidence: int) -> str:
    if confidence < 50:
        return "easy"
    if tech >= 80:
        return {"easy": "medium", "medium": "hard", "hard": "hard"}.get(current, "medium")
    if tech >= 50:
        return current
    return {"hard": "medium", "medium": "easy", "easy": "easy"}.get(current, "easy")


def _mentions_project(answer_text: str) -> bool:
    patterns = [
        r"\bi (built|developed|created|implemented|shipped|deployed)\b",
        r"\bmy (project|app|application|system|platform|service|api)\b",
        r"\bin my (previous|last|current|prior)\b",
        r"\bwe (built|developed|created|shipped)\b",
    ]
    al = answer_text.lower()
    return any(re.search(p, al) for p in patterns)


def _select_question(
    role: str, target_diff: str, covered_topics: set[str], asked_ids: set[str],
) -> Question | None:
    bank = _ADAPTIVE_BANK.get(role, [])
    curriculum = _CURRICULUM.get(role, [])

    # Prefer uncovered topics that come next in curriculum
    ordered_topics = [t for t in curriculum if t not in covered_topics]

    # Try preferred difficulty first, then relax
    for diff_try in [target_diff, "easy", "medium", "hard"]:
        for topic in ordered_topics + list(covered_topics):
            candidates = [
                q for q in bank
                if q["d"] == diff_try and q["t"] == topic and q["q"][:20] not in asked_ids
            ]
            if candidates:
                q = candidates[0]
                return Question(
                    question_id=_qid(), question=q["q"],
                    difficulty=q["d"], topic=q["t"], expected_points=q["p"],
                )
    return None


def _adaptation_reason(
    tech: int, confidence: int, old_diff: str, new_diff: str,
    old_topic: str, new_topic: str, project_followup: bool,
) -> str:
    if project_followup:
        return (
            f"You referenced hands-on project work in your answer. "
            f"Diving deeper into the specific technical decisions and challenges you encountered."
        )
    if confidence < 50:
        return (
            f"Your answer on '{old_topic}' was brief and showed some uncertainty (score: {tech}/100). "
            f"Asking a more structured question to help build confidence before moving forward."
        )
    if tech >= 80:
        if new_diff != old_diff:
            return (
                f"Excellent performance on '{old_topic}' (score: {tech}/100). "
                f"Escalating to {new_diff} difficulty — moving to '{new_topic}' to challenge you further."
            )
        return (
            f"Strong answer on '{old_topic}' (score: {tech}/100). "
            f"Exploring a related concept in '{new_topic}' to probe breadth of knowledge."
        )
    if tech >= 50:
        if new_topic != old_topic:
            return (
                f"Good grasp of '{old_topic}' (score: {tech}/100). "
                f"Advancing to '{new_topic}' to assess a broader skill set."
            )
        return (
            f"Solid foundation on '{old_topic}' (score: {tech}/100). "
            f"Probing deeper on the same topic to assess full understanding."
        )
    return (
        f"The answer on '{old_topic}' lacked depth (score: {tech}/100). "
        f"Stepping back to '{new_topic}' to check foundational knowledge before progressing."
    )


async def _generate_next_with_llm(
    role: str, session_data: dict, req: NextQuestionRequest,
    target_diff: str, covered_topics: set[str], last_answer: str,
) -> Question | None:
    from config import get_settings
    settings = get_settings()
    if not settings.has_llm_configured:
        return None
    try:
        from services.llm_client import call_llm, extract_json
        questions_summary = [
            f"Q{i+1}: [{q['topic']}] {q['question'][:60]}…"
            for i, q in enumerate(session_data.get("questions_asked", []))
        ]
        # Include project-domain context so the LLM stays on-role
        # best_project_domain is stored at session-start time by interview_routes
        project_context = ""
        proj_domain = session_data.get("best_project_domain", "")
        if proj_domain and proj_domain != "General Software":
            project_context = (
                f"Candidate's primary project domain: {proj_domain}. "
                f"Ensure questions stay relevant to the {role} role — "
                f"do not pivot to unrelated technical areas."
            )

        prompt = (
            f"You are an adaptive technical interviewer. Generate the NEXT interview question.\n\n"
            f"Role: {role}\n"
            f"Last answer score: {req.last_answer_score}/100\n"
            f"Last topic: {req.current_topic}\n"
            f"Target difficulty: {target_diff}\n"
            f"Topics already covered: {list(covered_topics)}\n"
            f"Questions asked so far:\n" + "\n".join(questions_summary) + "\n"
            f"Last answer excerpt: \"{last_answer[:300]}\"\n"
            f"{project_context}\n\n"
            "Return ONLY valid JSON (no markdown, no prose):\n"
            '{"question":"...","difficulty":"easy|medium|hard","topic":"...","expected_points":["...","...","..."]}'
        )
        raw = await call_llm(prompt, max_tokens=512)
        if raw is None:
            return None

        data = extract_json(raw)
        if not data:
            logger.warning("LLM next-question: could not parse JSON from response (len=%d)", len(raw))
            return None

        question_text = data.get("question", "").strip()
        if not question_text:
            logger.warning("LLM next-question: parsed JSON missing 'question' key. data=%s", data)
            return None

        return Question(
            question_id=_qid(),
            question=question_text,
            difficulty=data.get("difficulty") or target_diff,
            topic=data.get("topic") or req.current_topic,
            expected_points=data.get("expected_points") or [],
        )
    except Exception as exc:
        logger.warning("LLM next-question failed: %s: %s", type(exc).__name__, exc)
    return None


async def next_question(
    req: NextQuestionRequest, session_data: dict,
) -> tuple[Question, str, bool]:
    """
    Returns (question, reason_for_adaptation, session_complete).
    session_complete is True when the session has hit MAX_QUESTIONS.
    """
    role = session_data.get("selected_role", "")
    questions_asked = session_data.get("questions_asked", [])
    answers = session_data.get("answers", [])
    n_answered = len(answers)

    # Hard cap
    if n_answered >= MAX_QUESTIONS:
        dummy = Question(
            question_id=_qid(), question="", difficulty="easy",
            topic="Session Complete", expected_points=[],
        )
        return dummy, "Session complete.", True

    # Gather context
    old_diff = questions_asked[-1]["difficulty"] if questions_asked else "easy"
    target_diff = _next_difficulty(old_diff, req.last_answer_score, req.confidence_score)
    covered_topics = {q["topic"] for q in questions_asked}
    asked_ids = {q["question"][:20] for q in questions_asked}

    # Last answer text for contextual follow-up detection
    last_answer_text = answers[-1]["answer_text"] if answers else ""
    resume_techs = session_data.get("resume_techs", [])

    # ── Behavioral question injection at Q3 ───────────────────────────────────
    # Always include one behavioral question mid-interview to assess soft skills.
    if n_answered == 2 and "Behavioral & Communication" not in covered_topics:
        import random
        behavioral_q = random.choice(_BEHAVIORAL_BANK)
        asked_starts = {q["question"][:30] for q in questions_asked}
        for bq in _BEHAVIORAL_BANK:
            if bq["q"][:30] not in asked_starts:
                behavioral_q = bq
                break
        next_q = Question(
            question_id=_qid(), question=behavioral_q["q"],
            difficulty=behavioral_q["d"], topic=behavioral_q["t"],
            expected_points=behavioral_q["p"],
        )
        reason = (
            "You're doing well on the technical questions. "
            "Shifting briefly to a behavioral question to get a rounded picture of how you work."
        )
        return next_q, reason, False

    # ── Contextual follow-up detection ────────────────────────────────────────
    # Check if the candidate's answer mentions a specific technology or concept
    # that warrants a targeted follow-up question rather than a bank question.
    if last_answer_text and n_answered >= 1:
        try:
            from services.followup_generator import generate_followup
            followup_data = generate_followup(
                answer=last_answer_text,
                current_topic=req.current_topic,
                resume_techs=resume_techs,
            )
            if followup_data:
                fu_question, fu_reason, fu_points = followup_data
                # Only use follow-up if this topic hasn't been covered by a follow-up already
                followup_topics_used = session_data.get("followup_topics_used", [])
                fu_fingerprint = fu_question[:40]
                if fu_fingerprint not in followup_topics_used:
                    next_q = Question(
                        question_id=_qid(), question=fu_question,
                        difficulty=target_diff, topic=f"Follow-Up: {req.current_topic}",
                        expected_points=fu_points,
                    )
                    session_data.setdefault("followup_topics_used", []).append(fu_fingerprint)
                    return next_q, fu_reason, False
        except Exception as exc:
            logger.warning("Contextual follow-up failed, continuing: %s", exc)

    # Try LLM, then fall back to static bank
    next_q = await _generate_next_with_llm(
        role, session_data, req, target_diff, covered_topics, last_answer_text,
    )

    if next_q is None:
        logger.info("Next interview question source: question_bank_fallback.")
        next_q = _select_question(role, target_diff, covered_topics, asked_ids)
    else:
        from config import get_settings
        logger.info("Next interview question source: llm:%s.", get_settings().llm_provider.lower())

    if next_q is None:
        # Ultimate fallback — a generic deeper probe
        next_q = Question(
            question_id=_qid(),
            question="How would you approach debugging a production issue that only occurs intermittently under high load?",
            difficulty="medium", topic="Problem Solving",
            expected_points=[
                "Describe the initial triage and monitoring approach",
                "Explain how to reproduce intermittent issues",
                "Discuss log analysis and distributed tracing",
                "Describe the fix and prevention strategy",
            ],
        )

    reason = _adaptation_reason(
        req.last_answer_score, req.confidence_score,
        old_diff, next_q.difficulty, req.current_topic, next_q.topic, False,
    )
    return next_q, reason, False
