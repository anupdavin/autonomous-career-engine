import json
from pathlib import Path

BASE_DIR = Path(r"c:\Users\MeenaDavin\Desktop\Project 1")
RESUME_B2B = BASE_DIR / "resumes_vault" / "2026-09-29_B2B_Cloud_Fintech_v1.1_b2b_java_ka" / "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"
RESUME_AI  = BASE_DIR / "resumes_vault" / "2026-09-29_Global_AI_Platform_v1.2_spring_ai_r" / "Meena_Kannan_Lead_Ai_Software_Engineer.pdf"

TARGET_ROLES = [
    {
        "id": "binance_data_java_engineer_ai_llm_chatbot",
        "company": "Binance",
        "title": "Data / Java Engineer (AI/LLM Chatbot, Customer Service)",
        "location": "APAC (100% Remote)",
        "url": "https://jobicy.com/jobs/150065-data-java-engineer-ai-llm-chatbot-customer-service",
        "platform": "Jobicy Direct",
        "resume_pdf": str(RESUME_AI),
        "resume_name": RESUME_AI.name,
        "resume_exists": RESUME_AI.exists(),
        "cover_note": (
            "I am applying for the Data / Java Engineer (AI/LLM Chatbot) role at Binance. "
            "I bring 8+ years of backend engineering experience focused on Java 21, Spring Boot 3, and high-throughput messaging, "
            "combined with production integrations of Spring AI, RAG retrieval pipelines, and Model Context Protocol (MCP) tool servers.\n\n"
            "At NCS, I architected the microservice core for Singapore's Land Transport Authority (VRLS 2.0), transitioning monolithic "
            "workflows onto AWS EKS with Kafka event streams and Redis caching to handle peak transaction bursts. "
            "In parallel, I have implemented LLM agent pipelines using Claude and OpenAI APIs with structured tool execution "
            "to automate customer-facing intelligence and query resolution.\n\n"
            "My background directly matches Binance's focus on high-reliability Java architectures paired with real-time LLM inference. "
            "I am based in Chennai, India, available on a 60-day notice period, and work 100% remotely via direct global B2B contract or India EOR. "
            "I look forward to discussing how I can strengthen your chatbot infrastructure."
        )
    },
    {
        "id": "highlevel_lead_engineer_ai_studio",
        "company": "HighLevel",
        "title": "Lead Engineer - AI Studio",
        "location": "India (100% Remote)",
        "url": "https://jobs.lever.co/gohighlevel/29c16f45-a4ca-4eb8-bc4a-1738dc9219c1",
        "platform": "Lever",
        "resume_pdf": str(RESUME_AI),
        "resume_name": RESUME_AI.name,
        "resume_exists": RESUME_AI.exists(),
        "cover_note": (
            "I am writing to express my strong interest in the Lead Engineer - AI Studio position at HighLevel. "
            "With 8+ years building enterprise platforms and hands-on production experience in Spring AI, LLM orchestration, "
            "and MCP tool execution, I focus on turning generative AI prototypes into resilient developer and customer products.\n\n"
            "In my current leadership role at NCS, I guided the VRLS 2.0 platform modernisation on AWS EKS, establishing containerised "
            "microservices, Kafka stream processing, and Istio mTLS to support heavy daily user volumes. "
            "I have designed autonomous agentic loops, prompt evaluation harnesses, and multi-model routing systems "
            "that prevent hallucinations and enforce strict execution boundaries.\n\n"
            "HighLevel's mission to empower marketing and business automation with native AI aligns directly with my engineering focus. "
            "I am based in India, available on a 60-day notice period, and seek a full-time remote engineering role. "
            "I welcome the opportunity to discuss technical leadership within the AI Studio team."
        )
    },
    {
        "id": "canonical_software_engineer_kafka",
        "company": "Canonical",
        "title": "Software Engineer - Data Infrastructure - Kafka",
        "location": "Home based - EMEA / Worldwide",
        "url": "https://job-boards.greenhouse.io/canonical/jobs/5218601",
        "platform": "Greenhouse",
        "resume_pdf": str(RESUME_B2B),
        "resume_name": RESUME_B2B.name,
        "resume_exists": RESUME_B2B.exists(),
        "cover_note": (
            "I am applying for the Software Engineer - Data Infrastructure - Kafka role at Canonical. "
            "Over 8+ years of production engineering, I have focused heavily on event-driven architectures, Apache Kafka cluster integration, "
            "and distributed backend systems operating under strict availability and low-latency SLAs.\n\n"
            "Leading the VRLS 2.0 platform rebuild at NCS, I replaced legacy batch polling with real-time Kafka event streams, "
            "configuring consumer groups, topic partitioning, and dead-letter queues on AWS EKS with KEDA autoscaling. "
            "Earlier at BlackStraw.AI, I engineered real-time video inference event pipelines using Apache Kafka to coordinate high-volume feeds. "
            "I understand the operational complexities of running stateful message brokers on Kubernetes across distributed networks.\n\n"
            "I am based in India, available on a 60-day notice period, and work 100% remotely via global B2B contractor arrangement or full-time remote. "
            "I look forward to discussing how my messaging backbone background supports Canonical's data infrastructure offerings."
        )
    },
    {
        "id": "highlevel_staff_engineer_payments",
        "company": "HighLevel",
        "title": "Staff Engineer - Payments & Commerce Platform",
        "location": "India (100% Remote)",
        "url": "https://jobs.lever.co/gohighlevel/4313ec17-52ae-46a7-8cad-ff9c53c7e826",
        "platform": "Lever",
        "resume_pdf": str(RESUME_B2B),
        "resume_name": RESUME_B2B.name,
        "resume_exists": RESUME_B2B.exists(),
        "cover_note": (
            "I am writing to express my interest in the Staff Engineer - Payments & Commerce Platform position at HighLevel. "
            "I offer 8+ years of hands-on experience designing high-concurrency transactional architectures where ledger accuracy, "
            "idempotency, and fault isolation are paramount.\n\n"
            "At NCS, I led the core service design for the vehicle tax, registration, and permit modules on the Singapore Land Transport Authority platform. "
            "I structured transactional microservices on Java 21 and Spring Boot 3 with distributed tracing, Redis caching, "
            "and zero-downtime schema evolution to process critical public financial flows. "
            "At Wolters Kluwer, I developed legal billing compliance microservices handling sub-500ms validation cycles.\n\n"
            "HighLevel's payments backbone demands rigorous transactional rigor and scalable multi-tenant isolation. "
            "I am based in India, available on a 60-day notice period, and targeting a 100% remote staff engineering role. "
            "I look forward to discussing how my platform experience can advance your commerce infrastructure."
        )
    },
    {
        "id": "everbridge_senior_software_engineer_ai",
        "company": "Everbridge",
        "title": "Senior Software Engineer - Backend & AI-Enabled",
        "location": "India (100% Remote)",
        "url": "https://jobs.lever.co/everbridge/ff6eacff-741a-4f60-aff4-a45e89b003a9",
        "platform": "Lever",
        "resume_pdf": str(RESUME_AI),
        "resume_name": RESUME_AI.name,
        "resume_exists": RESUME_AI.exists(),
        "cover_note": (
            "I am applying for the Senior Software Engineer - Backend & AI-Enabled role at Everbridge. "
            "I have 8+ years of engineering background in enterprise Java microservices and distributed cloud backends, "
            "paired with recent production implementations of Spring AI, RAG vector retrieval, and automated model pipelines.\n\n"
            "Currently at NCS, I guide the architecture of high-scale transport services running on AWS EKS and Istio service mesh, "
            "leveraging Apache Kafka streams to coordinate asynchronous platform events during peak spikes. "
            "I have integrated LLM tool-calling systems via Model Context Protocol (MCP) to automate operational diagnostics and alerting workflows, "
            "ensuring reliable fallbacks when upstream model latency increases.\n\n"
            "Everbridge's mission in critical event management requires bulletproof backend uptime combined with intelligent data synthesis. "
            "I am based in India, available on a 60-day notice period, and seek a full-time remote engineering engagement. "
            "I welcome the opportunity to discuss how my skillset fits your team's roadmap."
        )
    },
    {
        "id": "gitlab_solutions_architect_germany_emea",
        "company": "GitLab",
        "title": "Solutions Architect",
        "location": "Remote, Germany / EMEA Open",
        "url": "https://job-boards.greenhouse.io/gitlab/jobs/8695969002",
        "platform": "Greenhouse",
        "resume_pdf": str(RESUME_B2B),
        "resume_name": RESUME_B2B.name,
        "resume_exists": RESUME_B2B.exists(),
        "cover_note": (
            "I am writing to apply for the Solutions Architect position at GitLab. "
            "With 8+ years leading large-scale system migrations, enterprise microservice architectures, and DevSecOps modernisation, "
            "I bridge technical depth in cloud infrastructure with executive stakeholder communication.\n\n"
            "At NCS, I spearheaded the architectural redesign of the Singapore Land Transport Authority core platform (VRLS 2.0). "
            "I collaborated with enterprise government stakeholders, systems integrators, and security teams to migrate legacy monoliths "
            "into containerised Kubernetes microservices on AWS EKS, establishing automated CI/CD pipelines via ArgoCD, Istio mTLS, and Kafka streams. "
            "I conduct technical discovery, lead architectural evaluations, and demonstrate measurable business outcomes to enterprise decision-makers.\n\n"
            "GitLab's DevSecOps platform represents the industry standard for modern software delivery. "
            "I am based in India, available on a 60-day notice period, and work 100% remotely via direct global B2B contract or full-time remote. "
            "I look forward to discussing how I can drive customer technical success across your enterprise accounts."
        )
    }
]

