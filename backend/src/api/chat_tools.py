"""Tools for the chat assistant: plain functions (testable without Strands) plus `make_tools`,
which wraps them as Strands `@tool`s for one request.

Every number the assistant gives should come from here: the saved plan, the engine re-run at
another size, the EMI formula, or fixed scheme facts (docs/RESEARCH.md and engine.constants).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from engine import PlanError, build_plan
from engine import constants as C
from engine.savings import emi

from . import aws
from .plan import PLAN_ID_RE

MAX_TOOL_CALLS = 8  # per request; protects credits if a model loops on tools
MIN_KW, MAX_KW = 0.5, 100.0

PlanLoader = Callable[[str], dict | None]


# ---------------------------------------------------------------- plan storage


def load_stored_plan(plan_id: str) -> dict | None:
    """The stored item as {plan, inputs}, or None when missing, expired or the id is malformed."""
    if not PLAN_ID_RE.match(plan_id or ""):
        return None
    item = aws.dynamodb().get_item(TableName=aws.PLANS_TABLE, Key={"planId": {"S": plan_id}}).get("Item")
    if not item or int(item.get("expiresAt", {}).get("N", "0")) < time.time():
        return None
    return {"plan": json.loads(item["plan"]["S"]),
            "inputs": json.loads(item["inputs"]["S"]) if "inputs" in item else None}


# ---------------------------------------------------------------- summaries


def _rs(v: Any) -> int | None:
    return None if v is None else round(float(v))


def subsidy_calc(kw: float, sub: dict) -> str | None:
    """How the central subsidy was worked out, in words, so the model doesn't invent its own maths."""
    if sub.get("mode") != "individual" or not kw:
        return None
    mult = C.CFA_SPECIAL_MULTIPLIER if sub.get("special_category") else 1.0
    r1, r2_ = round(C.CFA_FIRST_2KW_PER_KW * mult), round(C.CFA_THIRD_KW_PER_KW * mult)
    first, third = min(kw, 2), min(max(kw - 2, 0), 1)
    parts = [f"{first:g} kW x {_inr(r1)}"] + ([f"{third:g} kW x {_inr(r2_)}"] if third else [])
    text = " + ".join(parts) + f" = {_inr(sub.get('central') or 0)} central subsidy"
    if kw > C.FULL_SUBSIDY_KW:
        text += " (nothing extra above 3 kW)"
    return text


def option_summary(o: dict | None) -> dict | None:
    """The numbers of one system option that a chat answer may need (rupees rounded)."""
    if not o:
        return None
    sub, loan = o.get("subsidy") or {}, o.get("loan") or {}
    return {
        "label": o.get("label"),
        "kw": o.get("kw"),
        "cost_before_subsidy_rs": _rs(o.get("gross_cost")),
        "subsidy_central_rs": _rs(sub.get("central")),
        "subsidy_state_topup_rs": _rs(sub.get("state_topup")) if sub.get("state_topup_included") else 0,
        "subsidy_total_rs": _rs(sub.get("total")),
        "subsidy_calculation": subsidy_calc(o.get("kw") or 0, sub),
        "subsidy_notes": sub.get("notes") or [],
        "your_cost_after_subsidy_rs": _rs(o.get("net_cost")),
        "yearly_bill_before_rs": _rs(o.get("bill_before_year")),
        "yearly_bill_after_rs": _rs(o.get("bill_after_year")),
        "first_year_savings_rs": _rs(o.get("year1_savings")),
        "monthly_saving_avg_rs": _rs(o.get("monthly_saving_avg")),
        "payback_years": o.get("payback_years"),
        "savings_25_years_rs": _rs(o.get("savings_25y")),
        "net_gain_25_years_rs": _rs(o.get("net_gain_25y")),
        "solar_units_per_year": _rs(o.get("annual_generation_kwh")),
        "roof_area_needed_m2": o.get("roof_area_needed_m2"),
        "co2_saved_kg_per_year": _rs(o.get("co2_kg_per_year")),
        "trees_equivalent": o.get("trees_equivalent"),
        "loan": {
            "loan_amount_rs": _rs(loan.get("loan_amount")),
            "down_payment_rs": _rs(loan.get("margin_amount")),
            "rate_pct": loan.get("rate_pct"),
            "years": loan.get("years"),
            "emi_rs": _rs(loan.get("emi")),
            "emi_covered_by_monthly_saving": loan.get("emi_covered_by_saving"),
        } if loan else None,
        "flags": o.get("flags") or [],
    }


