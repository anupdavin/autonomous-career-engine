import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from config import SETTINGS


class SkillInductionPipeline:
    """
    Implements Behavioral Adaptation from DeepLearning.AI + Oracle's
    'Building Adaptive AI Agents' course:
      - Monitors agent execution traces (Generator -> Critic -> Refiner).
      - When a trace achieves a Critic Score >= threshold (or human approval),
        distills the winning pattern into a reusable Induced Skill stored in:
          1. The database (`induced_skills` table) for programmatic agent injection.
          2. `.agent/skills/<skill_name>/SKILL.md` so Antigravity natively discovers it!
    """

    def __init__(self, db_conn: sqlite3.Connection) -> None:
        self.conn = db_conn
        self._init_table()

    def _init_table(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS induced_skills (
                skill_slug TEXT PRIMARY KEY,
                role_category TEXT,
                trigger_pattern TEXT,
                winning_strategy TEXT,
                sample_pitch TEXT,
                critic_score INTEGER,
                usage_count INTEGER DEFAULT 1,
                created_at TEXT
            )
            """
        )
        self.conn.commit()

    def retrieve_applicable_skills(self, job_title: str, job_tags: List[str]) -> List[Dict[str, str]]:
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT skill_slug, role_category, winning_strategy, critic_score FROM induced_skills ORDER BY critic_score DESC LIMIT 5"
        ).fetchall()
        combined = f"{job_title} {' '.join(job_tags)}".lower()
        matched = []
        for r in rows:
            cat_words = [w for w in r["role_category"].lower().split() if len(w) > 2]
            if any(w in combined for w in cat_words) or len(matched) < 2:
                matched.append(
                    {
                        "skill_slug": r["skill_slug"],
                        "role_category": r["role_category"],
                        "winning_strategy": r["winning_strategy"],
                        "critic_score": r["critic_score"],
                    }
                )
        return matched

    def induce_skill_from_trace(
        self,
        role_category: str,
        job_title: str,
        winning_strategy: str,
        tailored_pitch: str,
        critic_score: int,
    ) -> Path:
        """
        Converts a high-scoring reflection trace into a persistent Skill in both
        the database and `.agent/skills/<slug>/SKILL.md`.
        """
        slug = re.sub(r"[^a-z0-9]+", "-", f"tailor-{role_category.lower()}").strip("-")
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """
            INSERT INTO induced_skills
            (skill_slug, role_category, trigger_pattern, winning_strategy, sample_pitch, critic_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(skill_slug) DO UPDATE SET
                winning_strategy = CASE WHEN excluded.critic_score >= induced_skills.critic_score THEN excluded.winning_strategy ELSE induced_skills.winning_strategy END,
                sample_pitch = CASE WHEN excluded.critic_score >= induced_skills.critic_score THEN excluded.sample_pitch ELSE induced_skills.sample_pitch END,
                critic_score = MAX(induced_skills.critic_score, excluded.critic_score),
                usage_count = induced_skills.usage_count + 1
            """,
            (
                slug,
                role_category,
                f"When tailoring applications for {role_category} / {job_title}",
                winning_strategy,
                tailored_pitch,
                critic_score,
                now,
            ),
        )
        self.conn.commit()

        skill_folder = SETTINGS.skills_dir / slug
        skill_folder.mkdir(parents=True, exist_ok=True)
        skill_md_path = skill_folder / "SKILL.md"

        skill_md_content = f"""---
name: {slug}
description: Auto-induced behavioral skill for scoring and tailoring {role_category} job applications (Critic Verified Score: {critic_score}/100).
---

# Induced Skill: {role_category} Application Strategy

> Automatically induced from successful execution trace on **{now}** (Critic Score: **{critic_score}/100**).

## When to Activate
Activate this skill whenever evaluating or tailoring resumes/outreach for **{role_category}** or similar roles (e.g., *{job_title}*).

## Winning Behavioral Strategy
{winning_strategy}

## Reference High-Scoring Application Pitch
```markdown
{tailored_pitch}
```
"""
        skill_md_path.write_text(skill_md_content, encoding="utf-8")
        return skill_md_path
