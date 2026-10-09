"""Field clean-up, two-model agreement, sanity checks and masking (no network)."""

import datetime as dt

from api.bedrock_client import ModelSpec, extract_json, models_from_env, unwrap
from api.fields import (
    clean_fields,
    mask_consumer_number,
    merge,
    normalize_digits,
    redact,
    sanity_check,
    to_number,
)
from api.speak import cap_text

TODAY = dt.date(2026, 10, 9)

BASE = {
    "is_electricity_bill": True,
    "discom": "BSES Rajdhani Power Limited (BRPL)",
    "state": "Delhi",
    "consumer_number": "152839471",
    "consumer_name": "Test Name",
    "tariff_category": "Domestic (DX)",
    "is_residential": True,
    "sanctioned_load_kw": 3,
    "connection_phase": "single",
    "billing_period_start": "2026-08-06",
    "billing_period_end": "2026-09-05",
    "billing_days": 30,
    "billing_cycle": "monthly",
    "units_billed_kwh": 342,
    "bill_amount_rs": 1323.01,
    "consumption_history": [
        {"month": "2026-08", "units_kwh": 389},
        {"month": "2026-07", "units_kwh": 412},
        {"month": "2026-06", "units_kwh": 455},
    ],
    "has_solar_net_meter": False,
    "export_units_kwh": None,
    "meter_reading_type": "actual",
    "pincode": "110075",
}


def variant(**changes):
    d = {**BASE, **changes}
    return clean_fields(d)


# ---------------------------------------------------------------- clean-up


def test_normalize_digits_indian_scripts():
    assert normalize_digits("४७.५०") == "47.50"  # Devanagari
    assert normalize_digits("৩৪২") == "342"  # Bengali
    assert normalize_digits("௧௨௩") == "123"  # Tamil
    assert normalize_digits("abc 12") == "abc 12"


def test_to_number_variants():
    assert to_number("1,323.01") == 1323.01
    assert to_number("₹ ३४२") == 342
    assert to_number("3 kW") == 3
    assert to_number(True) is None
    assert to_number("n/a") is None


def test_clean_fields_normalises_types():
    f = clean_fields({
        "units_billed_kwh": "३४२",
        "sanctioned_load_kw": "3.0 kW",
        "billing_days": "30",
        "is_residential": "yes",
        "connection_phase": "Single Phase",
        "billing_cycle": "Bi-Monthly",
        "billing_period_end": "05/09/2026",
        "consumer_number": "15 2839 471",
        "pincode": "११००७५",
        "state": "NCT of Delhi",
        "consumption_history": [
            {"month": "2026-7", "units_kwh": "412"},
            {"month": "2026-08", "units_kwh": 389},
            {"month": "2026-08", "units_kwh": 999},  # duplicate month dropped
            {"month": "bad", "units_kwh": 1},
        ],
        "unknown_key": 1,
    })
    assert f["units_billed_kwh"] == 342
    assert f["sanctioned_load_kw"] == 3.0
    assert f["billing_days"] == 30
    assert f["is_residential"] is True
    assert f["connection_phase"] == "single"
    assert f["billing_cycle"] == "bimonthly"
    assert f["billing_period_end"] == "2026-09-05"
    assert f["consumer_number"] == "152839471"
    assert f["pincode"] == "110075"
    assert f["state"] == "Delhi"
    assert f["consumption_history"] == [{"month": "2026-08", "units_kwh": 389}, {"month": "2026-07", "units_kwh": 412}]
    assert f["is_electricity_bill"] is True
    assert "unknown_key" not in f


# ---------------------------------------------------------------- agreement


def test_merge_agreement_is_high():
    m = merge([variant(), variant(discom="BRPL", bill_amount_rs=1323.4)])
    assert m["disagreements"] == []
    for k in ("units_billed_kwh", "consumption_history", "sanctioned_load_kw", "bill_amount_rs", "discom", "state",
              "is_residential", "billing_cycle"):
        assert m["confidence"][k] == "high", k
    assert m["fields"]["discom"] == BASE["discom"]  # primary's text kept
    assert m["confidence"]["export_units_kwh"] == "missing"


def test_merge_key_field_disagreement_is_check_with_candidates():
    m = merge([variant(units_billed_kwh=342), variant(units_billed_kwh=324)])
    assert m["confidence"]["units_billed_kwh"] == "check"
    assert m["fields"]["units_billed_kwh"] == 342  # primary model's value stays the default
    d = next(x for x in m["disagreements"] if x["field"] == "units_billed_kwh")
    assert d == {"field": "units_billed_kwh", "kind": "different", "candidates": [342, 324]}


def test_merge_history_compared_month_by_month():
    hist2 = [{"month": "2026-08", "units_kwh": 389}, {"month": "2026-07", "units_kwh": 421},
             {"month": "2026-06", "units_kwh": 455}]
    m = merge([variant(), variant(consumption_history=hist2)])
    assert m["confidence"]["consumption_history"] == "check"
    shorter = BASE["consumption_history"][:2]
    m2 = merge([variant(), variant(consumption_history=shorter)])
    assert m2["confidence"]["consumption_history"] == "check"


def test_merge_discom_matches_by_code():
    m = merge([variant(discom="BSES Rajdhani Power Ltd"), variant(discom="BRPL")])
    assert m["confidence"]["discom"] == "high"
    m2 = merge([variant(discom="BSES Rajdhani Power Ltd"), variant(discom="BSES Yamuna Power Ltd (BYPL)")])
    assert m2["confidence"]["discom"] == "check"


