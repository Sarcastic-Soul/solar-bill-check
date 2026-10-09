import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

BILLS = ROOT / "eval" / "bills"


def load_label(bill_id: str) -> dict:
    """Label fields from eval/bills, with list-valued alternatives reduced to the first one."""
    fields = json.loads((BILLS / bill_id / "label.json").read_text(encoding="utf-8"))["fields"]
    return {k: (v[0] if isinstance(v, list) and v and not isinstance(v[0], dict) else v) for k, v in fields.items()}


@pytest.fixture
def label():
    return load_label


# PVGIS output for Delhi (110075) and Pune (411001), checked live on 2026-10-09.
DELHI_SOLAR = {
    "annual_kwh_per_kw": 1553.09,
    "monthly_kwh_per_kw": [139.56, 134.5, 151.37, 143.98, 136.74, 116.01, 96.13, 99.61, 114.03, 142.82, 137.28, 141.05],
    "source": "pvgis",
}
PUNE_SOLAR = {
    "annual_kwh_per_kw": 1451.0,
    "monthly_kwh_per_kw": [150.9, 140.84, 149.25, 136.3, 130.98, 91.5, 73.9, 82.71, 93.37, 125.23, 133.48, 142.56],
    "source": "pvgis",
}
