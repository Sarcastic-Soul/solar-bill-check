"""Monthly consumption profile and system size."""

from __future__ import annotations

import math
from datetime import date

from . import constants as C
from .models import BillFields, ConsumptionProfile, SizingResult
from .tariffs import normalize_state


def _ym(s: str) -> tuple[int, int] | None:
    try:
        y, m = s.strip()[:7].split("-")
        y, m = int(y), int(m)
        return (y, m) if 1 <= m <= 12 else None
    except (ValueError, AttributeError):
        return None


def _prev(ym: tuple[int, int]) -> tuple[int, int]:
    y, m = ym
    return (y - 1, 12) if m == 1 else (y, m - 1)


def _date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def seasonal_profile(state: str | None) -> list[float]:
    p = C.SEASONAL_PROFILES[C.STATE_REGION.get(normalize_state(state) or "", C.DEFAULT_REGION)]
    mean = sum(p) / 12
    return [x / mean for x in p]


def is_bimonthly(bill: BillFields) -> bool:
    if bill.billing_cycle:
        return bill.billing_cycle == "bimonthly"
    days = bill.billing_days or _period_days(bill)
    return bool(days and days >= 45)


def _period_days(bill: BillFields) -> int | None:
    start, end = _date(bill.billing_period_start), _date(bill.billing_period_end)
    if start and end and end > start:
        return (end - start).days
    return None


def normalize_consumption(
    bill: BillFields, manual: list[float] | float | None = None, state: str | None = None
) -> ConsumptionProfile:
    """Turn whatever the bill (or the user) gives us into 12 monthly values, Jan..Dec."""
    if manual is not None:
        if isinstance(manual, (int, float)):
            monthly = [float(manual)] * 12
            return _profile(monthly, 1, "manual", ["MANUAL_AVERAGE"])
        if len(manual) == 12:
            return _profile([float(x) for x in manual], 12, "manual", [])
        raise ValueError("monthly_units must be one number or 12 values")

    flags: list[str] = []
    bimonthly = is_bimonthly(bill)
    if bimonthly:
        flags.append("BIMONTHLY_SPLIT")
    by_ym: dict[tuple[int, int], float] = {}

    def add(ym: tuple[int, int], units: float) -> None:
        if bimonthly:
            for k in (ym, _prev(ym)):
                by_ym.setdefault(k, units / 2)
        else:
            by_ym.setdefault(ym, units)

    for h in bill.consumption_history or []:
        ym = _ym(h.month)
        if ym:
            add(ym, h.units_kwh)

    current = bill.units_billed_kwh
    undated_current = None
    if current is not None and current >= 0:
        days = bill.billing_days or _period_days(bill)
        expected = 60 if bimonthly else 30
        if days and abs(days - expected) > 2:
            current = current * expected / days
            flags.append("PERIOD_NORMALISED")
        end = _date(bill.billing_period_end)
        if end:
            # History lists usually exclude the current bill; setdefault keeps history if both exist.
            add((end.year, end.month), current)
        elif not by_ym:
            undated_current = current / 2 if bimonthly else current

    if bill.meter_reading_type == "estimated":
        flags.append("ESTIMATED_READING")

    # Average the same calendar month across years.
    sums: dict[int, list[float]] = {}
    for (_, m), u in by_ym.items():
        sums.setdefault(m, []).append(u)
    known = {m: sum(v) / len(v) for m, v in sums.items()}

    if not known:
        if undated_current is None:
            raise ValueError("NO_CONSUMPTION")
        return _profile([undated_current] * 12, 1, "single_month", flags + ["SINGLE_MONTH_REPEATED"])
    if len(known) == 1:
        (only,) = known.values()
        return _profile([only] * 12, 1, "single_month", flags + ["SINGLE_MONTH_REPEATED"])
    if len(known) == 12:
        return _profile([known[m] for m in range(1, 13)], 12, "history", flags)

    profile = seasonal_profile(state or bill.state)
    scale = sum(known[m] / profile[m - 1] for m in known) / len(known)
    monthly = [known.get(m, scale * profile[m - 1]) for m in range(1, 13)]
    return _profile(monthly, len(known), "seasonal_fill", flags + ["MONTHS_FILLED_SEASONAL"])


def _profile(monthly: list[float], n: int, method: str, flags: list[str]) -> ConsumptionProfile:
    monthly = [round(max(0.0, x), 1) for x in monthly]
    annual = round(sum(monthly), 1)
    avg = round(annual / 12, 1)
    if avg < C.LOW_USAGE_UNITS_PER_MONTH:
        flags = flags + ["LOW_USAGE"]
    return ConsumptionProfile(monthly_kwh=monthly, annual_kwh=annual, average_monthly_kwh=avg, months_from_bill=n,
                              method=method, flags=flags)


def round_half(x: float) -> float:
    return math.floor(x * 2 + 0.5) / 2


def floor_half(x: float) -> float:
    return math.floor(x * 2 + 1e-9) / 2


def size_system(
    annual_kwh: float,
    yield_kwh_per_kw: float,
    sanctioned_kw: float | None = None,
    roof_area_m2: float | None = None,
    rwa: bool = False,
) -> SizingResult:
    ideal = annual_kwh / yield_kwh_per_kw if yield_kwh_per_kw > 0 else 0.0
    want = max(C.MIN_SYSTEM_KW, round_half(ideal))
    caps: dict[str, float] = {}
    if sanctioned_kw:
        caps["LOAD_CAP"] = floor_half(sanctioned_kw)
    if roof_area_m2:
        caps["ROOF_CAP"] = floor_half(roof_area_m2 / C.ROOF_M2_PER_KW)
    if not rwa:
        caps["MAX_10KW_CAP"] = C.MAX_AUTO_APPROVED_KW
    cap_kw = min(caps.values()) if caps else None
    applied = [code for code, v in caps.items() if v < want]
    rec = want if cap_kw is None else min(want, cap_kw)
    if rec < C.MIN_SYSTEM_KW:
        applied.append("CAP_BELOW_MIN_SIZE")
        rec = C.MIN_SYSTEM_KW

    alt, alt_flags = None, []
    if not rwa and rec != C.FULL_SUBSIDY_KW:
        roof_fits = roof_area_m2 is None or roof_area_m2 >= C.FULL_SUBSIDY_KW * C.ROOF_M2_PER_KW
        if roof_fits:
            alt = C.FULL_SUBSIDY_KW
            if sanctioned_kw is not None and sanctioned_kw < C.FULL_SUBSIDY_KW:
                alt_flags.append("NEEDS_LOAD_INCREASE")
            if rec > C.FULL_SUBSIDY_KW:
                alt_flags.append("SMALLER_THAN_NEED")
            else:
                alt_flags.append("LARGER_THAN_NEED")

    return SizingResult(
        ideal_kw=round(ideal, 2),
        recommended_kw=rec,
        caps_applied=applied,
        cap_kw=cap_kw,
        roof_area_needed_m2=rec * C.ROOF_M2_PER_KW,
        alternative_kw=alt,
        alternative_flags=alt_flags,
    )


def cost_per_kw(kw: float, override: float | None = None) -> float:
    if override:
        return float(override)
    return float(next(rate for min_kw, rate in C.COST_PER_KW_BANDS if kw >= min_kw))
