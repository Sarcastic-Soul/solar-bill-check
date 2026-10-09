import pytest

from engine.models import BillFields, HistoryPoint
from engine.sizing import cost_per_kw, normalize_consumption, size_system
from engine.subsidy import (
    central_cfa,
    compute_subsidy,
    is_special_category,
    rwa_cfa,
    rwa_eligible_kw,
)

# ---------------------------------------------------------------- subsidy


@pytest.mark.parametrize("kw,expected", [(1, 30_000), (2, 60_000), (2.5, 69_000), (3, 78_000), (5, 78_000)])
def test_central_cfa(kw, expected):
    assert central_cfa(kw) == expected


@pytest.mark.parametrize("kw,expected", [(1, 33_000), (2, 66_000), (3, 85_800), (10, 85_800)])
def test_central_cfa_special_category(kw, expected):
    assert central_cfa(kw, special=True) == pytest.approx(expected)


def test_special_category_states():
    for s in ("Sikkim", "Uttarakhand", "Himachal Pradesh", "Jammu & Kashmir", "Ladakh", "Assam",
              "Andaman & Nicobar Islands", "Lakshadweep"):
        assert is_special_category(s), s
    assert not is_special_category("Delhi")
    assert compute_subsidy(3, "Uttarakhand").total == pytest.approx(85_800)


def test_rwa_cap():
    assert rwa_eligible_kw(400, houses=100) == 300  # 3 kW x 100 houses
    assert rwa_eligible_kw(800, houses=400) == 500  # hard cap
    assert rwa_eligible_kw(50, houses=100) == 50  # installed is lower
    assert rwa_cfa(800, 400) == 500 * 18_000
    assert rwa_cfa(800, 400, special=True) == 500 * 19_800
    r = compute_subsidy(400, "Delhi", rwa_houses=100)
    assert r.mode == "rwa" and r.total == 300 * 18_000 and "RWA_CFA_CAPPED" in r.notes


def test_state_topups():
    up = compute_subsidy(3, "Uttar Pradesh")
    assert up.state_topup == 30_000 and up.state_topup_included and up.total == 108_000
    assert compute_subsidy(1, "Uttar Pradesh").state_topup == 15_000
    delhi = compute_subsidy(3, "Delhi")
    assert delhi.state_topup_status == "unconfirmed"
    assert not delhi.state_topup_included and delhi.total == 78_000
    assert "STATE_TOPUP_UNCONFIRMED_EXCLUDED" in delhi.notes
    assert compute_subsidy(3, "Delhi", include_unconfirmed_topup=True).total == 156_000


def test_no_subsidy_cases():
    assert compute_subsidy(3, "Telangana", residential=False).total == 0
    prev = compute_subsidy(3, "Delhi", previous_subsidy=True)
    assert prev.total == 0 and "PREVIOUS_SUBSIDY_TOPUP_ONLY" in prev.notes


# ---------------------------------------------------------------- sizing


def test_size_rounding_and_minimum():
    assert size_system(4350, 1450).recommended_kw == 3.0
    assert size_system(5100, 1450).recommended_kw == 3.5  # 3.52 -> 3.5
    assert size_system(600, 1450).recommended_kw == 1.0  # minimum 1 kW


def test_sanctioned_load_cap():
    s = size_system(9000, 1450, sanctioned_kw=2.2)
    assert s.recommended_kw == 2.0
    assert "LOAD_CAP" in s.caps_applied
    assert s.alternative_kw == 3.0 and "NEEDS_LOAD_INCREASE" in s.alternative_flags


def test_roof_and_10kw_caps():
    s = size_system(9000, 1450, sanctioned_kw=10, roof_area_m2=42)
    assert s.recommended_kw == 4.0 and s.caps_applied == ["ROOF_CAP"]
    big = size_system(30000, 1450, sanctioned_kw=25)
    assert big.recommended_kw == 10.0 and big.caps_applied == ["MAX_10KW_CAP"]
    assert size_system(30000, 1450, sanctioned_kw=25, rwa=True).recommended_kw == 20.5
    tiny_roof = size_system(4350, 1450, roof_area_m2=25)
    assert tiny_roof.recommended_kw == 2.5 and tiny_roof.alternative_kw is None


def test_cost_per_kw_bands():
    assert cost_per_kw(1) == 70_000
    assert cost_per_kw(1.5) == 70_000
    assert cost_per_kw(2) == 65_000
    assert cost_per_kw(3) == 62_000
    assert cost_per_kw(5) == 62_000
    assert cost_per_kw(3, override=55_000) == 55_000


# ---------------------------------------------------------------- consumption


def test_single_month_repeated():
    p = normalize_consumption(BillFields(units_billed_kwh=250))
    assert p.monthly_kwh == [250] * 12 and p.method == "single_month"
    assert "SINGLE_MONTH_REPEATED" in p.flags


def test_full_history_12_months(label):
    p = normalize_consumption(BillFields(**label("msedcl-marathi-devanagari-01")))
    assert p.method == "history" and p.months_from_bill == 12
    # Aug 2026 history (262) wins over the current bill (287, also ending in August)
    assert p.monthly_kwh[7] == 262


def test_bimonthly_split(label):
    p = normalize_consumption(BillFields(**label("tnpdcl-tamil-bimonthly-01")))
    assert "BIMONTHLY_SPLIT" in p.flags
    assert p.months_from_bill == 12
    assert p.monthly_kwh[8] == p.monthly_kwh[7] == 243  # current 486 over Aug-Sep
    assert p.monthly_kwh[6] == p.monthly_kwh[5] == 256  # history 512 ending July
    assert p.annual_kwh == pytest.approx((486 + 512 + 598 + 455 + 402 + 438), abs=0.5)


def test_seasonal_fill_and_period_normalisation():
    bill = BillFields(units_billed_kwh=330, billing_period_start="2026-08-01", billing_period_end="2026-09-03",
                      billing_days=33, state="Delhi",
                      consumption_history=[HistoryPoint(month="2026-08", units_kwh=400),
                                           HistoryPoint(month="2026-07", units_kwh=420)])
    p = normalize_consumption(bill)
    assert "PERIOD_NORMALISED" in p.flags and p.monthly_kwh[8] == 300  # 330 x 30/33
    assert p.method == "seasonal_fill" and p.months_from_bill == 3
    assert p.monthly_kwh[0] < p.monthly_kwh[5]  # winter lower than June in the north


def test_manual_entry():
    assert normalize_consumption(BillFields(), manual=300).monthly_kwh == [300] * 12
    twelve = list(range(100, 220, 10))
    assert normalize_consumption(BillFields(), manual=twelve).annual_kwh == sum(twelve)
    with pytest.raises(ValueError):
        normalize_consumption(BillFields())
