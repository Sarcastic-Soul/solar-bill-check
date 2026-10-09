import urllib.parse

import pytest

from engine.fetchers import Fetchers
from engine.models import Answers, BillFields
from engine.readiness import check_readiness


# ---------------------------------------------------------------- readiness


def by_code(checks):
    return {c.code: c for c in checks}


def test_readiness_all_good():
    bill = BillFields(is_residential=True, sanctioned_load_kw=3, consumer_number="123")
    checks = check_readiness(bill, Answers(owns_roof=True, name_matches_bank=True, previous_solar_subsidy=False), 3)
    assert all(c.status == "pass" for c in checks)


def test_readiness_problems():
    bill = BillFields(is_residential=True, sanctioned_load_kw=2, meter_reading_type="estimated")
    c = by_code(check_readiness(bill, Answers(owns_roof=False, name_matches_bank=False, previous_solar_subsidy=True),
                                3))
    assert c["NAME_MATCHES_BANK"].status == "fail"
    assert c["NAME_MATCHES_BANK"].fix == "CHANGE_NAME_ON_BILL_OR_USE_MATCHING_ACCOUNT"
    assert c["OWNS_ROOF"].status == "fail" and c["OWNS_ROOF"].fix == "ASK_OWNER_TO_APPLY_OR_USE_RWA_ROUTE"
    assert c["NO_PREVIOUS_SUBSIDY"].status == "warn"
    assert c["SANCTIONED_LOAD"].status == "warn" and c["SANCTIONED_LOAD"].fix == "APPLY_FOR_LOAD_INCREASE"
    assert c["CONSUMER_NUMBER"].status == "warn"
    assert c["ACTUAL_READING"].status == "warn"


def test_readiness_unanswered_is_warn():
    c = by_code(check_readiness(BillFields(), Answers()))
    assert c["OWNS_ROOF"].status == c["NAME_MATCHES_BANK"].status == c["RESIDENTIAL"].status == "warn"


# ---------------------------------------------------------------- fetchers (no network)

POSTAL_OK = [{"Status": "Success", "PostOffice": [{"State": "Maharashtra", "District": "Pune"}]}]
POSTAL_BAD = [{"Status": "Error", "Message": "No records found", "PostOffice": None}]
NOMINATIM_OK = [{"lat": "18.5336", "lon": "73.8807", "name": "411001"}]
PVGIS_OK = {"outputs": {"totals": {"fixed": {"E_y": 1451.01}},
                        "monthly": {"fixed": [{"month": m, "E_m": 120.9} for m in range(1, 13)]}}}
GSA_OK = {"annual": {"data": {"PVOUT_csi": 1590.3}}, "monthly": {"data": {"PVOUT_csi": [130.0] * 12}}}
PHOTON_OK = {"features": [{"properties": {"name": "110075", "countrycode": "IN"},
                           "geometry": {"coordinates": [77.0567, 28.5924]}}]}


def fake(routes):
    """get_json stub: routes maps a host substring to a response or an exception."""
    calls = []

    def get_json(url, headers, timeout):
        calls.append(url)
        host = urllib.parse.urlparse(url).netloc
        for key, resp in routes.items():
            if key in host:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise OSError(f"no route for {host}")

    return get_json, calls


def make(routes):
    get_json, calls = fake(routes)
    return Fetchers(get_json=get_json, nominatim_interval=0, cache={}), calls


def test_happy_path():
    f, calls = make({"postalpincode": POSTAL_OK, "nominatim": NOMINATIM_OK, "jrc": PVGIS_OK})
    loc, solar = f.resolve("411001")
    assert (loc.state, loc.district, loc.source) == ("Maharashtra", "Pune", "nominatim")
    assert loc.lat == pytest.approx(18.5336)
    assert solar.source == "pvgis" and solar.annual_kwh_per_kw == pytest.approx(1451.0)
    assert len(solar.monthly_kwh_per_kw) == 12
    pv = next(u for u in calls if "jrc" in u)
    assert "optimalangles=1" in pv and "mountingplace=building" in pv and "loss=14" in pv


def test_cache_avoids_repeat_calls():
    f, calls = make({"postalpincode": POSTAL_OK, "nominatim": NOMINATIM_OK, "jrc": PVGIS_OK})
    f.resolve("411001")
    n = len(calls)
    f.resolve("411001")
    assert len(calls) == n


def test_bad_pincode_status_and_photon_fallback():
    f, _ = make({"postalpincode": POSTAL_BAD, "nominatim": [], "photon": PHOTON_OK, "jrc": PVGIS_OK})
    loc = f.locate("110075")
    assert loc.state is None and loc.source == "photon"
    assert loc.lat == pytest.approx(28.5924)
    assert any("postalpincode" in e for e in f.errors)


def test_photon_postcode_mismatch_falls_back_to_state_capital():
    wrong = {"features": [{"properties": {"name": "110001", "countrycode": "IN"},
                           "geometry": {"coordinates": [77.2, 28.6]}}]}
    f, _ = make({"postalpincode": POSTAL_OK, "nominatim": TimeoutError("slow"), "photon": wrong})
    loc = f.locate("411001")
    assert loc.source == "state_capital" and loc.state == "Maharashtra"


def test_yield_fallbacks():
    f, _ = make({"jrc": TimeoutError("slow"), "globalsolaratlas": GSA_OK})
    s = f.solar_yield(18.5, 73.9)
    assert s.source == "global_solar_atlas" and s.annual_kwh_per_kw == pytest.approx(1590.3)
    f2, _ = make({"jrc": OSError("down"), "globalsolaratlas": ValueError("bad json")})
    s2 = f2.solar_yield(18.5, 73.9)
    assert s2.source == "constant" and s2.annual_kwh_per_kw == 1450
    assert Fetchers(get_json=fake({})[0], cache={}).solar_yield(None, None).source == "constant"
