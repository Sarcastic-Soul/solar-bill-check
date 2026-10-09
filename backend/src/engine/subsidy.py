"""PM Surya Ghar central subsidy (CFA), RWA mode and state top-ups."""

from __future__ import annotations

from . import constants as C
from .models import Assumption, SubsidyResult
from .tariffs import normalize_state


def is_special_category(state: str | None) -> bool:
    return normalize_state(state) in C.SPECIAL_CATEGORY_STATES


def central_cfa(kw: float, special: bool = False) -> float:
    """min(kW,2) x 30k + min(max(kW-2,0),1) x 18k, x1.1 in special-category states."""
    kw = max(0.0, kw)
    base = min(kw, 2) * C.CFA_FIRST_2KW_PER_KW + min(max(kw - 2, 0), 1) * C.CFA_THIRD_KW_PER_KW
    if special:
        return round(min(base * C.CFA_SPECIAL_MULTIPLIER, C.CFA_CAP_SPECIAL), 2)
    return round(min(base, C.CFA_CAP), 2)


def rwa_eligible_kw(installed_kw: float, houses: int) -> float:
    return max(0.0, min(installed_kw, C.CFA_RWA_KW_PER_HOUSE * houses, C.CFA_RWA_MAX_KW))


def rwa_cfa(installed_kw: float, houses: int, special: bool = False) -> float:
    rate = C.CFA_RWA_PER_KW_SPECIAL if special else C.CFA_RWA_PER_KW
    return round(rwa_eligible_kw(installed_kw, houses) * rate, 2)


def state_topup(state: str | None, kw: float, central: float) -> tuple[float, dict | None]:
    """Top-up amount the state reportedly adds, and its table entry (None if the state has none)."""
    rule = C.STATE_TOPUPS.get(normalize_state(state) or "")
    if not rule or kw <= 0:
        return 0.0, rule
    if rule["kind"] == "per_kw":
        return float(min(kw * rule["per_kw"], rule["cap"])), rule
    if rule["kind"] == "flat_matching":
        return float(min(rule["amount"], central)), rule
    raise ValueError(f"Unknown top-up kind {rule['kind']}")


def compute_subsidy(
    kw: float,
    state: str | None,
    *,
    residential: bool = True,
    rwa_houses: int | None = None,
    previous_subsidy: bool | None = None,
    include_state_topup: bool = True,
    include_unconfirmed_topup: bool = False,
) -> SubsidyResult:
    special = is_special_category(state)
    notes: list[str] = []
    if residential is False:
        return SubsidyResult(central=0, state_topup=0, state_topup_status=None, state_topup_included=False, total=0,
                             special_category=special, mode="none", eligible_kw=0, notes=["NON_RESIDENTIAL_NO_CFA"])
    if rwa_houses:
        eligible = rwa_eligible_kw(kw, rwa_houses)
        central = rwa_cfa(kw, rwa_houses, special)
        if eligible < kw:
            notes.append("RWA_CFA_CAPPED")
        return SubsidyResult(central=central, state_topup=0, state_topup_status=None, state_topup_included=False,
                             total=central, special_category=special, mode="rwa", eligible_kw=eligible, notes=notes)
    if previous_subsidy:
        # Earlier subsidy holders only get CFA on extra capacity up to 3 kW in total. We don't know
        # their old size, so stay conservative and count none.
        return SubsidyResult(central=0, state_topup=0, state_topup_status=None, state_topup_included=False, total=0,
                             special_category=special, mode="none", eligible_kw=0,
                             notes=["PREVIOUS_SUBSIDY_TOPUP_ONLY"])
    central = central_cfa(kw, special)
    topup, rule = state_topup(state, kw, central)
    included = False
    if rule:
        confirmed = rule["status"] != "unconfirmed"
        included = include_state_topup and (confirmed or include_unconfirmed_topup)
        if not included:
            notes.append("STATE_TOPUP_UNCONFIRMED_EXCLUDED" if not confirmed else "STATE_TOPUP_EXCLUDED")
    if kw > C.FULL_SUBSIDY_KW:
        notes.append("CFA_CAPPED_AT_3KW")
    return SubsidyResult(
        central=central,
        state_topup=topup,
        state_topup_status=rule["status"] if rule else None,
        state_topup_included=included,
        total=round(central + (topup if included else 0), 2),
        special_category=special,
        mode="individual",
        eligible_kw=min(kw, C.FULL_SUBSIDY_KW),
        notes=notes,
    )


def subsidy_assumptions(state: str | None, result: SubsidyResult) -> list[Assumption]:
    src = f"MNRE PM Surya Ghar guidelines, OM 7 Jun 2024 ({C.MNRE_GUIDELINES_URL})"
    out = [
        Assumption(key="cfa_first_2kw", value=C.CFA_FIRST_2KW_PER_KW, unit="Rs/kW", source=src),
        Assumption(key="cfa_third_kw", value=C.CFA_THIRD_KW_PER_KW, unit="Rs/kW", source=src),
        Assumption(key="cfa_cap", value=C.CFA_CAP_SPECIAL if result.special_category else C.CFA_CAP, unit="Rs",
                   source=src),
    ]
    if result.special_category:
        out.append(Assumption(key="cfa_special_category_multiplier", value=C.CFA_SPECIAL_MULTIPLIER, source=src))
    if result.mode == "rwa":
        rate = C.CFA_RWA_PER_KW_SPECIAL if result.special_category else C.CFA_RWA_PER_KW
        out.append(Assumption(key="cfa_rwa_per_kw", value=rate, unit="Rs/kW",
                              source=src + "; on min(installed, 3 kW x houses, 500 kW)"))
    rule = C.STATE_TOPUPS.get(normalize_state(state) or "")
    if rule:
        out.append(Assumption(key="state_topup", value=result.state_topup if result.state_topup_included else 0,
                              unit="Rs", source=rule["source"] + ("" if result.state_topup_included else " (not counted)"),
                              status=rule["status"]))
    return out