def plan_summary(plan_id: str, plan: dict) -> dict:
    d, cons = plan.get("discom") or {}, plan.get("consumption") or {}
    return {
        "plan_id": plan_id,
        "verdict": (plan.get("verdict") or {}).get("code"),
        "verdict_reasons": (plan.get("verdict") or {}).get("reasons") or [],
        "accuracy": plan.get("accuracy"),
        "accuracy_notes": plan.get("accuracy_notes") or [],
        "state": plan.get("state"),
        "special_category_state": plan.get("special_category"),
        "discom": d.get("name") or d.get("code"),
        "discom_net_metering_billing": d.get("billing_cycle"),
        "usage": {"average_monthly_units": cons.get("average_monthly_kwh"), "yearly_units": cons.get("annual_kwh"),
                  "method": cons.get("method"), "flags": cons.get("flags") or []},
        "solar_units_per_kw_per_year": (plan.get("solar") or {}).get("annual_kwh_per_kw"),
        "recommended": option_summary(plan.get("recommended")),
        "alternative": option_summary(plan.get("alternative")),
        "readiness": [{k: c.get(k) for k in ("code", "status", "reason", "fix")}
                      for c in plan.get("readiness") or []],
        "warnings": plan.get("warnings") or [],
    }


# ---------------------------------------------------------------- tool bodies


def get_plan_data(plan_id: str, loader: PlanLoader = load_stored_plan) -> dict:
    stored = loader(plan_id)
    if not stored:
        return {"error": "PLAN_NOT_FOUND", "message": "No saved plan with this id (it may have expired)."}
    return plan_summary(plan_id, stored["plan"])


def what_if_data(plan_id: str, kw: float, loader: PlanLoader = load_stored_plan) -> dict:
    try:
        kw = round(float(kw), 1)
    except (TypeError, ValueError):
        return {"error": "BAD_SIZE", "message": "kw must be a number."}
    if not MIN_KW <= kw <= MAX_KW:
        return {"error": "BAD_SIZE", "message": f"kw must be between {MIN_KW} and {MAX_KW}."}
    stored = loader(plan_id)
    if not stored:
        return {"error": "PLAN_NOT_FOUND", "message": "No saved plan with this id (it may have expired)."}
    inputs, plan = stored.get("inputs"), stored["plan"]
    if not inputs:
        return {"error": "INPUTS_NOT_SAVED", "message": "This plan was saved without its inputs; make a new plan."}
    answers = inputs.get("answers") or {}
    payload = {
        "bill": inputs.get("fields") or {},
        "monthly_units": inputs.get("monthly_units"),
        # The saved plan already holds the resolved location and solar yield, so no network lookups.
        "location": plan.get("location"),
        "solar": plan.get("solar"),
        "answers": {"owns_roof": answers.get("owns_roof"), "name_matches_bank": answers.get("name_matches_bank"),
                    "previous_solar_subsidy": answers.get("previous_subsidy")},
        "options": {**(inputs.get("overrides") or {}), "system_kw": kw},
    }
    try:
        p = build_plan(payload).model_dump(mode="json")
    except PlanError as e:
        return {"error": e.code, "message": "The engine could not build a plan at this size."}
    return {
        "plan_id": plan_id,
        "asked_kw": kw,
        "this_size": option_summary(p["recommended"]),
        "original_recommended": option_summary(plan.get("recommended")),
        "verdict_at_this_size": p["verdict"]["code"],
        "verdict_reasons": p["verdict"]["reasons"],
    }