def test_merge_one_missing_is_medium():
    m = merge([variant(sanctioned_load_kw=None), variant()])
    assert m["fields"]["sanctioned_load_kw"] == 3
    assert m["confidence"]["sanctioned_load_kw"] == "medium"
    assert m["disagreements"][0]["kind"] == "one_missing"


def test_merge_non_key_difference_is_medium_without_candidates():
    m = merge([variant(tariff_category="DX"), variant(tariff_category="Domestic")])
    assert m["confidence"]["tariff_category"] == "medium"
    assert all(d["field"] != "tariff_category" for d in m["disagreements"])


def test_merge_single_model_is_medium():
    m = merge([variant()])
    assert m["confidence"]["units_billed_kwh"] == "medium"
    assert m["confidence"]["export_units_kwh"] == "missing"
    assert m["disagreements"] == []


def test_merge_bool_disagreement():
    m = merge([variant(is_residential=True), variant(is_residential=False)])
    assert m["confidence"]["is_residential"] == "check"


# ---------------------------------------------------------------- sanity checks


def codes(warnings):
    return {w["code"] for w in warnings}


def test_sanity_clean_bill_has_no_check_warnings():
    f = variant()
    conf = {k: "high" for k in f}
    w = sanity_check(f, conf, TODAY)
    assert not [x for x in w if x["level"] == "check"], w


def test_sanity_units_and_load_out_of_range():
    f = variant(units_billed_kwh=25000, sanctioned_load_kw=250, consumption_history=None, bill_amount_rs=None)
    conf = {}
    w = sanity_check(f, conf, TODAY)
    assert {"UNITS_OUT_OF_RANGE", "LOAD_OUT_OF_RANGE"} <= codes(w)
    assert conf["units_billed_kwh"] == "check" and conf["sanctioned_load_kw"] == "check"


def test_sanity_amount_vs_units():
    w = sanity_check(variant(bill_amount_rs=50000), {}, TODAY)
    assert "AMOUNT_HIGH_FOR_UNITS" in codes(w)
    w = sanity_check(variant(bill_amount_rs=100), {}, TODAY)
    assert "AMOUNT_LOW_FOR_UNITS" in codes(w)
    # Free-units bill (Delhi, Rs 0) is fine
    w = sanity_check(variant(bill_amount_rs=0, units_billed_kwh=180), {}, TODAY)
    assert not {"AMOUNT_HIGH_FOR_UNITS", "AMOUNT_LOW_FOR_UNITS"} & codes(w)


def test_sanity_history_checks():
    hist = [{"month": "2027-05", "units_kwh": 300}, {"month": "2026-07", "units_kwh": 30000},
            {"month": "2026-06", "units_kwh": 400}]
    w = sanity_check(variant(consumption_history=clean_fields({"consumption_history": hist})["consumption_history"]),
                     {}, TODAY)
    assert {"HISTORY_MONTH_IN_FUTURE", "HISTORY_VALUE_OUT_OF_RANGE"} <= codes(w)


def test_sanity_units_far_from_history():
    w = sanity_check(variant(units_billed_kwh=3420), {}, TODAY)
    assert "UNITS_VS_HISTORY" in codes(w)


def test_sanity_cycle_vs_days_and_info_flags():
    f = variant(billing_cycle="bimonthly", billing_days=30, meter_reading_type="estimated", has_solar_net_meter=True,
                is_residential=False)
    w = sanity_check(f, {}, TODAY)
    assert {"BILLING_CYCLE_VS_DAYS", "ESTIMATED_READING", "ALREADY_HAS_SOLAR", "NON_RESIDENTIAL"} <= codes(w)


def test_sanity_not_a_bill():
    f = clean_fields({"is_electricity_bill": False})
    w = sanity_check(f, {}, TODAY)
    assert codes(w) == {"NOT_ELECTRICITY_BILL"}


def test_sanity_no_units():
    f = variant(units_billed_kwh=None, consumption_history=None)
    assert "NO_UNITS" in codes(sanity_check(f, {}, TODAY))


# ---------------------------------------------------------------- privacy and helpers


def test_mask_and_redact():
    assert mask_consumer_number("152839471") == "XXXXX9471"
    assert mask_consumer_number("1234") == "XX34"
    assert mask_consumer_number(None) is None
    r = redact(variant())
    assert r["consumer_number"] == "XXXXX9471"
    assert "consumer_name" not in r


def test_models_from_env_default_and_custom():
    d = models_from_env("")
    assert [m.id for m in d] == ["moonshotai.kimi-k2.5", "mistral.mistral-large-3-675b-instruct"]
    assert d[0].mode == "json" and d[0].max_tokens == 12000
    assert d[1].mode == "tool"
    c = models_from_env('[{"id": "in.moonshotai.kimi-k3", "region": "ap-south-1", "mode": "tool"}]')
    assert c == [ModelSpec(id="in.moonshotai.kimi-k3", region="ap-south-1", mode="tool", max_tokens=12000,
                           temperature=False)]


def test_extract_json_and_unwrap():
    text = '<think>hmm {"x": 1}</think>Here: ```json\n{"record_bill": {"units_billed_kwh": 5, "state": ' \
           '{"type": "string", "value": "Delhi"}}}\n```'
    obj = unwrap(extract_json(text))
    assert obj == {"units_billed_kwh": 5, "state": "Delhi"}


def test_cap_text():
    s = "पहला वाक्य। " * 200
    out, cut = cap_text(s, 100)
    assert cut and len(out) <= 100 and out.endswith("।")
    assert cap_text("short", 100) == ("short", False)
