import hashlib
from typing import Any, Dict, List

from guardrails import assert_no_emdashes, sanitize_no_emdashes
from oracle_memory import OracleAIMemoryManager, PROFILE_OVERLAP_RECOMMENDATION_THRESHOLD


BANNED_AI_PHRASES = (
    "thrilled to",
    "delve",
    "testament to",
    "seamless",
    "game-changer",
    "unparalleled",
    "synergy",
    "moreover",
    "furthermore",
    "target role alignment",
    "\u2014",
    "\u2013",
)


class ReflectiveJobAgent:
    """
    Ranks eligible roles with a deterministic graph heuristic and validates
    generated copy against the project's anti-bot and punctuation guardrails.
      - Strictly bans Unicode em-dashes (U+2014) and en-dashes (U+2013)
      - Ensures zero robotic formatting (no markdown bolding `**` in copy-paste notes, no AI buzzwords)
      - Uses natural first-person Senior Engineer prose with rotated sentence structure
    """

    def __init__(self, memory: OracleAIMemoryManager) -> None:
        self.memory = memory

    def _craft_human_authentic_note(self, job: Dict[str, Any], top_proj: Dict[str, Any]) -> str:
        """
        Generates a 100% human-sounding, first-person senior engineer outreach note
        guaranteed free of em-dashes, AI clichés, or robotic bullet headers.
        """
        title = sanitize_no_emdashes(job["title"].split("[")[0].split("(")[0].strip())
        company = sanitize_no_emdashes(job["company"].split("(")[0].strip())
        variant = int(hashlib.md5(f"{company}_{title}".encode("utf-8")).hexdigest(), 16) % 3

        if variant == 0:
            raw = (
                f"Hi {company} Engineering Team,\n\n"
                f"I'm reaching out regarding the {title} role. Over the past 9+ years I've led backend and cloud-native "
                f"architecture across high-volume platforms, most recently leading the VRLS 2.0 modernisation at NCS/LTA "
                f"where we migrated a legacy Java monolith onto Java 21, Spring Boot 3, AWS (EKS/ECS), Istio mTLS, and "
                f"Kafka with KEDA autoscaling.\n\n"
                f"Alongside core distributed systems work (cutting redundant API calls by ~40% during our Angular 13 to 18 "
                f"upgrade and replacing 15-minute batch jobs with real-time Kafka streams at BlackStraw.AI), I've been "
                f"hands-on integrating Spring AI, RAG pipelines, and MCP tool servers into production Java services.\n\n"
                f"I am based in India and targeting 100% remote roles, either via a Global B2B contract or full-time "
                f"through India EOR. Happy to walk through our VRLS 2.0 and Kafka "
                f"architecture anytime.\n\n"
                f"Best regards,\n"
                f"Meena Kannan\n"
                f"+91 97893 02084 | meenakannan92@gmail.com | linkedin.com/in/meena-kannan-mk"
            )
        elif variant == 1:
            raw = (
                f"Hello {company} Team,\n\n"
                f"Saw the opening for {title} and wanted to share my background directly. I have 9+ years building "
                f"mission-critical Java and cloud platforms, currently serving as Lead Software Engineer on the VRLS 2.0 "
                f"programme (Java 21, Spring Boot 3, Kubernetes, Kafka Streams, Redis, and ArgoCD GitOps supporting millions "
                f"of users).\n\n"
                f"A big focus of my recent work has been bridging production Java microservices with practical AI workflows, "
                f"rolling out Spring AI, RAG vector retrieval, and Anthropic MCP server patterns while keeping strict latency "
                f"and compliance guardrails (previously built a sub-500ms AI + Drools billing compliance engine at Wolters Kluwer).\n\n"
                f"I am based in India and interested in remote full-time roles through an India entity or EOR, or in "
                f"global B2B contracting. Would love to connect if my background fits what your squad is building.\n\n"
                f"Thanks,\n"
                f"Meena Kannan\n"
                f"+91 97893 02084 | meenakannan92@gmail.com | github.com/meenak95"
            )
        else:
            raw = (
                f"Hi Hiring Team at {company},\n\n"
                f"Applying for the {title} position. I'm a Lead Software Engineer with 9+ years of experience in Java 21, "
                f"Spring Boot 3, Apache Kafka, and AWS Kubernetes architectures, combined with hands-on delivery in Spring AI, "
                f"RAG pipelines, and MCP tool orchestration.\n\n"
                f"In my current lead role on VRLS 2.0 (NCS / LTA) and prior engineering roles at BlackStraw.AI and Wolters Kluwer, "
                f"I've owned end-to-end monolith-to-microservices migrations, Istio service mesh security, and real-time Kafka "
                f"event pipelines that cut reporting latency from 15+ minutes down to seconds.\n\n"
                f"I am based in India and targeting 100% remote work through a global B2B contract or full-time India employment. Looking forward "
                f"to discussing how I can contribute to the {company} engineering team.\n\n"
                f"Warm regards,\n"
                f"Meena Kannan\n"
                f"+91 97893 02084 | meenakannan92@gmail.com | linkedin.com/in/meena-kannan-mk"
            )

        cleaned = sanitize_no_emdashes(raw)
        assert_no_emdashes(cleaned, context_label="tailored_pitch")
        return cleaned

    def _deterministic_reflective_cycle(
        self,
        job: Dict[str, Any],
        graph_ctx: Dict[str, Any],
        episodic_memories: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        text = f"{job['title']} {job['company']} {' '.join(job.get('tags', []))} {job.get('description', '')}".lower()
        graph_paths = graph_ctx.get("graph_paths", [])
        total_hops = sum(p.get("relevance_hops", 0) for p in graph_paths)
        profile_anchors = {
            edge.split(" -> ", 1)[-1]
            for path in graph_paths
            if path.get("relevance_hops", 0) > 0
            for edge in path.get("activated_graph_edges", [])
            if " -> " in edge
        }

        # The score reflects distinct profile evidence overlaps, not success probability.
        base_score = min(85, 40 + len(profile_anchors) * 7)
        target_roles = " ".join(self.memory.profile.get("target_roles", [])).lower()
        if any(term in text for term in ("senior", "staff", "lead", "principal", "architect")) and any(
            term in target_roles for term in ("senior", "staff", "lead", "principal", "architect")
        ):
            base_score = min(88, base_score + 3)

        penalty = 0
        penalty_reasons = []
        if (
            "singapore onsite" in text
            or "physical presence in singapore" in text
            or "no remote from india" in text
            or "unpaid internship" in text
            or "onsite-only in us" in text
        ):
            penalty += 70
            penalty_reasons.append(
                "Violates consolidated Memory Rule: Strictly targeting 100% Remote from India (Full-Time or Global B2B); Singapore Onsite/Hybrid excluded"
            )

        has_related_human_approval = False
        for mem in episodic_memories:
            if mem.get("decision") == "REJECTED" and mem.get("similarity", 0) > 0.45 and mem.get("job_id") != job["id"]:
                penalty += 18
                penalty_reasons.append(
                    f"Vector similarity ({mem['similarity']}) to previously REJECTED role '{mem['title']}' ({mem['feedback_reason']})"
                )
            elif mem.get("decision") == "APPROVED" and mem.get("similarity", 0) > 0.40:
                has_related_human_approval = True

        if has_related_human_approval:
            base_score = min(92, base_score + 4)

        match_score = max(15, base_score - penalty)
        top_proj = (
            graph_paths[0]
            if graph_paths
            else {"project": "VRLS 2.0 Cloud-Native Microservices & AI Modernisation", "activated_graph_edges": []}
        )
        edges_str = ", ".join(top_proj.get("activated_graph_edges", [])[:4])

        refined_pitch = self._craft_human_authentic_note(job, top_proj)
        assert not any(bp in refined_pitch.lower() for bp in BANNED_AI_PHRASES), "Anti-Bot check failed"
        assert "**" not in refined_pitch, "Plaintext human note must not contain raw markdown bolding"
        assert_no_emdashes(refined_pitch, context_label="refined_pitch")

        winning_strategy = (
            "Write in plain-text first-person Senior Engineer voice (zero em-dashes, zero markdown stars, "
            "zero AI buzzwords, company-hash rotated opening) citing concrete LTA VRLS 2.0, BlackStraw.AI, and Wolters Kluwer metrics."
        )

        return {
            "match_score": match_score,
            "decision": "RECOMMENDED" if match_score >= PROFILE_OVERLAP_RECOMMENDATION_THRESHOLD else "SKIPPED_LOW_MATCH",
            "tailored_pitch": refined_pitch,
            "winning_strategy": winning_strategy,
            "reasoning_summary": (
                f"Profile graph matched {len(profile_anchors)} distinct skill or domain anchors across {total_hops} graph links ({edges_str}). This score is an evidence-overlap heuristic, not a probability of getting hired. Guardrail Check: PASSED (0 em-dashes, 0 AI clichés, plain-text human prose)."
            ),
        }

    async def evaluate_and_tailor_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        full_job_text = f"{job['title']} {job['company']} {' '.join(job.get('tags', []))} {job.get('description', '')}"

        graph_ctx = self.memory.traverse_knowledge_graph(full_job_text)
        episodic_memories = self.memory.retrieve_similar_episodic_memories(full_job_text, top_k=3)
        result = self._deterministic_reflective_cycle(
            job=job,
            graph_ctx=graph_ctx,
            episodic_memories=episodic_memories,
        )

        self.memory.save_episodic_memory(
            job_id=job["id"],
            title=job["title"],
            company=job["company"],
            url=job["url"],
            decision=result["decision"],
            match_score=result["match_score"],
            critic_score=0,
            tailored_pitch=result["tailored_pitch"],
            feedback_reason=result["reasoning_summary"],
            raw_text=full_job_text,
            source_platform=job.get("source", "Live Multi-Tier Feed"),
            work_location_status=job.get("work_location_status", "NEEDS_REVIEW"),
            work_location_evidence=job.get("work_location_evidence", ""),
        )

        return result
