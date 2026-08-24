"""Pure calculation modules with no I/O, database, network, UI, or clock access."""

from supply_planning.engine.explode import aggregate_item_demand, explode_bom
from supply_planning.engine.legacy_kw34 import (
    LegacyKw34Input,
    LegacyKw34Result,
    calculate_legacy_kw34,
)

__all__ = [
    "LegacyKw34Input",
    "LegacyKw34Result",
    "aggregate_item_demand",
    "calculate_legacy_kw34",
    "explode_bom",
]
