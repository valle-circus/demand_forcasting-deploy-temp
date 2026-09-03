from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.api.supply_planning_api.config import Settings  # noqa: E402
from apps.api.supply_planning_api.repository import (  # noqa: E402
    JsonObject,
    SupabaseCanonicalStore,
)
from apps.api.supply_planning_api.services import PlanningBackend  # noqa: E402


class MeasuredStore(SupabaseCanonicalStore):
    """Count reads while retaining the production PostgREST implementation."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.read_count = 0

    async def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, str] | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[JsonObject]:
        self.read_count += 1
        return await super().select_rows(
            table,
            columns=columns,
            filters=filters,
            order=order,
            limit=limit,
        )


async def measure(
    name: str,
    operation: Callable[[], Awaitable[Any]],
    *,
    cycles: int,
    store: MeasuredStore,
) -> None:
    samples: list[float] = []
    counts: list[int] = []
    for _index in range(cycles):
        store.read_count = 0
        started = perf_counter()
        await operation()
        samples.append((perf_counter() - started) * 1_000)
        counts.append(store.read_count)
    rounded = [round(sample) for sample in samples]
    print(
        f"{name}: median={round(statistics.median(samples))}ms "
        f"range={min(rounded)}-{max(rounded)}ms reads={counts}"
    )


async def run(cycles: int) -> None:
    settings = Settings()
    if not settings.supabase_configured:
        raise SystemExit("Supabase is not configured; no measurements were run.")
    store = MeasuredStore(settings)
    backend = PlanningBackend(store, settings)
    try:
        locations = await backend.list_locations()
        active_locations = locations["locations"]
        print(f"active_locations={len(active_locations)}")
        if not active_locations:
            raise SystemExit("No active locations are available to measure.")
        location_id = str(active_locations[0]["location_id"])
        status = await backend.planning_status(location_id)
        latest_run = status.get("latest_run")
        location_view = await backend.location_view(location_id)
        if location_view["locations"] != locations:
            raise RuntimeError("Location view changed the locations response contract.")
        if location_view["status"] != status:
            raise RuntimeError("Location view changed the planning-status contract.")
        if status["sources"].get("stock") is not None:
            independent_inventory = await backend.inventory(location_id)
            if location_view["inventory"] != independent_inventory:
                raise RuntimeError("Location view changed the inventory contract.")
        if isinstance(latest_run, dict):
            independent_run = await backend.get_planning_run(str(latest_run["run_id"]))
            if location_view["planning_run"] != independent_run:
                raise RuntimeError("Location view changed the planning-run contract.")
        print("location_view_equivalence=passed")

        await measure(
            "list_locations", backend.list_locations, cycles=cycles, store=store
        )
        await measure(
            "planning_status",
            lambda: backend.planning_status(location_id),
            cycles=cycles,
            store=store,
        )
        await measure(
            "location_view",
            lambda: backend.location_view(location_id),
            cycles=cycles,
            store=store,
        )
        if status["sources"].get("stock") is not None:
            await measure(
                "inventory",
                lambda: backend.inventory(location_id),
                cycles=cycles,
                store=store,
            )
        if isinstance(latest_run, dict):
            run_id = str(latest_run["run_id"])
            await measure(
                "get_planning_run",
                lambda: backend.get_planning_run(run_id),
                cycles=cycles,
                store=store,
            )
        await measure("overview", backend.overview, cycles=cycles, store=store)
    finally:
        await store.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only timing/count probe for UI backend read models."
    )
    parser.add_argument("--cycles", type=int, default=3)
    args = parser.parse_args()
    if args.cycles < 1:
        parser.error("--cycles must be at least 1")
    asyncio.run(run(args.cycles))


if __name__ == "__main__":
    main()
