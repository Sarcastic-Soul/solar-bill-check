"""`build_plan(PlanInput) -> Plan`: the one entry point for the Lambda and the chat agent tools.

Pure: no network. Location and solar yield are resolved beforehand (see fetchers.py)
and passed in; without them the national yield fallback is used.
"""

from __future__ import annotations

from typing import Any

from . import constants as C
from .models import (
    Accuracy,
    Assumption,
    DiscomInfo,
    Plan,
    PlanInput,
    SolarResource,
    SystemOption,
)
from .readiness import check_readiness
from .savings import (
    settlement_periods,
    co2_kg,
    lifetime_savings,
    loan_view,
    payback_years,
    simulate_year,
    solar_monthly,
    trees,
)
from .sizing import cost_per_kw, is_bimonthly, normalize_consumption, size_system
from .subsidy import compute_subsidy, is_special_category, subsidy_assumptions
from .tariffs import (
    EffectiveRateTariff,
    SlabTariff,
    TariffModel,
    default_entitlement,
    effective_rate_tariff,
    load_tariffs,
    normalize_state,
    r2,
    resolve_discom,
)
from .verdict import decide, free_units_band


class PlanError(ValueError):
    """Raised when no plan can be built. `code` is machine-readable."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


_ACCURACY_ORDER: list[Accuracy] = ["exact", "estimate", "rough"]


def _worse(a: Accuracy, b: Accuracy) -> Accuracy:
    return max(a, b, key=_ACCURACY_ORDER.index)


def build_plan(inp: PlanInput | dict[str, Any]) -> Plan:
    if not isinstance(inp, PlanInput):
        inp = PlanInput.model_validate(inp)
    bill, opts, answers = inp.bill, inp.options, inp.answers
    warnings: list[str] = []

    if bill.is_electricity_bill is False and inp.monthly_units is None:
        raise PlanError("NOT_ELECTRICITY_BILL")

    # -- where
    bill_state = normalize_state(bill.state)
    loc_state = normalize_state(inp.location.state) if inp.location else None
    state = bill_state or loc_state
    if bill_state and loc_state and bill_state != loc_state:
        warnings.append("STATE_MISMATCH_PINCODE_VS_BILL")
    pincode = bill.pincode or (inp.location.pincode if inp.location else None)

    # -- how much they use
    try:
        consumption = normalize_consumption(bill, inp.monthly_units, state)
    except ValueError as e:
        raise PlanError("NO_CONSUMPTION") from e
    units = consumption.monthly_kwh

    # -- tariff
    residential = bill.is_residential is not False
    code, matched = resolve_discom(bill.discom, state, pincode)
    tariff: TariffModel
    discom_info: DiscomInfo
    if code and residential:
        entitlement = opts.free_units_entitlement
        if entitlement is None:
            entitlement = default_entitlement(code, consumption.average_monthly_kwh)
        tariff = SlabTariff(code, bill.sanctioned_load_kw, bill.connection_phase, opts.apply_free_units, entitlement,
                            opts.tariff_overrides)
        accuracy: Accuracy = tariff.accuracy
        if code == "UPPCL" and bill.tariff_category and any(
            w in bill.tariff_category.lower() for w in ("rural", "ग्रामीण")
        ):
            accuracy = _worse(accuracy, "estimate")
            warnings.append("UP_RURAL_TARIFF_NOT_MODELLED")
        d = load_tariffs()["discoms"][code]
        s = tariff.s
        discom_info = DiscomInfo(code=code, name=d["name"], schedule=tariff.schedule_code, state=d["state"],
                                 matched_from=matched, accuracy=accuracy, billing_cycle=s["billing_cycle"],
                                 source_url=s["source_url"], as_of=s["as_of"])
        if is_bimonthly(bill) != (tariff.period_months == 2) and inp.monthly_units is None and bill.billing_cycle:
            warnings.append("BILLING_CYCLE_DIFFERS_FROM_DISCOM")
    else:
        if not residential:
            warnings.append("NON_RESIDENTIAL_TARIFF_FROM_BILL")
        elif bill.discom:
            warnings.append("DISCOM_NOT_MODELLED")
        period_months = 2 if is_bimonthly(bill) else 1
        tariff = effective_rate_tariff(bill.bill_amount_rs, bill.units_billed_kwh, opts.free_units_per_month,
                                       period_months, opts.tariff_overrides.get("EXPORT_RATE"))
        if "bill" not in tariff.rate_source:
            warnings.append("DEFAULT_EFFECTIVE_RATE")
        accuracy = "rough"
        discom_info = DiscomInfo(code=code, name=bill.discom, schedule=None, state=state, matched_from=matched,
                                 accuracy="rough", billing_cycle="bimonthly" if period_months == 2 else "monthly",
                                 effective_rate_rs=round(tariff.rate, 2))
    if bill.has_solar_net_meter:
        warnings.append("ALREADY_HAS_SOLAR")
    if "ESTIMATED_READING" in consumption.flags:
        warnings.append("ESTIMATED_READING")

    # -- sun
    solar = inp.solar or SolarResource(annual_kwh_per_kw=C.DEFAULT_YIELD_KWH_PER_KW, source="constant")

    # -- size
    rwa = bool(opts.rwa_houses)
    sizing = size_system(consumption.annual_kwh, solar.annual_kwh_per_kw, bill.sanctioned_load_kw, opts.roof_area_m2,
                         rwa=rwa)

    tariff_rise = C.TARIFF_RISE_PCT if opts.tariff_rise_pct is None else opts.tariff_rise_pct
    degradation = C.PANEL_DEGRADATION_PCT if opts.degradation_pct is None else opts.degradation_pct

    def option(label: str, kw: float) -> SystemOption:
        cpk = cost_per_kw(kw, opts.cost_per_kw)
        gross = r2(kw * cpk)
        sub = compute_subsidy(kw, state, residential=residential, rwa_houses=opts.rwa_houses,
                              previous_subsidy=answers.previous_solar_subsidy,
                              include_state_topup=opts.include_state_topup,
                              include_unconfirmed_topup=opts.include_unconfirmed_topup)
        net_cost = r2(max(0.0, gross - sub.total))
        gen = solar_monthly(kw, solar, opts.shading_loss_pct)
        export_rate, _ = tariff.export_rate(kw)
        yr = simulate_year(tariff, units, gen, export_rate)
        total25 = lifetime_savings(tariff, units, gen, export_rate, degradation_pct=degradation,
                                   tariff_rise_pct=tariff_rise)
        saving = r2(yr.total_saving)
        annual_gen = round(sum(gen), 1)
        co2 = co2_kg(annual_gen)
        flags: list[str] = []
        if bill.sanctioned_load_kw is not None and kw > bill.sanctioned_load_kw:
            flags.append("NEEDS_LOAD_INCREASE")
        if opts.roof_area_m2 is not None and kw * C.ROOF_M2_PER_KW > opts.roof_area_m2:
            flags.append("EXCEEDS_ROOF_AREA")
        if not rwa and kw > C.MAX_AUTO_APPROVED_KW:
            flags.append("ABOVE_10KW_NEEDS_DISCOM_STUDY")
        if yr.export_kwh > 0:
            flags.append("SURPLUS_EXPORTED")
        return SystemOption(
            label=label, kw=kw, cost_per_kw=cpk, gross_cost=gross, subsidy=sub, net_cost=net_cost,
            annual_generation_kwh=annual_gen, roof_area_needed_m2=kw * C.ROOF_M2_PER_KW, monthly=yr.rows,
            bill_before_year=yr.bill_before, bill_after_year=yr.bill_after, export_kwh=yr.export_kwh,
            export_income=yr.export_income, year1_savings=saving, monthly_saving_avg=r2(saving / 12),
            payback_years=payback_years(net_cost, saving), savings_25y=total25, net_gain_25y=r2(total25 - net_cost),
            co2_kg_per_year=co2, trees_equivalent=trees(co2),
            loan=loan_view(gross, saving / 12, opts.loan_rate_pct, opts.loan_years), flags=flags,
        )

    if opts.system_kw:
        primary = option("custom", opts.system_kw)
        alternative = (option("recommended", sizing.recommended_kw)
                       if sizing.recommended_kw != opts.system_kw else None)
    else:
        primary = option("recommended", sizing.recommended_kw)
        alternative = option("full_subsidy_3kw", sizing.alternative_kw) if sizing.alternative_kw else None
        if alternative:
            alternative.flags = sizing.alternative_flags + [f for f in alternative.flags if f not in
                                                            sizing.alternative_flags]

    # -- verdict
    shares = []
    for months in settlement_periods(tariff.period_months):
        b = tariff.period_bill(sum(units[m - 1] for m in months))
        shares.append(b.subsidy / b.gross if b.gross > 0 else 1.0)
    in_band = free_units_band(shares) if _has_free_units(tariff) else False

    accuracy_notes: list[str] = []
    if accuracy != "exact":
        accuracy_notes.append("TARIFF_" + accuracy.upper())
    if consumption.method == "single_month" or "MANUAL_AVERAGE" in consumption.flags:
        accuracy_notes.append("SINGLE_MONTH_REPEATED")
        accuracy = _worse(accuracy, "estimate")
    elif consumption.method == "seasonal_fill":
        accuracy_notes.append("MONTHS_FILLED_SEASONAL")
    if solar.source == "constant":
        accuracy_notes.append("YIELD_NATIONAL_DEFAULT")
        accuracy = _worse(accuracy, "estimate")

    verdict = decide(
        payback_years=primary.payback_years,
        emi_covered=primary.loan.emi_covered_by_saving,
        is_residential=bill.is_residential,
        has_solar=bill.has_solar_net_meter,
        in_free_band=in_band,
        low_usage="LOW_USAGE" in consumption.flags,
        caps_applied=sizing.caps_applied if not opts.system_kw else [],
        previous_subsidy=answers.previous_solar_subsidy,
        accuracy=discom_info.accuracy,
    )

    readiness = check_readiness(bill, answers, primary.kw)
    assumptions = _assumptions(tariff, state, primary, solar, consumption.method, tariff_rise, degradation, opts)

    return Plan(
        engine_version=C.ENGINE_VERSION,
        accuracy=accuracy,
        accuracy_notes=accuracy_notes,
        discom=discom_info,
        state=state,
        special_category=is_special_category(state),
        location=inp.location,
        consumption=consumption,
        solar=solar,
        sizing=sizing,
        recommended=primary,
        alternative=alternative,
        verdict=verdict,
        readiness=readiness,
        assumptions=assumptions,
        warnings=list(dict.fromkeys(warnings)),
    )


def build_plan_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """JSON in, JSON out, for the Lambda handler and agent tools."""
    return build_plan(payload).model_dump(mode="json")


def _has_free_units(tariff: TariffModel) -> bool:
    if isinstance(tariff, SlabTariff):
        return tariff.free_on
    if isinstance(tariff, EffectiveRateTariff):
        return tariff.free_units > 0
    return False


def _assumptions(tariff: TariffModel, state: str | None, opt: SystemOption, solar: SolarResource, method: str,
                 tariff_rise: float, degradation: float, opts) -> list[Assumption]:
    out = list(tariff.assumptions())
    rate, status = tariff.export_rate(opt.kw)
    out.append(Assumption(key="export_rate", value=rate, unit="Rs/kWh",
                          source="Year-end surplus under net metering; " + _export_note(tariff), status=status))
    out += subsidy_assumptions(state, opt.subsidy)
    out.append(Assumption(key="cost_per_kw", value=opt.cost_per_kw, unit="Rs/kW",
                          source="Entered by you" if opts.cost_per_kw else C.COST_SOURCE,
                          status="user" if opts.cost_per_kw else "default"))
    yield_src = {
        "pvgis": "PVGIS 5.3 (EU JRC), optimal tilt, building-mounted, 14% losses",
        "global_solar_atlas": "Global Solar Atlas PVOUT (World Bank / Solargis)",
        "constant": C.YIELD_SOURCE_CONSTANT,
        "user": "Entered by you",
    }[solar.source]
    out.append(Assumption(key="solar_yield", value=round(solar.annual_kwh_per_kw, 1), unit="kWh/kW/year",
                          source=yield_src, status="default" if solar.source == "constant" else "official"))
    if opts.shading_loss_pct:
        out.append(Assumption(key="shading_loss", value=opts.shading_loss_pct, unit="%", source="Entered by you",
                              status="user"))
    out += [
        Assumption(key="roof_area_per_kw", value=C.ROOF_M2_PER_KW, unit="m2/kW",
                   source="MNRE: 10-12 m2 shadow-free area per kW"),
        Assumption(key="panel_degradation", value=degradation, unit="%/year", source="Typical module warranty",
                   status="default"),
        Assumption(key="tariff_rise", value=tariff_rise, unit="%/year", source="Our assumption for long-term savings",
                   status="default"),
        Assumption(key="lifetime", value=C.LIFETIME_YEARS, unit="years", source="Typical module warranty",
                   status="default"),
        Assumption(key="co2_factor", value=C.CO2_KG_PER_KWH, unit="kg/kWh", source=C.CO2_SOURCE),
        Assumption(key="co2_per_tree", value=C.KG_CO2_PER_TREE_YEAR, unit="kg/year", source=C.TREE_SOURCE,
                   status="default"),
        Assumption(key="loan_rate", value=opt.loan.rate_pct, unit="%/year", source=C.LOAN_SOURCE,
                   status="approx" if opt.loan.tier == "upto_2_lakh" else "default"),
        Assumption(key="loan_margin", value=round(opt.loan.margin_amount / opt.gross_cost, 2) if opt.gross_cost else 0,
                   unit="fraction", source=C.LOAN_SOURCE),
        Assumption(key="loan_years", value=opt.loan.years, unit="years", source=C.LOAN_SOURCE),
    ]
    if method == "seasonal_fill":
        out.append(Assumption(key="seasonal_fill", value="regional usage shape",
                              source="Missing months scaled from the months on your bill using a typical "
                                     "seasonal shape for your region", status="default"))
    return out


def _export_note(tariff: TariffModel) -> str:
    if isinstance(tariff, SlabTariff):
        return tariff.s["net_metering"]["note"]
    return load_tariffs()["fallback"]["export_rate_note"]
