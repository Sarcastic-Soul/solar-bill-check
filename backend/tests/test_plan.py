import pytest
from conftest import DELHI_SOLAR, PUNE_SOLAR

from engine import PlanError, build_plan, build_plan_dict


def plan(bill, solar=None, **kw):
    return build_plan({"bill": bill, "solar": solar, **kw})


def delhi(units, load=3.0):
    return {"discom": "BSES Rajdhani Power Limited (BRPL)", "state": "Delhi", "is_residential": True,
            "units_billed_kwh": units, "sanctioned_load_kw": load, "connection_phase": "single"}


def test_delhi_180_units_not_worth_it():
    p = plan(delhi(180), DELHI_SOLAR)
    assert p.recommended.bill_before_year == 0
    assert p.verdict.code == "not_now"
    assert p.verdict.reasons[0] == "FREE_UNITS_BAND"
    assert p.discom.accuracy == "exact"


def test_delhi_450_units():
    p = plan(delhi(450, load=5), DELHI_SOLAR)
    r = p.recommended
    assert r.kw == 3.5
    # Solar takes net use under 200 units, where Delhi's subsidy makes the bill zero
    assert r.bill_after_year == 0
    assert r.year1_savings == pytest.approx(r.bill_before_year + r.export_income)
    assert p.verdict.code == "worth_it"
    assert r.payback_years < 6


def test_msedcl_350_units_good_payback():
    bill = {"discom": "MSEDCL", "state": "Maharashtra", "is_residential": True, "units_billed_kwh": 350,
            "sanctioned_load_kw": 3, "connection_phase": "single", "pincode": "411001"}
    p = plan(bill, PUNE_SOLAR)
    r = p.recommended
    assert r.kw == 3.0
    assert r.subsidy.total == 78_000 and r.net_cost == 186_000 - 78_000
    assert 1.5 < r.payback_years < 3.5
    assert p.verdict.code == "worth_it" and p.verdict.reasons[0] == "PAYBACK_SHORT"
    assert r.loan.emi_covered_by_saving
    assert p.alternative is None  # recommended is already 3 kW
    assert p.discom.accuracy == "exact"
    assert p.accuracy == "estimate"  # one month repeated for the whole year


def test_uppcl_300_units_with_state_topup():
    bill = {"discom": "Madhyanchal Vidyut Vitran Nigam Ltd. (MVVNL), UPPCL", "state": "Uttar Pradesh",
            "is_residential": True, "units_billed_kwh": 300, "sanctioned_load_kw": 3}
    p = plan(bill, {"annual_kwh_per_kw": 1500, "source": "pvgis"})
    r = p.recommended
    assert p.discom.code == "UPPCL"
    assert r.kw == 2.5
    assert r.subsidy.central == 69_000 and r.subsidy.state_topup == 30_000 and r.subsidy.total == 99_000
    assert p.verdict.code == "worth_it"
    assert any(a.key == "state_topup" and a.status == "reported" for a in p.assumptions)


def test_tnpdcl_bimonthly_from_mock_bill(label):
    p = plan(label("tnpdcl-tamil-bimonthly-01"), {"annual_kwh_per_kw": 1500, "source": "pvgis"})
    assert p.discom.code == "TNPDCL" and p.discom.billing_cycle == "bimonthly"
    assert p.discom.accuracy == "estimate" and p.accuracy == "estimate"
    assert "BIMONTHLY_SPLIT" in p.consumption.flags
    r = p.recommended
    # Rows in a 2-month block share the block's bill equally
    assert r.monthly[7].bill_before == r.monthly[8].bill_before
    assert r.bill_before_year > 0 and r.year1_savings > 0
    assert "TARIFF_ESTIMATE" in p.verdict.reasons


def test_special_category_state_unknown_discom():
    bill = {"discom": "Uttarakhand Power Corporation Ltd (UPCL)", "state": "Uttarakhand", "is_residential": True,
            "units_billed_kwh": 320, "bill_amount_rs": 2080, "sanctioned_load_kw": 4}
    p = plan(bill)
    assert p.special_category
    assert p.discom.code is None and p.discom.accuracy == "rough"
    assert p.discom.effective_rate_rs == pytest.approx(6.5)
    assert "DISCOM_NOT_MODELLED" in p.warnings
    r = p.recommended
    assert r.kw == 2.5  # 3,840 kWh / 1,450
    assert r.subsidy.special_category and r.subsidy.total == pytest.approx((60_000 + 9_000) * 1.1)
    assert p.alternative.subsidy.total == pytest.approx(85_800)
    assert "YIELD_NATIONAL_DEFAULT" in p.accuracy_notes


def test_rwa_mode():
    bill = {"discom": "MSEDCL", "state": "Maharashtra", "is_residential": True, "units_billed_kwh": 6000,
            "sanctioned_load_kw": 60, "connection_phase": "three"}
    p = plan(bill, PUNE_SOLAR, options={"rwa_houses": 10})
    r = p.recommended
    assert r.kw > 10  # no 10 kW cap in RWA mode
    assert r.subsidy.mode == "rwa"
    assert r.subsidy.eligible_kw == 30  # 3 kW x 10 houses
    assert r.subsidy.total == 30 * 18_000
    assert p.alternative is None


