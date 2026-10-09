"""DISCOM tariff models: slab bills with fixed charges, surcharges and free-unit schemes.

Two models share one interface (`period_bill(units) -> BillBreakdown`):
- `SlabTariff`: a schedule from data/tariffs.json ("exact" or "estimate").
- `EffectiveRateTariff`: unknown DISCOM, rate = bill amount / units ("rough").
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from . import constants as C
from .models import Accuracy, Assumption, BillBreakdown, BillLine

DATA_PATH = Path(__file__).parent / "data" / "tariffs.json"


def r2(x: float) -> float:
    """Round half up to paise, the way bills print amounts."""
    return round(x + (1e-9 if x >= 0 else -1e-9), 2)


@lru_cache(maxsize=1)
def load_tariffs() -> dict:
    with DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- DISCOM lookup


def _alias_in(alias: str, text: str) -> bool:
    if alias.isascii():
        return re.search(rf"(?<![A-Z0-9]){re.escape(alias)}(?![A-Z0-9])", text) is not None
    return alias in text


def resolve_discom(
    discom_text: str | None, state: str | None = None, pincode: str | None = None
) -> tuple[str | None, str]:
    """Return (discom code or None, matched_from: 'bill' | 'state' | 'none')."""
    data = load_tariffs()
    if discom_text and discom_text.strip():
        text = discom_text.upper()
        for code, d in data["discoms"].items():
            if any(_alias_in(a.upper(), text) for a in d["aliases"]):
                return code, "bill"
        # A DISCOM is printed but we don't model it: don't guess from the state.
        return None, "none"
    if state:
        code = data["state_defaults"].get(normalize_state(state))
        if code == "MSEDCL" and pincode and pincode.startswith("400"):
            return None, "none"
        if code:
            return code, "state"
    return None, "none"


_STATE_ALIASES = {
    "NCT OF DELHI": "Delhi",
    "NEW DELHI": "Delhi",
    "DELHI": "Delhi",
    "UP": "Uttar Pradesh",
    "TN": "Tamil Nadu",
    "MH": "Maharashtra",
    "KA": "Karnataka",
    "J&K": "Jammu and Kashmir",
    "JAMMU & KASHMIR": "Jammu and Kashmir",
    "JAMMU AND KASHMIR": "Jammu and Kashmir",
    "ANDAMAN & NICOBAR ISLANDS": "Andaman and Nicobar Islands",
    "ANDAMAN AND NICOBAR": "Andaman and Nicobar Islands",
    "ANDAMAN & NICOBAR": "Andaman and Nicobar Islands",
    "ORISSA": "Odisha",
    "PONDICHERRY": "Puducherry",
    "UTTARANCHAL": "Uttarakhand",
}


def normalize_state(state: str | None) -> str | None:
    """Canonical English state name ('NCT of Delhi' -> 'Delhi', 'tamil nadu' -> 'Tamil Nadu')."""
    if not state:
        return None
    words = state.strip().split()
    key = " ".join(words).upper()
    if key in _STATE_ALIASES:
        return _STATE_ALIASES[key]
    return " ".join(w.lower() if w.lower() == "and" else w.capitalize() for w in words)


# ---------------------------------------------------------------- models


class TariffModel(Protocol):
    code: str
    accuracy: Accuracy
    period_months: int

    def period_bill(self, units: float) -> BillBreakdown: ...

    def export_rate(self, system_kw: float) -> tuple[float, str]: ...

    def assumptions(self) -> list[Assumption]: ...


def slab_energy(units: float, slabs: list[dict]) -> float:
    """Telescopic energy charge. slabs = [{'up_to': N | None, 'rate': r}, ...]."""
    total, lo = 0.0, 0.0
    for s in slabs:
        if units <= lo:
            break
        hi = s["up_to"] if s["up_to"] is not None else float("inf")
        total += r2((min(units, hi) - lo) * s["rate"])
        lo = hi
    return r2(total)


class SlabTariff:
    def __init__(
        self,
        discom: str,
        sanctioned_kw: float | None = None,
        phase: str | None = None,
        apply_free_units: bool | None = None,
        free_units_entitlement: float | None = None,
        overrides: dict[str, float] | None = None,
    ):
        data = load_tariffs()
        if discom in data["discoms"]:
            self.code = discom
            self.discom = data["discoms"][discom]
            self.schedule_code = self.discom["schedule"]
        elif discom in data["schedules"]:  # allow passing a schedule directly
            self.code = self.schedule_code = discom
            self.discom = {"name": discom, "state": None}
        else:
            raise KeyError(f"Unknown DISCOM or schedule: {discom}")
        self.s = data["schedules"][self.schedule_code]
        self.accuracy: Accuracy = self.s["accuracy"]
        self.period_months = 2 if self.s["billing_cycle"] == "bimonthly" else 1
        self.sanctioned_kw_given = sanctioned_kw is not None
        self.sanctioned_kw = sanctioned_kw if sanctioned_kw else C.DEFAULT_SANCTIONED_KW
        self.phase = phase or "single"
        self.overrides = dict(overrides or {})
        rule = self.s.get("free_units")
        self.free_rule = rule
        self.free_on = bool(rule) and (rule.get("default_on", True) if apply_free_units is None else apply_free_units)
        self.entitlement = free_units_entitlement

    # -- pieces

    def fixed_charge(self) -> float:
        fc = self.s["fixed_charge"]
        basis = fc["basis"]
        if basis == "none":
            per_month = 0.0
        elif basis == "per_phase":
            per_month = fc["three"] if self.phase == "three" else fc["single"]
        elif basis == "per_kw":
            per_month = max(self.sanctioned_kw, fc.get("min_kw", 0)) * fc["rate"]
        elif basis == "per_kw_band":
            rate = next(b["rate"] for b in fc["bands"] if b["up_to_kw"] is None or self.sanctioned_kw <= b["up_to_kw"])
            per_month = self.sanctioned_kw * rate
        else:
            raise ValueError(f"Unknown fixed charge basis {basis}")
        return r2(per_month * self.period_months)

    def _charges(self, units: float, fixed: float, energy: float) -> list[BillLine]:
        values = {"fixed": fixed, "energy": energy}
        lines = []
        for ch in self.s["charges"]:
            rate = self.overrides.get(ch["code"], ch["rate"])
            if ch["kind"] == "pct":
                amt = r2(rate * sum(values[b] for b in ch["base"]))
            elif ch["kind"] == "per_unit":
                amt = r2(rate * units)
            else:
                raise ValueError(f"Unknown charge kind {ch['kind']}")
            values[ch["code"]] = amt
            lines.append(BillLine(code=ch["code"], label=f"{ch['label']} @ {_fmt_rate(ch, rate)}", amount=amt))
        return lines

    def _gross(self, units: float, fixed: float, energy: float) -> tuple[list[BillLine], float]:
        charges = self._charges(units, fixed, energy)
        return charges, r2(fixed + energy + sum(c.amount for c in charges))

    def _free_units(self, units: float) -> float:
        rule = self.free_rule
        tier = next(t for t in rule["tiers"] if t["up_to"] is None or units <= t["up_to"])
        free = float(tier["free_units"])
        if self.entitlement is not None and rule.get("entitlement"):
            free = min(free, self.entitlement * self.period_months)
        return min(free, units)

    # -- the bill

    def period_bill(self, units: float) -> BillBreakdown:
        units = max(0.0, float(units))
        fixed = self.fixed_charge()
        energy = slab_energy(units, self.s["energy_slabs"])
        charges, gross = self._gross(units, fixed, energy)
        lines = [
            BillLine(code="FIXED", label="Fixed charges", amount=fixed),
            BillLine(code="ENERGY", label="Energy charges", amount=energy),
            *charges,
        ]
        subsidy, free_applied = 0.0, 0.0
        rule = self.free_rule if self.free_on else None
        if rule and rule["kind"] == "band_waiver":
            band = next(b for b in rule["bands"] if b["up_to"] is None or units <= b["up_to"])
            if band["waive"] == "bill":
                subsidy = gross
            elif band["waive"] == "energy_share":
                subsidy = min(r2(band["share"] * energy), band.get("cap_rs", float("inf")))
            if subsidy:
                free_applied = units if band["waive"] == "bill" else 0.0
        elif rule and rule["kind"] == "free_units":
            free_applied = self._free_units(units)
            if free_applied > 0:
                energy_after = r2(energy - slab_energy(free_applied, self.s["energy_slabs"]))
                fixed_after = r2(fixed * (1 - free_applied / units)) if rule.get("prorate_fixed") and units else fixed
                _, gross_after = self._gross(units, fixed_after, energy_after)
                subsidy = r2(gross - gross_after)
        if subsidy:
            lines.append(BillLine(code="SUBSIDY", label=rule["label"], amount=-subsidy))
        return BillBreakdown(
            discom=self.code,
            units=units,
            period_units=units,
            period_months=self.period_months,
            fixed=fixed,
            energy=energy,
            lines=lines,
            gross=gross,
            subsidy=subsidy,
            net=r2(max(0.0, gross - subsidy)),
            free_units_applied=free_applied,
            accuracy=self.accuracy,
        )

    def export_rate(self, system_kw: float) -> tuple[float, str]:
        nm = self.s["net_metering"]
        if "EXPORT_RATE" in self.overrides:
            return self.overrides["EXPORT_RATE"], "user"
        if nm.get("by_size"):
            rate = next(b["rate"] for b in nm["by_size"] if b["up_to_kw"] is None or system_kw <= b["up_to_kw"])
            return rate, nm["status"]
        return nm["export_rate_rs_per_kwh"], nm["status"]

    def assumptions(self) -> list[Assumption]:
        s, src = self.s, self.s["source_url"]
        out = [
            Assumption(key="tariff_schedule", value=s["label"], source=f"{src} (as of {s['as_of']})",
                       status="official" if self.accuracy == "exact" else "reported"),
            Assumption(key="energy_slabs", value=_slab_text(s["energy_slabs"]),
                       unit="Rs/kWh per " + ("2-month bill" if self.period_months == 2 else "month"), source=src,
                       status="official" if self.accuracy == "exact" else "reported"),
        ]
        fc = s["fixed_charge"]
        if fc["basis"] != "none":
            out.append(Assumption(key="fixed_charge", value=_fixed_text(fc), unit="Rs/month", source=src,
                                  status="official" if self.accuracy == "exact" else "reported"))
            if not self.sanctioned_kw_given and fc["basis"] in ("per_kw", "per_kw_band"):
                out.append(Assumption(key="sanctioned_load_assumed", value=self.sanctioned_kw, unit="kW",
                                      source="Not on the bill; assumed (affects fixed charges only)", status="default"))
        for ch in s["charges"]:
            rate = self.overrides.get(ch["code"], ch["rate"])
            out.append(Assumption(key=f"charge_{ch['code'].lower()}", value=rate,
                                  unit="fraction" if ch["kind"] == "pct" else "Rs/kWh",
                                  source=ch.get("note") or src,
                                  status="user" if ch["code"] in self.overrides else ch.get("status", "official")))
        if self.free_rule:
            out.append(Assumption(key="free_units_scheme",
                                  value=f"{self.free_rule['label']}: {'on' if self.free_on else 'off'}",
                                  source=f"{self.free_rule['note']} ({self.free_rule.get('source_url', src)})",
                                  status="official" if self.accuracy == "exact" else "reported"))
            if self.free_on and self.entitlement is not None and self.free_rule.get("entitlement"):
                out.append(Assumption(key="free_units_entitlement", value=round(self.entitlement, 1), unit="kWh/month",
                                      source="Last year's average use + 10%, capped at 200", status="derived"))
        return out


class EffectiveRateTariff:
    """Unknown DISCOM: one flat rate from the user's own bill."""

    accuracy: Accuracy = "rough"
    period_months = 1

    def __init__(self, rate: float, rate_source: str, free_units_per_month: float | None = None, code: str = "UNKNOWN",
                 export_rate: float | None = None):
        self.code = code
        self.rate = rate
        self.rate_source = rate_source
        self.free_units = free_units_per_month or 0.0
        self._export = export_rate

    def period_bill(self, units: float) -> BillBreakdown:
        units = max(0.0, float(units))
        free = min(self.free_units, units)
        energy = r2(units * self.rate)
        subsidy = r2(free * self.rate)
        lines = [BillLine(code="ENERGY_EFFECTIVE", label=f"All charges at Rs {self.rate:.2f}/unit", amount=energy)]
        if subsidy:
            lines.append(BillLine(code="SUBSIDY", label="State free units", amount=-subsidy))
        return BillBreakdown(discom=self.code, units=units, period_units=units, period_months=1, fixed=0.0,
                             energy=energy, lines=lines, gross=energy, subsidy=subsidy, net=r2(energy - subsidy),
                             free_units_applied=free, accuracy="rough")

    def export_rate(self, system_kw: float) -> tuple[float, str]:
        if self._export is not None:
            return self._export, "user"
        fb = load_tariffs()["fallback"]
        return fb["export_rate_rs_per_kwh"], fb["export_rate_status"]

    def assumptions(self) -> list[Assumption]:
        out = [Assumption(key="effective_rate", value=round(self.rate, 2), unit="Rs/kWh", source=self.rate_source,
                          status="derived" if "bill" in self.rate_source else "default")]
        if self.free_units:
            out.append(Assumption(key="free_units_per_month", value=self.free_units, unit="kWh/month",
                                  source="Entered by the user", status="user"))
        return out


