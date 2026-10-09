"""Input and output models for the engine (pydantic v2).

`BillFields` mirrors the extraction schema in api/extract_prompt.py, so the
output of the bill reader can be passed in as-is (unknown keys are ignored).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Accuracy = Literal["exact", "estimate", "rough"]
CheckStatus = Literal["pass", "warn", "fail"]
VerdictCode = Literal["worth_it", "worth_it_with_loan", "not_now"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---------------------------------------------------------------- inputs


class HistoryPoint(_Model):
    month: str = Field(description="YYYY-MM; for bi-monthly bills, the end month of the period")
    units_kwh: float


class BillFields(_Model):
    is_electricity_bill: bool | None = True
    discom: str | None = None
    state: str | None = None
    consumer_number: str | None = None
    consumer_name: str | None = None
    tariff_category: str | None = None
    is_residential: bool | None = None
    sanctioned_load_kw: float | None = None
    connection_phase: Literal["single", "three"] | None = None
    billing_period_start: str | None = None
    billing_period_end: str | None = None
    billing_days: int | None = None
    billing_cycle: Literal["monthly", "bimonthly"] | None = None
    units_billed_kwh: float | None = None
    bill_amount_rs: float | None = None
    consumption_history: list[HistoryPoint] | None = None
    has_solar_net_meter: bool | None = None
    export_units_kwh: float | None = None
    meter_reading_type: Literal["actual", "estimated", "unknown"] | None = None
    pincode: str | None = None


class Location(_Model):
    pincode: str | None = None
    state: str | None = None
    district: str | None = None
    lat: float | None = None
    lon: float | None = None
    source: str | None = Field(default=None, description="geocoder used: nominatim | photon | state_capital")


class SolarResource(_Model):
    annual_kwh_per_kw: float
    monthly_kwh_per_kw: list[float] | None = Field(default=None, description="12 values, Jan..Dec")
    source: Literal["pvgis", "global_solar_atlas", "constant", "user"] = "constant"


class Answers(_Model):
    owns_roof: bool | None = None
    name_matches_bank: bool | None = None
    previous_solar_subsidy: bool | None = None


class Options(_Model):
    roof_area_m2: float | None = None
    system_kw: float | None = Field(default=None, description="Force a size (e.g. 'what if I install 2 kW?')")
    cost_per_kw: float | None = Field(default=None, description="Override the default market price per kW")
    apply_free_units: bool | None = Field(default=None, description="None = the DISCOM's default")
    free_units_entitlement: float | None = Field(default=None, description="Gruha Jyothi style entitlement, units/month")
    free_units_per_month: float | None = Field(default=None, description="Unknown DISCOM: free units the state gives")
    include_unconfirmed_topup: bool = False
    include_state_topup: bool = True
    tariff_overrides: dict[str, float] = Field(default_factory=dict, description="charge code -> rate, e.g. {'PPAC': 0.1819}")
    tariff_rise_pct: float | None = None
    degradation_pct: float | None = None
    shading_loss_pct: float = 0.0
    loan_rate_pct: float | None = None
    loan_years: int | None = None
    rwa_houses: int | None = Field(default=None, description="RWA / group housing mode: number of houses")


class PlanInput(_Model):
    bill: BillFields = Field(default_factory=BillFields)
    monthly_units: list[float] | float | None = Field(
        default=None, description="Manual entry: one average month, or 12 values Jan..Dec. Overrides the bill."
    )
    location: Location | None = None
    solar: SolarResource | None = None
    answers: Answers = Field(default_factory=Answers)
    options: Options = Field(default_factory=Options)


# ---------------------------------------------------------------- outputs


class BillLine(_Model):
    code: str
    label: str
    amount: float


class BillBreakdown(_Model):
    discom: str
    units: float = Field(description="Units this breakdown covers (one month for monthly_bill)")
    period_units: float = Field(description="Units in the billing period the slabs were applied to")
    period_months: int
    fixed: float
    energy: float
    lines: list[BillLine]
    gross: float
    subsidy: float
    net: float
    free_units_applied: float = 0.0
    accuracy: Accuracy


class Assumption(_Model):
    key: str
    value: float | str | None
    unit: str | None = None
    source: str
    status: Literal["official", "approx", "reported", "unconfirmed", "default", "derived", "user"] = "official"


class DiscomInfo(_Model):
    code: str | None
    name: str | None
    schedule: str | None
    state: str | None
    matched_from: Literal["bill", "state", "none"]
    accuracy: Accuracy
    billing_cycle: Literal["monthly", "bimonthly"]
    source_url: str | None = None
    as_of: str | None = None
    effective_rate_rs: float | None = Field(default=None, description="Fallback model only")


class ConsumptionProfile(_Model):
    monthly_kwh: list[float] = Field(description="12 values, Jan..Dec")
    annual_kwh: float
    average_monthly_kwh: float
    months_from_bill: int
    method: Literal["history", "seasonal_fill", "single_month", "manual"]
    flags: list[str] = Field(default_factory=list)


class SizingResult(_Model):
    ideal_kw: float
    recommended_kw: float
    caps_applied: list[str]
    cap_kw: float | None
    roof_area_needed_m2: float
    alternative_kw: float | None
    alternative_flags: list[str] = Field(default_factory=list)


class SubsidyResult(_Model):
    central: float
    state_topup: float
    state_topup_status: str | None
    state_topup_included: bool
    total: float
    special_category: bool
    mode: Literal["individual", "rwa", "none"]
    eligible_kw: float
    notes: list[str] = Field(default_factory=list)


class MonthRow(_Model):
    month: int = Field(description="1..12")
    units: float
    solar_kwh: float
    banked_kwh: float = Field(description="Surplus added to the net-metering bank this month")
    bank_used_kwh: float
    billed_units_after: float
    bill_before: float
    bill_after: float
    saving: float


class LoanView(_Model):
    loan_amount: float
    margin_amount: float
    rate_pct: float
    years: int
    emi: float
    monthly_saving: float
    emi_covered_by_saving: bool
    tier: Literal["upto_2_lakh", "above_2_lakh"]


class SystemOption(_Model):
    label: Literal["recommended", "full_subsidy_3kw", "custom"]
    kw: float
    cost_per_kw: float
    gross_cost: float
    subsidy: SubsidyResult
    net_cost: float
    annual_generation_kwh: float
    roof_area_needed_m2: float
    monthly: list[MonthRow]
    bill_before_year: float
    bill_after_year: float
    export_kwh: float
    export_income: float
    year1_savings: float
    monthly_saving_avg: float
    payback_years: float | None
    savings_25y: float
    net_gain_25y: float
    co2_kg_per_year: float
    trees_equivalent: float
    loan: LoanView
    flags: list[str] = Field(default_factory=list)


class Verdict(_Model):
    code: VerdictCode
    reasons: list[str] = Field(description="Machine-readable reason codes, most important first")


class ReadinessCheck(_Model):
    code: str
    status: CheckStatus
    reason: str
    fix: str | None = None


class Plan(_Model):
    engine_version: str
    accuracy: Accuracy
    accuracy_notes: list[str]
    discom: DiscomInfo
    state: str | None
    special_category: bool
    location: Location | None
    consumption: ConsumptionProfile
    solar: SolarResource
    sizing: SizingResult
    recommended: SystemOption
    alternative: SystemOption | None
    verdict: Verdict
    readiness: list[ReadinessCheck]
    assumptions: list[Assumption]
    warnings: list[str]
