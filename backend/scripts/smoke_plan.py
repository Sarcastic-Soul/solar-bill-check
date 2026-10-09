"""Live smoke test: real pincode / geocoding / PVGIS lookups, then a plan.

    uv run --with pydantic python backend/scripts/smoke_plan.py [--json]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engine import build_plan  # noqa: E402
from engine.fetchers import Fetchers  # noqa: E402

CASES = {
    "411001": {
        "discom": "Maharashtra State Electricity Distribution Co. Ltd. (MSEDCL)",
        "state": "Maharashtra",
        "is_residential": True,
        "tariff_category": "LT I(B) Residential",
        "sanctioned_load_kw": 3.0,
        "connection_phase": "single",
        "units_billed_kwh": 350,
        "billing_cycle": "monthly",
        "consumer_number": "170012345678",
        "pincode": "411001",
    },
    # Same fields as the mock bill eval/bills/delhi-brpl-hindi-clean-01
    "110075": {
        "discom": "BSES Rajdhani Power Limited (BRPL)",
        "state": "Delhi",
        "is_residential": True,
        "tariff_category": "Domestic (DX)",
        "sanctioned_load_kw": 3.0,
        "connection_phase": "single",
        "billing_period_start": "2026-08-06",
        "billing_period_end": "2026-09-05",
        "billing_days": 30,
        "billing_cycle": "monthly",
        "units_billed_kwh": 342,
        "bill_amount_rs": 1323.01,
        "consumer_number": "152839471",
        "consumption_history": [
            {"month": "2026-08", "units_kwh": 389},
            {"month": "2026-07", "units_kwh": 412},
            {"month": "2026-06", "units_kwh": 455},
            {"month": "2026-05", "units_kwh": 398},
            {"month": "2026-04", "units_kwh": 251},
            {"month": "2026-03", "units_kwh": 186},
        ],
        "pincode": "110075",
    },
}


def rs(x: float | None) -> str:
    return "-" if x is None else f"Rs {x:,.0f}"


def summary(pin: str, plan, seconds: float, errors: list[str]) -> str:
    loc = plan.location
    out = [
        f"=== {pin}: {loc.district}, {loc.state}  ({loc.lat:.4f}, {loc.lon:.4f} via {loc.source}); lookups {seconds:.1f}s",
        f"DISCOM {plan.discom.code} ({plan.discom.matched_from}), tariff accuracy {plan.discom.accuracy}; "
        f"plan accuracy {plan.accuracy} {plan.accuracy_notes}",
        f"Yield {plan.solar.annual_kwh_per_kw:.0f} kWh/kW/yr from {plan.solar.source}; "
        f"use {plan.consumption.annual_kwh:.0f} kWh/yr ({plan.consumption.method})",
        f"Verdict: {plan.verdict.code} {plan.verdict.reasons}",
    ]
    for o in (plan.recommended, plan.alternative):
        if not o:
            continue
        out += [
            f"  [{o.label}] {o.kw} kW: cost {rs(o.gross_cost)} - subsidy {rs(o.subsidy.total)} = {rs(o.net_cost)}",
            f"      bill/yr {rs(o.bill_before_year)} -> {rs(o.bill_after_year)}, export {o.export_kwh:.0f} kWh "
            f"= {rs(o.export_income)}; saving/yr {rs(o.year1_savings)} ({rs(o.monthly_saving_avg)}/month)",
            f"      payback {o.payback_years} yrs; 25-yr savings {rs(o.savings_25y)}; "
            f"CO2 {o.co2_kg_per_year:,.0f} kg/yr = {o.trees_equivalent:.0f} trees",
            f"      loan {rs(o.loan.loan_amount)} @ {o.loan.rate_pct}% x {o.loan.years}y: EMI {rs(o.loan.emi)} "
            f"vs saving {rs(o.loan.monthly_saving)}/month (covered: {o.loan.emi_covered_by_saving}) {o.flags}",
        ]
    out.append("Readiness: " + ", ".join(f"{c.code}={c.status}" for c in plan.readiness))
    if plan.warnings:
        out.append(f"Warnings: {plan.warnings}")
    if errors:
        out.append(f"Fetch errors: {errors}")
    return "\n".join(out)


def main() -> None:
    as_json = "--json" in sys.argv
    fetchers = Fetchers()
    for pin, bill in CASES.items():
        fetchers.errors.clear()
        t0 = time.monotonic()
        location, solar = fetchers.resolve(pin)
        took = time.monotonic() - t0
        plan = build_plan({"bill": bill, "location": location, "solar": solar,
                           "answers": {"owns_roof": True, "name_matches_bank": True, "previous_solar_subsidy": False}})
        if as_json:
            print(json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=1))
        else:
            print(summary(pin, plan, took, list(fetchers.errors)))
            print()


if __name__ == "__main__":
    main()