def effective_rate_tariff(
    bill_amount_rs: float | None,
    units: float | None,
    free_units_per_month: float | None = None,
    period_months: int = 1,
    export_rate: float | None = None,
) -> EffectiveRateTariff:
    """Rate = bill amount / billed units (net of any free units). Falls back to a national default."""
    free = (free_units_per_month or 0.0) * period_months
    if bill_amount_rs and units and units - free > 0:
        rate = bill_amount_rs / (units - free)
        return EffectiveRateTariff(rate, "Your bill: amount / units", free_units_per_month, export_rate=export_rate)
    fb = load_tariffs()["fallback"]
    return EffectiveRateTariff(fb["default_effective_rate_rs_per_kwh"], fb["default_effective_rate_note"],
                               free_units_per_month, export_rate=export_rate)


# ---------------------------------------------------------------- public helpers


def default_entitlement(discom: str, average_monthly_kwh: float) -> float | None:
    """Free-unit entitlement for schemes tied to past use (Gruha Jyothi: average + 10%, max 200)."""
    data = load_tariffs()
    rule = data["schedules"][data["discoms"][discom]["schedule"]].get("free_units") or {}
    ent = rule.get("entitlement")
    if not ent:
        return None
    return min(ent["cap"], average_monthly_kwh * ent["multiplier"])


