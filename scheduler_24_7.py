import argparse
import asyncio
import tracemalloc
from datetime import datetime, timezone
from typing import Any, Dict, List

from config import SETTINGS
from application_preparation import prepare_approved_materials, preparation_schedule_error
from agent_run_ledger import AgentRunLedger, RunAlreadyActive
from guardrails import assert_no_emdashes, sanitize_no_emdashes
from job_collector import collect_candidate_jobs_detailed
from oracle_memory import OracleAIMemoryManager
from reflective_agent import ReflectiveJobAgent


def generate_markdown_report(
    memory: OracleAIMemoryManager,
    evaluated_jobs: List[Dict[str, Any]],
    peak_ram_mb: float,
) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    rules = memory.get_active_rules()

    lines = [
        "# Global Remote Job Search Report",
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

    lines.extend(["", "---", "", "## 2. Newly Evaluated Roles (Deterministic Match Heuristic)", ""])

    for item in evaluated_jobs:
        job = item["job"]
        res = item["result"]
        badge = "RECOMMENDED" if res["decision"] == "RECOMMENDED" else "FILTERED OUT (Dealbreaker / Low Match)"
        source_label = job.get("source", "Live Platform Connector")
        lines.extend(
            [
                f"### [{badge}] {job['title']} - *{job['company']}*",
                f"- **Platform Source**: `{source_label}` | **Apply / View Link**: [{job['url']}]({job['url']})",
                f"- **Profile Evidence Score**: **{res['match_score']}/100**",
                f"- **Graph & Episodic Reasoning**: {res['reasoning_summary']}",
                "- **Scoring Method**: Deterministic graph and prior human feedback heuristic, not an LLM critic.",
            ]
        )
        if res.get("induced_skill_path"):
            lines.append(f"- **Induced Reusable Skill**: [`{res['induced_skill_path']}`](file:///{res['induced_skill_path'].replace(chr(92), '/')})")
        if res["decision"] == "RECOMMENDED":
            lines.extend(
                [
                    "",
                    "#### Draft Application Pitch",
                    "```text",
                    res["tailored_pitch"],
                    "```",
                ]
            )
        lines.append("")

    final_report = sanitize_no_emdashes("\n".join(lines))
    assert_no_emdashes(final_report, context_label="job_matches_report.md")
    return final_report


async def run_discovery_cycle(force_rescore: bool = False) -> str:
    ledger = AgentRunLedger()
    run_id = ledger.start_run("job_discovery", "Discovery run accepted")
    tracemalloc.start()
    run_finished = False
    stats: Dict[str, Any] = {
        "force_rescore": force_rescore,
        "collected_jobs": 0,
        "evaluated_jobs": 0,
        "skipped_seen_jobs": 0,
        "recommended_jobs": 0,
        "report_updated": False,
    }

    try:
        ledger.record_event(
            run_id,
            "phase_started",
            "collecting",
            "Fetching current listings from configured public sources.",
        )
        memory = OracleAIMemoryManager()
        agent = ReflectiveJobAgent(memory=memory)
        print(f"[AdaptiveJobAgent] Storage Mode: {memory.backend_mode}")

        collection = await collect_candidate_jobs_detailed(limit=200)
        jobs = collection["jobs"]
        sources = collection["sources"]
        stats["collected_jobs"] = len(jobs)
        stats["source_outcomes"] = sources
        for source in sources:
            source_status = str(source.get("status", "unknown"))
            ledger.record_event(
                run_id,
                "source_finished",
                "collecting",
                f"{source.get('source', 'Unknown source')}: {source.get('eligible_count', 0)} eligible listings.",
                status="warning" if source_status == "warning" else "info",
                details=source,
            )

        ledger.record_event(
            run_id,
            "phase_started",
            "evaluating",
            f"Evaluating {len(jobs)} global-eligible listings against profile evidence.",
            details={"collected_jobs": len(jobs), "force_rescore": force_rescore},
        )
        evaluated: List[Dict[str, Any]] = []
        skipped_seen = 0
        for index, job in enumerate(jobs, start=1):
            if not force_rescore and memory.is_job_seen(job["id"]):
                skipped_seen += 1
                print(f"  [Skip] Already in Episodic Memory: {job['id']} ({job['title']})")
                continue
            res = await agent.evaluate_and_tailor_job(job)
            evaluated.append({"job": job, "result": res})
            print(
                f"  [{res['decision']}] {job['title']} @ {job['company']} "
                f"| Profile evidence={res['match_score']}/100"
            )
            if index % 10 == 0:
                ledger.record_event(
                    run_id,
                    "progress",
                    "evaluating",
                    f"Reviewed {index} of {len(jobs)} listings.",
                    details={"processed": index, "total": len(jobs)},
                )

        _, peak_bytes = tracemalloc.get_traced_memory()
        peak_mb = peak_bytes / (1024 * 1024)
        recommended = sum(
            1 for item in evaluated if item["result"].get("decision") == "RECOMMENDED"
        )
        stats.update(
            {
                "evaluated_jobs": len(evaluated),
                "skipped_seen_jobs": skipped_seen,
                "recommended_jobs": recommended,
                "peak_python_memory_mb": round(peak_mb, 2),
            }
        )

        if evaluated:
            ledger.record_event(
                run_id,
                "phase_started",
                "reporting",
                "Writing the report for newly evaluated listings.",
                details={"report_path": SETTINGS.report_path.name},
            )
            report_md = generate_markdown_report(memory, evaluated, peak_mb)
            SETTINGS.report_path.write_text(report_md, encoding="utf-8")
            stats["report_updated"] = True
            print(f"\n[Report Updated] {SETTINGS.report_path} (Peak Python allocation: {peak_mb:.2f} MB)")

        warning_sources = sum(1 for source in sources if source.get("status") == "warning")
        run_status = "PARTIAL" if warning_sources else "SUCCEEDED"
        summary = (
            f"Discovery completed: {len(jobs)} eligible listings, {len(evaluated)} newly evaluated, "
            f"{recommended} recommended."
        )
        ledger.finish_run(
            run_id,
            run_status,
            summary,
            stats=stats,
        )
        run_finished = True
        print(f"[AgentRun {run_status}] {run_id}: {summary}")
        return run_id
    except asyncio.CancelledError:
        if not run_finished:
            ledger.finish_run(
                run_id,
                "CANCELLED",
                "Discovery was cancelled before it completed.",
                stats=stats,
            )
            run_finished = True
        raise
    except Exception as exc:
        if not run_finished:
            ledger.finish_run(
                run_id,
                "FAILED",
                "Discovery failed. Review the recorded phase and retry after correcting the cause.",
                error_type=type(exc).__name__,
                stats=stats,
            )
            run_finished = True
        print(f"[AgentRun FAILED] {run_id}: {type(exc).__name__}")
        raise
    finally:
        tracemalloc.stop()


async def run_daemon(interval_minutes: int) -> None:
    print(f"[24/7 Scheduler] Starting continuous adaptive loop (every {interval_minutes} mins)...")
    consecutive_failures = 0
    while True:
        try:
            await run_discovery_cycle(force_rescore=False)
            consecutive_failures = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            consecutive_failures += 1
            retry_delay = min(
                interval_minutes * 60,
                60 * (2 ** min(consecutive_failures - 1, 4)),
            )
            print(
                f"[24/7 Scheduler] Run failed with {type(exc).__name__}; "
                f"retrying in {retry_delay} seconds."
            )
            await asyncio.sleep(retry_delay)
            continue
        await asyncio.sleep(interval_minutes * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive & Memory-Aware 24/7 Job Search Agent")
    parser.add_argument("--once", action="store_true", help="Run a single discovery & reflection cycle")
    parser.add_argument("--force", action="store_true", help="Re-evaluate jobs even if already in episodic memory")
    parser.add_argument("--daemon", action="store_true", help="Run continuously 24/7 on an interval")
    parser.add_argument(
        "--recover-stale-run",
        metavar="RUN_ID",
        help="After inspecting its process, mark the exact stale run ID as abandoned",
    )
    parser.add_argument(
        "--prepare-approved-materials",
        action="store_true",
        help="Explicitly prepare packets for approved roles during this run; never submits applications",
    )
    parser.add_argument("--interval-minutes", type=int, default=SETTINGS.poll_interval_minutes)
    parser.add_argument(
        "--feedback",
        nargs=3,
        metavar=("JOB_ID", "DECISION", "REASON"),
        help="Consolidate user feedback (APPROVED or REJECTED) into Oracle AI Memory Rules",
    )
    args = parser.parse_args()

    mode_error = preparation_schedule_error(args.daemon, args.prepare_approved_materials)
    if mode_error:
        parser.error(mode_error)
    if args.interval_minutes < 1:
        parser.error("--interval-minutes must be at least 1")
    if args.recover_stale_run and (args.daemon or args.prepare_approved_materials or args.feedback):
        parser.error("--recover-stale-run cannot be combined with daemon, preparation, or feedback mode")

    if args.feedback:
        job_id, decision, reason = args.feedback
        memory = OracleAIMemoryManager()
        rule = memory.consolidate_user_feedback(job_id, decision, reason, source="explicit_cli")
        print(f"[Memory Consolidation] Wrote new long-term rule: {rule}")
        return

    if args.recover_stale_run:
        ledger = AgentRunLedger()
        ledger.recover_stale_run(args.recover_stale_run)
        print(f"[AgentRun Recovery] Recorded operator recovery for {args.recover_stale_run}")
        return

    if args.prepare_approved_materials:
        prep_result = prepare_approved_materials(True, min_auto_score=75)
        print(f"[Application Prep: {prep_result['status']}] {prep_result['summary']}")
        for action in prep_result["next_actions"]:
            print(f"  [Next] {action}")
        for artifact in prep_result["artifacts"]:
            print(f"  [Artifact] {artifact}")
        if prep_result["status"] in {"blocked", "error"}:
            raise SystemExit(2)
        return

    if args.daemon:
        asyncio.run(run_daemon(args.interval_minutes))
    else:
        asyncio.run(run_discovery_cycle(force_rescore=args.force))


if __name__ == "__main__":
    main()