def loan_emi_data(amount: float, rate_pct: float = C.LOAN_TIER1_RATE_PCT, years: int = C.LOAN_YEARS) -> dict:
    try:
        amount, rate_pct, years = float(amount), float(rate_pct), int(years)
    except (TypeError, ValueError):
        return {"error": "BAD_INPUT", "message": "amount, rate_pct and years must be numbers."}
    if not 1_000 <= amount <= 10_000_000:
        return {"error": "BAD_INPUT", "message": "amount must be between Rs 1,000 and Rs 1 crore."}
    if not 0 <= rate_pct <= 30:
        return {"error": "BAD_INPUT", "message": "rate_pct must be between 0 and 30."}
    if not 1 <= years <= 30:
        return {"error": "BAD_INPUT", "message": "years must be between 1 and 30."}
    e = emi(amount, rate_pct, years)
    total = round(e * years * 12)
    return {"amount_rs": round(amount), "rate_pct": rate_pct, "years": years, "months": years * 12,
            "emi_rs": round(e), "total_paid_rs": total, "total_interest_rs": total - round(amount)}


def _inr(v: float) -> str:
    """12345678 -> 'Rs 1,23,45,678' (Indian grouping)."""
    s = str(round(v))
    head, tail = s[:-3], s[-3:]
    while len(head) > 2:
        tail = head[-2:] + "," + tail if tail else head[-2:]
        head = head[:-2]
    return "Rs " + (head + "," + tail if head else tail)


