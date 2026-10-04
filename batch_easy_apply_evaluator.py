import os
import sys
import json
import time
from playwright.sync_api import sync_playwright

WORKSPACE = r"C:\Users\MeenaDavin\Desktop\Project 1"
SCREENSHOT_DIR = os.path.join(WORKSPACE, "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

RESUME_PATH = os.path.join(
    WORKSPACE,
    "resumes_vault",
    "2026-09-27_B2B_Cloud_Fintech_v1.1_b2b_java_ka",
    "Meena_Kannan_Principal_Java_Cloud_Architect.pdf"
)

PROFILE = {
    "name": "Meena Kannan",
    "first_name": "Meena",
    "last_name": "Kannan",
    "email": "meenakannan92@gmail.com",
    "phone": "+91 97893 02084",
    "phone_digits": "9789302084",
    "country_code": "+91",
    "current_company": "NCS (Client: Land Transport Authority)",
    "current_title": "Lead Software Engineer",
    "linkedin": "https://www.linkedin.com/in/meena-kannan-mk",
    "github": "https://github.com/meenak95",
    "location": "India",
    "city": "Chennai",
    "state": "Tamil Nadu",
    "country": "India",
    "years_experience": "9",
    "notice_period": "30 days"
}

TARGET_JOBS = [
    {
        "id": "ashby_oscilar_java_01",
        "company": "Oscilar",
        "title": "Sr./Staff Backend Engineer - Java (Remote - India)",
        "platform": "Ashby",
        "url": "https://jobs.ashbyhq.com/oscilar/110eabbc-5e6f-4e21-8fed-28b67f9683d4/aba9b33a-d68a-4933-b4e6-d98342416801/application",
        "alt_url": "https://jobs.ashbyhq.com/oscilar/fa4d5eac-a03f-4996-9419-4b3c997b6f87/application"
    },
    {
        "id": "ashby_signoz_platform_02",
        "company": "SigNoz",
        "title": "Staff Backend Engineer - Platform (Remote - India / Worldwide)",
        "platform": "Ashby",
        "url": "https://jobs.ashbyhq.com/signoz/5ba2b181-0b62-49d9-b092-8e539ee1a7c7/application",
        "alt_url": "https://jobs.ashbyhq.com/signoz/e8c0ae83-391b-4c68-be61-ca32392d223f/application"
    },
    {
        "id": "ashby_junipersquare_tech_lead_03",
        "company": "Juniper Square",
        "title": "Senior Technical Lead (Remote - India)",
        "platform": "Ashby",
        "url": "https://jobs.ashbyhq.com/junipersquare/b4a12519-61f1-4770-b77e-289524a87a15/application",
        "alt_url": "https://jobs.ashbyhq.com/junipersquare/d73010b4-3a52-4752-b8ec-f187a550d53c/application"
    },
    {
        "id": "lever_highlevel_app_eng_04",
        "company": "HighLevel",
        "title": "Application Engineer (Java/Python Integrations - Remote India)",
        "platform": "Lever",
        "url": "https://jobs.lever.co/gohighlevel/92965a0b-946a-4b31-ab79-4582582cee60/apply",
        "alt_url": "https://jobs.lever.co/gohighlevel/39718784-e43b-43b6-9fee-5a33975e7640/apply"
    },
    {
        "id": "recruitee_gravity9_lead_java_05",
        "company": "gravity9",
        "title": "Lead Java Developer / Architect (Remote B2B)",
        "platform": "Recruitee",
        "url": "https://gravity9.recruitee.com/o/lead-java-developerarchitect/apply",
        "alt_url": "https://gravity9.recruitee.com/o/senior-java-developer/apply"
    },
    {
        "id": "breezy_zinier_sde2_06",
        "company": "Zinier",
        "title": "SDE 2 - Java/JEE Backend & Full Stack Development (Remote India)",
        "platform": "BreezyHR",
        "url": "https://zinier.breezy.hr/p/0623606e4214-sde-2-java-jee-backend-full-stack-development/apply",
        "alt_url": None
    },
    {
        "id": "workable_euronet_tech_lead_07",
        "company": "Euronet Worldwide",
        "title": "Technical Lead - Java / Backend (Remote India)",
        "platform": "Workable",
        "url": "https://apply.workable.com/euronet-worldwide-inc/j/7E24F754E2/apply/",
        "alt_url": None
    }
]

def _required_value_is_present(element):
    return element.evaluate("""element => {
        if (element.disabled) return true;

        const type = (element.type || "").toLowerCase();
        if (type === "checkbox") return element.checked;
        if (type === "radio") {
            const group = element.form?.elements.namedItem(element.name);
            if (group instanceof RadioNodeList) {
                return Array.from(group).some(option => option.checked);
            }
            return element.checked;
        }
        if (element.tagName === "SELECT") {
            if (element.selectedIndex < 0) return false;
            const value = (element.value || "").trim();
            const label = (element.options[element.selectedIndex]?.text || "").trim();
            return Boolean(value) && !/^(select|choose|please select)\\b/i.test(label);
        }
        if (type === "file") return Boolean(element.files?.length);
        return String(element.value || "").trim().length > 0;
    }""")


def _required_field_label(element):
    return element.evaluate("""element => {
        const labels = Array.from(element.labels || [])
            .map(label => label.innerText.trim())
            .filter(Boolean);
        const fieldsetLabel = element.closest("fieldset")
            ?.querySelector("legend")?.innerText?.trim();
        return labels.join(" / ")
            || element.getAttribute("aria-label")
            || fieldsetLabel
            || element.getAttribute("name")
            || element.getAttribute("id")
            || element.getAttribute("placeholder")
            || "unnamed required field";
    }""")


def _missing_required_fields(page, selector):
    missing = []
    for element in page.query_selector_all(selector):
        if not _required_value_is_present(element):
            label = _required_field_label(element)
            if label not in missing:
                missing.append(label)
    return missing


def _mark_ready_for_manual_review(page, result):
    result["status"] = "READY_FOR_USER_REVIEW"
    result["details"] = (
        "Known profile fields were prefilled where possible. Review every answer, "
        "location requirement, and employer attestation, then submit manually. "
        "This evaluator does not submit applications."
    )
    screenshot_path = os.path.join(
        SCREENSHOT_DIR,
        f"{result['company']}_ready_for_review.png",
    )
    page.screenshot(path=screenshot_path)
    result["screenshot"] = screenshot_path


def evaluate_and_prepare(page, job):
    res = {
        "job_id": job["id"],
        "company": job["company"],
        "title": job["title"],
        "platform": job["platform"],
        "url": job["url"],
        "status": "INITIALIZING",
        "blockers": [],
        "screenshot": None,
        "details": ""
    }
    
    print(f"\n--- Processing {job['company']}: {job['title']} ---")
    url_to_try = job["url"]
    
    try:
        response = page.goto(url_to_try, wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"Direct URL failed ({e}), checking alt_url if available...")
        if job.get("alt_url"):
            url_to_try = job["alt_url"]
            try:
                response = page.goto(url_to_try, wait_until="networkidle", timeout=30000)
            except Exception as e2:
                res["status"] = "URL_INACCESSIBLE"
                res["details"] = f"Failed both primary and alternate URLs: {e2}"
                return res
        else:
            res["status"] = "URL_INACCESSIBLE"
            res["details"] = str(e)
            return res
            
    page_text = page.inner_text("body").lower()
    if "no longer available" in page_text or "page not found" in page_text or "404" in page.title().lower():
        if job.get("alt_url") and url_to_try != job["alt_url"]:
            print(f"Primary URL closed, attempting alt_url {job['alt_url']}...")
            try:
                page.goto(job["alt_url"], wait_until="networkidle", timeout=30000)
                page_text = page.inner_text("body").lower()
            except Exception:
                pass
                
        if "no longer available" in page_text or "page not found" in page_text:
            res["status"] = "ROLE_CLOSED"
            res["details"] = "Posting is no longer open or accepts no more applicants."
            return res

    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{job['company']}_form.png")
    page.screenshot(path=screenshot_path)
    res["screenshot"] = screenshot_path
    
    # Platform-specific form filling
    if job["platform"] == "Ashby":
        fill_ashby(page, res)
    elif job["platform"] == "Lever":
        fill_lever(page, res)
    elif job["platform"] == "Recruitee":
        fill_recruitee(page, res)
    elif job["platform"] == "BreezyHR":
        fill_breezy(page, res)
    elif job["platform"] == "Workable":
        fill_workable(page, res)
    else:
        res["status"] = "PLATFORM_NOT_SUPPORTED"

    return res

def fill_ashby(page, res):
    print("Evaluating Ashby form structure...")
    time.sleep(2)
    
    # 1. Resume upload
    file_inputs = page.query_selector_all('input[type="file"]')
    if file_inputs:
        try:
            file_inputs[0].set_input_files(RESUME_PATH)
            print("Uploaded resume PDF.")
            time.sleep(2)
        except Exception as e:
            print(f"Resume upload note: {e}")

    # 2. Basic fields
    # Name
    name_el = page.query_selector('input[name="_systemfield_name"], input[autocomplete="name"], input[id*="name"]')
    if name_el and not name_el.input_value():
        name_el.fill(PROFILE["name"])
        print("Filled Name.")

    # Email
    email_el = page.query_selector('input[name="_systemfield_email"], input[type="email"], input[autocomplete="email"]')
    if email_el and not email_el.input_value():
        email_el.fill(PROFILE["email"])
        print("Filled Email.")

    # Phone
    phone_el = page.query_selector('input[name="_systemfield_phone"], input[type="tel"]')
    if phone_el and not phone_el.input_value():
        phone_el.fill(PROFILE["phone"])
        print("Filled Phone.")

    # LinkedIn
    linkedin_el = page.query_selector('input[name*="linkedin" i], input[placeholder*="linkedin" i], input[id*="linkedin" i]')
    if linkedin_el and not linkedin_el.input_value():
        linkedin_el.fill(PROFILE["linkedin"])
        print("Filled LinkedIn.")

    # GitHub
    github_el = page.query_selector('input[name*="github" i], input[placeholder*="github" i], input[id*="github" i]')
    if github_el and not github_el.input_value():
        github_el.fill(PROFILE["github"])
        print("Filled GitHub.")

    unanswered_required = _missing_required_fields(
        page,
        'input[aria-required="true"], select[aria-required="true"], '
        'textarea[aria-required="true"], [required]',
    )

    if unanswered_required:
        res["status"] = "BLOCKED_REQUIRES_USER_INPUT"
        res["blockers"] = unanswered_required
        res["details"] = f"Form has {len(unanswered_required)} unanswered required fields."
        ss = os.path.join(SCREENSHOT_DIR, f"{res['company']}_blocked.png")
        page.screenshot(path=ss)
        res["screenshot"] = ss
        print(f"BLOCKED: Unanswered required fields: {unanswered_required}")
    else:
        _mark_ready_for_manual_review(page, res)

def fill_lever(page, res):
    print("Evaluating Lever form structure...")
    time.sleep(2)
    
    # Resume upload
    file_inputs = page.query_selector_all('input[type="file"]')
    if file_inputs:
        try:
            file_inputs[0].set_input_files(RESUME_PATH)
            print("Uploaded resume to Lever.")
            time.sleep(2)
        except Exception as e:
            print(f"Resume note: {e}")

    # Name
    name_el = page.query_selector('input[name="name"]')
    if name_el and not name_el.input_value():
        name_el.fill(PROFILE["name"])
        print("Filled Name.")

    # Email
    email_el = page.query_selector('input[name="email"]')
    if email_el and not email_el.input_value():
        email_el.fill(PROFILE["email"])
        print("Filled Email.")

    # Phone
    phone_el = page.query_selector('input[name="phone"]')
    if phone_el and not phone_el.input_value():
        phone_el.fill(PROFILE["phone"])
        print("Filled Phone.")

    # Current company
    org_el = page.query_selector('input[name="org"]')
    if org_el and not org_el.input_value():
        org_el.fill(PROFILE["current_company"])
        print("Filled Current Company.")

    # URLs
    li_el = page.query_selector('input[name="urls[LinkedIn]"]')
    if li_el and not li_el.input_value():
        li_el.fill(PROFILE["linkedin"])
        print("Filled LinkedIn.")

    gh_el = page.query_selector('input[name="urls[GitHub]"], input[name="urls[Portfolio]"], input[name="urls[Other]"]')
    if gh_el and not gh_el.input_value():
        gh_el.fill(PROFILE["github"])
        print("Filled GitHub.")

    # Check for empty required fields
    unanswered = _missing_required_fields(
        page,
        'input[required], textarea[required], select[required], '
        'input[aria-required="true"], textarea[aria-required="true"], '
        'select[aria-required="true"]',
    )

    if unanswered:
        res["status"] = "BLOCKED_REQUIRES_USER_INPUT"
        res["blockers"] = unanswered
        res["details"] = f"Lever form requires answers for: {', '.join(unanswered)}"
        blocked_ss = os.path.join(SCREENSHOT_DIR, f"{res['company']}_blocked.png")
        page.screenshot(path=blocked_ss)
        res["screenshot"] = blocked_ss
    else:
        _mark_ready_for_manual_review(page, res)

def fill_recruitee(page, res):
    print("Evaluating Recruitee form structure...")
    time.sleep(2)
    # Check if form exists
    form = page.query_selector("form")
    if not form:
        res["status"] = "FORM_NOT_FOUND"
        return
        
    # File upload
    file_inputs = page.query_selector_all('input[type="file"]')
    if file_inputs:
        try:
            file_inputs[0].set_input_files(RESUME_PATH)
            time.sleep(2)
        except Exception:
            pass

    # Basic inputs
    name_el = page.query_selector('input[name*="name" i]')
    if name_el and not name_el.input_value():
        name_el.fill(PROFILE["name"])
        
    email_el = page.query_selector('input[type="email"]')
    if email_el and not email_el.input_value():
        email_el.fill(PROFILE["email"])
        
    phone_el = page.query_selector('input[type="tel"]')
    if phone_el and not phone_el.input_value():
        phone_el.fill(PROFILE["phone"])

    # Required check
    unanswered = _missing_required_fields(page, '[required], [aria-required="true"]')
    if unanswered:
        res["status"] = "BLOCKED_REQUIRES_USER_INPUT"
        res["blockers"] = unanswered
        ss = os.path.join(SCREENSHOT_DIR, f"{res['company']}_blocked.png")
        page.screenshot(path=ss)
        res["screenshot"] = ss
    else:
        _mark_ready_for_manual_review(page, res)

def fill_breezy(page, res):
    print("Evaluating BreezyHR form structure...")
    time.sleep(2)
    name_el = page.query_selector('input[id="name"]')
    if name_el and not name_el.input_value():
        name_el.fill(PROFILE["name"])
        
    email_el = page.query_selector('input[id="email"]')
    if email_el and not email_el.input_value():
        email_el.fill(PROFILE["email"])
        
    phone_el = page.query_selector('input[id="phone"]')
    if phone_el and not phone_el.input_value():
        phone_el.fill(PROFILE["phone"])

    file_inputs = page.query_selector_all('input[type="file"]')
    if file_inputs:
        try:
            file_inputs[0].set_input_files(RESUME_PATH)
            time.sleep(2)
        except Exception:
            pass
            
    unanswered = _missing_required_fields(page, '[required], [aria-required="true"]')
    if unanswered:
        res["status"] = "BLOCKED_REQUIRES_USER_INPUT"
        res["blockers"] = unanswered
        ss = os.path.join(SCREENSHOT_DIR, f"{res['company']}_blocked.png")
        page.screenshot(path=ss)
        res["screenshot"] = ss
    else:
        _mark_ready_for_manual_review(page, res)

def fill_workable(page, res):
    print("Evaluating Workable form structure...")
    time.sleep(2)
    # Check if page loaded
    name_el = page.query_selector('input[name="firstname"], input[name="name"]')
    if name_el and not name_el.input_value():
        name_el.fill(PROFILE["first_name"])
        
    lname_el = page.query_selector('input[name="lastname"]')
    if lname_el and not lname_el.input_value():
        lname_el.fill(PROFILE["last_name"])
        
    email_el = page.query_selector('input[type="email"]')
    if email_el and not email_el.input_value():
        email_el.fill(PROFILE["email"])
        
    phone_el = page.query_selector('input[type="tel"]')
    if phone_el and not phone_el.input_value():
        phone_el.fill(PROFILE["phone"])

    file_inputs = page.query_selector_all('input[type="file"]')
    if file_inputs:
        try:
            file_inputs[0].set_input_files(RESUME_PATH)
            time.sleep(2)
        except Exception:
            pass
            
    unanswered = _missing_required_fields(page, '[required], [aria-required="true"]')
    if unanswered:
        res["status"] = "BLOCKED_REQUIRES_USER_INPUT"
        res["blockers"] = unanswered
        ss = os.path.join(SCREENSHOT_DIR, f"{res['company']}_blocked.png")
        page.screenshot(path=ss)
        res["screenshot"] = ss
    else:
        _mark_ready_for_manual_review(page, res)

def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()
        
        for job in TARGET_JOBS:
            res = evaluate_and_prepare(page, job)
            results.append(res)
            time.sleep(2)
            
        browser.close()

    out_file = os.path.join(WORKSPACE, "application_readiness_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nCompleted evaluation of {len(results)} jobs. Results saved to {out_file}.")

if __name__ == "__main__":
    main()