def test_sanctioned_load_cap():
    p = plan(delhi(800, load=2), DELHI_SOLAR)
    assert p.sizing.ideal_kw > 6
    assert p.recommended.kw == 2.0
    assert "LOAD_CAP" in p.sizing.caps_applied and "LOAD_CAP" in p.verdict.reasons
    assert p.alternative.kw == 3.0 and "NEEDS_LOAD_INCREASE" in p.alternative.flags
    load = next(c for c in p.readiness if c.code == "SANCTIONED_LOAD")
    assert load.status == "pass"  # 2 kW system fits a 2 kW load


def test_unknown_discom_fallback(label):
    p = plan(label("tatapower-mumbai-nohistory-01"), PUNE_SOLAR)
    assert p.discom.code is None and p.discom.matched_from == "none"
    assert p.discom.effective_rate_rs == pytest.approx(2156 / 218, abs=0.01)
    assert p.accuracy == "rough"
    assert "SINGLE_MONTH_REPEATED" in p.accuracy_notes
    assert p.verdict.reasons[-1] == "TARIFF_ROUGH"


def test_unknown_discom_with_state_free_units():
    bill = {"discom": "Some Other DISCOM", "state": "Punjab", "is_residential": True, "units_billed_kwh": 250,
            "bill_amount_rs": 400}
    p = plan(bill, options={"free_units_per_month": 300})
    # 250 units against 300 free: the bill is covered by free units, so solar can't save much
    assert p.verdict.code == "not_now" and p.verdict.reasons[0] == "FREE_UNITS_BAND"


def test_already_solar(label):
    p = plan(label("adani-mumbai-solar-english-01"), PUNE_SOLAR)
    assert p.verdict.code == "not_now" and p.verdict.reasons[0] == "ALREADY_SOLAR"
    assert "ALREADY_HAS_SOLAR" in p.warnings
    assert any(c.code == "NO_EXISTING_SOLAR" and c.status == "warn" for c in p.readiness)


def test_non_residential(label):
    p = plan(label("tgspdcl-telugu-commercial-01"))
    assert p.verdict.code == "not_now" and p.verdict.reasons[0] == "NON_RESIDENTIAL"
    assert p.recommended.subsidy.total == 0
    assert any(c.code == "RESIDENTIAL" and c.status == "fail" for c in p.readiness)


def test_delhi_mock_bill_full_plan(label):
    p = plan(label("delhi-brpl-hindi-clean-01"), DELHI_SOLAR,
             answers={"owns_roof": True, "name_matches_bank": True, "previous_solar_subsidy": False})
    assert p.discom.code == "BRPL" and p.discom.matched_from == "bill"
    assert p.consumption.method == "seasonal_fill" and p.consumption.months_from_bill == 7
    assert p.consumption.monthly_kwh[8] == 342  # current bill, September
    assert p.sizing.ideal_kw == pytest.approx(2.29, abs=0.01)  # 3,562 kWh/yr / 1,553
    assert p.recommended.kw == 2.5  # nearest 0.5 kW
    assert p.alternative.kw == 3.0
    assert p.verdict.code in ("worth_it", "worth_it_with_loan")
    assert all(c.status == "pass" for c in p.readiness)
    keys = {a.key for a in p.assumptions}
    assert {"tariff_schedule", "charge_ppac", "free_units_scheme", "export_rate", "cfa_first_2kw", "cost_per_kw",
            "solar_yield", "co2_factor", "co2_per_tree", "tariff_rise", "panel_degradation", "loan_rate"} <= keys


def test_custom_size_and_overrides():
    p = plan(delhi(450, load=5), DELHI_SOLAR,
             options={"system_kw": 2, "cost_per_kw": 60_000, "tariff_overrides": {"PPAC": 0.1819}})
    assert p.recommended.label == "custom" and p.recommended.kw == 2
    assert p.recommended.gross_cost == 120_000
    assert p.alternative.label == "recommended" and p.alternative.kw == 3.5
    assert any(a.key == "charge_ppac" and a.status == "user" for a in p.assumptions)


def test_co2_and_trees():
    p = plan(delhi(450, load=5), DELHI_SOLAR)
    r = p.recommended
    assert r.co2_kg_per_year == pytest.approx(r.annual_generation_kwh * 0.71, abs=0.1)
    assert r.trees_equivalent == pytest.approx(r.co2_kg_per_year / 21, abs=0.1)


def test_errors_and_json_entry():
    with pytest.raises(PlanError) as e:
        build_plan({"bill": {"is_electricity_bill": False}})
    assert e.value.code == "NOT_ELECTRICITY_BILL"
    with pytest.raises(PlanError):
        build_plan({"bill": {"discom": "BRPL"}})
    out = build_plan_dict({"bill": delhi(300), "solar": DELHI_SOLAR})
    assert out["verdict"]["code"] in ("worth_it", "worth_it_with_loan", "not_now")
    assert len(out["recommended"]["monthly"]) == 12


def test_manual_units_without_bill():
    p = build_plan({"bill": {"state": "Maharashtra"}, "monthly_units": 400, "location": {"pincode": "411001"},
                    "solar": PUNE_SOLAR})
    assert p.discom.code == "MSEDCL" and p.discom.matched_from == "state"
    assert p.consumption.method == "manual"
