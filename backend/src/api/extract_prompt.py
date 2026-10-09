"""Shared bill-extraction prompt and JSON schema.

Used by the eval harness (eval/run_bench.py) and, later, by the API Lambda.
Keep this module free of third-party imports so it can be dropped into any
runtime as-is.

The field list matches eval/SCHEMA.md `fields`.
"""

from __future__ import annotations

import json

PROMPT_VERSION = "2026-10-09.2"

TOOL_NAME = "record_bill"

FIELD_ORDER = [
    "is_electricity_bill",
    "discom",
    "state",
    "consumer_number",
    "consumer_name",
    "tariff_category",
    "is_residential",
    "sanctioned_load_kw",
    "connection_phase",
    "billing_period_start",
    "billing_period_end",
    "billing_days",
    "billing_cycle",
    "units_billed_kwh",
    "bill_amount_rs",
    "consumption_history",
    "has_solar_net_meter",
    "export_units_kwh",
    "meter_reading_type",
    "pincode",
]


def _nullable(type_: str, description: str, **extra) -> dict:
    return {"type": [type_, "null"], "description": description, **extra}


BILL_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "is_electricity_bill": {
            "type": "boolean",
            "description": "true if the document is an Indian electricity bill. false for anything else; then set every other field to null.",
        },
        "discom": _nullable(
            "string",
            "Distribution company (DISCOM) as printed: full name, plus its short code in brackets if the bill shows one.",
        ),
        "state": _nullable(
            "string",
            "Indian state or UT of the connection, full English name. May be inferred from the DISCOM or the printed address.",
        ),
        "consumer_number": _nullable(
            "string",
            "Main consumer identifier exactly as printed (CA No., Consumer No., K No., Account No., RR No., Service No., BP No.). Western digits, no spaces.",
        ),
        "consumer_name": _nullable("string", "Name of the consumer as printed, in English letters if printed in English, otherwise as printed."),
        "tariff_category": _nullable("string", "Tariff category / class exactly as printed on the bill (code and words)."),
        "is_residential": _nullable("boolean", "true for domestic / residential tariffs, false for commercial, industrial, agricultural etc."),
        "sanctioned_load_kw": _nullable(
            "number",
            "Sanctioned / contracted / connected load in kW. Convert W to kW. If only kVA is printed, use that number.",
        ),
        "connection_phase": _nullable("string", "'single' or 'three' (phase of supply), null if not printed.", enum=["single", "three", None]),
        "billing_period_start": _nullable("string", "Start of the billing period (previous reading date), YYYY-MM-DD."),
        "billing_period_end": _nullable("string", "End of the billing period (current reading date), YYYY-MM-DD."),
        "billing_days": _nullable("integer", "Number of days billed, only if printed on the bill; null otherwise (do not compute it)."),
        "billing_cycle": _nullable("string", "'monthly' or 'bimonthly' (about 60 days per bill).", enum=["monthly", "bimonthly", None]),
        "units_billed_kwh": _nullable("number", "Units (kWh) billed for the current period. For net-metered bills, the net billed units."),
        "bill_amount_rs": _nullable(
            "number",
            "Current bill's net amount payable in rupees, by the due date, NOT including arrears / previous dues if shown separately.",
        ),
        "consumption_history": {
            "type": ["array", "null"],
            "description": "Every month shown in the bill's consumption history table or chart, newest first. null if the bill shows no history.",
            "items": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "YYYY-MM. For bi-monthly bills, the end month of the period."},
                    "units_kwh": {"type": "number", "description": "Units for that month (whole period for bi-monthly)."},
                },
                "required": ["month", "units_kwh"],
            },
        },
        "has_solar_net_meter": _nullable(
            "boolean",
            "true if the bill shows net metering / rooftop solar / export units; false if it is a normal bill without them.",
        ),
        "export_units_kwh": _nullable("number", "Units exported to the grid this period (net-metered bills only), else null."),
        "meter_reading_type": _nullable(
            "string",
            "'actual' for a normal meter reading, 'estimated' for average / assessed / RNA / door-locked / faulty-meter billing, 'unknown' if not stated.",
            enum=["actual", "estimated", "unknown", None],
        ),
        "pincode": _nullable("string", "6-digit PIN code from the consumer's supply address, if printed."),
    },
    "required": FIELD_ORDER,
}

SYSTEM_PROMPT = """You read Indian electricity bills and copy their key facts into a fixed JSON structure.

Rules:
1. Bills can be in any Indian script (Devanagari for Hindi/Marathi, Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Gurmukhi, Odia) mixed with English. Read them all.
2. Write every number with Western digits 0-9: convert Devanagari or other Indian digits (e.g. ४७.५० -> 47.50). Numbers are plain JSON numbers: no commas, no currency signs, no units.
3. If a field is not printed on the bill, return null. Never guess, never invent, never fill in a typical value. A wrong value is worse than null. (state may be inferred from the DISCOM or printed address.)
4. bill_amount_rs is the CURRENT bill's net payable amount (by the due date), NOT including arrears, previous balance or late-payment surcharge if those are shown separately. If the bill only shows one total that already includes arrears and no current-bill figure, use the figure labelled as current bill / bill amount; if none exists, use the net payable.
5. units_billed_kwh is the units charged for this billing period (current reading minus previous reading times multiplying factor, or the 'billed units' figure).
6. consumption_history: list every month shown in the bill's past-consumption table or bar chart, newest first, as {"month": "YYYY-MM", "units_kwh": number}. Only use numbers that are printed; do not estimate from bar heights. For bi-monthly bills use the END month of each two-month period and the units for the whole period. Return null if the bill shows no history.
7. Dates are YYYY-MM-DD. Indian bills print dates as DD-MM-YYYY or DD/MM/YY: convert carefully (day first).
8. billing_cycle is 'bimonthly' when one bill covers about two months (about 60 days), else 'monthly'.
9. If the document is not an electricity bill (e.g. a water bill, phone bill, receipt, random photo), set is_electricity_bill to false and every other field to null.
10. Copy names, numbers and categories exactly as printed; do not translate tariff categories."""

USER_INSTRUCTION_TOOL = (
    f"Read this electricity bill and call the `{TOOL_NAME}` tool with every field. "
    "Use null for anything not printed on the bill."
)


def _schema_text() -> str:
    return json.dumps(BILL_JSON_SCHEMA, ensure_ascii=False, indent=1)


USER_INSTRUCTION_JSON = (
    "Read this electricity bill and reply with ONLY one JSON object (no prose, no markdown fences) "
    "that matches this JSON schema. Include every key; use null for anything not printed on the bill.\n\n"
    + _schema_text()
)


def tool_spec() -> dict:
    """Bedrock Converse toolSpec for forced tool use."""
    return {
        "toolSpec": {
            "name": TOOL_NAME,
            "description": "Record the fields read from an Indian electricity bill.",
            "inputSchema": {"json": BILL_JSON_SCHEMA},
        }
    }


def empty_result() -> dict:
    """All-null result in the schema's shape."""
    return {k: None for k in FIELD_ORDER}
