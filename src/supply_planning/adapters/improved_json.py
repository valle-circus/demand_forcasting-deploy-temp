from __future__ import annotations

import json
from pathlib import Path

from supply_planning.application.run_improved import ImprovedRunResult


def write_improved_audit_json(path: Path, result: ImprovedRunResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.as_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
