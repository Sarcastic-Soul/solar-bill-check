"""National constants used by the engine, each with its source.

Anything state- or DISCOM-specific lives in data/tariffs.json instead.
"""

from __future__ import annotations

ENGINE_VERSION = "2026-10-09.1"

MNRE_GUIDELINES_URL = (
    "https://jbvnl.co.in/SOLAR/Operational%20Guidelines%20to%20PM%20Suryaghar%207%20June%2024.pdf"
)
PIB_EXPLAINER_URL = "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/mar/doc2025313520001.pdf"

# Central financial assistance (CFA), PM Surya Ghar, MNRE OM 7 Jun 2024.
CFA_FIRST_2KW_PER_KW = 30_000
CFA_THIRD_KW_PER_KW = 18_000
CFA_CAP = 78_000
CFA_SPECIAL_MULTIPLIER = 1.1
CFA_CAP_SPECIAL = 85_800
CFA_RWA_PER_KW = 18_000
CFA_RWA_PER_KW_SPECIAL = 19_800
CFA_RWA_KW_PER_HOUSE = 3
CFA_RWA_MAX_KW = 500

SPECIAL_CATEGORY_STATES = frozenset(
    {
        # North-Eastern states incl. Sikkim
        "Arunachal Pradesh",
        "Assam",
        "Manipur",
        "Meghalaya",
        "Mizoram",
        "Nagaland",
        "Sikkim",
        "Tripura",
        # Hill states and UTs
        "Uttarakhand",
        "Himachal Pradesh",
        "Jammu and Kashmir",
        "Ladakh",
        # Island UTs
        "Andaman and Nicobar Islands",
        "Lakshadweep",
    }
)

# State top-ups on top of the central CFA. Off by default when unconfirmed.
STATE_TOPUPS = {
    "Uttar Pradesh": {
        "kind": "per_kw",
        "per_kw": 15_000,
        "cap": 30_000,
        "status": "reported",
        "default_on": True,
        "source": "Installer and news sites (RESEARCH.md section 1); not checked against a UP govt order",
    },
    "Delhi": {
        "kind": "flat_matching",
        "amount": 78_000,
        "status": "unconfirmed",
        "default_on": False,
        "source": "2026 Delhi scheme reported to match the central CFA; not checked against the official notification",
    },
}

# Market price per kW (installed, DCR, on-grid), 2026. User can override.
COST_PER_KW_BANDS = [  # (min_kw, rs_per_kw)
    (3.0, 62_000),
    (2.0, 65_000),
    (0.0, 70_000),
]
COST_SOURCE = "Installer sites 2026 (Rs 55k-85k/kW, smaller systems cost more per kW); app default"

# Solar yield
DEFAULT_YIELD_KWH_PER_KW = 1450.0
YIELD_SOURCE_CONSTANT = "National fallback when PVGIS and Global Solar Atlas both fail"
ROOF_M2_PER_KW = 10.0  # MNRE: 10-12 m2 shadow-free area per kW

# Sizing caps
MIN_SYSTEM_KW = 1.0
MAX_AUTO_APPROVED_KW = 10.0  # feasibility auto-approved up to 10 kW for LT residential
FULL_SUBSIDY_KW = 3.0

# Long-term savings
PANEL_DEGRADATION_PCT = 0.5
TARIFF_RISE_PCT = 3.0
LIFETIME_YEARS = 25

# Climate
CO2_KG_PER_KWH = 0.71  # CEA CO2 Baseline Database v21.0, FY 2024-25
CO2_SOURCE = "CEA CO2 Baseline Database v21.0 (FY 2024-25)"
KG_CO2_PER_TREE_YEAR = 21.0
TREE_SOURCE = "Common estimate: a mature tree absorbs about 21 kg CO2 a year"

# Concessional loan via Jan Samarth (12 public sector banks)
LOAN_TIER1_MAX_RS = 200_000
LOAN_TIER1_RATE_PCT = 6.0  # repo 5.50% + 0.5%
LOAN_TIER1_MARGIN = 0.10
LOAN_TIER2_RATE_PCT = 8.0  # "home-loan rate or HL + 1%", varies by bank
LOAN_TIER2_MARGIN = 0.20
LOAN_YEARS = 10
LOAN_SOURCE = "PM Surya Ghar financing FAQ; RBI repo 5.50% (7 Oct 2026)"

# Verdict thresholds
PAYBACK_WORTH_IT_YEARS = 6.0
PAYBACK_WITH_LOAN_YEARS = 10.0
LOW_USAGE_UNITS_PER_MONTH = 100.0

# Net-metering settlement year starts in April (financial year).
SETTLEMENT_START_MONTH = 4

# Rough seasonal shape of household use (Jan..Dec, mean 1.0), used only to fill
# months missing from the bill history. AC load makes the north peak in May-Jul.
SEASONAL_PROFILES = {
    "north": [0.75, 0.70, 0.80, 1.00, 1.30, 1.40, 1.30, 1.20, 1.15, 0.95, 0.75, 0.70],
    "west": [0.90, 0.90, 0.95, 1.10, 1.25, 1.10, 0.95, 0.95, 1.00, 1.05, 0.95, 0.90],
    "south": [0.95, 1.00, 1.10, 1.20, 1.15, 0.95, 0.90, 0.90, 0.95, 0.95, 0.95, 1.00],
}
STATE_REGION = {
    "Delhi": "north",
    "Uttar Pradesh": "north",
    "Haryana": "north",
    "Punjab": "north",
    "Rajasthan": "north",
    "Bihar": "north",
    "Madhya Pradesh": "north",
    "Chandigarh": "north",
    "Jharkhand": "north",
    "Maharashtra": "west",
    "Gujarat": "west",
    "Goa": "west",
    "Chhattisgarh": "west",
    "Odisha": "west",
    "West Bengal": "west",
    "Telangana": "south",
    "Andhra Pradesh": "south",
    "Karnataka": "south",
    "Tamil Nadu": "south",
    "Kerala": "south",
    "Puducherry": "south",
}
DEFAULT_REGION = "west"

# Assumed sanctioned load when the bill doesn't show one (affects fixed charges only).
DEFAULT_SANCTIONED_KW = 2.0