SCHEME_FACTS: dict[str, list[str]] = {
    "subsidy": [
        (
            f"Central subsidy (CFA) under PM Surya Ghar: {_inr(C.CFA_FIRST_2KW_PER_KW)} per kW for the first 2 kW, "
            f"{_inr(C.CFA_THIRD_KW_PER_KW)} for the 3rd kW, nothing extra above 3 kW."
        ),
        f"So: 1 kW = {_inr(30_000)}, 2 kW = {_inr(60_000)}, 3 kW or more = {_inr(C.CFA_CAP)} (the cap).",
        f"Special category states get 10% more: up to {_inr(C.CFA_CAP_SPECIAL)}.",
        "Paid on the panels' DC capacity, not the inverter size. Batteries get no subsidy.",
        (
            "Paid into the bank account of the person named on the electricity bill, about 15-30 days after "
            "commissioning (sources differ)."
        ),
        (
            "Some states add a top-up: Uttar Pradesh reportedly Rs 15,000 per kW up to Rs 30,000; Delhi's 2026 scheme "
            "is reported to add up to Rs 78,000 but this is not confirmed. Check with your DISCOM."
        ),
        (
            "Only for residential connections, grid-connected systems, and people who have not had a solar subsidy "
            "before (earlier users get it only for extra capacity, up to 3 kW in total)."
        ),
    ],
    "special_category": [
        (
            "Special category states/UTs get 10% higher subsidy (Rs 33,000/kW for the first 2 kW, Rs 19,800 for the "
            "3rd kW, cap Rs 85,800)."
        ),
        "They are: " + ", ".join(sorted(C.SPECIAL_CATEGORY_STATES)) + ".",
    ],
    "rwa": [
        (
            f"RWA / group housing common areas: {_inr(C.CFA_RWA_PER_KW)} per kW "
            f"({_inr(C.CFA_RWA_PER_KW_SPECIAL)} in special category states)."
        ),
        (
            f"Counted on the lower of installed kW and {C.CFA_RWA_KW_PER_HOUSE} kW x number of houses, "
            f"up to {C.CFA_RWA_MAX_KW} kW."
        ),
        "The RWA applies, not individual flat owners.",
    ],
    "dcr": [
        (
            "Panels must be DCR: made in India from Indian cells. Any non-DCR panel makes the whole system lose "
            "the subsidy."
        ),
        "Ask the vendor for the DCR certificate number before signing.",
        "DCR panels cost about Rs 8,000-12,000 more per kW, already included in typical prices.",
    ],
    "steps": [
        (
            "1. Register on pmsuryaghar.gov.in with your mobile number and OTP; enter state, district, DISCOM and "
            "consumer number. You do this yourself; the app never applies for you."
        ),
        (
            "2. Feasibility: up to 10 kW is auto-approved for residential (LT) connections. Do not install before "
            "approval."
        ),
        (
            "3. Choose a vendor registered for your DISCOM and agree the price. After the agreement is uploaded the "
            "vendor is locked for 45 days."
        ),
        "4. The vendor installs and fills the installation details; you check and submit them.",
        "5. Net meter is installed and the agreement signed (32 states/UTs have dropped the fees).",
        "6. DISCOM inspection, then the commissioning certificate.",
        (
            "7. Upload a cancelled cheque or passbook (name must match the bill exactly) and redeem the e-token. "
            "Subsidy arrives in about 15-30 days."
        ),
        (
            "Documents: bank proof, Aadhaar authentication on the portal, geo-tagged photo, DCR undertaking, "
            "vendor agreement with 5-year maintenance."
        ),
    ],
    "loan": [
        "Concessional loan from 12 public sector banks, applied for through jansamarth.in.",
        (
            f"Up to Rs 2 lakh (about 3 kW): repo rate + 0.5%, about {C.LOAN_TIER1_RATE_PCT:g}% now, "
            f"{C.LOAN_TIER1_MARGIN:.0%} down payment, no income proof."
        ),
        (
            f"Rs 2-6 lakh (3-10 kW): home-loan rate or HL + 1% (we assume about {C.LOAN_TIER2_RATE_PCT:g}%), "
            f"{C.LOAN_TIER2_MARGIN:.0%} down payment, PAN and income of Rs 3 lakh or more."
        ),
        f"No collateral, up to {C.LOAN_YEARS} years, 6-month moratorium, no processing fee.",
    ],
    "net_metering": [
        (
            "Net metering: the DISCOM puts a two-way meter; solar units you don't use go to the grid and are "
            "subtracted from what you take."
        ),
        (
            "Extra units at year end are paid at a low rate that differs by state: Delhi pays the DISCOM's average "
            "power purchase cost (we assume about Rs 2), Maharashtra Rs 2.82 for FY 2026-27, Karnataka Rs 1.96-2.58, "
            "Uttar Pradesh not confirmed (Rs 0.50-2)."
        ),
        "So size for your own use; oversizing earns little.",
        "Delhi: a 2026 rule cut net-meter time to 25 days and waived fees up to 10 kW.",
    ],
    "red_flags": [
        "The portal pmsuryaghar.gov.in is free. Never pay anyone who says they are 'from the government'.",
        "Never share your Aadhaar number, OTP or bank details with callers or vendors on chat.",
        "Do not install before feasibility approval.",
        "Non-DCR panels lose the whole subsidy: ask for the DCR certificate number.",
        "Never pay in full before installation; agree a payment schedule in writing.",
        "Make sure 5-year maintenance is in the vendor agreement and the price is per DC kW.",
    ],
    "deadline": [
        "PM Surya Ghar runs until 31 March 2027. Budget for FY27 is Rs 22,000 crore.",
        "There is talk of a next phase but nothing official, so applying before the deadline is safer.",
    ],
    "eligibility": [
        "Indian citizen who owns a house with a suitable roof.",
        "Valid residential electricity connection (consumer number).",
        "No earlier solar subsidy (earlier users get it only for extra capacity up to 3 kW in total).",
        "Grid-connected systems only. Non-residential connections get no subsidy (farms: see PM-KUSUM).",
        "The bank account name must match the name on the electricity bill exactly.",
    ],
    "sizing": [
        "1 kW gives about 4-5.5 units a day on a sunny day; 3 kW gives about 300+ units a month.",
        f"Roof: about {C.ROOF_M2_PER_KW:g} m2 of shadow-free area per kW.",
        "Rough guide: 0-150 units/month = 1-2 kW, 150-300 = 2-3 kW, 300+ = above 3 kW.",
        "Market price 2026 is about Rs 55,000-85,000 per kW installed (smaller systems cost more per kW).",
    ],
}
TOPIC_ALIASES = {
    "subsidies": "subsidy", "cfa": "subsidy", "slabs": "subsidy", "subsidy_slabs": "subsidy",
    "special": "special_category", "special_category_states": "special_category", "hill_states": "special_category",
    "rwa_rate": "rwa", "society": "rwa", "group_housing": "rwa", "dcr_panels": "dcr", "panels": "dcr",
    "application": "steps", "apply": "steps", "how_to_apply": "steps", "process": "steps", "documents": "steps",
    "application_steps": "steps", "jan_samarth": "loan", "emi": "loan", "bank": "loan",
    "net_meter": "net_metering", "export": "net_metering", "scam": "red_flags", "fraud": "red_flags",
    "warnings": "red_flags", "redflags": "red_flags", "last_date": "deadline", "end_date": "deadline",
    "eligible": "eligibility", "who_can_apply": "eligibility", "size": "sizing", "roof": "sizing",
    "cost": "sizing", "price": "sizing",
}


