"""Readiness check before applying on pmsuryaghar.gov.in (SCOPE.md section 4).

Each check has a status (pass / warn / fail), a reason code and, when it isn't a
pass, a fix code. The UI translates both.
"""

from __future__ import annotations

from .models import Answers, BillFields, ReadinessCheck


def _yes_no(code: str, answer: bool | None, *, good: bool, fail_reason: str, fail_fix: str,
            pass_reason: str, unknown_fix: str, fail_status: str = "fail") -> ReadinessCheck:
    if answer is None:
        return ReadinessCheck(code=code, status="warn", reason="NOT_ANSWERED", fix=unknown_fix)
    if answer == good:
        return ReadinessCheck(code=code, status="pass", reason=pass_reason)
    return ReadinessCheck(code=code, status=fail_status, reason=fail_reason, fix=fail_fix)


def check_readiness(bill: BillFields, answers: Answers, system_kw: float | None = None) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []

    if bill.is_electricity_bill is False:
        checks.append(ReadinessCheck(code="ELECTRICITY_BILL", status="fail", reason="NOT_ELECTRICITY_BILL",
                                     fix="UPLOAD_ELECTRICITY_BILL"))

    # The subsidy goes to a bank account whose name must match the bill exactly.
    checks.append(_yes_no("NAME_MATCHES_BANK", answers.name_matches_bank, good=True,
                          fail_reason="NAME_MISMATCH", fail_fix="CHANGE_NAME_ON_BILL_OR_USE_MATCHING_ACCOUNT",
                          pass_reason="NAME_MATCHES", unknown_fix="CHECK_NAME_ON_BILL_VS_BANK"))

    if bill.is_residential is None:
        checks.append(ReadinessCheck(code="RESIDENTIAL", status="warn", reason="CATEGORY_UNKNOWN",
                                     fix="CONFIRM_DOMESTIC_CATEGORY"))
    elif bill.is_residential:
        checks.append(ReadinessCheck(code="RESIDENTIAL", status="pass", reason="DOMESTIC_CONNECTION"))
    else:
        checks.append(ReadinessCheck(code="RESIDENTIAL", status="fail", reason="NON_RESIDENTIAL_CATEGORY",
                                     fix="SCHEME_IS_RESIDENTIAL_ONLY_SEE_PM_KUSUM_FOR_FARMS"))

    checks.append(_yes_no("OWNS_ROOF", answers.owns_roof, good=True, fail_reason="NOT_ROOF_OWNER",
                          fail_fix="ASK_OWNER_TO_APPLY_OR_USE_RWA_ROUTE", pass_reason="OWNS_ROOF",
                          unknown_fix="CONFIRM_ROOF_OWNERSHIP"))

    checks.append(_yes_no("NO_PREVIOUS_SUBSIDY", answers.previous_solar_subsidy, good=False,
                          fail_reason="HAD_SOLAR_SUBSIDY_BEFORE", fail_fix="TOPUP_ONLY_UP_TO_3KW_TOTAL",
                          pass_reason="FIRST_SUBSIDY", unknown_fix="CONFIRM_NO_EARLIER_SUBSIDY", fail_status="warn"))

    if bill.sanctioned_load_kw is None:
        checks.append(ReadinessCheck(code="SANCTIONED_LOAD", status="warn", reason="LOAD_UNKNOWN",
                                     fix="ENTER_SANCTIONED_LOAD_FROM_BILL"))
    elif system_kw is not None and bill.sanctioned_load_kw < system_kw:
        checks.append(ReadinessCheck(code="SANCTIONED_LOAD", status="warn", reason="LOAD_BELOW_SYSTEM_SIZE",
                                     fix="APPLY_FOR_LOAD_INCREASE"))
    else:
        checks.append(ReadinessCheck(code="SANCTIONED_LOAD", status="pass", reason="LOAD_OK"))

    if bill.consumer_number:
        checks.append(ReadinessCheck(code="CONSUMER_NUMBER", status="pass", reason="CONSUMER_NUMBER_FOUND"))
    else:
        checks.append(ReadinessCheck(code="CONSUMER_NUMBER", status="warn", reason="CONSUMER_NUMBER_MISSING",
                                     fix="ENTER_CONSUMER_NUMBER_FROM_BILL"))

    if bill.has_solar_net_meter:
        checks.append(ReadinessCheck(code="NO_EXISTING_SOLAR", status="warn", reason="ALREADY_HAS_NET_METER",
                                     fix="CHECK_EXISTING_SYSTEM_OR_ADD_CAPACITY_UP_TO_3KW"))

    if bill.meter_reading_type == "estimated":
        checks.append(ReadinessCheck(code="ACTUAL_READING", status="warn", reason="ESTIMATED_READING",
                                     fix="CHECK_UNITS_AGAINST_METER"))
    return checks
