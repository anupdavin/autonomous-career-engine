import re
from typing import Any, Dict

from guardrails import assert_no_emdashes, sanitize_no_emdashes


FX_TO_INR = {
    "USD": 83.5,
    "EUR": 91.0,
    "GBP": 108.0,
    "SGD": 63.0,
    "INR": 1.0,
}


def compute_india_new_regime_tax(taxable_income_inr: float) -> float:
    """
    Computes India Income Tax (FY 2026-27 New Tax Regime Slabs + 4% Health & Education Cess):
      - Up to Rs. 12,00,000 taxable income: 0 tax (Section 87A rebate)
      - 0 to 4L     : 0%
      - 4L to 8L    : 5%
      - 8L to 12L   : 10%
      - 12L to 16L  : 15%
      - 16L to 20L  : 20%
      - 20L to 24L  : 25%
      - Above 24L   : 30%
    """
    if taxable_income_inr <= 1200000:
        return 0.0

    slabs = [
        (400000, 0.00),
        (400000, 0.05),
        (400000, 0.10),
        (400000, 0.15),
        (400000, 0.20),
        (400000, 0.25),
    ]
    remaining = taxable_income_inr
    base_tax = 0.0
    for slab_width, rate in slabs:
        if remaining <= 0:
            break
        chunk = min(remaining, slab_width)
        base_tax += chunk * rate
        remaining -= chunk

    if remaining > 0:
        base_tax += remaining * 0.30

    # Surcharge of 10% if taxable income > 50 Lakhs
    if taxable_income_inr > 5000000:
        base_tax *= 1.10

    return round(base_tax * 1.04, 2)  # +4% Health & Education Cess


def calculate_b2b_vs_employee_takehome(gross_annual_inr: float) -> Dict[str, Any]:
    """
    Calculates side-by-side India take-home salary:
      1. Global B2B Independent Contractor (Section 44ADA 50% Presumptive Profit up to 75L + 0% GST under LUT Export of Services)
      2. Full-Time Employee / India EOR (Salaried New Tax Regime with Rs. 75,000 Standard Deduction + PF)
    """
    # 1. Global B2B Section 44ADA Calculation
    if gross_annual_inr <= 7500000:
        b2b_taxable_profit = gross_annual_inr * 0.50
        b2b_scheme_note = "Sec 44ADA (50% Presumptive Profit) + 0% GST LUT Export"
    else:
        # Above 75L requires regular books (assume ~65% net profit after home office, hardware, CA/legal expenses)
        b2b_taxable_profit = gross_annual_inr * 0.65
        b2b_scheme_note = "Regular Business Audit (~35% Expense Deduction) + 0% GST LUT"

    b2b_annual_tax = compute_india_new_regime_tax(b2b_taxable_profit)
    b2b_annual_in_hand = gross_annual_inr - b2b_annual_tax
    b2b_monthly_in_hand = round(b2b_annual_in_hand / 12.0)
    b2b_eff_tax_pct = round((b2b_annual_tax / gross_annual_inr) * 100.0, 1) if gross_annual_inr else 0.0

    # 2. Full-Time Salaried / EOR Calculation
    standard_deduction = 75000.0
    annual_pf_deduction = 43200.0  # Employer + Employee statutory PF cap (Rs. 3,600/mo)
    emp_taxable = max(0.0, gross_annual_inr - standard_deduction - (annual_pf_deduction / 2.0))
    emp_annual_tax = compute_india_new_regime_tax(emp_taxable)
    emp_annual_in_hand = gross_annual_inr - emp_annual_tax - annual_pf_deduction - 2400.0  # Rs. 200/mo Prof Tax
    emp_monthly_in_hand = round(emp_annual_in_hand / 12.0)
    emp_eff_tax_pct = round((emp_annual_tax / gross_annual_inr) * 100.0, 1) if gross_annual_inr else 0.0

    monthly_b2b_advantage = b2b_monthly_in_hand - emp_monthly_in_hand

    return {
        "gross_annual_inr": round(gross_annual_inr),
        "gross_lpa_str": f"INR {round(gross_annual_inr / 100000, 1)} LPA",
        "b2b": {
            "scheme": b2b_scheme_note,
            "taxable_profit_inr": round(b2b_taxable_profit),
            "annual_tax_inr": round(b2b_annual_tax),
            "effective_tax_pct": b2b_eff_tax_pct,
            "monthly_in_hand_inr": b2b_monthly_in_hand,
        },
        "employee_eor": {
            "scheme": "Salaried New Regime (Rs 75k Std Ded + PF + PT)",
            "taxable_income_inr": round(emp_taxable),
            "annual_tax_inr": round(emp_annual_tax),
            "effective_tax_pct": emp_eff_tax_pct,
            "monthly_in_hand_inr": emp_monthly_in_hand,
        },
        "monthly_b2b_tax_savings_inr": monthly_b2b_advantage,
    }


