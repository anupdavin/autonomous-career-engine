import asyncio
import html
import random
import re
from typing import Any, Dict, List

import httpx

from eligibility import global_remote_evidence
from job_sources import GREENHOUSE_BOARDS, LEVER_BOARDS
from lever_postings import parse_lever_posting


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
}

async def fetch_tier1_linkedin_worldwide_and_india_remote(
    client: httpx.AsyncClient,
    max_items: int = 30,
    source_outcomes: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """
    Tier 1: Discover LinkedIn leads, then retain only postings whose own metadata
    explicitly supports remote work from India.
    """
    results: List[Dict[str, Any]] = []
    seen_ids = set()
    outcome = {
        "source": "LinkedIn public job search",
        "status": "ok",
        "request_count": 0,
        "eligible_count": 0,
        "error_count": 0,
    }
    queries = [
        ("Java%20Tech%20Lead", "Worldwide", ""),
        ("Enterprise%20Solutions%20Architect", "Worldwide", "&f_WT=2"),
        ("B2B%20Cloud%20Consultant", "Worldwide", "&f_WT=2"),
        ("Staff%20Backend%20Engineer%20Java%20Kafka", "Worldwide", "&f_WT=2"),
        ("Java%20Spring%20Boot%20Contract%20Remote", "Worldwide", "&f_WT=2"),
        ("Pre-Sales%20AI%20Architect", "Worldwide", "&f_WT=2"),
        ("Strategic%20Alliances%20Director", "Worldwide", "&f_WT=2"),
        ("Solutions%20Architect%20Cloud%20Java%20AWS", "Worldwide", "&f_WT=2"),
    ]
    for keywords, location, wt_filter in queries:
        if len(results) >= max_items:
            break
        await asyncio.sleep(random.uniform(0.2, 0.5))
        url = (
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={keywords}&location={location}{wt_filter}&f_TPR=r604800&start=0"
        )
        try:
            outcome["request_count"] += 1
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code != 200:
                outcome["error_count"] += 1
                continue
            if resp.status_code == 200 and "<li" in resp.text:
                cards = resp.text.split("<li")
                for card in cards[1:]:
                    title_m = re.search(r'class="base-search-card__title"[^>]*>([^<]+)<', card)
                    comp_m = re.search(r'class="hidden-nested-link"[^>]*>([^<]+)<', card) or re.search(
                        r'class="base-search-card__subtitle"[^>]*>\s*([^<\n]+)', card
                    )
                    link_m = re.search(r'href="(https://[^"?]+linkedin\.com/jobs/view/[^"?]+)', card)
                    if title_m and link_m:
                        title = html.unescape(title_m.group(1).strip())
                        company = html.unescape(comp_m.group(1).strip()) if comp_m else "Global Remote Partner"
                        job_url = link_m.group(1).strip()
                        location_m = re.search(
                            r'class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</(?:span|div)>',
                            card,
                            flags=re.IGNORECASE | re.DOTALL,
                        )
                        job_location = (
                            html.unescape(re.sub(r"<[^>]+>", " ", location_m.group(1))).strip()
                            if location_m
                            else ""
                        )
                        eligibility_evidence = global_remote_evidence(
                            job_location,
                            f"{title}. {job_location}",
                        )
                        if not eligibility_evidence:
                            continue
                        job_num_m = re.search(r"-(\d{8,12})$", job_url) or re.search(r"/view/(\d{8,12})", job_url)
                        job_num = job_num_m.group(1) if job_num_m else re.sub(r"[^a-zA-Z0-9]+", "_", f"{company}_{title}".lower())[:30]
                        jid = f"li_global_{job_num}"
                        if jid in seen_ids:
                            continue
                        seen_ids.add(jid)
                        results.append(
                            {
                                "id": jid,
                                "source": "Tier 1: LinkedIn Public Job Search",
                                "title": title,
                                "company": company,
                                "location": job_location,
                                "work_location_status": "VERIFIED",
                                "work_location_evidence": eligibility_evidence,
                                "role_category": "Lead Java and Cloud-Native Engineering",
                                "url": job_url,
                                "tags": [],
                                "description": (
                                    f"LinkedIn listing title: {title}. Listing location: {job_location}. Source URL: {job_url}."
                                ),
                            }
                        )
                        if len(results) >= max_items:
                            break
            if len(results) >= max_items:
                break
        except Exception as exc:
            outcome["error_count"] += 1
            print(f"  [Connector Note] LinkedIn ({location}): {exc}")
    outcome["eligible_count"] = len(results)
    if outcome["error_count"]:
        outcome["status"] = "warning"
    if source_outcomes is not None:
        source_outcomes.append(outcome)
    return results


async def fetch_tier2_greenhouse_multi_hub_global(
    client: httpx.AsyncClient,
    max_items: int = 80,
    source_outcomes: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """
    Tier 2: Direct Greenhouse ATS feeds. A company office in India does not establish
    that a specific role can be worked from India, so each listing needs direct evidence.
    """
    results: List[Dict[str, Any]] = []
    for board_slug, company_label in GREENHOUSE_BOARDS:
        if len(results) >= max_items:
            break
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_slug}/jobs?content=true"
        board_added = 0
        outcome = {
            "source": f"Greenhouse: {board_slug}",
            "status": "ok",
            "request_count": 1,
            "eligible_count": 0,
            "error_count": 0,
        }
        try:
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code == 200:
                jobs = resp.json().get("jobs", [])
                for j in jobs:
                    title = str(j.get("title", ""))
                    loc = str((j.get("location") or {}).get("name", ""))
                    combined = f"{title} {loc}".lower()
                    raw_html = html.unescape(str(j.get("content", "")))
                    clean_desc = " ".join(re.sub(r"<[^>]+>", " ", raw_html).split())[:6000]
                    eligibility_evidence = global_remote_evidence(loc, clean_desc)
                    if not eligibility_evidence:
                        continue
                    if any(
                        k in title.lower()
                        for k in ("java", "backend", "software engineer", "tech lead", "lead", "staff", "principal", "ai", "platform", "architect", "distributed", "cloud", "kafka", "sre", "devops", "infrastructure", "data engineer", "ml engineer", "python")
                    ):
                        results.append(
                            {
                                "id": f"gh_rem_{board_slug}_{j.get('id')}",
                                "source": "Tier 2: Direct Global & Multi-Hub ATS (Greenhouse)",
                                "title": title,
                                "company": company_label,
                                "location": loc,
                                "work_location_status": "VERIFIED",
                                "work_location_evidence": eligibility_evidence,
                                "role_category": "Global Remote/B2B",
                                "url": f"https://job-boards.greenhouse.io/{board_slug}/jobs/{j.get('id')}",
                                "tags": [],
                                "description": clean_desc,
                            }
                        )
                        board_added += 1
                        if board_added >= 5 or len(results) >= max_items:
                            break
            else:
                outcome["error_count"] += 1
        except Exception as exc:
            outcome["error_count"] += 1
            print(f"  [Connector Note] Greenhouse ({board_slug}): {exc}")
        outcome["eligible_count"] = board_added
        if outcome["error_count"]:
            outcome["status"] = "warning"
        if source_outcomes is not None:
            source_outcomes.append(outcome)
    return results


async def fetch_tier3_lever_remote(
    client: httpx.AsyncClient,
    max_items: int = 20,
    source_outcomes: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Fetch published Lever listings through its public read-only postings feed."""
    results: List[Dict[str, Any]] = []
    for site_slug, company_label in LEVER_BOARDS:
        if len(results) >= max_items:
            break
        url = f"https://api.lever.co/v0/postings/{site_slug}?mode=json&limit=100"
        outcome = {
            "source": f"Lever: {site_slug}",
            "status": "ok",
            "request_count": 1,
            "eligible_count": 0,
            "error_count": 0,
        }
        try:
            response = await client.get(url, headers=HEADERS)
            if response.status_code != 200:
                outcome["error_count"] += 1
            else:
                postings = response.json()
                if not isinstance(postings, list):
                    outcome["error_count"] += 1
                else:
                    for posting in postings:
                        if not isinstance(posting, dict):
                            continue
                        job = parse_lever_posting(posting, site_slug, company_label)
                        if job is None:
                            continue
                        results.append(job)
                        outcome["eligible_count"] += 1
                        if len(results) >= max_items:
                            break
        except Exception as exc:
            outcome["error_count"] += 1
            print(f"  [Connector Note] Lever ({site_slug}): {type(exc).__name__}")
        if outcome["error_count"]:
            outcome["status"] = "warning"
        if source_outcomes is not None:
            source_outcomes.append(outcome)
    return results


async def fetch_tier4_global_b2b_remote_boards(
    client: httpx.AsyncClient,
    max_items: int = 20,
    source_outcomes: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    # The legacy JSON feed has no trustworthy listing-level location evidence.
    # Keep it out of the application pipeline until each entry is checked against a live posting.
    if source_outcomes is not None:
        source_outcomes.append(
            {
                "source": "Legacy global feed",
                "status": "disabled",
                "request_count": 0,
                "eligible_count": 0,
                "error_count": 0,
            }
        )
    return []


async def collect_candidate_jobs_detailed(limit: int = 200) -> Dict[str, Any]:
    linkedin_outcomes: List[Dict[str, Any]] = []
    greenhouse_outcomes: List[Dict[str, Any]] = []
    lever_outcomes: List[Dict[str, Any]] = []
    legacy_outcomes: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        t1, t2, t3, t4 = await asyncio.gather(
            fetch_tier1_linkedin_worldwide_and_india_remote(
                client, max_items=25, source_outcomes=linkedin_outcomes
            ),
            fetch_tier2_greenhouse_multi_hub_global(
                client, max_items=80, source_outcomes=greenhouse_outcomes
            ),
            fetch_tier3_lever_remote(
                client, max_items=40, source_outcomes=lever_outcomes
            ),
            fetch_tier4_global_b2b_remote_boards(
                client, max_items=20, source_outcomes=legacy_outcomes
            ),
        )

    all_jobs: List[Dict[str, Any]] = []
    for batch in (t4, t3, t2, t1):
        for job in batch:
            evidence = global_remote_evidence(job.get("location", ""), job.get("description", ""))
            if not evidence:
                continue
            job["work_location_status"] = "VERIFIED"
            job["work_location_evidence"] = evidence
            all_jobs.append(job)

    return {
        "jobs": all_jobs[:limit],
        "sources": linkedin_outcomes + greenhouse_outcomes + lever_outcomes + legacy_outcomes,
    }


async def collect_candidate_jobs(limit: int = 60) -> List[Dict[str, Any]]:
    """Return eligible listings while preserving the existing collector interface."""
    result = await collect_candidate_jobs_detailed(limit=limit)
    return result["jobs"]


