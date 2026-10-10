import array
import hashlib
import json
import math
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_system.migrations import ensure_schema_current
from config import SETTINGS
from guardrails import sanitize_no_emdashes
from resume_vault import TailoredResumeVault
from tax_salary_engine import estimate_job_compensation_and_tax

try:
    import oracledb
except ImportError:
    oracledb = None


PROFILE_OVERLAP_RECOMMENDATION_THRESHOLD = 75
PROFILE_OVERLAP_REVIEW_THRESHOLD = 60


def initial_lifecycle_stage(decision: str, match_score: int, work_location_status: str) -> str:
    """Keep plausible, India-verified roles visible for review without approving them."""
    if decision == "RECOMMENDED" and match_score >= PROFILE_OVERLAP_RECOMMENDATION_THRESHOLD:
        return "SHORTLISTED"
    if work_location_status == "VERIFIED" and match_score >= PROFILE_OVERLAP_REVIEW_THRESHOLD:
        return "SHORTLISTED"
    return "DEAD_ZONE"


def compute_lightweight_embedding(text: str, dim: int = 64) -> List[float]:
    vec = [0.0] * dim
    tokens = [t.strip(".,;:!?()[]{}\"'").lower() for t in text.split() if len(t) > 2]
    for token in tokens:
        h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 6) for x in vec]


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    return sum(a * b for a, b in zip(v1, v2))


