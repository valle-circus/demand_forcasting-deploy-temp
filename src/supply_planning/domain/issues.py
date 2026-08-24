from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


class ExceptionCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    DUPLICATE_KEY = "DUPLICATE_KEY"
    MISSING_BOM = "MISSING_BOM"
    PLACEHOLDER_SOURCE = "PLACEHOLDER_SOURCE"
    UNKNOWN_CRITICAL_SOURCE = "UNKNOWN_CRITICAL_SOURCE"
    UNEXPLAINED_BLANK_ORDER = "UNEXPLAINED_BLANK_ORDER"
    OBSERVED_ORDER_DIFFERS = "OBSERVED_ORDER_DIFFERS"
    CONFLICTING_MASTER_DATA = "CONFLICTING_MASTER_DATA"
    UNAVAILABLE_OPTIONAL_SOURCE = "UNAVAILABLE_OPTIONAL_SOURCE"
    UNAVOIDABLE_PRE_ARRIVAL_STOCKOUT = "UNAVOIDABLE_PRE_ARRIVAL_STOCKOUT"
    INFEASIBLE_ORDER_CONSTRAINTS = "INFEASIBLE_ORDER_CONSTRAINTS"


@dataclass(frozen=True, slots=True)
class PlanningIssue:
    code: ExceptionCode
    severity: Severity
    message: str
    remedy: str
    dataset: str | None = None
    record_ref: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "remedy": self.remedy,
            "dataset": self.dataset,
            "record_ref": self.record_ref,
        }
