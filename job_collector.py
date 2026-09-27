import asyncio
import html
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List

import httpx

from config import BASE_DIR

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
}

TARGET_KEYWORDS = (
    "java",
    "spring",
    "lead",
    "staff",
    "principal",
    "architect",
    "microservices",
    "kafka",
    "kubernetes",
    "backend",
    "ai",
    "cloud",
    "rag",
    "distributed",
    "platform",
    "solutions",
    "consulting",
    "tech lead",
)

EXTERNAL_DISCOVERED_FILE = BASE_DIR / "discovered_global_jobs.json"


async def fetch_tier1_linkedin_worldwide_and_india_remote(
    client: httpx.AsyncClient, max_items: int = 30
) -> List[Dict[str, Any]]:
    """
    Tier 1: Multi-region LinkedIn Discovery across Worldwide, European Union, Poland/EMEA,
    UK, US, and India so global engineering roles like Appfire Java Tech Lead (#4429510386)
    are never missed due to single-country geo-tags.
    """
    results: List[Dict[str, Any]] = []
    seen_ids = set()
    queries = [
        ("Java%20Tech%20Lead", "Worldwide", "Global B2B / Multi-Hub Entity", ""),
        ("Java%20Tech%20Lead", "Poland", "EMEA / Global B2B & India Entity (e.g. Appfire)", ""),
        ("Java%20Tech%20Lead", "European%20Union", "EU / Global B2B Contract", "&f_WT=2"),
        ("Lead%20Java%20Spring%20Boot%20Microservices", "India", "Full-Time Remote / India EOR", "&f_WT=2"),
        ("Principal%20Java%20Architect%20Cloud%20AWS", "India", "Principal Cloud Architect (India Remote)", "&f_WT=2"),
        ("Staff%20Backend%20Engineer%20Java%20Kafka", "Worldwide", "Global Remote Staff Backend & Kafka", "&f_WT=2"),
        ("Java%20Spring%20Boot%20Contract%20Remote", "Worldwide", "Global USD/EUR B2B Contract", "&f_WT=2"),
        ("Senior%20Java%20Spring%20AI%20RAG%20Kafka", "India", "100% Remote AI & Backend (India)", "&f_WT=2"),
        ("Technical%20Lead%20Java%20Kubernetes%20Microservices", "India", "Technical Lead (India Remote)", "&f_WT=2"),
        ("Solutions%20Architect%20Cloud%20Java%20AWS", "India", "Cloud Solutions Architect (India Remote)", "&f_WT=2"),
    ]
    for keywords, location, contract_label, wt_filter in queries:
        if len(results) >= max_items:
            break
        await asyncio.sleep(random.uniform(0.2, 0.5))
        url = (
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={keywords}&location={location}{wt_filter}&f_TPR=r604800&start=0"
        )
        try:
            resp = await client.get(url, headers=HEADERS)
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
                        if "singapore" in company.lower() or "singapore" in title.lower():
                            continue
                        job_url = link_m.group(1).strip()
                        job_num_m = re.search(r"-(\d{8,12})$", job_url) or re.search(r"/view/(\d{8,12})", job_url)
                        job_num = job_num_m.group(1) if job_num_m else re.sub(r"[^a-zA-Z0-9]+", "_", f"{company}_{title}".lower())[:30]
                        jid = f"li_global_{job_num}"
                        if jid in seen_ids:
                            continue
                        seen_ids.add(jid)
                        results.append(
                            {
                                "id": jid,
                                "source": f"Tier 1: LinkedIn Global & India Discovery ({contract_label})",
                                "title": f"{title} [Global B2B / India Remote Eligible]",
                                "company": f"{company} ({location})",
                                "role_category": "Global B2B / India-Remote Lead Java & Cloud-Native",
                                "url": job_url,
                                "tags": [
                                    "Global B2B / India Entity",
                                    "Java 21",
                                    "Spring Boot 3",
                                    "Kafka",
                                    "Kubernetes",
                                    "AWS",
                                    "Angular 18",
                                ],
                                "description": (
                                    f"Discovered via Multi-Geo Global Search ({contract_label}): "
                                    f"{title} at {company} ({job_url}). Core stack alignment: Java 21, Spring Boot 3, AWS, Angular, Kafka, and AI."
                                ),
                            }
                        )
                        if len(results) >= max_items:
                            return results
        except Exception as exc:
            print(f"  [Connector Note] LinkedIn ({location}): {exc}")
    return results


