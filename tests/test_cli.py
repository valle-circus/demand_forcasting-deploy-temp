from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from supply_planning.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_legacy" / "legacy_inputs.csv"


class CliTests(unittest.TestCase):
    def test_legacy_run_writes_auditable_deterministic_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.json"
            second_path = Path(directory) / "second.json"
            with redirect_stdout(io.StringIO()):
                first_code = main(
                    ["legacy-run", "--input", str(FIXTURE), "--output", str(first_path)]
                )
                second_code = main(
                    ["legacy-run", "--input", str(FIXTURE), "--output", str(second_path)]
                )

            self.assertEqual(first_code, 0)
            self.assertEqual(second_code, 0)
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            payload = json.loads(first_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["profile"], "legacy_kw34/v1")
            self.assertEqual(payload["summary"]["line_count"], 3)
            self.assertEqual(payload["summary"]["calculated_order_units"], 10)
            self.assertEqual(payload["summary"]["issue_count"], 1)
            self.assertEqual(payload["lines"][1]["issues"][0]["code"], "UNEXPLAINED_BLANK_ORDER")

    def test_invalid_file_error_is_actionable_and_has_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bad_input = Path(directory) / "bad.csv"
            bad_input.write_text("item_id,grams_per_day\nITEM_A,nope\n", encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main(
                    [
                        "legacy-run",
                        "--input",
                        str(bad_input),
                        "--output",
                        str(Path(directory) / "out.json"),
                    ]
                )

            self.assertEqual(code, 2)
            self.assertIn("missing required columns", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
