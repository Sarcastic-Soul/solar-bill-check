"""Month-by-month savings with net metering, long-term savings, loan and CO2."""

from __future__ import annotations

from dataclasses import dataclass

from . import constants as C
from .models import LoanView, MonthRow, SolarResource
from .tariffs import TariffModel, r2


def solar_monthly(kw: float, solar: SolarResource, shading_loss_pct: float = 0.0) -> list[float]:
    """kWh generated each month (Jan..Dec) by a `kw` system."""
    keep = 1 - max(0.0, min(shading_loss_pct, 100.0)) / 100
    if solar.monthly_kwh_per_kw and len(solar.monthly_kwh_per_kw) == 12:
        per_kw = solar.monthly_kwh_per_kw
        # Scale so the months add up to the annual figure (PVGIS E_m already does; GSA may not).
        total = sum(per_kw)
        if total > 0:
            per_kw = [x * solar.annual_kwh_per_kw / total for x in per_kw]
    else:
        per_kw = [solar.annual_kwh_per_kw / 12] * 12
    return [kw * x * keep for x in per_kw]


def settlement_periods(period_months: int) -> list[list[int]]:
    """Billing periods as lists of month numbers, in settlement-year order (April first)."""
    order = [(C.SETTLEMENT_START_MONTH - 1 + i) % 12 + 1 for i in range(12)]
    return [order[i:i + period_months] for i in range(0, 12, period_months)]


@dataclass
class YearResult:
    rows: list[MonthRow]  # Jan..Dec
    bill_before: float
    bill_after: float
    export_kwh: float
    export_income: float

    @property
    def bill_saving(self) -> float:
        return self.bill_before - self.bill_after

    @property
    def total_saving(self) -> float:
        return self.bill_saving + self.export_income


def simulate_year(
    tariff: TariffModel, units: list[float], solar: list[float], export_rate: float
) -> YearResult:
    """Net metering: surplus goes into a bank that offsets later bills; what's left at
    the end of the settlement year is paid at the export rate."""
    rows: dict[int, MonthRow] = {}
    bank = 0.0
    for months in settlement_periods(tariff.period_months):
        u = sum(units[m - 1] for m in months)
        s = sum(solar[m - 1] for m in months)
        before = tariff.period_bill(u).net
        net = u - s
        if net >= 0:
            used = min(bank, net)
            bank -= used
            billed, banked = net - used, 0.0
        else:
            used, billed, banked = 0.0, 0.0, -net
            bank += banked
        after = tariff.period_bill(billed).net
        k = len(months)
        for m in months:
            rows[m] = MonthRow(
                month=m,
                units=round(units[m - 1], 1),
                solar_kwh=round(solar[m - 1], 1),
                banked_kwh=round(banked / k, 1),
                bank_used_kwh=round(used / k, 1),
                billed_units_after=round(billed / k, 1),
                bill_before=r2(before / k),
                bill_after=r2(after / k),
                saving=r2((before - after) / k),
            )
    ordered = [rows[m] for m in range(1, 13)]
    return YearResult(
        rows=ordered,
        bill_before=r2(sum(r.bill_before for r in ordered)),
        bill_after=r2(sum(r.bill_after for r in ordered)),
        export_kwh=round(bank, 1),
        export_income=r2(bank * export_rate),
    )


def lifetime_savings(
    tariff: TariffModel,
    units: list[float],
    solar: list[float],
    export_rate: float,
    years: int = C.LIFETIME_YEARS,
    degradation_pct: float = C.PANEL_DEGRADATION_PCT,
    tariff_rise_pct: float = C.TARIFF_RISE_PCT,
) -> float:
    """Sum of yearly savings. Panels lose `degradation_pct` a year; bill savings grow with
    the tariff (export rate kept flat, which is conservative)."""
    total = 0.0
    for y in range(years):
        keep = (1 - degradation_pct / 100) ** y
        yr = simulate_year(tariff, units, [s * keep for s in solar], export_rate)
        total += yr.bill_saving * (1 + tariff_rise_pct / 100) ** y + yr.export_income
    return r2(total)


def payback_years(net_cost: float, yearly_saving: float, max_years: float = C.LIFETIME_YEARS) -> float | None:
    """Simple payback. None when it never pays back within the panels' life."""
    if yearly_saving <= 0:
        return None
    years = round(max(0.0, net_cost) / yearly_saving, 1)
    return years if years <= max_years else None


def emi(principal: float, rate_pct: float, years: int) -> float:
    n = years * 12
    r = rate_pct / 100 / 12
    if principal <= 0:
        return 0.0
    if r == 0:
        return r2(principal / n)
    return r2(principal * r * (1 + r) ** n / ((1 + r) ** n - 1))


def loan_view(gross_cost: float, monthly_saving: float, rate_pct: float | None = None,
              years: int | None = None) -> LoanView:
    """Jan Samarth concessional loan: up to Rs 2 lakh at about 6% with 10% margin;
    above that, home-loan-like rate with 20% margin."""
    years = years or C.LOAN_YEARS
    loan = gross_cost * (1 - C.LOAN_TIER1_MARGIN)
    if loan <= C.LOAN_TIER1_MAX_RS:
        tier, margin, rate = "upto_2_lakh", C.LOAN_TIER1_MARGIN, C.LOAN_TIER1_RATE_PCT
    else:
        tier, margin, rate = "above_2_lakh", C.LOAN_TIER2_MARGIN, C.LOAN_TIER2_RATE_PCT
        loan = gross_cost * (1 - margin)
    rate = rate if rate_pct is None else rate_pct
    e = emi(loan, rate, years)
    return LoanView(loan_amount=r2(loan), margin_amount=r2(gross_cost - loan), rate_pct=rate, years=years, emi=e,
                    monthly_saving=r2(monthly_saving), emi_covered_by_saving=e <= monthly_saving, tier=tier)


def co2_kg(kwh: float) -> float:
    return round(kwh * C.CO2_KG_PER_KWH, 1)


def trees(kg_co2: float) -> float:
    return round(kg_co2 / C.KG_CO2_PER_TREE_YEAR, 1)
