import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


@dataclass
class OracleAIConfig:
    """
    Configuration for Oracle AI Database 23ai / 26ai (Thin Mode via python-oracledb).
    Automatically falls back to a local SQLite + Vector/Graph emulator if Oracle Cloud
    credentials are not yet provided, keeping local RAM usage under 50 MB.
    """
    user: str = field(default_factory=lambda: os.getenv("ORACLE_USER", ""))
    password: str = field(default_factory=lambda: os.getenv("ORACLE_PASSWORD", ""))
    dsn: str = field(default_factory=lambda: os.getenv("ORACLE_DSN", ""))
    wallet_dir: str = field(default_factory=lambda: os.getenv("ORACLE_WALLET_DIR", ""))
    local_fallback_db: Path = field(default_factory=lambda: BASE_DIR / "oracle_ai_local_mirror.db")

    @property
    def is_cloud_configured(self) -> bool:
        return bool(self.user and self.password and self.dsn)


@dataclass
class AgentSettings:
    profile_path: Path = BASE_DIR / "candidate_profile.json"
    skills_dir: Path = BASE_DIR / ".agent" / "skills"
    report_path: Path = BASE_DIR / "job_matches_report.md"
    max_reflection_iterations: int = 2
    critic_pass_threshold: int = 88
    skill_induction_threshold: int = 90
    poll_interval_minutes: int = 120
    oracle: OracleAIConfig = field(default_factory=OracleAIConfig)


SETTINGS = AgentSettings()
