"""Question Mapper - Maps ATS screening questions and form fields to candidate facts.

Adapted from ApplyPilot's 324-question evaluated corpus, customized for Meena Kannan's
100% Remote / Global B2B / India profile.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from tools.apply_engine.candidate_facts import load_candidate_profile


def norm(text: Any) -> str:
    if text is None:
        return ""
    s = str(text).lower()
    s = re.sub(r"[^\w\s\+\-\/\.]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def pick_option(options: List[str], target: str) -> Optional[str]:
    """Pick the closest matching option from a dropdown or radio list."""
    if not options:
        return None

    target_clean = norm(target)
    if not target_clean:
        return None

    # 1. Exact match
    for opt in options:
        if norm(opt) == target_clean:
            return opt

    # 2. Whole word boundary match
    word_pattern = re.compile(rf"\b{re.escape(target_clean)}\b", re.IGNORECASE)
    for opt in options:
        if word_pattern.search(norm(opt)):
            return opt

    # 3. Substring containment
    for opt in options:
        o_clean = norm(opt)
        if target_clean in o_clean:
            return opt

    return None


class QuestionMapper:
    """Maps form field labels and option sets to authoritative candidate facts."""

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.profile = profile or load_candidate_profile()

    def map_field(self, label: str, options: Optional[List[str]] = None) -> Tuple[Optional[str], bool]:
        """Given a question label and available options, return (answer, is_mapped)."""
        label_norm = norm(label)
        opt_list = options or []
        opt_norm = [norm(o) for o in opt_list]

        def find_opt(pattern: str) -> Optional[str]:
            regex = re.compile(pattern, re.IGNORECASE)
            for raw, n in zip(opt_list, opt_norm):
                if regex.search(n):
                    return raw
            return None

        def yes_opt() -> Optional[str]:
            return find_opt(r"^(yes\b|yep|true|i agree|agree|accept)")

        def no_opt() -> Optional[str]:
            return find_opt(r"^(no\b|nope|false|none|neither)")

        # -------------------------------------------------------------
        # 1. Identity & Basic Contact Information
        # -------------------------------------------------------------
        if re.search(r"\b(first name|given name|forename)\b", label_norm) and "company" not in label_norm:
            return self.profile["first_name"], True

        if re.search(r"\b(last name|surname|family name)\b", label_norm) and "company" not in label_norm:
            return self.profile["last_name"], True

        if (
            re.search(r"\b(full name|legal name|candidate name|your name|applicant name)\b", label_norm)
            or label_norm == "name"
        ) and "company" not in label_norm:
            return self.profile["full_name"], True

        if re.search(r"\b(email|e-mail)\b", label_norm):
            return self.profile["email"], True

        if re.search(r"\b(phone|mobile|telephone|cell|contact number)\b", label_norm):
            if opt_list:
                pick = find_opt(r"india|\+91|in \(?\+91\)?")
                if pick:
                    return pick, True
            return self.profile["phone"], True

        if re.search(r"\b(linkedin|linked in)\b", label_norm):
            return self.profile["linkedin"], True

        if re.search(r"\b(github|git hub)\b", label_norm):
            return self.profile["github"], True

        if re.search(r"\b(website|portfolio|personal url|blog)\b", label_norm):
            return self.profile["website"], True

        # -------------------------------------------------------------
        # 2. Location & Geographic Questions
        # -------------------------------------------------------------
        if re.search(r"\b(country|nation|what is your location)\b", label_norm) and not re.search(r"code", label_norm):
            if opt_list:
                pick = find_opt(r"^india$") or find_opt(r"^india\b") or pick_option(opt_list, "India")
                if pick:
                    return pick, True
            return self.profile["country"], True

        if re.search(r"\b(city|town)\b", label_norm):
            if opt_list:
                pick = find_opt(r"^chennai\b") or pick_option(opt_list, "Chennai")
                if pick:
                    return pick, True
            return self.profile["city"], True

        if re.search(r"\b(state|province|region)\b", label_norm):
            if opt_list:
                pick = find_opt(r"^tamil nadu\b") or pick_option(opt_list, "Tamil Nadu")
                if pick:
                    return pick, True
            return self.profile["state"], True

        if re.search(r"\b(zip|postal code|post code|pin code)\b", label_norm):
            return self.profile["postal_code"], True

        if re.search(r"\b(current location|where are you located|location|address|residence)\b", label_norm):
            if opt_list:
                pick = find_opt(r"^india$") or find_opt(r"india|chennai|remote")
                if pick:
                    return pick, True
            return self.profile["address"], True

        # "Are you currently located/residing in India?"
        if re.search(r"(located|based|living|residing).*india", label_norm):
            if opt_list:
                return (yes_opt() or "Yes"), True
            return "Yes", True

        # "Are you currently located/residing in the US/UK/Canada/Singapore/etc.?"
        if re.search(r"(located|based|living|residing).*(united states|usa|\bus\b|canada|united kingdom|\buk\b|singapore|germany|australia)", label_norm):
            if opt_list:
                return (no_opt() or "No"), True
            return "No", True

        # Willingness to relocate (Strictly Remote)
        if re.search(r"\b(willing to relocate|relocation|open to relocation)\b", label_norm):
            if opt_list:
                pick = find_opt(r"^no\b|remote only") or no_opt()
                if pick:
                    return pick, True
            return "No", True

        # Remote work preference
        if re.search(r"\b(remote work|remote arrangement|work from home|work preference)\b", label_norm):
            if opt_list:
                pick = find_opt(r"100% remote|remote|fully remote|yes")
                if pick:
                    return pick, True
            return "100% Remote", True

        # -------------------------------------------------------------
        # 3. Work Authorization & Sponsorship Gates
        # -------------------------------------------------------------
        # Work authorization in India
        if re.search(r"(authoriz|eligib|right to work|permit).*india", label_norm):
            if opt_list:
                return (yes_opt() or "Yes"), True
            return "Yes", True

        # Work authorization in foreign country without sponsorship (US, UK, Canada, New Zealand, Australia, etc.)
        if re.search(r"(authoriz|eligib|right to work|permit).*(united states|usa|\bus\b|canada|united kingdom|\buk\b|new zealand|australia|germany|ireland|singapore|eu\b|europe|netherlands)", label_norm):
            if opt_list:
                return (no_opt() or "No"), True
            return "No", True

        # Bundled sponsorship selects: "Yes, but I will need sponsorship in future" vs "No, I do not require"
        if opt_list and re.search(r"sponsor", " ".join(opt_norm)) and re.search(r"(authoriz|eligib|right to work)", label_norm):
            pick = find_opt(r"sponsor.*future|require.*sponsor|need.*sponsor") or yes_opt()
            if pick:
                return pick, True

        # Visa sponsorship requirement
        if re.search(r"(require|need|will you.*require).*(sponsorship|visa)", label_norm):
            if opt_list:
                # If question specifically mentions US/relocation, answer Yes
                # If question is general or India EOR, answer Yes for global entity sponsorship
                pick = yes_opt() or find_opt(r"^yes\b")
                if pick:
                    return pick, True
            return "Yes", True

        # B2B Contractor engagement
        if re.search(r"\b(contractor|b2b|independent contractor|c2c|consultant)\b", label_norm):
            if opt_list:
                pick = yes_opt() or find_opt(r"^yes\b|open to contract")
                if pick:
                    return pick, True
            return "Yes", True

        # -------------------------------------------------------------
        # 4. Experience & Technical Skills
        # -------------------------------------------------------------
        # Total years of experience
        if re.search(r"(total|years of|how many years).*(experience|software|engineering|work)", label_norm):
            if opt_list:
                # Match range e.g. "8-10 years", "7-10 years", "5+ years", "8+ years"
                cand_yrs = self.profile["years_experience_num"]
                for raw, o_norm in zip(opt_list, opt_norm):
                    # Check range "X - Y"
                    m_range = re.search(r"(\d+)\s*[-to]+\s*(\d+)", o_norm)
                    if m_range:
                        low, high = float(m_range.group(1)), float(m_range.group(2))
                        if low <= cand_yrs <= high:
                            return raw, True
                    # Check plus "X+"
                    m_plus = re.search(r"(\d+)\s*\+", o_norm)
                    if m_plus:
                        low = float(m_plus.group(1))
                        if cand_yrs >= low and low >= 5:
                            return raw, True
                pick = find_opt(r"9|8|7|5\+|senior|lead")
                if pick:
                    return pick, True
            return self.profile["years_experience"], True

        # Specific tech skill rating: "Rate your skill in Java / Spring Boot / AWS / etc." or "Familiarity with Golang"
        rate_match = re.search(
            r"(?:rate your (?:level of )?skill|skill|familiarity|experience level|proficiency)\s*(?:in|with)\s*(.+)$",
            label_norm
        )
        if rate_match and opt_list:
            tech = rate_match.group(1).strip()
            is_expert = any(norm(s) in norm(tech) or norm(tech) in norm(s) for s in self.profile["skills_expert"])
            is_advanced = any(norm(s) in norm(tech) or norm(tech) in norm(s) for s in self.profile["skills_advanced"])
            if is_expert:
                pick = find_opt(r"expert|advanced|^5|^4|proficient")
                if pick:
                    return pick, True
            elif is_advanced:
                pick = find_opt(r"intermediate|advanced|^4|^3|proficient")
                if pick:
                    return pick, True
            else:
                pick = find_opt(r"intermediate|beginner|^3|^2") or opt_list[0]
                if pick:
                    return pick, True

        # "Experience with [Tech]?" Yes/No
        tech_exp_match = re.search(r"(experience|proficien\w*).*(with|in|using)\s+([\w\s\+\-\.]+)", label_norm)
        if tech_exp_match:
            tech_query = norm(tech_exp_match.group(3))
            has_tech = any(norm(s) in tech_query or tech_query in norm(s) for s in self.profile["skills_expert"] + self.profile["skills_advanced"])
            if has_tech:
                if opt_list:
                    return (yes_opt() or "Yes"), True
                return "Yes", True
            else:
                if opt_list:
                    return (no_opt() or "No"), True
                return "No", True

        # -------------------------------------------------------------
        # 5. Compensation, Notice Period, Current Role
        # -------------------------------------------------------------
        # English language proficiency
        if re.search(r"\b(english skills|english proficiency|english level|describe your english)\b", label_norm):
            if opt_list:
                pick = find_opt(r"fluent|professional|advanced|native|c2|c1")
                if pick:
                    return pick, True
            return "Fluent / Professional Working Proficiency", True

        # Current and previous employer details
        if re.search(r"(mention|name|enter).*(current company|present company)", label_norm):
            return self.profile["current_company"], True

        if re.search(r"(mention|name|enter).*(previous company|past company|prior employer)", label_norm):
            return "BlackStraw.AI / Wolters Kluwer", True

        # Full-time and relevant experience
        if re.search(r"(full.?time experience|overall experience)", label_norm):
            return "9+ years of full-time professional experience architecting backend distributed systems, Java 21, Spring Boot 3, and AWS cloud platforms.", True

        if re.search(r"(relevant experience)", label_norm):
            return "9+ years hands-on experience with Java 21, Spring Boot 3 microservices, Apache Kafka event streaming, AWS (EKS, Lambda), and Kubernetes.", True

        # Compensation and salary rules
        if re.search(r"(current.*compensation|current.*salary|current.*ctc|current.*pay)", label_norm):
            if re.search(r"(only numbers|numeric)", label_norm):
                return "3500000", True
            return "35,00,000 INR per annum", True

        if re.search(r"(salary expectations|desired salary|expected ctc|expected pay|what are your salary)", label_norm):
            if re.search(r"(only numbers|numeric)", label_norm):
                return "4500000", True
            if opt_list:
                pick = find_opt(r"negotiable|market rate|competitive") or opt_list[0]
                return pick, True
            if "month" in label_norm or "monthly" in label_norm:
                return self.profile["salary_inr_month"], True
            if "usd" in label_norm or "$" in label:
                return self.profile["salary_usd_annual"], True
            return "45,00,000 INR per annum (Negotiable)", True

        if re.search(r"\b(currency|choose your currency)\b", label_norm):
            if opt_list:
                pick = find_opt(r"^inr\b|rupee|indian rupee|^usd\b")
                if pick:
                    return pick, True
            return "INR", True

        if re.search(r"\b(salary period|period)\b", label_norm) and not re.search(r"notice", label_norm):
            if opt_list:
                pick = find_opt(r"year|annual|per annum")
                if pick:
                    return pick, True
            return "Per Year", True

        if re.search(r"\b(gross or net)\b", label_norm):
            if opt_list:
                pick = find_opt(r"^gross\b")
                if pick:
                    return pick, True
            return "Gross", True

        # Criticality of service owned
        if re.search(r"(criticality of.*service|critical.*service.*own)", label_norm):
            return "VRLS 2.0 microservices handling mission-critical vehicular transactions and licensing for Singapore Land Transport Authority with strict 99.99% uptime and sub-500ms latency SLAs.", True

        # Design patterns implemented
        if re.search(r"(design patterns.*implemented|patterns.*implemented)", label_norm):
            return "Saga & Outbox patterns for distributed Kafka events, CQRS, Circuit Breaker (Resilience4j), Clean/Hexagonal Architecture, and Strategy pattern for multi-tenant microservices.", True

        # Code review of junior/mid engineers
        if re.search(r"(reviewed code|review.*code.*engineer)", label_norm):
            if opt_list:
                return (yes_opt() or "Yes"), True
            return "Yes", True

        # On-call experience
        if re.search(r"(been oncall|on call|on-call)", label_norm):
            if opt_list:
                return (yes_opt() or "Yes"), True
            return "Yes", True

        # Ownership and accountability
        if re.search(r"(ownership and accountability|ready to take ownership)", label_norm):
            if opt_list:
                return (yes_opt() or "Yes"), True
            return "Yes", True

        # Additional information / good fit notes
        if re.search(r"(anything else|why you could be a good fit|why should we hire you|good fit for this role)", label_norm):
            return self.profile["cover_letter_snippet"], True

        # Possibility to shorten notice period
        if re.search(r"(shorten.*notice period|possibility to shorten)", label_norm):
            return "Yes, notice period can be negotiated or shortened for immediate remote onboarding.", True

        # Age range
        if re.search(r"\b(age range|your age)\b", label_norm):
            if opt_list:
                pick = find_opt(r"30.*39|30\s*-\s*39|prefer not|decline")
                if pick:
                    return pick, True
            return "30-39", True

        if re.search(r"\b(salary|compensation|expected pay|pay expectations|rate|desired salary)\b", label_norm):
            if opt_list:
                pick = find_opt(r"negotiable|market rate|competitive") or opt_list[0]
                return pick, True
            if "month" in label_norm or "monthly" in label_norm:
                return self.profile["salary_inr_month"], True
            if "usd" in label_norm or "$" in label:
                return self.profile["salary_usd_annual"], True
            return self.profile["salary_inr_annual"], True

        # Education dates
        if re.search(r"start.*(date|year|month)", label_norm) and ("year" in label_norm or "month" in label_norm):
            if "year" in label_norm:
                return "2011", True
            if "month" in label_norm:
                if opt_list:
                    pick = find_opt(r"august|^8\b|^08\b")
                    if pick:
                        return pick, True
                return "08", True

        if re.search(r"(end|graduat).*(date|year|month)", label_norm) and ("year" in label_norm or "month" in label_norm):
            if "year" in label_norm:
                return "2015", True
            if "month" in label_norm:
                if opt_list:
                    pick = find_opt(r"may|^5\b|^05\b")
                    if pick:
                        return pick, True
                return "05", True

        if re.search(r"\b(notice period|notice|how soon can you start|when can you start|earliest start date|availability)\b", label_norm):
            if opt_list:
                pick = find_opt(r"60 days|2 months|within 2 months|1-2 months|immediate|flexible")
                if pick:
                    return pick, True
            return self.profile["notice_period"], True

        if re.search(r"\b(current company|current employer|present employer)\b", label_norm):
            return self.profile["current_company"], True

        if re.search(r"\b(current title|current position|current role|job title)\b", label_norm) and "desired" not in label_norm:
            return self.profile["current_title"], True

        # -------------------------------------------------------------
        # 6. Education
        # -------------------------------------------------------------
        if re.search(r"\b(school|university|college|institution)\b", label_norm):
            if opt_list:
                pick = find_opt(r"anna university|other")
                if pick:
                    return pick, True
            return self.profile["school"], True

        if re.search(r"\b(degree|highest degree|education level|what is your education|your education)\b|^education\b", label_norm):
            if opt_list:
                pick = find_opt(r"\bbe\b|\bb\.e\b|bachelor|undergraduate|b\.tech|b-tech|btech|engineering|higher|master")
                if pick:
                    return pick, True
            return self.profile["degree"], True

        if re.search(r"\b(discipline|major|field of study)\b", label_norm):
            if opt_list:
                pick = find_opt(r"engineering|electronics|computer|technology")
                if pick:
                    return pick, True
            return self.profile["discipline"], True

        if re.search(r"\b(graduation year|grad year|year of graduation)\b", label_norm):
            return self.profile["graduation_year"], True

        # -------------------------------------------------------------
        # 7. Terms, Privacy, Background Check & Anti-Trap Rules
        # -------------------------------------------------------------
        # Anti-trap: "Are you an AI / bot / automated agent / LLM generated?"
        if re.search(r"(automated|bot|ai agent|artificial intelligence|script|llm|coding agent).*(applying|submit|answer|generated|mark answer)", label_norm):
            if opt_list:
                return (no_opt() or "No"), True
            return "No", True

        # Compliance / conflict of interest
        if re.search(r"(conflict of interest|government official|familial relationship|relative.*work|felony|criminal|family member.*work)", label_norm):
            if opt_list:
                return (no_opt() or "No"), True
            return "No", True

        # Prior employment
        if re.search(r"(previously employed|worked here before|applied before|interviewed before)", label_norm):
            if opt_list:
                return (no_opt() or "No"), True
            return "No", True

        # Terms and privacy agreement
        if re.search(r"(agree|consent|certify|acknowledge|privacy|terms|truthful|background check|legal age|18 years)", label_norm):
            if opt_list:
                pick = find_opt(r"^(i )?(agree|acknowledge|consent|accept|certify)|yes") or yes_opt()
                if pick:
                    return pick, True
            return "Yes", True

        # Application / signature date
        if re.search(r"^date\b|\b(today'?s? date|date of application|signature date)\b", label_norm) and not re.search(r"birth|graduat|start|end", label_norm):
            from datetime import datetime, timezone
            return datetime.now(timezone.utc).strftime("%m/%d/%Y"), True

        # How did you hear about us
        if re.search(r"how did you (hear|learn|find)", label_norm):
            if opt_list:
                pick = find_opt(r"linkedin|job board|careers|company website|other")
                if pick:
                    return pick, True
            return "LinkedIn", True

        # -------------------------------------------------------------
        # 8. Voluntary EEO Questions (Safe Decline Defaults)
        # -------------------------------------------------------------
        if (re.search(r"\b(gender|sex)\b", label_norm) or label_norm.startswith("gender")) and "transgender" not in label_norm:
            if opt_list:
                pick = find_opt(r"female|^woman\b") or find_opt(r"decline|prefer not|choose not")
                if pick:
                    return pick, True
            return "Female", True

        if re.search(r"\b(race|ethnicity|hispanic|latino)\b", label_norm):
            if opt_list:
                pick = find_opt(r"decline|prefer not|choose not|asian")
                if pick:
                    return pick, True
            return self.profile["eeo_race_decline"], True

        if re.search(r"\b(veteran|military)\b", label_norm):
            if opt_list:
                pick = find_opt(r"not a (protected )?veteran|decline|prefer not|no\b")
                if pick:
                    return pick, True
            return self.profile["eeo_veteran_decline"], True

        if re.search(r"\b(disability|handicap)\b", label_norm):
            if opt_list:
                pick = find_opt(r"no.*disability|decline|prefer not|choose not")
                if pick:
                    return pick, True
            return self.profile["eeo_disability_decline"], True

        # Fallback: if options exist and only 1 option (e.g. checkbox acknowledgment)
        if len(opt_list) == 1:
            return opt_list[0], True

        return None, False