class OracleAIMemoryManager:
    """
    Implements the DeepLearning.AI + Oracle 'Agent Memory' & 'Building Adaptive AI Agents'
    architecture plus Full Application Lifecycle CRM, Follow-up SLA timers, Dead Zone tracking,
    Versioned Resume Vault linking, and India B2B/EOR Salary & Taxation enrichment.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        local_conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        self.config = SETTINGS.oracle
        if SETTINGS.profile_path.exists():
            self.profile = json.loads(SETTINGS.profile_path.read_text(encoding="utf-8"))
        else:
            self.profile = {}
        self.oracle_conn = None
        if local_conn is not None:
            self.local_conn = local_conn
        else:
            target_db = db_path if db_path is not None else self.config.local_fallback_db
            if self.config.is_cloud_configured and oracledb is not None and db_path is None:
                try:
                    connect_kwargs: Dict[str, Any] = {
                        "user": self.config.user,
                        "password": self.config.password,
                        "dsn": self.config.dsn,
                    }
                    if self.config.wallet_dir:
                        connect_kwargs["config_dir"] = self.config.wallet_dir
                        connect_kwargs["wallet_location"] = self.config.wallet_dir
                    self.oracle_conn = oracledb.connect(**connect_kwargs)
                except Exception as exc:
                    print(f"[OracleAI] Cloud connection unavailable ({exc}); using local mirror.")

            self.local_conn = sqlite3.connect(str(target_db), check_same_thread=False)
        self.local_conn.row_factory = sqlite3.Row
        self._init_storage()
        self.vault = TailoredResumeVault(self.local_conn)
        self._seed_knowledge_graph()
        self._backfill_crm_columns()

    @property
    def backend_mode(self) -> str:
        return "Oracle AI Database 26ai" if self.oracle_conn else "SQLite Local Mirror"

    def _init_storage(self) -> None:
        ensure_schema_current(self.local_conn)
        cur = self.local_conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        for db_rule in self.profile.get("dealbreakers", []):
            cur.execute(
                """
                INSERT OR IGNORE INTO consolidated_memory_rules (rule_type, rule_text, confidence, updated_at)
                VALUES ('DEALBREAKER', ?, 0.95, ?)
                """,
                (sanitize_no_emdashes(f"Avoid roles that match dealbreaker: {db_rule}"), now),
            )
        self.local_conn.commit()

    def _backfill_crm_columns(self) -> None:
        """
        Enriches any existing rows in agent_episodic_memories with tax/salary calculations,
        versioned resume assignments, and initial lifecycle stages if not yet populated.
        """
        cur = self.local_conn.cursor()
        rows = cur.execute("SELECT * FROM agent_episodic_memories").fetchall()
        now_dt = datetime.now(timezone.utc)

        for r in rows:
            job_id = r["job_id"]
            title = sanitize_no_emdashes(r["title"] or "")
            company = sanitize_no_emdashes(r["company"] or "")
            pitch = sanitize_no_emdashes(r["tailored_pitch"] or "")
            reason = sanitize_no_emdashes(r["feedback_reason"] or "")

            comp_info = estimate_job_compensation_and_tax(
                {"title": title, "company": company, "source": r["source_platform"] or "", "tags": []}
            )
            ver_id = r["resume_version_id"]
            if not ver_id or ver_id == "v1.0-master-cloud-ai":
                ver_id = self.vault.select_best_version_for_job(title, [])

            stage = r["lifecycle_stage"]
            applied_at = r["applied_at"] or ""
            next_followup = r["next_followup_due_at"] or ""
            closure_reason = r["closure_reason"] or ""

            cur.execute(
                """
                UPDATE agent_episodic_memories
                SET title = ?, company = ?, tailored_pitch = ?, feedback_reason = ?,
                    lifecycle_stage = ?, engagement_type = ?, engagement_label = ?,
                    salary_range_display = ?, primary_monthly_in_hand_inr = ?,
                    b2b_monthly_in_hand_inr = ?, eor_monthly_in_hand_inr = ?,
                    effective_tax_pct = ?, tax_summary = ?, resume_version_id = ?,
                    applied_at = ?, next_followup_due_at = ?, closure_reason = ?
                WHERE job_id = ?
                """,
                (
                    title,
                    company,
                    pitch,
                    reason,
                    stage,
                    comp_info["engagement_type"],
                    comp_info["engagement_label"],
                    comp_info["salary_range_display"],
                    comp_info["primary_monthly_in_hand_inr"],
                    comp_info["b2b_monthly_in_hand_inr"],
                    comp_info["eor_monthly_in_hand_inr"],
                    comp_info["primary_effective_tax_pct"],
                    comp_info["tax_summary"],
                    ver_id,
                    applied_at,
                    next_followup,
                    closure_reason,
                    job_id,
                ),
            )
        # Undo the legacy demo-only APPLIED status if it has no submission event.
        cur.execute(
            """
            UPDATE agent_episodic_memories
            SET lifecycle_stage = 'SHORTLISTED', applied_at = '',
                next_followup_due_at = '', followup_count = 0
            WHERE job_id = 'job_b2b_global_java_ai_01'
              AND lifecycle_stage = 'APPLIED'
              AND NOT EXISTS (
                  SELECT 1 FROM application_timeline_events
                  WHERE application_timeline_events.job_id = agent_episodic_memories.job_id
                    AND application_timeline_events.to_stage IN ('APPLIED', 'INTERVIEW', 'OFFER')
              )
            """
        )

        legacy_approvals = cur.execute(
            """
            SELECT job.job_id
            FROM agent_episodic_memories AS job
            WHERE job.lifecycle_stage = 'APPROVED'
              AND EXISTS (
                  SELECT 1
                  FROM application_timeline_events AS event
                  WHERE event.job_id = job.job_id
                    AND event.to_stage = 'APPROVED'
                    AND event.note LIKE 'Autopilot auto-approved%'
              )
            """
        ).fetchall()
        reconcile_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        for row in legacy_approvals:
            cur.execute(
                "UPDATE agent_episodic_memories SET lifecycle_stage = 'SHORTLISTED' WHERE job_id = ?",
                (row["job_id"],),
            )
            cur.execute(
                """
                INSERT INTO application_timeline_events (job_id, from_stage, to_stage, note, event_at)
                VALUES (?, 'APPROVED', 'SHORTLISTED', ?, ?)
                """,
                (
                    row["job_id"],
                    "Reconciled legacy automated approval. Requires human approval and India location review.",
                    reconcile_at,
                ),
            )
        approvals_without_events = cur.execute(
            """
            SELECT job.job_id
            FROM agent_episodic_memories AS job
            WHERE job.lifecycle_stage = 'APPROVED'
              AND NOT EXISTS (
                  SELECT 1
                  FROM application_timeline_events AS event
                  WHERE event.job_id = job.job_id
                    AND event.to_stage = 'APPROVED'
              )
            """
        ).fetchall()
        for row in approvals_without_events:
            cur.execute(
                "UPDATE agent_episodic_memories SET lifecycle_stage = 'SHORTLISTED' WHERE job_id = ?",
                (row["job_id"],),
            )
            cur.execute(
                """
                INSERT INTO application_timeline_events (job_id, from_stage, to_stage, note, event_at)
                VALUES (?, 'APPROVED', 'SHORTLISTED', ?, ?)
                """,
                (
                    row["job_id"],
                    "Reconciled approval with no human approval event. Requires explicit review.",
                    reconcile_at,
                ),
            )
        self.local_conn.commit()

    def _seed_knowledge_graph(self) -> None:
        kg = self.profile.get("knowledge_graph", {})
        cur = self.local_conn.cursor()
        for skill in kg.get("skills", []):
            cur.execute(
                "INSERT OR REPLACE INTO kg_vertices VALUES (?, 'SKILL', ?, ?)",
                (skill["id"], skill["name"], json.dumps(skill)),
            )
        for proj in kg.get("projects", []):
            cur.execute(
                "INSERT OR REPLACE INTO kg_vertices VALUES (?, 'PROJECT', ?, ?)",
                (proj["id"], proj["title"], json.dumps(proj)),
            )
            for skill_id in proj.get("uses_skills", []):
                edge_id = f"{proj['id']}__USES__{skill_id}"
                cur.execute(
                    "INSERT OR REPLACE INTO kg_edges VALUES (?, ?, ?, 'USES_SKILL')",
                    (edge_id, proj["id"], skill_id),
                )
            for domain in proj.get("solves_domains", []):
                dom_id = f"dom_{domain.lower().replace(' ', '_')}"
                cur.execute(
                    "INSERT OR REPLACE INTO kg_vertices VALUES (?, 'DOMAIN', ?, ?)",
                    (dom_id, domain, json.dumps({"domain": domain})),
                )
                edge_id = f"{proj['id']}__SOLVES__{dom_id}"
                cur.execute(
                    "INSERT OR REPLACE INTO kg_edges VALUES (?, ?, ?, 'SOLVES_DOMAIN')",
                    (edge_id, proj["id"], dom_id),
                )
        self.local_conn.commit()

    def traverse_knowledge_graph(self, job_text: str) -> Dict[str, Any]:
        lower_job = job_text.lower()
        cur = self.local_conn.cursor()
        projects = cur.execute("SELECT * FROM kg_vertices WHERE vertex_type = 'PROJECT'").fetchall()

        matched_graph_paths: List[Dict[str, Any]] = []
        for proj_row in projects:
            proj_meta = json.loads(proj_row["metadata_json"])
            edges = cur.execute(
                """
                SELECT e.relation, v.vertex_id, v.vertex_type, v.name, v.metadata_json
                FROM kg_edges e
                JOIN kg_vertices v ON e.target_id = v.vertex_id
                WHERE e.source_id = ?
                """,
                (proj_row["vertex_id"],),
            ).fetchall()

            activated_nodes = []
            for edge in edges:
                node_name = edge["name"]
                skill_terms = {
                    "skill_java_spring": ("java", "java 21", "java 18", "spring boot", "springboot", "webflux"),
                    "skill_k8s_cloud": ("aws", "eks", "ecs", "kubernetes", "k8s", "docker", "helm", "istio"),
                    "skill_event_driven": ("kafka", "kafka streams", "event-driven", "event driven", "event stream", "keda", "redis", "outbox", "saga"),
                    "skill_ai_agents": ("spring ai", "rag", "retrieval augmented generation", "mcp", "model context protocol", "claude api", "agentic workflow"),
                    "skill_databases": ("oracle database", "oracle db", "postgresql", "mysql", "mongodb", "redis", "flyway"),
                    "skill_frontend": ("angular", "react", "next.js", "ngrx", "rxjs", "typescript", "graphql"),
                    "skill_devsecops": ("argocd", "jenkins", "github actions", "terraform", "vault", "keycloak", "opentelemetry"),
                    "skill_leadership": ("technical lead", "engineering lead", "lead engineer", "solution architect", "solutions architect", "scrum master", "architecture decision record"),
                }
                domain_terms = {
                    "cloud-native modernisation": ("cloud-native", "cloud native", "cloud modernisation", "cloud modernization"),
                    "microservices architecture": ("microservices", "microservice", "service architecture"),
                    "distributed remote delivery": ("distributed systems", "distributed system", "remote engineering teams"),
                    "event-driven scaling": ("event-driven", "event driven", "event streams", "kafka"),
                    "spring ai & mcp integration": ("spring ai", "mcp server", "model context protocol", "rag pipeline"),
                    "real-time streaming": ("real-time", "real time", "kafka streams", "event streams"),
                    "ai/ml inference integration": ("inference", "model serving", "AI model"),
                    "latency optimization": ("latency", "low-latency", "response time"),
                    "high-throughput backend": ("high-throughput", "high throughput", "backend platform"),
                }
                if edge["vertex_type"] == "SKILL":
                    terms = skill_terms.get(edge["vertex_id"], ())
                elif edge["vertex_type"] == "DOMAIN":
                    terms = domain_terms.get(node_name.lower(), ())
                else:
                    terms = (node_name,)
                if any(
                    re.search(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])", lower_job)
                    for term in terms
                ):
                    activated_nodes.append(f"{edge['relation']} -> {node_name}")

            matched_graph_paths.append(
                {
                    "project": proj_row["name"],
                    "summary": proj_meta.get("summary", ""),
                    "activated_graph_edges": activated_nodes
                    or [f"USES_SKILL -> {e['name']}" for e in edges[:3]],
                    "relevance_hops": len(activated_nodes),
                }
            )

        matched_graph_paths.sort(key=lambda x: x["relevance_hops"], reverse=True)
        return {
            "candidate_name": self.profile.get("candidate_name"),
            "headline": self.profile.get("headline"),
            "graph_paths": matched_graph_paths,
        }

    def _qualifying_human_feedback_note(self, cur, job_id: str, decision: str) -> Optional[str]:
        decision = decision.upper()
        rows = cur.execute(
            "SELECT reason FROM human_feedback_events WHERE job_id = ? AND decision = ? ORDER BY feedback_id DESC",
            (job_id, decision),
        ).fetchall()
        for row in rows:
            note = sanitize_no_emdashes(str(row["reason"] or "")).strip()
            if len(note) >= 12:
                return note
        return None

    def retrieve_similar_episodic_memories(self, job_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        query_vec = compute_lightweight_embedding(job_text)
        cur = self.local_conn.cursor()
        rows = cur.execute(
            """
            SELECT job.*, feedback.decision AS human_decision, feedback.reason AS human_reason,
                   feedback.source AS human_source, feedback.created_at AS human_feedback_at
            FROM agent_episodic_memories AS job
            JOIN (
                SELECT job_id, MAX(feedback_id) AS latest_feedback_id
                FROM human_feedback_events
                GROUP BY job_id
            ) AS latest ON latest.job_id = job.job_id
            JOIN human_feedback_events AS feedback
              ON feedback.feedback_id = latest.latest_feedback_id
            WHERE feedback.decision IN ('APPROVED', 'REJECTED')
            """
        ).fetchall()
        scored = []
        for r in rows:
            human_note = sanitize_no_emdashes(str(r["human_reason"] or "")).strip()
            if len(human_note) < 12:
                continue
            if not r["embedding_json"]:
                continue
            emb = json.loads(r["embedding_json"])
            sim = cosine_similarity(query_vec, emb)
            col_keys = r.keys()
            scored.append(
                {
                    "job_id": r["job_id"],
                    "title": r["title"],
                    "company": r["company"],
                    "decision": r["human_decision"],
                    "match_score": r["match_score"],
                    "feedback_reason": human_note,
                    "similarity": round(sim, 3),
                    "lifecycle_stage": r["lifecycle_stage"] if "lifecycle_stage" in col_keys else "SHORTLISTED",
                    "work_location_status": r["work_location_status"] if "work_location_status" in col_keys else "NEEDS_REVIEW",
                    "source_platform": r["source_platform"] if "source_platform" in col_keys else "",
                    "feedback_source": r["human_source"] if "human_source" in col_keys else "",
                    "feedback_created_at": r["human_feedback_at"] if "human_feedback_at" in col_keys else "",
                    "submission_evidence_source": r["submission_evidence_source"] if "submission_evidence_source" in col_keys else "",
                    "raw_listing_source": r["raw_listing_source"] if "raw_listing_source" in col_keys else "",
                }
            )
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    def get_memory_provenance(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves full audit and provenance details for a specific episodic memory.
        Combines job metadata, work location evidence, submission evidence,
        complete human feedback audit events, and timeline transitions.
        """
        cur = self.local_conn.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(agent_episodic_memories)").fetchall()}
        row = cur.execute(
            "SELECT * FROM agent_episodic_memories WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if not row:
            return None

        feedback_rows = cur.execute(
            """
            SELECT feedback_id, decision, reason, source, created_at
            FROM human_feedback_events
            WHERE job_id = ?
            ORDER BY feedback_id ASC
            """,
            (job_id,),
        ).fetchall()

        timeline_rows = cur.execute(
            """
            SELECT event_id, from_stage, to_stage, note, event_at
            FROM application_timeline_events
            WHERE job_id = ?
            ORDER BY event_id ASC
            """,
            (job_id,),
        ).fetchall()

        source_provenance = {}
        if "source_provenance_json" in cols and row["source_provenance_json"]:
            try:
                source_provenance = json.loads(row["source_provenance_json"])
            except (json.JSONDecodeError, TypeError):
                source_provenance = {}

        return {
            "job_id": row["job_id"],
            "title": row["title"],
            "company": row["company"],
            "url": row["url"],
            "source_platform": row["source_platform"] if "source_platform" in cols else "",
            "raw_listing_source": row["raw_listing_source"] if "raw_listing_source" in cols else "",
            "source_provenance": source_provenance,
            "lifecycle_stage": row["lifecycle_stage"] if "lifecycle_stage" in cols else "SHORTLISTED",
            "work_location_status": row["work_location_status"] if "work_location_status" in cols else "NEEDS_REVIEW",
            "work_location_evidence": row["work_location_evidence"] if "work_location_evidence" in cols else "",
            "submission_evidence_at": row["submission_evidence_at"] if "submission_evidence_at" in cols else "",
            "submission_evidence_source": row["submission_evidence_source"] if "submission_evidence_source" in cols else "",
            "acknowledged_at": row["acknowledged_at"] if "acknowledged_at" in cols else "",
            "acknowledgement_evidence_source": row["acknowledgement_evidence_source"] if "acknowledgement_evidence_source" in cols else "",
            "match_score": row["match_score"],
            "ranker_decision": row["ranker_decision"] if "ranker_decision" in cols else "",
            "created_at": row["created_at"],
            "feedback_history": [dict(f) for f in feedback_rows],
            "timeline_history": [dict(t) for t in timeline_rows],
        }

    def list_provenance_records(self, limit: int = 50, lifecycle_stage: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lists summarized provenance records using the v_episodic_memory_provenance view if available.
        """
        cur = self.local_conn.cursor()
        tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')").fetchall()}
        if "v_episodic_memory_provenance" in tables:
            if lifecycle_stage:
                rows = cur.execute(
                    "SELECT * FROM v_episodic_memory_provenance WHERE lifecycle_stage = ? ORDER BY created_at DESC LIMIT ?",
                    (lifecycle_stage, limit),
                ).fetchall()
            else:
                rows = cur.execute(
                    "SELECT * FROM v_episodic_memory_provenance ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

        if lifecycle_stage:
            rows = cur.execute(
                "SELECT job_id, title, company, url, lifecycle_stage, work_location_status, created_at "
                "FROM agent_episodic_memories WHERE lifecycle_stage = ? ORDER BY created_at DESC LIMIT ?",
                (lifecycle_stage, limit),
            ).fetchall()
        else:
            rows = cur.execute(
                "SELECT job_id, title, company, url, lifecycle_stage, work_location_status, created_at "
                "FROM agent_episodic_memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def is_job_seen(self, job_id: str) -> bool:
        cur = self.local_conn.cursor()
        row = cur.execute(
            "SELECT 1 FROM agent_episodic_memories WHERE job_id = ?", (job_id,)
        ).fetchone()
        return row is not None

    def get_active_rules(self) -> List[str]:
        cur = self.local_conn.cursor()
        rows = cur.execute(
            "SELECT rule_type, rule_text, confidence FROM consolidated_memory_rules ORDER BY confidence DESC"
        ).fetchall()
        profile_dealbreakers = {
            sanitize_no_emdashes(f"Avoid roles that match dealbreaker: {reason}")
            for reason in self.profile.get("dealbreakers", [])
        }
        active_rules = []
        for row in rows:
            rule_type = row["rule_type"]
            rule_text = row["rule_text"]
            if rule_type == "DEALBREAKER" and rule_text not in profile_dealbreakers:
                continue
            if rule_type in {"PREFERENCE_BOOST", "LEARNED_AVOIDANCE"}:
                prefix = "When evaluating jobs similar to "
                if not rule_text.startswith(prefix):
                    continue
                job_id = rule_text[len(prefix):].split(", enforce ", 1)[0].strip()
                decision = "APPROVED" if rule_type == "PREFERENCE_BOOST" else "REJECTED"
                if not self._qualifying_human_feedback_note(cur, job_id, decision):
                    continue
            active_rules.append(
                sanitize_no_emdashes(f"[{rule_type} | conf={row['confidence']:.2f}] {rule_text}")
            )
        return active_rules

    def save_episodic_memory(
        self,
        job_id: str,
        title: str,
        company: str,
        url: str,
        decision: str,
        match_score: int,
        critic_score: int,
        tailored_pitch: str,
        feedback_reason: str,
        raw_text: str,
        source_platform: str = "Live Multi-Tier Feed",
        work_location_status: str = "NEEDS_REVIEW",
        work_location_evidence: str = "",
        raw_listing_source: str = "",
        source_provenance_json: str = "{}",
    ) -> None:
        clean_title = sanitize_no_emdashes(title)
        clean_comp = sanitize_no_emdashes(company)
        clean_pitch = sanitize_no_emdashes(tailored_pitch)
        clean_reason = sanitize_no_emdashes(feedback_reason)

        vec = compute_lightweight_embedding(f"{clean_title} {clean_comp} {raw_text}")
        now = datetime.now(timezone.utc).isoformat()
        comp_info = estimate_job_compensation_and_tax(
            {"title": clean_title, "company": clean_comp, "source": source_platform, "tags": []}
        )
        ver_id = self.vault.select_best_version_for_job(clean_title, [])
        stage = initial_lifecycle_stage(decision, match_score, work_location_status)
        closure_reason = "" if stage == "SHORTLISTED" else f"Auto-Filtered ({match_score}/100): {clean_reason[:120]}"

        cur = self.local_conn.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(agent_episodic_memories)").fetchall()}
        has_provenance = "raw_listing_source" in cols and "source_provenance_json" in cols

        if has_provenance:
            cur.execute(
                """
                INSERT INTO agent_episodic_memories
                (job_id, title, company, url, decision, ranker_decision, match_score, score_model_version, critic_score, tailored_pitch,
                 feedback_reason, embedding_json, created_at, lifecycle_stage, source_platform,
                 engagement_type, engagement_label, salary_range_display, primary_monthly_in_hand_inr,
                 b2b_monthly_in_hand_inr, eor_monthly_in_hand_inr, effective_tax_pct, tax_summary,
                 resume_version_id, closure_reason, work_location_status, work_location_evidence,
                 raw_listing_source, source_provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    title = excluded.title,
                    company = excluded.company,
                    url = excluded.url,
                    decision = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM human_feedback_events
                            WHERE human_feedback_events.job_id = excluded.job_id
                        ) THEN agent_episodic_memories.decision
                        ELSE excluded.decision
                    END,
                    ranker_decision = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM human_feedback_events
                            WHERE human_feedback_events.job_id = excluded.job_id
                        ) THEN agent_episodic_memories.ranker_decision
                        ELSE excluded.ranker_decision
                    END,
                    match_score = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM human_feedback_events
                            WHERE human_feedback_events.job_id = excluded.job_id
                        ) THEN agent_episodic_memories.match_score
                        ELSE excluded.match_score
                    END,
                    score_model_version = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM human_feedback_events
                            WHERE human_feedback_events.job_id = excluded.job_id
                        ) THEN agent_episodic_memories.score_model_version
                        ELSE excluded.score_model_version
                    END,
                    critic_score = excluded.critic_score,
                    tailored_pitch = excluded.tailored_pitch,
                    feedback_reason = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM human_feedback_events
                            WHERE human_feedback_events.job_id = excluded.job_id
                        ) THEN agent_episodic_memories.feedback_reason
                        ELSE excluded.feedback_reason
                    END,
                    embedding_json = excluded.embedding_json,
                    created_at = excluded.created_at,
                    source_platform = excluded.source_platform,
                    work_location_status = CASE
                        WHEN excluded.work_location_status = 'VERIFIED' THEN excluded.work_location_status
                        ELSE agent_episodic_memories.work_location_status
                    END,
                    work_location_evidence = CASE
                        WHEN excluded.work_location_status = 'VERIFIED' THEN excluded.work_location_evidence
                        ELSE agent_episodic_memories.work_location_evidence
                    END,
                    raw_listing_source = CASE
                        WHEN excluded.raw_listing_source != '' THEN excluded.raw_listing_source
                        ELSE agent_episodic_memories.raw_listing_source
                    END,
                    source_provenance_json = CASE
                        WHEN excluded.source_provenance_json != '{}' THEN excluded.source_provenance_json
                        ELSE agent_episodic_memories.source_provenance_json
                    END
                """,
                (
                    job_id,
                    clean_title,
                    clean_comp,
                    url,
                    decision,
                    decision,
                    match_score,
                    "profile-overlap-v2",
                    critic_score,
                    clean_pitch,
                    clean_reason,
                    json.dumps(vec),
                    now,
                    stage,
                    sanitize_no_emdashes(source_platform),
                    comp_info["engagement_type"],
                    comp_info["engagement_label"],
                    comp_info["salary_range_display"],
                    comp_info["primary_monthly_in_hand_inr"],
                    comp_info["b2b_monthly_in_hand_inr"],
                    comp_info["eor_monthly_in_hand_inr"],
                    comp_info["primary_effective_tax_pct"],
                    comp_info["tax_summary"],
                    ver_id,
                    sanitize_no_emdashes(closure_reason),
                    work_location_status,
                    sanitize_no_emdashes(work_location_evidence),
                    sanitize_no_emdashes(raw_listing_source),
                    source_provenance_json,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO agent_episodic_memories
                (job_id, title, company, url, decision, ranker_decision, match_score, score_model_version, critic_score, tailored_pitch,
                 feedback_reason, embedding_json, created_at, lifecycle_stage, source_platform,
                 engagement_type, engagement_label, salary_range_display, primary_monthly_in_hand_inr,
                 b2b_monthly_in_hand_inr, eor_monthly_in_hand_inr, effective_tax_pct, tax_summary,
                 resume_version_id, closure_reason, work_location_status, work_location_evidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    title = excluded.title,
                    company = excluded.company,
                    url = excluded.url,
                    decision = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM human_feedback_events
                            WHERE human_feedback_events.job_id = excluded.job_id
                        ) THEN agent_episodic_memories.decision
                        ELSE excluded.decision
                    END,
                    ranker_decision = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM human_feedback_events
                            WHERE human_feedback_events.job_id = excluded.job_id
                        ) THEN agent_episodic_memories.ranker_decision
                        ELSE excluded.ranker_decision
                    END,
                    match_score = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM human_feedback_events
                            WHERE human_feedback_events.job_id = excluded.job_id
                        ) THEN agent_episodic_memories.match_score
                        ELSE excluded.match_score
                    END,
                    score_model_version = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM human_feedback_events
                            WHERE human_feedback_events.job_id = excluded.job_id
                        ) THEN agent_episodic_memories.score_model_version
                        ELSE excluded.score_model_version
                    END,
                    critic_score = excluded.critic_score,
                    tailored_pitch = excluded.tailored_pitch,
                    feedback_reason = CASE
                        WHEN EXISTS (
                            SELECT 1 FROM human_feedback_events
                            WHERE human_feedback_events.job_id = excluded.job_id
                        ) THEN agent_episodic_memories.feedback_reason
                        ELSE excluded.feedback_reason
                    END,
                    embedding_json = excluded.embedding_json,
                    created_at = excluded.created_at,
                    source_platform = excluded.source_platform,
                    work_location_status = CASE
                        WHEN excluded.work_location_status = 'VERIFIED' THEN excluded.work_location_status
                        ELSE agent_episodic_memories.work_location_status
                    END,
                    work_location_evidence = CASE
                        WHEN excluded.work_location_status = 'VERIFIED' THEN excluded.work_location_evidence
                        ELSE agent_episodic_memories.work_location_evidence
                    END
                """,
                (
                    job_id,
                    clean_title,
                    clean_comp,
                    url,
                    decision,
                    decision,
                    match_score,
                    "profile-overlap-v2",
                    critic_score,
                    clean_pitch,
                    clean_reason,
                    json.dumps(vec),
                    now,
                    stage,
                    sanitize_no_emdashes(source_platform),
                    comp_info["engagement_type"],
                    comp_info["engagement_label"],
                    comp_info["salary_range_display"],
                    comp_info["primary_monthly_in_hand_inr"],
                    comp_info["b2b_monthly_in_hand_inr"],
                    comp_info["eor_monthly_in_hand_inr"],
                    comp_info["primary_effective_tax_pct"],
                    comp_info["tax_summary"],
                    ver_id,
                    sanitize_no_emdashes(closure_reason),
                    work_location_status,
                    sanitize_no_emdashes(work_location_evidence),
                ),
            )
        self.local_conn.commit()

    def update_job_lifecycle_stage(
        self,
        job_id: str,
        new_stage: str,
        note: str = "",
        closure_reason: str = "",
        evidence_source: str = "",
    ) -> Dict[str, Any]:
        """
        Transitions a job across lifecycle stages:
        SHORTLISTED -> APPROVED -> APPLIED -> INTERVIEW -> OFFER -> DEAD_ZONE
        Automatically sets follow-up SLA dates (Day 4, Day 10, Day 21 expiry) and creates a versioned resume snapshot on APPROVED.
        """
        cur = self.local_conn.cursor()
        row = cur.execute("SELECT * FROM agent_episodic_memories WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            raise ValueError(f"Job {job_id} not found")

        old_stage = row["lifecycle_stage"]
        if new_stage == "APPROVED" and row["work_location_status"] != "VERIFIED":
            raise ValueError("Verify India remote eligibility from the official posting before approval")
        if new_stage == "APPROVED" and len(note.strip()) < 12:
            raise ValueError("Add a specific reason for approving this role so future rankings learn from your decision")
        if new_stage == "APPROVED" and old_stage != "SHORTLISTED":
            raise ValueError("Only a shortlisted role can be approved for application")
        if new_stage == "DEAD_ZONE" and not note.strip():
            raise ValueError("Add a reason for closing this role")
        if new_stage == "APPLIED":
            if row["work_location_status"] != "VERIFIED":
                raise ValueError("Verify India remote eligibility from the official posting before recording an application")
            if old_stage != "APPROVED":
                raise ValueError("Approve the role after eligibility review before recording an application")
            if len(note.strip()) < 12:
                raise ValueError("Paste the ATS receipt text or confirmation email subject")
            if len(evidence_source.strip()) < 4:
                raise ValueError("Record the receipt URL, saved evidence filename, or email reference")

        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M UTC")

        applied_at = row["applied_at"] or ""
        submission_evidence_at = row["submission_evidence_at"] or ""
        submission_evidence_source = row["submission_evidence_source"] or ""
        next_followup = row["next_followup_due_at"] or ""
        followup_count = int(row["followup_count"] or 0)
        ver_id = row["resume_version_id"]

        if new_stage == "APPROVED":
            # Auto-generate a tailored resume snapshot in the Resume Vault
            ver_id = self.vault.create_role_specific_version(
                job_id=job_id,
                job_title=row["title"],
                company=row["company"],
                pitch=row["tailored_pitch"],
            )
            self.consolidate_user_feedback(job_id, "APPROVED", note, source="application_review")
        elif new_stage == "APPLIED":
            applied_at = now_str
            submission_evidence_at = now_str
            submission_evidence_source = sanitize_no_emdashes(evidence_source.strip())[:500]
            due_dt = now_dt + timedelta(days=4)
            next_followup = f"{due_dt.strftime('%Y-%m-%d')} (Day 4 Follow-Up SLA)"
        elif new_stage == "FOLLOWUP_SENT":
            new_stage = "APPLIED"
            followup_count += 1
            next_days = 6 if followup_count == 1 else 11
            due_dt = now_dt + timedelta(days=next_days)
            next_followup = f"{due_dt.strftime('%Y-%m-%d')} (Follow-Up #{followup_count + 1} / 21d Dead-Zone Guard)"
        elif new_stage == "DEAD_ZONE":
            closure_reason = sanitize_no_emdashes(closure_reason or note or "Role Closed / Moved to Dead Applications Zone")
            if "reject" in closure_reason.lower() and closure_reason.lower() not in {"role closed / rejected", "rejected"}:
                self.consolidate_user_feedback(job_id, "REJECTED", closure_reason, source="application_review")

        cur.execute(
            """
            UPDATE agent_episodic_memories
            SET lifecycle_stage = ?, applied_at = ?, next_followup_due_at = ?,
                submission_evidence_at = ?, submission_evidence_source = ?,
                followup_count = ?, closure_reason = ?, resume_version_id = ?
            WHERE job_id = ?
            """,
            (
                new_stage,
                applied_at,
                next_followup,
                submission_evidence_at,
                submission_evidence_source,
                followup_count,
                sanitize_no_emdashes(closure_reason),
                ver_id,
                job_id,
            ),
        )
        cur.execute(
            """
            INSERT INTO application_timeline_events (job_id, from_stage, to_stage, note, event_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                job_id,
                old_stage,
                new_stage,
                sanitize_no_emdashes(
                    f"Submission receipt: {note.strip()} | Evidence reference: {evidence_source.strip()}"
                    if new_stage == "APPLIED"
                    else note or f"Transitioned {old_stage} -> {new_stage}"
                ),
                now_str,
            ),
        )
        self.local_conn.commit()
        return {"job_id": job_id, "old_stage": old_stage, "new_stage": new_stage, "resume_version_id": ver_id}

    def get_all_crm_jobs(self) -> List[Dict[str, Any]]:
        cur = self.local_conn.cursor()
        rows = cur.execute(
            """
            SELECT * FROM agent_episodic_memories
            ORDER BY
                CASE WHEN lifecycle_stage != 'DEAD_ZONE' AND work_location_status = 'VERIFIED' THEN 0 ELSE 1 END,
                CASE WHEN score_model_version = 'profile-overlap-v2' THEN 0 ELSE 1 END,
                match_score DESC,
                created_at DESC
            """
        ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            item.pop("embedding_json", None)
            # Generate ready-to-send plain-text follow-up note (zero em-dashes)
            clean_title = sanitize_no_emdashes((r["title"] or "").split("[")[0].strip())
            clean_comp = sanitize_no_emdashes((r["company"] or "").split("(")[0].strip())
            item["followup_template"] = sanitize_no_emdashes(
                f"Hi {clean_comp} Hiring Team,\n\n"
                f"Following up on my application for the {clean_title} role submitted on {r['applied_at'] or 'recently'}. "
                f"I remain very interested in bringing my 9+ years of Java 21, Spring Boot 3, AWS/Kubernetes, Kafka, "
                f"and Spring AI / MCP production experience to your team. I am based in India and interested in a 100% remote role through India EOR or a global B2B contract.\n\n"
                f"Please let me know if any additional technical details or architecture walkthroughs would be helpful.\n\n"
                f"Best regards,\n"
                f"Meena Kannan | +91 97893 02084 | meenakannan92@gmail.com"
            )
            result.append(item)
        return result

    def consolidate_user_feedback(
        self, job_id: str, decision: str, reason: str, source: str = "explicit_user_input"
    ) -> str:
        decision = decision.upper().strip()
        if decision not in {"APPROVED", "REJECTED"}:
            raise ValueError("Feedback decision must be APPROVED or REJECTED")
        now = datetime.now(timezone.utc).isoformat()
        clean_reason = sanitize_no_emdashes(reason).strip()
        if len(clean_reason) < 12:
            raise ValueError("Add a specific reason of at least 12 characters")
        cur = self.local_conn.cursor()
        if not cur.execute("SELECT 1 FROM agent_episodic_memories WHERE job_id = ?", (job_id,)).fetchone():
            raise ValueError(f"Job {job_id} not found")
        cur.execute(
            """
            UPDATE agent_episodic_memories
            SET decision = ?, feedback_reason = ?
            WHERE job_id = ?
            """,
            (decision, clean_reason, job_id),
        )
        cur.execute(
            "INSERT INTO human_feedback_events (job_id, decision, reason, source, created_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, decision, clean_reason, source, now),
        )
        rule_type = "PREFERENCE_BOOST" if decision == "APPROVED" else "LEARNED_AVOIDANCE"
        consolidated_rule = sanitize_no_emdashes(
            f"When evaluating jobs similar to {job_id}, enforce {decision} pattern: {clean_reason}"
        )
        cur.execute(
            """
            INSERT INTO consolidated_memory_rules (rule_type, rule_text, confidence, updated_at)
            VALUES (?, ?, 0.92, ?)
            ON CONFLICT(rule_text) DO UPDATE SET
                confidence = MIN(0.99, confidence + 0.03),
                source_count = source_count + 1,
                updated_at = excluded.updated_at
            """,
            (rule_type, consolidated_rule, now),
        )
        self.local_conn.commit()
        return consolidated_rule