def estimate_job_compensation_and_tax(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classifies engagement type (Global B2B Contract vs Full-Time Remote India / EOR),
    estimates or extracts salary range, and computes exact India in-hand monthly salary.
    """
    combined = f"{job.get('title', '')} {job.get('company', '')} {job.get('source', '')} {' '.join(job.get('tags', []))}".lower()

    is_b2b_primary = any(
        w in combined
        for w in ("b2b", "contract", "remoteok", "worldwide", "deel", "global", "elastic", "gitlab", "canonical")
    )

    if "principal" in combined or "architect" in combined or "staff" in combined:
        if is_b2b_primary:
            currency = "USD"
            min_foreign, max_foreign = 80000, 110000
            mid_inr = ((min_foreign + max_foreign) / 2.0) * FX_TO_INR["USD"]
            range_display = "$80k - $110k USD/yr (INR 66.8L - 91.8L)"
        else:
            currency = "INR"
            mid_inr = 4800000.0
            range_display = "INR 42.0 LPA - 54.0 LPA"
    elif "lead" in combined or "tech lead" in combined:
        if is_b2b_primary:
            currency = "USD"
            min_foreign, max_foreign = 70000, 95000
            mid_inr = ((min_foreign + max_foreign) / 2.0) * FX_TO_INR["USD"]
            range_display = "$70k - $95k USD/yr (INR 58.4L - 79.3L)"
        else:
            currency = "INR"
            mid_inr = 4000000.0
            range_display = "INR 35.0 LPA - 45.0 LPA"
    else:
        if is_b2b_primary:
            currency = "USD"
            min_foreign, max_foreign = 60000, 82000
            mid_inr = ((min_foreign + max_foreign) / 2.0) * FX_TO_INR["USD"]
            range_display = "$60k - $82k USD/yr (INR 50.1L - 68.5L)"
        else:
            currency = "INR"
            mid_inr = 3400000.0
            range_display = "INR 30.0 LPA - 38.0 LPA"

    breakdown = calculate_b2b_vs_employee_takehome(mid_inr)
    recommended_mode = "GLOBAL_B2B_CONTRACT" if is_b2b_primary else "FULL_TIME_INDIA_EOR"
    active_mode_data = breakdown["b2b"] if is_b2b_primary else breakdown["employee_eor"]

    summary_text = sanitize_no_emdashes(
        f"{range_display} | Mode: {'Global B2B (Sec 44ADA + 0% GST LUT)' if is_b2b_primary else 'India Remote EOR / Salaried'} "
        f"| Est. In-Hand: Rs. {active_mode_data['monthly_in_hand_inr']:,}/mo (Eff. Tax: {active_mode_data['effective_tax_pct']}%)"
    )
    assert_no_emdashes(summary_text, "tax_summary")

    return {
        "engagement_type": recommended_mode,
        "engagement_label": "Global B2B Contract (USD/EUR -> India Sec 44ADA)"
        if is_b2b_primary
        else "Full-Time Remote India (EOR / Salaried)",
        "currency": currency,
        "salary_range_display": sanitize_no_emdashes(range_display),
        "gross_midpoint_inr": breakdown["gross_annual_inr"],
        "primary_monthly_in_hand_inr": active_mode_data["monthly_in_hand_inr"],
        "primary_effective_tax_pct": active_mode_data["effective_tax_pct"],
        "primary_tax_scheme": active_mode_data["scheme"],
        "b2b_monthly_in_hand_inr": breakdown["b2b"]["monthly_in_hand_inr"],
        "b2b_effective_tax_pct": breakdown["b2b"]["effective_tax_pct"],
        "eor_monthly_in_hand_inr": breakdown["employee_eor"]["monthly_in_hand_inr"],
        "eor_effective_tax_pct": breakdown["employee_eor"]["effective_tax_pct"],
        "monthly_b2b_savings_inr": breakdown["monthly_b2b_tax_savings_inr"],
        "tax_summary": summary_text,
    }