# Verify guardrails on all generated cover notes
for r in TARGET_ROLES:
    note = r["cover_note"]
    assert "\u2014" not in note, f"Em-dash in {r['id']}"
    assert "\u2013" not in note, f"En-dash in {r['id']}"
    assert "\u2015" not in note, f"Horizontal bar in {r['id']}"
    assert "**" not in note, f"Markdown bold in {r['id']}"
    for bad in ["delve", "testament to", "thrilled to", "seamless", "game-changer", "synergy", "moreover", "furthermore"]:
        assert bad not in note.lower(), f"Cliché '{bad}' in {r['id']}"

out_json = BASE_DIR / "application_drafts" / "curated_wave1_packets_2026-10-04.json"
out_json.write_text(json.dumps(TARGET_ROLES, indent=2), encoding="utf-8")
print(f"Successfully generated and validated {len(TARGET_ROLES)} curated packets at {out_json}")

# Also update codex_review_prompt.md with this refined bundle
prompt_lines = [
    "# REFINED WAVE 1 AUDIT: APPLICATION PACKETS (2026-10-04)\n",
    "Audit these 6 refined, high-match application packets for Meena Kannan.",
    "Corrections made from prior review: calibrated to 8+ years, added 60-day notice, distinct company-tailored text, verified stack match.\n",
    "## Guardrail Rules to Enforce:",
    "1. 0 em-dashes (U+2014) or en-dashes (U+2013).",
    "2. 0 AI clichés ('delve', 'seamless', 'game-changer', etc.). Plain-text first-person senior engineer prose only.",
    "3. Candidate facts: 8+ years, Java 21, Spring Boot 3, AWS EKS, Istio, Kafka, Redis, Spring AI, MCP, NCS VRLS 2.0, 60-day notice, Chennai India.",
    "4. Target: 100% Remote Global / India. Zero Singapore onsite/hybrid.\n",
    "---"
]

for idx, r in enumerate(TARGET_ROLES, 1):
    prompt_lines.append(f"\n### Packet {idx}: {r['company']} - {r['title']}")
    prompt_lines.append(f"- Location: {r['location']}")
    prompt_lines.append(f"- Platform: {r['platform']}")
    prompt_lines.append(f"- URL: {r['url']}")
    prompt_lines.append(f"- Selected Resume: `{r['resume_name']}`")
    prompt_lines.append(f"- Cover Note:\n```text\n{r['cover_note']}\n```\n")

prompt_lines.append("\n## Required Output:\nEvaluate each of the 6 packets: Guardrails check, factual check, role alignment score (0-100), and verdict [APPROVED] or [REVISION_REQUIRED].")

prompt_file = BASE_DIR / "application_drafts" / "codex_review_prompt.md"
prompt_file.write_text("\n".join(prompt_lines), encoding="utf-8")
print(f"Updated {prompt_file} with refined bundle.")
