import argparse
import asyncio
import tracemalloc
from datetime import datetime, timezone
from typing import Any, Dict, List

from config import SETTINGS
from guardrails import assert_no_emdashes, sanitize_no_emdashes
from job_collector import collect_candidate_jobs
from oracle_memory import OracleAIMemoryManager
from reflective_agent import ReflectiveJobAgent
from skill_induction import SkillInductionPipeline


def generate_markdown_report(
    memory: OracleAIMemoryManager,
    evaluated_jobs: List[Dict[str, Any]],
    peak_ram_mb: float,
) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    rules = memory.get_active_rules()

    lines = [
        "# Adaptive & Self-Improving 24/7 Job Search Dashboard",
        "",
        f"- **Last Execution**: `{now_str}`",
        f"- **Memory & Graph Engine**: `{memory.backend_mode}`",
        f"- **Peak Process Memory Overhead**: **`{peak_ram_mb:.2f} MB RAM`** *(Leaves ~8.5 GB free RAM untouched)*",
        "",
        "---",
        "",
        "## 1. Consolidated Long-Term Memory Rules (Oracle AI Memory Manager)",
    ]
    for r in rules:
        lines.append(f"- `{r}`")

    lines.extend(["", "---", "", "## 2. Evaluated Job Opportunities (Generator -> Critic -> Refiner Loop)", ""])

    for item in evaluated_jobs:
        job = item["job"]
        res = item["result"]
        badge = "RECOMMENDED" if res["decision"] == "RECOMMENDED" else "FILTERED OUT (Dealbreaker / Low Match)"
        source_label = job.get("source", "Live Platform Connector")
        lines.extend(
            [
                f"### [{badge}] {job['title']} - *{job['company']}*",
                f"- **Platform Source**: `{source_label}` | **Apply / View Link**: [{job['url']}]({job['url']})",
                f"- **Match Score**: **{res['match_score']}/100** | **Critic Reflection Score**: `{res['initial_critic_score']}` -> **`{res['final_critic_score']}/100`** ({res['reflection_iterations']} iterations)",
                f"- **Graph & Episodic Reasoning**: {res['reasoning_summary']}",
                f"- **Critic Self-Correction Trace**: *{res['critic_feedback']}*",
            ]
        )
        if res.get("induced_skill_path"):
            lines.append(f"- **Induced Reusable Skill**: [`{res['induced_skill_path']}`](file:///{res['induced_skill_path'].replace(chr(92), '/')})")
        if res["decision"] == "RECOMMENDED":
            lines.extend(
                [
                    "",
                    "#### Tailored Application Pitch (Post-Reflection)",
                    "```text",
                    res["tailored_pitch"],
                    "```",
                ]
            )
        lines.append("")

    final_report = sanitize_no_emdashes("\n".join(lines))
    assert_no_emdashes(final_report, context_label="job_matches_report.md")
    return final_report


async def run_discovery_cycle(force_rescore: bool = False) -> None:
    tracemalloc.start()
    memory = OracleAIMemoryManager()
    skills = SkillInductionPipeline(memory.local_conn)
    agent = ReflectiveJobAgent(memory=memory, skill_pipeline=skills)

    print(f"[AdaptiveJobAgent] Storage Mode: {memory.backend_mode}")
    jobs = await collect_candidate_jobs(limit=45)
    evaluated: List[Dict[str, Any]] = []

    for job in jobs:
        if not force_rescore and memory.is_job_seen(job["id"]):
            print(f"  [Skip] Already in Episodic Memory: {job['id']} ({job['title']})")
            continue
        res = await agent.evaluate_and_tailor_job(job)
        evaluated.append({"job": job, "result": res})
        print(
            f"  [{res['decision']}] {job['title']} @ {job['company']} "
            f"| Match={res['match_score']}/100 | Critic={res['initial_critic_score']}->{res['final_critic_score']}"
        )
        if res.get("induced_skill_path"):
            print(f"    -> [Behavioral Adaptation] Induced Skill saved: {res['induced_skill_path']}")

    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_bytes / (1024 * 1024)

    # Run Autonomous Autopilot: Auto-approve >=90 matches & render real ATS-safe PDFs + packets
    from auto_applicator import run_autonomous_autopilot
    autopilot_kits = run_autonomous_autopilot(min_auto_score=90)
    print(f"[Autopilot] {len(autopilot_kits)} high-conviction roles auto-approved with ready PDF resumes.")

    if evaluated:
        report_md = generate_markdown_report(memory, evaluated, peak_mb)
        SETTINGS.report_path.write_text(report_md, encoding="utf-8")
        print(f"\n[Report Updated] {SETTINGS.report_path} (Peak Python allocation: {peak_mb:.2f} MB)")


async def run_daemon(interval_minutes: int) -> None:
    print(f"[24/7 Scheduler] Starting continuous adaptive loop (every {interval_minutes} mins)...")
    while True:
        await run_discovery_cycle(force_rescore=False)
        await asyncio.sleep(interval_minutes * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive & Memory-Aware 24/7 Job Search Agent")
    parser.add_argument("--once", action="store_true", help="Run a single discovery & reflection cycle")
    parser.add_argument("--force", action="store_true", help="Re-evaluate jobs even if already in episodic memory")
    parser.add_argument("--daemon", action="store_true", help="Run continuously 24/7 on an interval")
    parser.add_argument("--interval-minutes", type=int, default=SETTINGS.poll_interval_minutes)
    parser.add_argument(
        "--feedback",
        nargs=3,
        metavar=("JOB_ID", "DECISION", "REASON"),
        help="Consolidate user feedback (APPROVED or REJECTED) into Oracle AI Memory Rules",
    )
    args = parser.parse_args()

    if args.feedback:
        job_id, decision, reason = args.feedback
        memory = OracleAIMemoryManager()
        rule = memory.consolidate_user_feedback(job_id, decision, reason)
        print(f"[Memory Consolidation] Wrote new long-term rule: {rule}")
        return

    if args.daemon:
        asyncio.run(run_daemon(args.interval_minutes))
    else:
        asyncio.run(run_discovery_cycle(force_rescore=args.force))


if __name__ == "__main__":
    main()