async def fetch_tier2_greenhouse_multi_hub_global(
    client: httpx.AsyncClient, max_items: int = 25
) -> List[Dict[str, Any]]:
    """
    Tier 2: Direct Global ATS Feeds across 20+ Global Tech Companies.
    Does NOT blindly discard EMEA/Poland/US hub tags if the company operates an India entity
    or hires Global B2B contractors (such as Appfire, Canonical, GitLab, Camunda, Confluent).
    """
    results: List[Dict[str, Any]] = []
    boards = [
        ("appfire", "Appfire (Global B2B & India Entity)"),
        ("canonical", "Canonical (Global Remote / B2B Contractor-Friendly)"),
        ("gitlab", "GitLab (100% All-Remote Global)"),
        ("grafanalabs", "Grafana Labs (100% Remote Global / India)"),
        ("cockroachlabs", "Cockroach Labs (Distributed SQL / Remote)"),
        ("temporaltechnologies", "Temporal Technologies (Distributed Workflows / Remote)"),
        ("camunda", "Camunda (Java Process Orchestration / Remote)"),
        ("redis", "Redis (Real-Time Data Platform / Remote India)"),
        ("kong", "Kong Inc. (Cloud API & AI Gateway / Remote India)"),
        ("postman", "Postman (API Platform / India Remote)"),
        ("harness", "Harness (AI Software Delivery / India)"),
        ("rubrik", "Rubrik (Cloud Data Security / India)"),
        ("mongodb", "MongoDB (Cloud Database / Remote India)"),
        ("confluent", "Confluent (Apache Kafka Platform / Remote India)"),
        ("elastic", "Elastic (Distributed / Remote-First)"),
        ("automattic", "Automattic (100% Global Distributed Remote)"),
        ("wikimedia", "Wikimedia Foundation (Global Remote B2B/Contractor)"),
        ("gp", "G-P / Globalization Partners (Remote-First Global EOR)"),
        ("togetherai", "Together AI (AI Infrastructure & Agent Systems)"),
        ("neuraflash", "NeuraFlash / Accenture (Cloud & AI Architecture)"),
    ]
    for board_slug, company_label in boards:
        if len(results) >= max_items:
            break
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_slug}/jobs?content=true"
        board_added = 0
        try:
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code == 200:
                jobs = resp.json().get("jobs", [])
                # Check if company has an India office/entity anywhere on its board
                has_india_entity = any("india" in str((jb.get("location") or {}).get("name", "")).lower() for jb in jobs)
                for j in jobs:
                    title = str(j.get("title", ""))
                    loc = str((j.get("location") or {}).get("name", ""))
                    combined = f"{title} {loc}".lower()
                    if "singapore" in loc.lower() and "india" not in loc.lower() and "remote" not in loc.lower():
                        continue
                    if any(
                        k in title.lower()
                        for k in ("java", "backend", "software engineer", "tech lead", "lead", "staff", "principal", "ai", "platform", "architect", "distributed", "cloud", "kafka")
                    ) and (
                        has_india_entity
                        or any(
                            loc_k in combined
                            for loc_k in ("india", "remote", "anywhere", "global", "distributed", "apac", "home based", "worldwide", "poland", "bulgaria", "emea")
                        )
                    ):
                        raw_html = html.unescape(str(j.get("content", "")))
                        clean_desc = " ".join(re.sub(r"<[^>]+>", " ", raw_html).split())[:600]
                        results.append(
                            {
                                "id": f"gh_rem_{board_slug}_{j.get('id')}",
                                "source": "Tier 2: Direct Global & Multi-Hub ATS (Greenhouse)",
                                "title": f"{title} ({loc} - Global B2B / India Entity Eligible)",
                                "company": f"{company_label}",
                                "role_category": "Global B2B / India Entity Cloud & AI Engineering",
                                "url": f"https://job-boards.greenhouse.io/{board_slug}/jobs/{j.get('id')}",
                                "tags": ["Global B2B / India Entity", "Java 21", "Spring Boot", "AWS", "Kubernetes", "AI"],
                                "description": clean_desc or f"{title} at {company_label} ({loc}).",
                            }
                        )
                        board_added += 1
                        if board_added >= 2 or len(results) >= max_items:
                            break
        except Exception as exc:
            print(f"  [Connector Note] Greenhouse ({board_slug}): {exc}")
    return results


async def fetch_tier3_global_b2b_remote_boards(
    client: httpx.AsyncClient, max_items: int = 20
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if EXTERNAL_DISCOVERED_FILE.exists():
        try:
            ext_jobs = json.loads(EXTERNAL_DISCOVERED_FILE.read_text(encoding="utf-8"))
            for ej in ext_jobs:
                if isinstance(ej, dict) and ej.get("id") and ej.get("title"):
                    results.append(ej)
        except Exception:
            pass
    return results[:max_items]


async def collect_candidate_jobs(limit: int = 60) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=9.0, follow_redirects=True) as client:
        t1, t2, t3 = await asyncio.gather(
            fetch_tier1_linkedin_worldwide_and_india_remote(client, max_items=25),
            fetch_tier2_greenhouse_multi_hub_global(client, max_items=25),
            fetch_tier3_global_b2b_remote_boards(client, max_items=20),
        )

    all_jobs: List[Dict[str, Any]] = []
    for batch in (t3, t2, t1):
        all_jobs.extend(batch)

    return all_jobs[:limit]
