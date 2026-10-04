import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from config import BASE_DIR
from guardrails import assert_no_emdashes, sanitize_no_emdashes

VAULT_DIR = BASE_DIR / "resumes_vault"
VAULT_DIR.mkdir(parents=True, exist_ok=True)


def build_ats_safe_filename(role_title: str, ext: str = "pdf") -> str:
    """
    Generates a 100% recruiter-safe, ATS-optimized upload filename with ZERO
    version tags (`v1.2`) or company names so hiring managers never suspect automation.
    Format: `Meena_Kannan_<Clean_Role_Title>.pdf`
    Example: `Meena_Kannan_Lead_Software_Engineer.pdf`
    """
    clean = role_title.split("[")[0].split("(")[0].split("-")[0].strip()
    words = [w for w in re.sub(r"[^a-zA-Z0-9\s]", " ", clean).split() if len(w) > 1][:4]
    role_slug = "_".join(w.capitalize() for w in words) if words else "Lead_Software_Engineer"
    return f"Meena_Kannan_{role_slug}.{ext}"


def build_internal_vault_subfolder(company: str, version_id: str) -> str:
    """
    Generates the internal tracking folder name so you know exactly which version
    was sent to which company on which date, while keeping the file inside it cleanly named.
    Format: `<YYYY-MM-DD>_<CompanySlug>_<VersionID>`
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    comp_clean = company.split("(")[0].strip()
    comp_slug = re.sub(r"[^a-zA-Z0-9]+", "_", comp_clean).strip("_")[:20] or "Global"
    ver_slug = re.sub(r"[^a-zA-Z0-9.]+", "_", version_id).strip("_")[:16]
    return f"{date_str}_{comp_slug}_{ver_slug}"


BASE_RESUME_VERSIONS: List[Dict[str, Any]] = [
    {
        "version_id": "v1.0-master-cloud-ai",
        "version_tag": "v1.0 (Master Baseline)",
        "company_tag": "General_Master",
        "role_clean": "Lead Software Engineer",
        "target_track": "All-Round Lead Software Engineer (Cloud-Native + AI)",
        "headline": "Lead Software Engineer | 9+ Yrs | Java 21, Spring Boot 3, AWS, K8s, Kafka & Spring AI / MCP (Remote from India)",
        "executive_summary": (
            "Lead Software Engineer with 9+ years delivering production systems across fintech, legaltech, enterprise SaaS, "
            "and high-scale citizen platforms. Currently leading VRLS 2.0 (Java 21, Spring Boot 3, AWS EKS/ECS, Istio mTLS, "
            "Kafka, KEDA, Redis, ArgoCD) and rolling out Spring AI, RAG pipelines, MCP tool servers, and Claude API workflows. "
            "Based in India and targeting 100% remote work through Global B2B Contracts (USD/EUR/GBP) or Full-Time Remote (India EOR)."
        ),
        "highlighted_bullets": [
            "Architected Spring Boot 3 + Java 21 microservices backbone for VRLS 2.0 across registration, road tax, and permits on AWS.",
            "Implemented Istio service mesh (mTLS, DNS discovery) and Kafka + KEDA autoscaling + Redis caching for peak traffic.",
            "Cut redundant API calls by ~40% leading the Angular 13 to 18 migration with NgRx and RxJS.",
            "Replaced 15-minute batch polling with real-time Apache Kafka event streams for AI retail inference at BlackStraw.AI.",
            "Built sub-500ms AI + Drools BRMS legal billing compliance microservice at Wolters Kluwer."
        ],
        "linked_job_id": "MASTER_BASELINE",
    },
    {
        "version_id": "v1.1-b2b-java-kafka-architect",
        "version_tag": "v1.1 (Global B2B Backend & Event-Driven Focus)",
        "company_tag": "B2B_Cloud_Fintech",
        "role_clean": "Principal Java Cloud Architect",
        "target_track": "Principal / Lead Java 21, Kafka & Kubernetes Microservices (Global B2B / Fintech)",
        "headline": "Principal / Lead Java 21 & Distributed Systems Consultant | Spring Boot 3, Kafka Streams, AWS EKS & Istio (Global B2B)",
        "executive_summary": (
            "Distributed Systems & Backend Technical Lead (9+ Yrs) specializing in monolith-to-microservices modernisation, "
            "high-throughput Apache Kafka event choreography (Outbox & Saga patterns), Kubernetes (EKS/Helm/Istio mTLS), "
            "and multi-database reliability (Oracle DB, PostgreSQL, Redis). Set up in India for rapid Global B2B onboarding."
        ),
        "highlighted_bullets": [
            "Led end-to-end monolith decomposition into cloud-native Java 21 / Spring Boot 3 microservices serving millions of users.",
            "Engineered high-throughput Kafka Streams, KEDA event-driven autoscaling, and Redis caching layers eliminating timeout cascades.",
            "Standardised zero-downtime GitOps releases via ArgoCD, Jenkins, GitHub Actions, SonarQube, Vault, and OpenTelemetry.",
            "Authored technical architecture decision records (ADRs) and handover specifications across 8 core licensing domains."
        ],
        "linked_job_id": "TRACK_BACKEND_B2B",
    },
    {
        "version_id": "v1.2-spring-ai-rag-mcp",
        "version_tag": "v1.2 (AI-Augmented Engineering: Spring AI, RAG & MCP)",
        "company_tag": "Global_AI_Platform",
        "role_clean": "Lead AI Software Engineer",
        "target_track": "Lead AI Platform & Agentic Integration Engineer (Spring AI / RAG / MCP / Claude API)",
        "headline": "Lead AI-Augmented Software Engineer | Spring AI, RAG Vector Pipelines, Anthropic MCP Servers & Java/Python Microservices",
        "executive_summary": (
            "Lead Engineer bridging enterprise Java 21 / Python microservices with production LLM & Agentic architectures. "
            "Hands-on creator of Spring AI services, domain-specific RAG vector retrieval pipelines, Model Context Protocol (MCP) "
            "backend tool servers, and deterministic evaluation guardrails."
        ),
        "highlighted_bullets": [
            "Prototyped and rolled out Spring AI, Claude API, and MCP server patterns for backend tool invocation and microservice telemetry.",
            "Designed RAG retrieval pipelines with custom chunking, vector embeddings, and domain-specific evaluation loops reducing hallucination risk.",
            "Integrated real-time ML inference REST endpoints with Apache Kafka streams at BlackStraw.AI (15+ mins latency cut to real-time).",
            "Combined AI anomaly detection models with deterministic Drools BRMS rules at Wolters Kluwer for sub-500ms legal compliance."
        ],
        "linked_job_id": "TRACK_AI_MCP",
    },
]


class TailoredResumeVault:
    """
    Manages Dual-Naming Resume Vault:
      1. Employer-Facing ATS Filename (`Meena_Kannan_<Role_Title>.pdf`) - zero version numbers or bot markers!
      2. Internal Archive Folder (`resumes_vault/<YYYY-MM-DD>_<Company>_<VersionID>/Meena_Kannan_<Role_Title>.html`)
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._init_table()

    def _write_physical_vault_file(
        self,
        subfolder_name: str,
        ats_pdf_filename: str,
        headline: str,
        summary: str,
        bullets: List[str],
    ) -> str:
        folder = VAULT_DIR / subfolder_name
        folder.mkdir(parents=True, exist_ok=True)
        html_filename = ats_pdf_filename.replace(".pdf", ".html")
        target_path = folder / html_filename
        pdf_title = ats_pdf_filename.replace(".pdf", "")

        bullets_html = "".join(f"<li style='margin-bottom:6px;'>{b}</li>" for b in bullets)
        html_doc = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>{pdf_title}</title>
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 820px; margin: 28px auto; color: #111827; line-height: 1.5; }}
    h1 {{ font-size: 24px; margin-bottom: 2px; color: #0f172a; }}
    h2.sub {{ font-size: 14px; color: #0369a1; margin-top: 0; font-weight: 600; }}
    .contact {{ font-size: 12.5px; color: #374151; margin-bottom: 14px; }}
    hr {{ border: 0; border-top: 1px solid #cbd5e1; margin: 12px 0; }}
    h3 {{ font-size: 13.5px; text-transform: uppercase; color: #0f172a; letter-spacing: 0.04em; margin-bottom: 6px; }}
    p, li {{ font-size: 13px; }}
  </style>
</head>
<body>
  <h1>MEENA KANNAN</h1>
  <h2 class="sub">{headline}</h2>
  <div class="contact">
    India & Global Remote | +91 97893 02084 | meenakannan92@gmail.com | linkedin.com/in/meena-kannan-mk | github.com/meenak95
  </div>
  <hr/>
  <h3>Professional Summary</h3>
  <p>{summary}</p>
  <h3>Selected Impact & Architecture Highlights</h3>
  <ul>{bullets_html}</ul>
  <h3>Core Experience</h3>
  <p><strong>Lead Software Engineer | NCS (Client: Land Transport Authority - VRLS 2.0)</strong> (Dec 2023 - Present)<br/>
  Java 21, Spring Boot 3, AWS EKS/ECS, Istio mTLS, Kafka, KEDA, Redis, Angular 18 (-40% redundant API calls), ArgoCD, Spring AI & MCP.</p>
  <p><strong>Application Consultant | NCS (Client: LTA VRLS Platform)</strong> (Dec 2021 - Dec 2023)<br/>
  Technical owner of live VRLS platform across 8 licensing modules (Java, Spring MVC, Oracle DB, Kafka, JMS).</p>
  <p><strong>Senior Software Engineer | BlackStraw.AI (India)</strong> (May 2021 - Nov 2021)<br/>
  Built Spring Boot + Apache Kafka real-time AI inference pipelines cutting reporting delays from 15+ mins to near real-time.</p>
  <p><strong>Software Engineer | HDB Portal Systems (Aug 2019 - Dec 2020) & Wolters Kluwer LegalTech AI (Jul 2018 - Jul 2019)</strong><br/>
  Engineered sub-500ms AI + Drools BRMS legal billing compliance engine and HDB regulatory transaction workflows.</p>
</body>
</html>"""
        clean_html = sanitize_no_emdashes(html_doc)
        assert_no_emdashes(clean_html, "physical_resume_html")
        target_path.write_text(clean_html, encoding="utf-8")
        return str(target_path.relative_to(BASE_DIR)).replace("\\", "/")

    def _init_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_vault_versions (
                version_id TEXT PRIMARY KEY,
                version_tag TEXT,
                target_track TEXT,
                headline TEXT,
                executive_summary TEXT,
                bullets_json TEXT,
                linked_job_id TEXT,
                created_at TEXT
            )
            """
        )
        existing_cols = {
            r[1] for r in self.conn.execute("PRAGMA table_info(resume_vault_versions)").fetchall()
        }
        for col_name, col_def in [
            ("ats_upload_filename", "TEXT DEFAULT 'Meena_Kannan_Lead_Software_Engineer.pdf'"),
            ("internal_vault_path", "TEXT DEFAULT ''"),
        ]:
            if col_name not in existing_cols:
                self.conn.execute(f"ALTER TABLE resume_vault_versions ADD COLUMN {col_name} {col_def}")

        now = datetime.now(timezone.utc).isoformat()
        for item in BASE_RESUME_VERSIONS:
            ats_name = build_ats_safe_filename(item["role_clean"], "pdf")
            sub = build_internal_vault_subfolder(item["company_tag"], item["version_id"])
            clean_headline = sanitize_no_emdashes(item["headline"])
            clean_summary = sanitize_no_emdashes(item["executive_summary"])
            clean_bullets = [sanitize_no_emdashes(b) for b in item["highlighted_bullets"]]
            rel_path = self._write_physical_vault_file(
                subfolder_name=sub,
                ats_pdf_filename=ats_name,
                headline=clean_headline,
                summary=clean_summary,
                bullets=clean_bullets,
            )
            self.conn.execute(
                """
                INSERT OR REPLACE INTO resume_vault_versions
                (version_id, version_tag, target_track, headline, executive_summary, bullets_json,
                 linked_job_id, created_at, ats_upload_filename, internal_vault_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["version_id"],
                    sanitize_no_emdashes(item["version_tag"]),
                    sanitize_no_emdashes(item["target_track"]),
                    clean_headline,
                    clean_summary,
                    json.dumps(clean_bullets),
                    item["linked_job_id"],
                    now,
                    ats_name,
                    rel_path,
                ),
            )
        self.conn.commit()

    def select_best_version_for_job(self, job_title: str, tags: List[str]) -> str:
        combined = f"{job_title} {' '.join(tags)}".lower()
        if any(k in combined for k in ("ai", "rag", "mcp", "llm", "search", "agent")):
            return "v1.2-spring-ai-rag-mcp"
        if any(k in combined for k in ("architect", "principal", "kafka", "backend", "java", "spring")):
            return "v1.1-b2b-java-kafka-architect"
        return "v1.0-master-cloud-ai"

    def create_role_specific_version(self, job_id: str, job_title: str, company: str, pitch: str) -> str:
        now = datetime.now(timezone.utc).isoformat()
        count = self.conn.execute("SELECT COUNT(*) FROM resume_vault_versions").fetchone()[0]
        ver_id = f"v2.{max(1, count - 2)}-{job_id[:16]}"
        clean_title = sanitize_no_emdashes(job_title.split("[")[0].strip())
        clean_comp = sanitize_no_emdashes(company.split("(")[0].strip())
        ver_tag = sanitize_no_emdashes(f"v2.{max(1, count - 2)} (Tailored: {clean_comp[:22]})")

        ats_name = build_ats_safe_filename(clean_title, "pdf")
        sub = build_internal_vault_subfolder(clean_comp, ver_id)

        headline = sanitize_no_emdashes(
            f"Meena Kannan - {clean_title} | 9+ Yrs Java 21, Spring Boot 3, AWS/K8s/Kafka & Spring AI (Remote from India)"
        )
        summary = sanitize_no_emdashes(
            f"Lead Software Engineer (9+ Yrs) tailored for {clean_title} at {clean_comp}. Proven ownership of cloud-native Java 21 & Spring Boot 3 microservices "
            f"(VRLS 2.0 on AWS EKS/Istio/Kafka) and AI-augmented backend engineering (Spring AI, RAG, MCP). Based in India and targeting 100% remote work through Global B2B Contract or full-time India employment."
        )
        bullets = [
            sanitize_no_emdashes(f"Direct Stack Alignment ({clean_comp}): Architected VRLS 2.0 microservices (Java 21, Spring Boot 3, AWS EKS, Istio mTLS, Kafka, KEDA, Redis)."),
            "Cut redundant API calls by ~40% leading the Angular 13 to 18 (NgRx/RxJS) migration and instituted Scrum ADR governance.",
            "Slashed AI inference reporting delays from 15+ mins to near real-time using Apache Kafka event streams at BlackStraw.AI.",
            "Rolled out Spring AI, RAG vector pipelines, Model Context Protocol (MCP) tool servers, and sub-500ms Drools/AI rule engines."
        ]

        rel_path = self._write_physical_vault_file(
            subfolder_name=sub,
            ats_pdf_filename=ats_name,
            headline=headline,
            summary=summary,
            bullets=bullets,
        )

        self.conn.execute(
            """
            INSERT OR REPLACE INTO resume_vault_versions
            (version_id, version_tag, target_track, headline, executive_summary, bullets_json,
             linked_job_id, created_at, ats_upload_filename, internal_vault_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ver_id,
                ver_tag,
                sanitize_no_emdashes(f"{clean_title} @ {clean_comp}"),
                headline,
                summary,
                json.dumps(bullets),
                job_id,
                now,
                ats_name,
                rel_path,
            ),
        )
        self.conn.commit()
        return ver_id

    def list_versions(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM resume_vault_versions ORDER BY created_at DESC"
        ).fetchall()
        return [
            {
                "version_id": r["version_id"],
                "version_tag": r["version_tag"],
                "target_track": r["target_track"],
                "headline": r["headline"],
                "executive_summary": r["executive_summary"],
                "bullets": json.loads(r["bullets_json"]),
                "linked_job_id": r["linked_job_id"],
                "ats_upload_filename": r["ats_upload_filename"],
                "internal_vault_path": r["internal_vault_path"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
