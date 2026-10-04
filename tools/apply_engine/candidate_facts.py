"""Authoritative candidate facts for ATS question mapping and form fill."""

import json
from pathlib import Path
from typing import Any, Dict

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = WORKSPACE_ROOT / "candidate_profile.json"
FACT_REVIEW_PATH = WORKSPACE_ROOT / "candidate_fact_review.json"


def load_candidate_profile() -> Dict[str, Any]:
    profile_data: Dict[str, Any] = {}
    if PROFILE_PATH.exists():
        try:
            profile_data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        except Exception:
            profile_data = {}

    fact_review: Dict[str, Any] = {}
    if FACT_REVIEW_PATH.exists():
        try:
            fact_review = json.loads(FACT_REVIEW_PATH.read_text(encoding="utf-8"))
        except Exception:
            fact_review = {}

    notice_period_val = "60 days"
    facts = fact_review.get("facts", {})
    if "notice_period" in facts and facts["notice_period"].get("verified"):
        notice_period_val = facts["notice_period"].get("value", "60 days")

    return {
        "first_name": "Meena",
        "last_name": "Kannan",
        "full_name": "Meena Kannan",
        "email": "meenakannan92@gmail.com",
        "phone": "+91 97893 02084",
        "phone_clean": "9789302084",
        "phone_intl": "+919789302084",
        "address": "Chennai, Tamil Nadu, India",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "country": "India",
        "postal_code": "600001",
        "linkedin": "https://www.linkedin.com/in/meena-kannan-mk",
        "github": "https://github.com/meenak95",
        "website": "https://github.com/meenak95",
        "current_company": "NCS Group",
        "current_title": "Lead Software Engineer",
        "years_experience": "9",
        "years_experience_num": 9.5,
        "notice_period": notice_period_val,
        "availability": "60 days (Immediate for B2B consulting / remote onboarding)",
        "salary_inr_month": "3,00,000 - 4,00,000 INR",
        "salary_inr_annual": "40,00,000 - 55,00,000 INR",
        "salary_usd_annual": "$110,000 - $140,000 USD",
        "salary_general": "Negotiable based on role scope and engagement model",
        "work_auth_india": "yes",
        "work_auth_us": "no",
        "sponsorship_us": "yes",
        "b2b_contractor": "yes",
        "remote_preference": "100% Remote (Based in India)",
        "relocate": "no",
        "school": "Anna University",
        "degree": "Bachelor of Engineering (B.E.)",
        "discipline": "Electronics and Communication Engineering",
        "graduation_year": "2015",
        "gender": "Female",
        "pronouns": "She/Her",
        "eeo_race_decline": "Decline to self-identify",
        "eeo_gender_decline": "Decline to self-identify",
        "eeo_veteran_decline": "I am not a protected veteran",
        "eeo_disability_decline": "No, I do not have a disability",
        "skills_expert": [
            "Java", "Java 21", "Java 17", "Spring Boot", "Spring Boot 3",
            "Microservices", "REST APIs", "AWS", "EKS", "Kubernetes",
            "Apache Kafka", "Kafka Streams", "Event-Driven Architecture",
            "PostgreSQL", "Oracle DB", "Redis", "Docker", "Git", "CI/CD",
            "Distributed Systems", "Clean Architecture", "TDD", "JUnit"
        ],
        "skills_advanced": [
            "Spring AI", "RAG Pipelines", "Model Context Protocol (MCP)",
            "Claude API", "Python", "Angular 18", "TypeScript", "Istio",
            "ArgoCD", "Helm", "Terraform", "OpenTelemetry", "Keycloak"
        ],
        "cover_letter_snippet": (
            "I am a Lead Software Engineer with 9+ years building Java 21, Spring Boot 3, "
            "Kubernetes, Kafka, and AWS cloud-native platforms. Most recently architected "
            "microservices for Singapore Land Transport Authority (VRLS 2.0) on AWS EKS, Istio mTLS, "
            "and Kafka Streams, while leading Spring AI, RAG pipelines, and MCP server integrations. "
            "Based in India, strictly targeting 100% remote roles via Global B2B contract or India entity."
        )
    }