def scheme_facts_data(topic: str) -> dict:
    key = (topic or "").strip().lower().replace("-", "_").replace(" ", "_")
    key = TOPIC_ALIASES.get(key, key)
    if key not in SCHEME_FACTS:
        return {"error": "UNKNOWN_TOPIC", "topics": sorted(SCHEME_FACTS)}
    return {"topic": key, "facts": SCHEME_FACTS[key],
            "source": "MNRE PM Surya Ghar guidelines (OM 7 Jun 2024), pmsuryaghar.gov.in FAQ, PIB, as of Oct 2026"}


# ---------------------------------------------------------------- Strands tools


def make_tools(default_plan_id: str | None, loader: PlanLoader = load_stored_plan) -> list:
    """Strands tools for one request. A missing or malformed plan_id falls back to the session's plan,
    plans are cached for the request, and tool calls are capped."""
    from strands import tool

    cache: dict[str, dict | None] = {}
    calls = {"n": 0}

    def _pid(plan_id: str | None) -> str:
        pid = (plan_id or "").strip()
        return pid if PLAN_ID_RE.match(pid) or not default_plan_id else default_plan_id

    def _load(pid: str) -> dict | None:
        if pid not in cache:
            cache[pid] = loader(pid)
        return cache[pid]

    def _budget() -> dict | None:
        calls["n"] += 1
        if calls["n"] > MAX_TOOL_CALLS:
            return {"error": "TOOL_LIMIT", "message": "Tool limit reached. Answer now with what you have."}
        return None

    @tool
    def get_plan(plan_id: str) -> dict:
        """Get the user's saved solar plan: verdict, recommended size, cost, subsidy, savings, payback, loan EMI,
        CO2 and the readiness checklist.

        Args:
            plan_id: The plan id given in the system prompt.
        """
        return _budget() or get_plan_data(_pid(plan_id), _load)

    @tool
    def what_if(plan_id: str, kw: float) -> dict:
        """Re-run the user's plan at a different system size and return cost, subsidy, savings, payback and EMI
        for that size, next to the original recommendation.

        Args:
            plan_id: The plan id given in the system prompt.
            kw: System size in kW to try, for example 2 or 3.5.
        """
        return _budget() or what_if_data(_pid(plan_id), kw, _load)

    @tool
    def loan_emi(amount: float, rate_pct: float = C.LOAN_TIER1_RATE_PCT, years: int = C.LOAN_YEARS) -> dict:
        """Monthly EMI for a loan amount. Use for loan questions with a custom amount, rate or tenure.

        Args:
            amount: Loan amount in rupees.
            rate_pct: Yearly interest rate in percent. Jan Samarth solar loan up to Rs 2 lakh is about 6.
            years: Loan tenure in years (Jan Samarth allows up to 10).
        """
        return _budget() or loan_emi_data(amount, rate_pct, years)

    @tool
    def scheme_facts(topic: str) -> dict:
        """Fixed, sourced facts about PM Surya Ghar: Muft Bijli Yojana.

        Args:
            topic: One of subsidy, special_category, rwa, dcr, steps, loan, net_metering, red_flags, deadline,
                eligibility, sizing.
        """
        return _budget() or scheme_facts_data(topic)

    return [get_plan, what_if, loan_emi, scheme_facts]
