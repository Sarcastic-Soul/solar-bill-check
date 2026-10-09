"""Network lookups: pincode -> state/district/lat-lon, and lat/lon -> solar yield.

Kept apart from the maths so the engine stays pure. Uses urllib only. Every call
goes through `Fetchers.get_json`, so tests (and the Lambda) can inject their own.

Fallback chains:
  location: postalpincode.in (state, district) + Nominatim -> Photon -> state capital
  yield:    PVGIS 5.3 -> Global Solar Atlas -> 1450 kWh/kW/year
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from . import constants as C
from .models import Location, SolarResource
from .tariffs import normalize_state

USER_AGENT = "solar-bill-check/0.1 (github.com/Sarcastic-Soul/solar-bill-check)"
TIMEOUT_S = 6.0

POSTALPINCODE_URL = "https://api.postalpincode.in/pincode/{pin}"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PHOTON_URL = "https://photon.komoot.io/api/"
PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
GSA_URL = "https://api.globalsolaratlas.info/data/lta"

GetJson = Callable[[str, dict[str, str], float], Any]


def urllib_get_json(url: str, headers: dict[str, str], timeout: float) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# Nominatim's usage policy: at most 1 request per second per application.
_nominatim_lock = threading.Lock()
_nominatim_last = 0.0

_CACHE: dict[str, Any] = {}

STATE_CAPITALS: dict[str, tuple[float, float]] = {
    "Andhra Pradesh": (16.51, 80.52),
    "Arunachal Pradesh": (27.08, 93.61),
    "Assam": (26.14, 91.79),
    "Bihar": (25.59, 85.14),
    "Chhattisgarh": (21.25, 81.63),
    "Goa": (15.49, 73.83),
    "Gujarat": (23.22, 72.65),
    "Haryana": (30.73, 76.78),
    "Himachal Pradesh": (31.10, 77.17),
    "Jharkhand": (23.34, 85.31),
    "Karnataka": (12.97, 77.59),
    "Kerala": (8.52, 76.94),
    "Madhya Pradesh": (23.26, 77.41),
    "Maharashtra": (19.08, 72.88),
    "Manipur": (24.82, 93.94),
    "Meghalaya": (25.58, 91.89),
    "Mizoram": (23.73, 92.72),
    "Nagaland": (25.67, 94.11),
    "Odisha": (20.30, 85.82),
    "Punjab": (30.73, 76.78),
    "Rajasthan": (26.91, 75.79),
    "Sikkim": (27.33, 88.61),
    "Tamil Nadu": (13.08, 80.27),
    "Telangana": (17.39, 78.49),
    "Tripura": (23.83, 91.29),
    "Uttar Pradesh": (26.85, 80.95),
    "Uttarakhand": (30.32, 78.03),
    "West Bengal": (22.57, 88.36),
    "Delhi": (28.61, 77.21),
    "Jammu and Kashmir": (34.08, 74.80),
    "Ladakh": (34.15, 77.58),
    "Puducherry": (11.94, 79.81),
    "Chandigarh": (30.73, 76.78),
    "Andaman and Nicobar Islands": (11.62, 92.73),
    "Lakshadweep": (10.57, 72.64),
    "Dadra and Nagar Haveli and Daman and Diu": (20.40, 72.83),
}


@dataclass
class Fetchers:
    get_json: GetJson = urllib_get_json
    timeout: float = TIMEOUT_S
    nominatim_interval: float = 1.0
    cache: dict[str, Any] = field(default_factory=lambda: _CACHE)
    errors: list[str] = field(default_factory=list)

    def _get(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return self.get_json(url, headers or {}, self.timeout)

    def _try(self, name: str, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except Exception as e:  # network, JSON and shape errors all mean "try the next source"
            self.errors.append(f"{name}: {type(e).__name__}: {e}"[:200])
            return None

    # -- pincode

    def pincode_info(self, pin: str) -> dict[str, str] | None:
        """{'state', 'district'} from India Post data, or None. A bad pin still returns HTTP 200."""
        def call():
            data = self._get(POSTALPINCODE_URL.format(pin=pin))
            entry = data[0] if isinstance(data, list) and data else {}
            if entry.get("Status") != "Success" or not entry.get("PostOffice"):
                raise ValueError(f"status {entry.get('Status')}: {entry.get('Message')}")
            po = entry["PostOffice"][0]
            return {"state": normalize_state(po.get("State")), "district": po.get("District")}
        return self._try("postalpincode", call)

    def nominatim(self, pin: str) -> tuple[float, float] | None:
        def call():
            global _nominatim_last
            with _nominatim_lock:
                wait = self.nominatim_interval - (time.monotonic() - _nominatim_last)
                if wait > 0:
                    time.sleep(wait)
                try:
                    data = self._get(NOMINATIM_URL, {"postalcode": pin, "countrycodes": "in", "format": "jsonv2",
                                                     "limit": 1})
                finally:
                    _nominatim_last = time.monotonic()
            if not data:
                raise ValueError("no result")
            return float(data[0]["lat"]), float(data[0]["lon"])
        return self._try("nominatim", call)

    def photon(self, pin: str) -> tuple[float, float] | None:
        def call():
            data = self._get(PHOTON_URL, {"q": f"{pin} India", "limit": 1})
            feats = data.get("features") or []
            if not feats:
                raise ValueError("no result")
            props = feats[0].get("properties", {})
            if pin not in (props.get("postcode"), props.get("name")) or props.get("countrycode") not in ("IN", None):
                raise ValueError(f"postcode mismatch: {props.get('postcode') or props.get('name')}")
            lon, lat = feats[0]["geometry"]["coordinates"]
            return float(lat), float(lon)
        return self._try("photon", call)

    def locate(self, pin: str) -> Location:
        pin = (pin or "").strip()
        key = f"loc:{pin}"
        if key in self.cache:
            return self.cache[key]
        info = self.pincode_info(pin) or {}
        state = info.get("state")
        source, coords = None, self.nominatim(pin)
        if coords:
            source = "nominatim"
        else:
            coords = self.photon(pin)
            source = "photon" if coords else None
        if not coords and state in STATE_CAPITALS:
            coords, source = STATE_CAPITALS[state], "state_capital"
        loc = Location(pincode=pin, state=state, district=info.get("district"),
                       lat=coords[0] if coords else None, lon=coords[1] if coords else None, source=source)
        if info or coords:
            self.cache[key] = loc
        return loc

    # -- solar yield

    def pvgis(self, lat: float, lon: float) -> SolarResource | None:
        def call():
            data = self._get(PVGIS_URL, {"lat": round(lat, 4), "lon": round(lon, 4), "peakpower": 1, "loss": 14,
                                         "optimalangles": 1, "mountingplace": "building", "outputformat": "json"})
            out = data["outputs"]
            e_y = float(out["totals"]["fixed"]["E_y"])
            months = sorted(out["monthly"]["fixed"], key=lambda m: m["month"])
            e_m = [float(m["E_m"]) for m in months]
            if e_y <= 0 or len(e_m) != 12:
                raise ValueError("bad PVGIS output")
            return SolarResource(annual_kwh_per_kw=round(e_y, 1), monthly_kwh_per_kw=[round(x, 2) for x in e_m],
                                 source="pvgis")
        return self._try("pvgis", call)

    def global_solar_atlas(self, lat: float, lon: float) -> SolarResource | None:
        def call():
            data = self._get(GSA_URL, {"loc": f"{lat:.4f},{lon:.4f}"})
            annual = float(data["annual"]["data"]["PVOUT_csi"])
            monthly = (data.get("monthly") or {}).get("data", {}).get("PVOUT_csi")
            if annual <= 0:
                raise ValueError("bad GSA output")
            m = [round(float(x), 2) for x in monthly] if monthly and len(monthly) == 12 else None
            return SolarResource(annual_kwh_per_kw=round(annual, 1), monthly_kwh_per_kw=m, source="global_solar_atlas")
        return self._try("global_solar_atlas", call)

    def solar_yield(self, lat: float | None, lon: float | None) -> SolarResource:
        if lat is None or lon is None:
            return SolarResource(annual_kwh_per_kw=C.DEFAULT_YIELD_KWH_PER_KW, source="constant")
        key = f"yield:{lat:.2f},{lon:.2f}"
        if key in self.cache:
            return self.cache[key]
        res = self.pvgis(lat, lon)
        if res is None and self.errors and "ConnectionResetError" in self.errors[-1]:
            res = self.pvgis(lat, lon)  # resets fail fast and are usually one-offs; timeouts are not retried
        res = res or self.global_solar_atlas(lat, lon)
        if res:
            self.cache[key] = res
            return res
        return SolarResource(annual_kwh_per_kw=C.DEFAULT_YIELD_KWH_PER_KW, source="constant")

    def resolve(self, pin: str) -> tuple[Location, SolarResource]:
        loc = self.locate(pin)
        return loc, self.solar_yield(loc.lat, loc.lon)


def resolve_pincode(pin: str, fetchers: Fetchers | None = None) -> tuple[Location, SolarResource]:
    return (fetchers or Fetchers()).resolve(pin)
