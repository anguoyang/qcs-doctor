"""Shared check result model and registry (ported from RK Edge Doctor).

Every check returns one dict:
    {"id", "title", "status", "value", "detail", "hint", "fixable", "evidence"}
status is one of pass / warn / fail / skip. "fixable" means an A-level fix
action exists for this finding (see qcsdoctor.fix); "evidence" names the
failure-path file the check is grounded in. No check without evidence.
"""

from typing import Any, Optional

STATUSES = ("pass", "warn", "fail", "skip")


def result(check_id: str, title: str, status: str, value: Any,
           detail: str = "", hint: Optional[str] = None,
           fixable: bool = False, evidence: str = "") -> dict:
    return {"id": check_id, "title": title, "status": status, "value": value,
            "detail": detail, "hint": hint if status != "pass" else None,
            "fixable": fixable, "evidence": evidence}


def skipped(check_id: str, title: str, detail: str,
            hint: str = "Check that the source exists and is readable.",
            evidence: str = "") -> dict:
    return result(check_id, title, "skip", None, detail, hint,
                  fixable=False, evidence=evidence)
