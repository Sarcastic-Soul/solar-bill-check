"""Deterministic solar calculation engine (no LLM, no network in the maths).

    from engine import build_plan, PlanInput
    plan = build_plan(PlanInput(bill=..., location=..., solar=...))

Network lookups for location and solar yield live in engine.fetchers.
"""

from .models import (
    Answers,
    BillFields,
    Location,
    Options,
    Plan,
    PlanInput,
    SolarResource,
)
from .plan import PlanError, build_plan, build_plan_dict
from .tariffs import monthly_bill, period_bill

__all__ = [
    "Answers",
    "BillFields",
    "Location",
    "Options",
    "Plan",
    "PlanError",
    "PlanInput",
    "SolarResource",
    "build_plan",
    "build_plan_dict",
    "monthly_bill",
    "period_bill",
]