def period_bill(discom: str, period_units: float, sanctioned_kw: float | None = None, phase: str | None = None,
                apply_subsidy: bool = True, **kw) -> BillBreakdown:
    """Bill for one billing period of the DISCOM (two months for bi-monthly DISCOMs)."""
    return SlabTariff(discom, sanctioned_kw, phase, apply_subsidy, **kw).period_bill(period_units)


def monthly_bill(discom: str, units: float, sanctioned_kw: float | None = None, phase: str | None = None,
                 apply_subsidy: bool = True, *, free_units_entitlement: float | None = None,
                 overrides: dict[str, float] | None = None) -> BillBreakdown:
    """Bill for one month of use.

    For bi-monthly DISCOMs the slabs and free units apply to the 2-month block, so
    the block is billed on 2 x units and halved (not billed as one month).
    """
    model = SlabTariff(discom, sanctioned_kw, phase, apply_subsidy, free_units_entitlement, overrides)
    b = model.period_bill(units * model.period_months)
    if model.period_months == 1:
        return b
    k = 1 / model.period_months
    return b.model_copy(update={
        "units": units,
        "fixed": r2(b.fixed * k),
        "energy": r2(b.energy * k),
        "lines": [BillLine(code=ln.code, label=ln.label, amount=r2(ln.amount * k)) for ln in b.lines],
        "gross": r2(b.gross * k),
        "subsidy": r2(b.subsidy * k),
        "net": r2(b.net * k),
        "free_units_applied": b.free_units_applied * k,
    })


def _fmt_rate(ch: dict, rate: float) -> str:
    return f"{rate * 100:g}%" if ch["kind"] == "pct" else f"Rs {rate:g}/unit"


def _slab_text(slabs: list[dict]) -> str:
    parts, lo = [], 0
    for s in slabs:
        hi = s["up_to"]
        parts.append(f"{lo + 1 if lo else 0}-{hi}: {s['rate']:.2f}" if hi is not None else f">{lo}: {s['rate']:.2f}")
        lo = hi
    return ", ".join(parts)


def _fixed_text(fc: dict) -> str:
    if fc["basis"] == "per_phase":
        return f"single-phase Rs {fc['single']}, three-phase Rs {fc['three']}"
    if fc["basis"] == "per_kw":
        return f"Rs {fc['rate']}/kW"
    if fc["basis"] == "per_kw_band":
        lo, parts = 0, []
        for b in fc["bands"]:
            hi = b["up_to_kw"]
            band = f">{lo}" if hi is None else f"{lo}-{hi}"
            parts.append(f"{band} kW: Rs {b['rate']}/kW")
            lo = hi
        return ", ".join(parts)
    return fc["basis"]
