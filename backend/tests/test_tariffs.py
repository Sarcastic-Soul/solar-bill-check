import pytest

from engine.tariffs import (
    SlabTariff,
    effective_rate_tariff,
    monthly_bill,
    normalize_state,
    period_bill,
    resolve_discom,
    slab_energy,
)


def test_telescopic_slabs():
    slabs = [{"up_to": 200, "rate": 3.0}, {"up_to": 400, "rate": 4.5}, {"up_to": None, "rate": 6.5}]
    assert slab_energy(0, slabs) == 0
    assert slab_energy(200, slabs) == 600
    assert slab_energy(342, slabs) == 600 + 142 * 4.5
    assert slab_energy(450, slabs) == 600 + 900 + 50 * 6.5


# ---------------------------------------------------------------- mock bills (eval/bills), same rules


def test_delhi_brpl_mock_bill_exact_with_printed_ppac(label):
    f = label("delhi-brpl-hindi-clean-01")
    b = monthly_bill("BRPL", f["units_billed_kwh"], f["sanctioned_load_kw"], f["connection_phase"],
                     overrides={"PPAC": 0.1819})
    lines = {ln.code: ln.amount for ln in b.lines}
    # Printed on the mock bill: energy 1239, fixed 3 kW x 50, PPAC 252.66, surcharge 111.12,
    # pension 97.23, tax 92.50, subsidy 619.50, net 1323.01.
    assert lines["ENERGY"] == 1239.0
    assert lines["FIXED"] == 150.0
    assert lines["PPAC"] == 252.66
    assert lines["SURCHARGE"] == 111.12
    assert lines["PENSION_TRUST"] == 97.23
    assert lines["ELECTRICITY_TAX"] == 92.50
    assert b.subsidy == 619.50
    assert b.net == f["bill_amount_rs"] == 1323.01


def test_delhi_brpl_mock_bill_close_with_default_ppac(label):
    # Default PPAC is 18% (the mock printed 18.19%); the gap is 0.19% of (fixed + energy) plus tax on it.
    f = label("delhi-brpl-hindi-clean-01")
    b = monthly_bill("BRPL", f["units_billed_kwh"], f["sanctioned_load_kw"], f["connection_phase"])
    assert b.net == pytest.approx(f["bill_amount_rs"], abs=5)


def test_delhi_bypl_zero_bill(label):
    f = label("delhi-bypl-zero-subsidy-01")
    b = monthly_bill("BYPL", f["units_billed_kwh"], f["sanctioned_load_kw"])
    assert b.gross > 0
    assert b.net == f["bill_amount_rs"] == 0


def test_delhi_tpddl_7kw_three_phase(label):
    f = label("delhi-tpddl-3phase-7kw-01")
    b = monthly_bill("TPDDL", f["units_billed_kwh"], f["sanctioned_load_kw"], "three", overrides={"PPAC": 0.1819})
    assert b.fixed == 700  # 7 kW x Rs 100 (5-15 kW band)
    assert b.subsidy == 0
    assert b.net == f["bill_amount_rs"]


def test_delhi_subsidy_bands():
    assert monthly_bill("BRPL", 200, 2).net == 0
    b = monthly_bill("BRPL", 400, 2)
    assert b.subsidy == 0.5 * (600 + 900)  # 750 < 800 cap
    assert monthly_bill("BRPL", 401, 2).subsidy == 0
    assert monthly_bill("BRPL", 180, 2, apply_subsidy=False).net > 0


def test_uppcl_mock_bill(label):
    f = label("uppcl-hindi-arrears-01")
    b = monthly_bill("UPPCL", f["units_billed_kwh"], f["sanctioned_load_kw"])
    assert b.net == f["bill_amount_rs"] == 2124.15


def test_tnpdcl_mock_bill_bimonthly(label):
    f = label("tnpdcl-tamil-bimonthly-01")
    block = period_bill("TNPDCL", f["units_billed_kwh"])
    assert block.period_months == 2
    assert block.net == pytest.approx(1481.8)  # printed rounded to 1482
    assert round(block.net) == f["bill_amount_rs"]
    # monthly_bill bills the 2-month block on 2 x units and halves it
    m = monthly_bill("TNPDCL", f["units_billed_kwh"] / 2)
    assert m.period_units == f["units_billed_kwh"]
    assert m.net == pytest.approx(1481.8 / 2)


