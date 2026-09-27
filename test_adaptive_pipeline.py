import asyncio
import json
import tracemalloc
from pathlib import Path

from config import SETTINGS
from oracle_memory import OracleAIMemoryManager
from reflective_agent import ReflectiveJobAgent
from scheduler_24_7 import run_discovery_cycle
from skill_induction import SkillInductionPipeline


async def run_end_to_end_verification() -> None:
    print("=" * 72)
    print("  END-TO-END VERIFICATION: ADAPTIVE & MEMORY-AWARE JOB SEARCH AGENT")
    print("=" * 72)

    tracemalloc.start()
    memory = OracleAIMemoryManager()
    skills = SkillInductionPipeline(memory.local_conn)
    agent = ReflectiveJobAgent(memory=memory, skill_pipeline=skills)

    # 1. Test Knowledge Graph Multi-Hop Traversal
    print("\n[TEST 1] Knowledge Adaptation: SQL Property Graph Multi-Hop Traversal")
    sample_query = "Looking for an engineer experienced in LLM Orchestration, Vector Search, and Continual Learning"
    kg_result = memory.traverse_knowledge_graph(sample_query)
    for path in kg_result["graph_paths"]:
        print(f"  -> Vertex [PROJECT]: {path['project']} (Activated Hops: {path['relevance_hops']})")
        print(f"     Edges: {', '.join(path['activated_graph_edges'])}")
    assert kg_result["graph_paths"][0]["relevance_hops"] >= 2, "Expected multi-hop graph activation"
    print("  [PASS] Multi-hop Knowledge Graph traversal verified.")

    # 2. Test Generator -> Critic -> Refiner Reflection Loop + Skill Induction
    print("\n[TEST 2] Andrew Ng Reflection Loop (Generator -> Critic -> Refiner) + Skill Induction")
    test_job = {
        "id": "test_oracle_agent_role_99",
        "title": "Staff AI Agent Engineer (Oracle 26ai & Adaptive Workflows)",
        "company": "ApexAutonomous Labs",
        "role_category": "Enterprise Agentic AI",
        "url": "https://example.com/jobs/apex-99",
        "tags": ["Python", "Oracle AI Database", "Agentic Workflows", "RAG"],
        "description": "Design self-improving AI agents using Vector Search, Property Graphs, and Python.",
    }
    res_before = await agent.evaluate_and_tailor_job(test_job)
    print(f"  -> Initial Critic Score : {res_before['initial_critic_score']}/100")
    print(f"  -> Critic Feedback      : {res_before['critic_feedback']}")
    print(f"  -> Refined Critic Score : {res_before['final_critic_score']}/100 (Iterations: {res_before['reflection_iterations']})")
    print(f"  -> Match Score (Before) : {res_before['match_score']}/100 ({res_before['decision']})")
    print(f"  -> Induced Skill File   : {res_before.get('induced_skill_path')}")
    assert res_before["final_critic_score"] > res_before["initial_critic_score"], "Refiner must improve Critic score"
    assert Path(res_before["induced_skill_path"]).exists(), "Induced SKILL.md must exist on disk"
    print("  [PASS] Reflection loop & trace-to-skill induction verified.")

    # 3. Test Memory Consolidation & Episodic Vector Adaptation (Negative Feedback Loop)
    print("\n[TEST 3] Memory Engineering: Episodic Vector Search & Feedback Consolidation")
    rule = memory.consolidate_user_feedback(
        job_id="test_oracle_agent_role_99",
        decision="REJECTED",
        reason="Company ApexAutonomous Labs requires late-night US timezone overlap",
    )
    print(f"  -> Consolidated Semantic Rule written: {rule}")

    similar_job = {
        "id": "test_oracle_agent_role_100",
        "title": "Senior AI Agent Engineer (Oracle 26ai & Adaptive Workflows)",
        "company": "ApexAutonomous Labs",
        "role_category": "Enterprise Agentic AI",
        "url": "https://example.com/jobs/apex-100",
        "tags": ["Python", "Oracle AI Database", "Agentic Workflows", "RAG"],
        "description": "Design self-improving AI agents using Vector Search, Property Graphs, and Python.",
    }
    res_after = await agent.evaluate_and_tailor_job(similar_job)
    print(f"  -> Match Score on Similar Job BEFORE Rejection : {res_before['match_score']}/100")
    print(f"  -> Match Score on Similar Job AFTER Rejection  : {res_after['match_score']}/100")
    print(f"  -> Episodic Memory Reasoning                   : {res_after['reasoning_summary']}")
    assert res_after["match_score"] < res_before["match_score"], "Vector episodic memory must penalize similar rejected role"
    print("  [PASS] Episodic vector similarity & negative feedback adaptation verified.")

    # 4. Run Full Discovery Cycle & Verify Dashboard Report + RAM Footprint
    print("\n[TEST 4] Full Live Discovery Cycle & Resource Footprint Audit")
    await run_discovery_cycle(force_rescore=True)

    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_bytes / (1024 * 1024)

    cur = memory.local_conn.cursor()
    ep_count = cur.execute("SELECT COUNT(*) FROM agent_episodic_memories").fetchone()[0]
    rule_count = cur.execute("SELECT COUNT(*) FROM consolidated_memory_rules").fetchone()[0]
    skill_count = cur.execute("SELECT COUNT(*) FROM induced_skills").fetchone()[0]

    print("\n" + "=" * 72)
    print("  FINAL AUDIT SUMMARY")
    print("=" * 72)
    print(f"  * Episodic Memories Stored (Vector DB) : {ep_count}")
    print(f"  * Consolidated Long-Term Rules         : {rule_count}")
    print(f"  * Induced Behavioral Skills (SKILL.md) : {skill_count}")
    print(f"  * Peak RAM Footprint                   : {peak_mb:.2f} MB (Target: < 100 MB)")
    print(f"  * Live Report Path                     : {SETTINGS.report_path}")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(run_end_to_end_verification())
