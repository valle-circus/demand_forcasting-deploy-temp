from __future__ import annotations

import unittest

from supply_planning.domain.issues import ExceptionCode, Severity
from supply_planning.domain.models import InputSourceStatus, Provenance, RunMode
from supply_planning.validation.gates import CRITICAL_DATASETS, evaluate_run_mode


def _statuses(po_provenance: Provenance) -> tuple[InputSourceStatus, ...]:
    return tuple(
        InputSourceStatus(
            dataset=dataset,
            provenance=po_provenance if dataset == "purchase_orders" else Provenance.OBSERVED,
            record_count=0 if dataset == "purchase_orders" else 1,
            source_version="test-v1",
        )
        for dataset in CRITICAL_DATASETS
    )


class RunModeGateTests(unittest.TestCase):
    def test_fixture_allows_empty_po_placeholder_with_warning(self) -> None:
        issues = evaluate_run_mode(
            RunMode.FIXTURE,
            _statuses(Provenance.EMPTY_PLACEHOLDER),
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, Severity.WARNING)
        self.assertEqual(issues[0].code, ExceptionCode.PLACEHOLDER_SOURCE)

    def test_shadow_and_production_fail_closed_on_unknown_po_source(self) -> None:
        for mode in (RunMode.SHADOW, RunMode.PRODUCTION):
            with self.subTest(mode=mode):
                issues = evaluate_run_mode(
                    mode,
                    _statuses(Provenance.EMPTY_PLACEHOLDER),
                )
                self.assertEqual(issues[0].severity, Severity.BLOCKER)
                self.assertEqual(issues[0].code, ExceptionCode.UNKNOWN_CRITICAL_SOURCE)

    def test_observed_empty_po_result_is_known_not_missing(self) -> None:
        issues = evaluate_run_mode(
            RunMode.PRODUCTION,
            _statuses(Provenance.OBSERVED),
        )
        self.assertEqual(issues, ())


if __name__ == "__main__":
    unittest.main()
