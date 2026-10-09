import pytest

from engine.models import SolarResource
from engine.savings import emi, lifetime_savings, loan_view, payback_years, simulate_year, solar_monthly
from engine.tariffs import EffectiveRateTariff, SlabTariff


def flat(rate=8.0):
    return EffectiveRateTariff(rate, "test")


def test_simple_month_by_month():
    yr = simulate_year(flat(), [300] * 12, [200] * 12, export_rate=2.0)
    assert yr.bill_before == 300 * 8 * 12
    assert yr.bill_after == 100 * 8 * 12
    assert yr.export_kwh == 0 and yr.total_saving == 200 * 8 * 12


def test_surplus_is_banked_then_paid_at_export_rate():
    units = [200] * 12
    solar = [300 if m in (3, 4, 5) else 150 for m in range(1, 13)]  # surplus in Mar, Apr, May
    yr = simulate_year(flat(), units, solar, export_rate=2.0)
    by_m = {r.month: r for r in yr.rows}
    # April's 100-unit surplus is used up in June (settlement year starts in April)
    assert by_m[4].banked_kwh == 100 and by_m[6].bank_used_kwh == 50 and by_m[7].bank_used_kwh == 50
    # March is the last month of the settlement year: its surplus is paid out, not carried
    assert yr.export_kwh == 100
    assert yr.export_income == 200


def test_bimonthly_blocks_use_block_slabs():
    t = SlabTariff("TNPDCL")
    yr = simulate_year(t, [250] * 12, [0] * 12, export_rate=2.0)
    # 500 per block: 200 free, 200 x 4.70, 100 x 6.30 = 1570 per block, 6 blocks
    assert yr.bill_before == pytest.approx(1570 * 6)


def test_solar_monthly_profile_and_shading():
    res = SolarResource(annual_kwh_per_kw=1200, monthly_kwh_per_kw=[100] * 12, source="pvgis")
    assert sum(solar_monthly(2, res)) == pytest.approx(2400)
    assert sum(solar_monthly(2, res, shading_loss_pct=25)) == pytest.approx(1800)
    flat_res = SolarResource(annual_kwh_per_kw=1450, source="constant")
    assert solar_monthly(1, flat_res) == [pytest.approx(1450 / 12)] * 12


def test_lifetime_degradation_and_tariff_rise():
    t, units, solar = flat(), [300] * 12, [200] * 12
    base = simulate_year(t, units, solar, 2.0).total_saving
    assert lifetime_savings(t, units, solar, 2.0, degradation_pct=0, tariff_rise_pct=0) == pytest.approx(25 * base)
    with_rise = lifetime_savings(t, units, solar, 2.0)
    assert with_rise > 25 * base  # 3% rise outweighs 0.5% degradation


def test_payback():
    assert payback_years(108_000, 36_000) == 3.0
    assert payback_years(108_000, 0) is None
    assert payback_years(108_000, 1_000) is None  # 108 years: beyond panel life


def test_emi_and_loan_tiers():
    assert emi(167_400, 6.0, 10) == pytest.approx(1858.48, abs=0.01)
    small = loan_view(186_000, 3000)
    assert small.tier == "upto_2_lakh" and small.loan_amount == 167_400 and small.emi_covered_by_saving
    big = loan_view(310_000, 3000)
    assert big.tier == "above_2_lakh" and big.margin_amount == 62_000 and big.rate_pct == 8.0