def test_tnpdcl_free_unit_tiers():
    assert period_bill("TNPDCL", 200).net == 0  # <= 500: first 200 free
    assert period_bill("TNPDCL", 500).net == pytest.approx(200 * 4.70 + 100 * 6.30)
    # > 500: only 100 free, so crossing 500 costs a lot
    assert period_bill("TNPDCL", 501).net == pytest.approx(300 * 4.70 + 100 * 6.30 + 1 * 8.40)


def test_msedcl_mock_bill_close(label):
    # The mock adds FAC (Rs 71.10) and a Rs 10 municipal fixed charge we leave out (FAC changes monthly),
    # so ours is about Rs 95 lower: within 3%.
    f = label("msedcl-marathi-devanagari-01")
    b = monthly_bill("MSEDCL", f["units_billed_kwh"], f["sanctioned_load_kw"], "single")
    assert b.net == pytest.approx(f["bill_amount_rs"], rel=0.03)
    assert b.net < f["bill_amount_rs"]


def test_msedcl_phase_fixed_charge():
    assert monthly_bill("MSEDCL", 100, 3, "single").fixed == 130
    assert monthly_bill("MSEDCL", 100, 3, "three").fixed == 435


def test_bescom_gruha_jyothi():
    within = monthly_bill("BESCOM", 140, 2, free_units_entitlement=148)
    assert within.net == 0
    partial = monthly_bill("BESCOM", 180, 2, free_units_entitlement=148)
    assert 0 < partial.net < monthly_bill("BESCOM", 180, 2, apply_subsidy=False).net
    # Above 200 units the whole bill is payable (the mock bill gives a partial subsidy at 236; see report)
    above = monthly_bill("BESCOM", 236, 2, free_units_entitlement=148)
    assert above.subsidy == 0


def test_unknown_discom_effective_rate():
    t = effective_rate_tariff(2156.0, 218)
    assert t.accuracy == "rough"
    assert t.period_bill(218).net == pytest.approx(2156.0)
    assert t.period_bill(100).net == pytest.approx(2156.0 / 218 * 100)
    zero = effective_rate_tariff(0.0, 168)
    assert zero.rate == 7.0  # national default when the bill is zero


def test_resolve_discom():
    assert resolve_discom("BSES Rajdhani Power Limited (BRPL)") == ("BRPL", "bill")
    assert resolve_discom("Madhyanchal Vidyut Vitran Nigam Ltd. (MVVNL), UPPCL") == ("UPPCL", "bill")
    assert resolve_discom("Tamil Nadu Power Distribution Corporation Ltd (TNPDCL)") == ("TNPDCL", "bill")
    assert resolve_discom("TANGEDCO") == ("TNPDCL", "bill")
    assert resolve_discom("महावितरण") == ("MSEDCL", "bill")
    assert resolve_discom("The Tata Power Company Ltd. (Mumbai Distribution)", "Maharashtra") == (None, "none")
    assert resolve_discom("CESC Limited", "West Bengal") == (None, "none")
    assert resolve_discom(None, "NCT of Delhi") == ("BRPL", "state")
    assert resolve_discom(None, "Maharashtra", "400071") == (None, "none")
    assert resolve_discom(None, "Maharashtra", "411001") == ("MSEDCL", "state")


def test_normalize_state():
    assert normalize_state("NCT OF DELHI") == "Delhi"
    assert normalize_state("tamil nadu") == "Tamil Nadu"
    assert normalize_state("Jammu & Kashmir") == "Jammu and Kashmir"
    assert normalize_state("ANDAMAN & NICOBAR ISLANDS") == "Andaman and Nicobar Islands"


def test_every_schedule_has_source_and_accuracy():
    for code in ("BRPL", "BYPL", "TPDDL", "MSEDCL", "UPPCL", "BESCOM", "TNPDCL"):
        t = SlabTariff(code)
        assert t.accuracy in ("exact", "estimate")
        assert t.s["source_url"].startswith("https://")
        assert t.s["as_of"]
        rate, _ = t.export_rate(3)
        assert rate > 0
    assert SlabTariff("MSEDCL").export_rate(3)[0] == 2.82
    assert SlabTariff("BESCOM").export_rate(1.5)[0] == 1.96
    assert SlabTariff("BESCOM").export_rate(5)[0] == 2.58
