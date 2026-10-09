"""The verdict: worth it / worth it with a loan / not now, with reason codes for the UI.

Reason codes (first one is the main reason):
  ALREADY_SOLAR, NON_RESIDENTIAL, FREE_UNITS_BAND,
  NO_SAVINGS (no payback within the 25-year panel life),
  PAYBACK_SHORT, PAYBACK_MEDIUM, PAYBACK_LONG, EMI_COVERED_BY_SAVING,
  then context: LOW_USAGE, LOAD_CAP, ROOF_CAP, MAX_10KW_CAP, PREVIOUS_SUBSIDY,
  TARIFF_ESTIMATE, TARIFF_ROUGH.
"""

from __future__ import annotations

from . import constants as C
from .models import Accuracy, Verdict


def free_units_band(subsidy_shares: list[float]) -> bool:
    """True when free units already cover at least half the bill in at least half the months.
    `subsidy_shares` is subsidy / gross bill per billing period, before solar."""
    if not subsidy_shares:
        return False
    covered = sum(1 for s in subsidy_shares if s >= 0.5)
    return covered * 2 >= len(subsidy_shares)


def decide(
    *,
    payback_years: float | None,
    emi_covered: bool,
    is_residential: bool | None = True,
    has_solar: bool | None = False,
    in_free_band: bool = False,
    low_usage: bool = False,
    caps_applied: list[str] | None = None,
    previous_subsidy: bool | None = False,
    accuracy: Accuracy = "exact",
) -> Verdict:
    reasons: list[str] = []
    if has_solar:
        code, reasons = "not_now", ["ALREADY_SOLAR"]
    elif is_residential is False:
        code, reasons = "not_now", ["NON_RESIDENTIAL"]
    elif in_free_band:
        code, reasons = "not_now", ["FREE_UNITS_BAND"]
    elif payback_years is None:
        code, reasons = "not_now", ["NO_SAVINGS"]
    elif payback_years <= C.PAYBACK_WORTH_IT_YEARS:
        code, reasons = "worth_it", ["PAYBACK_SHORT"]
    elif payback_years <= C.PAYBACK_WITH_LOAN_YEARS:
        code, reasons = "worth_it_with_loan", ["PAYBACK_MEDIUM"] + (["EMI_COVERED_BY_SAVING"] if emi_covered else [])
    elif emi_covered:
        code, reasons = "worth_it_with_loan", ["EMI_COVERED_BY_SAVING", "PAYBACK_LONG"]
    else:
        code, reasons = "not_now", ["PAYBACK_LONG"]

    if low_usage:
        reasons.append("LOW_USAGE")
    reasons += [c for c in (caps_applied or []) if c in ("LOAD_CAP", "ROOF_CAP", "MAX_10KW_CAP")]
    if previous_subsidy:
        reasons.append("PREVIOUS_SUBSIDY")
    if accuracy == "estimate":
        reasons.append("TARIFF_ESTIMATE")
    elif accuracy == "rough":
        reasons.append("TARIFF_ROUGH")
    return Verdict(code=code, reasons=list(dict.fromkeys(reasons)))
