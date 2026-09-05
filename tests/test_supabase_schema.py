from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DIR = ROOT / "supabase" / "migrations"
SEED_PATH = ROOT / "supabase" / "seed.sql"

WORKFLOW_TABLES = {
    "source_imports",
    "forecast_daily",
    "menu_calendar",
    "bom_lines",
    "inventory_snapshots",
    "purchase_order_lines",
    "planning_netting_results",
    "planning_projection_days",
}

WORKSPACE_SCOPED_TABLES = {
    "master_data_versions",
    "locations",
    "items",
    "item_policy_overrides",
    "delivery_rules",
    "source_imports",
    "forecast_daily",
    "menu_calendar",
    "bom_lines",
    "inventory_snapshots",
    "purchase_order_lines",
    "planning_runs",
    "planning_run_inputs",
    "planning_lines",
    "planning_recommendations",
    "planning_exceptions",
    "planning_netting_results",
    "planning_projection_days",
}


def _schema_sql() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(MIGRATION_DIR.glob("*.sql"))
    )


def _table_columns(schema_sql: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    create_pattern = re.compile(
        r"create table public\.(?P<table>[a-z_][a-z0-9_]*)\s*\((?P<body>.*?)\n\);",
        re.IGNORECASE | re.DOTALL,
    )
    ignored = {"check", "constraint", "foreign", "primary", "unique"}
    for match in create_pattern.finditer(schema_sql):
        columns: set[str] = set()
        for line in match.group("body").splitlines():
            column_match = re.match(r"\s{4}([a-z_][a-z0-9_]*)\s+", line)
            if column_match and column_match.group(1).lower() not in ignored:
                columns.add(column_match.group(1).lower())
        result[match.group("table").lower()] = columns

    alter_pattern = re.compile(
        r"alter table public\.(?P<table>[a-z_][a-z0-9_]*)\s+(?P<body>.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    for match in alter_pattern.finditer(schema_sql):
        table = match.group("table").lower()
        for column in re.findall(
            r"\badd column\s+([a-z_][a-z0-9_]*)",
            match.group("body"),
            re.IGNORECASE,
        ):
            result.setdefault(table, set()).add(column.lower())
    return result


def _required_table_columns(schema_sql: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    ignored = {"check", "constraint", "foreign", "primary", "unique"}
    create_pattern = re.compile(
        r"create table public\.(?P<table>[a-z_][a-z0-9_]*)\s*\((?P<body>.*?)\n\);",
        re.IGNORECASE | re.DOTALL,
    )
    for match in create_pattern.finditer(schema_sql):
        required: set[str] = set()
        for line in match.group("body").splitlines():
            column_match = re.match(
                r"\s{4}(?P<column>[a-z_][a-z0-9_]*)\s+(?P<definition>.*)",
                line,
                re.IGNORECASE,
            )
            if column_match is None:
                continue
            if column_match.group("column").lower() in ignored:
                continue
            definition = column_match.group("definition").lower()
            if "not null" in definition and "default" not in definition:
                required.add(column_match.group("column").lower())
        result[match.group("table").lower()] = required

    alter_pattern = re.compile(
        r"alter table public\.(?P<table>[a-z_][a-z0-9_]*)\s+(?P<body>.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    for match in alter_pattern.finditer(schema_sql):
        table = match.group("table").lower()
        for column, definition in re.findall(
            r"\badd column\s+([a-z_][a-z0-9_]*)\s+([^,;]+)",
            match.group("body"),
            re.IGNORECASE,
        ):
            normalized = definition.lower()
            if "not null" in normalized and "default" not in normalized:
                result.setdefault(table, set()).add(column.lower())
        for column in re.findall(
            r"\balter column\s+([a-z_][a-z0-9_]*)\s+set not null",
            match.group("body"),
            re.IGNORECASE,
        ):
            result.setdefault(table, set()).add(column.lower())
    return result


class SupabaseSchemaTests(unittest.TestCase):
    def test_workflow_tables_are_rls_denied_by_default(self) -> None:
        schema = _schema_sql().lower()
        columns = _table_columns(schema)

        self.assertTrue(WORKFLOW_TABLES.issubset(columns))
        for table in WORKFLOW_TABLES:
            self.assertIn(
                f"alter table public.{table} enable row level security;",
                schema,
            )
            self.assertIn(
                f"revoke all on public.{table} from anon, authenticated;",
                schema,
            )

        self.assertNotIn("bytea", schema)

    def test_seed_only_references_declared_tables_and_columns(self) -> None:
        schema = _schema_sql()
        schema_columns = _table_columns(schema)
        required_columns = _required_table_columns(schema)
        seed = SEED_PATH.read_text(encoding="utf-8")
        self.assertIn("Synthetic UI-only data", seed)

        insert_pattern = re.compile(
            r"insert into public\.(?P<table>[a-z_][a-z0-9_]*)\s*"
            r"\((?P<columns>.*?)\)\s*(?:values|select)",
            re.IGNORECASE | re.DOTALL,
        )
        inserts = list(insert_pattern.finditer(seed))
        self.assertGreater(len(inserts), 0)
        for match in inserts:
            table = match.group("table").lower()
            self.assertIn(table, schema_columns)
            supplied = {
                column.strip().lower()
                for column in match.group("columns").split(",")
            }
            unknown = supplied - schema_columns[table]
            self.assertEqual(set(), unknown, f"seed has unknown {table} columns")
            missing = required_columns[table] - supplied
            self.assertEqual(set(), missing, f"seed misses required {table} columns")

    def test_run_and_import_traceability_columns_exist(self) -> None:
        columns = _table_columns(_schema_sql())
        self.assertTrue(
            {"location_id", "completed_at", "failure_summary"}.issubset(
                columns["planning_runs"]
            )
        )
        self.assertIn("source_import_id", columns["planning_run_inputs"])
        self.assertIn("source_import_id", columns["master_data_versions"])

    def test_every_planning_relation_has_a_required_workspace_boundary(self) -> None:
        schema = _schema_sql()
        columns = _table_columns(schema)
        required = _required_table_columns(schema)

        for table in WORKSPACE_SCOPED_TABLES:
            self.assertIn("workspace_id", columns[table], table)
            self.assertIn("workspace_id", required[table], table)

    def test_private_workspace_authorization_boundary_exists(self) -> None:
        schema = _schema_sql().lower()
        for table in (
            "workspaces",
            "app_user_profiles",
            "workspace_memberships",
            "user_location_access",
        ):
            self.assertIn(f"create table public.{table}", schema)
            self.assertIn(
                f"alter table public.{table} enable row level security;",
                schema,
            )
            self.assertIn(
                f"revoke all on public.{table} from anon, authenticated;",
                schema,
            )
        self.assertIn("provision_private_workspace_for_user_v1", schema)
        self.assertIn("master_data_versions_one_active_per_workspace_environment", schema)
        self.assertIn("inventory_snapshots_validate_source_location", schema)
        self.assertIn("planning_lines_validate_run_location", schema)
        self.assertIn("actor cannot manage master data in this workspace", schema)
        self.assertIn("and version.status = 'active'", schema)

    def test_daily_projection_matches_engine_output_contract(self) -> None:
        columns = _table_columns(_schema_sql())
        self.assertEqual(
            {
                "workspace_id",
                "run_id",
                "location_id",
                "item_id",
                "projection_date",
                "opening_balance_g",
                "demand_g",
                "open_po_receipts_g",
                "candidate_receipts_g",
                "closing_balance_g",
                "stockout_g",
            },
            columns["planning_projection_days"],
        )

    def test_actionable_risk_and_shelf_life_evidence_columns_exist(self) -> None:
        columns = _table_columns(_schema_sql())
        self.assertTrue(
            {
                "candidate_expiry_date",
                "shelf_life_cap_basis",
                "forecast_through_expiry",
                "projected_candidate_residual_at_expiry_g",
                "max_cover_end_date",
                "forecast_through_max_cover",
                "binding_constraint",
                "constraint_status",
                "rounding_direction",
            }.issubset(columns["planning_lines"])
        )
        self.assertTrue(
            {
                "risk_horizon_end_date",
                "risk_evaluated_through_date",
                "risk_horizon_fully_observed",
                "actionable_risk_status",
                "first_stockout_within_horizon_date",
                "projected_balance_at_risk_horizon_end_g",
                "max_stockout_within_horizon_g",
            }.issubset(columns["planning_netting_results"])
        )

    def test_event_aware_supply_coverage_columns_exist(self) -> None:
        columns = _table_columns(_schema_sql())
        self.assertTrue(
            {
                "coverage_contract_version",
                "on_hand_coverage_days",
                "on_hand_coverage_through_date",
                "on_hand_first_uncovered_date",
                "on_hand_coverage_forecast_limited",
                "with_open_po_coverage_days",
                "with_open_po_coverage_through_date",
                "with_open_po_first_uncovered_date",
                "with_open_po_coverage_forecast_limited",
                "with_proposal_coverage_days",
                "with_proposal_coverage_through_date",
                "with_proposal_first_uncovered_date",
                "with_proposal_coverage_forecast_limited",
                "open_po_coverage_extension_days",
                "open_po_coverage_extension_status",
                "proposal_coverage_extension_days",
                "proposal_coverage_extension_status",
                "open_po_receipts_at_or_after_gap",
                "proposal_receipts_at_or_after_gap",
                "protection_horizon_days",
            }.issubset(columns["planning_netting_results"])
        )
        schema = _schema_sql().lower()
        self.assertIn(
            "with_open_po_coverage_days\n"
            "                = on_hand_coverage_days + open_po_coverage_extension_days",
            schema,
        )
        self.assertIn(
            "with_proposal_coverage_days\n"
            "                = with_open_po_coverage_days + proposal_coverage_extension_days",
            schema,
        )
        self.assertIn("planning persistence v3 requires run.schema_version = 3", schema)
        self.assertIn(
            "planning persistence v3 requires coverage_contract_version = 1",
            schema,
        )
        self.assertIn(
            "when on_hand_coverage_forecast_limited then 'not_observable'",
            schema,
        )

    def test_backend_transaction_and_immutability_functions_exist(self) -> None:
        schema = _schema_sql().lower()
        for function in (
            "activate_master_data_version_v1",
            "persist_master_import_v1",
            "persist_source_import_v1",
            "persist_planning_run_v1",
            "persist_planning_run_v2",
            "persist_planning_run_v3",
        ):
            self.assertIn(f"create function public.{function}", schema)
            self.assertIn(f"grant execute on function public.{function}", schema)
        self.assertIn("source_imports_reject_finalized_mutation", schema)
        self.assertIn("forecast_daily_reject_finalized_mutation", schema)
        self.assertIn("purchase_order_lines_reject_finalized_mutation", schema)
        self.assertIn("active master-data versions are immutable", schema)

    def test_deterministic_run_retry_is_idempotent_and_hash_guarded(self) -> None:
        schema = _schema_sql().lower()

        self.assertIn("where run_id = requested_run_id", schema)
        self.assertIn("if existing_input_hash <> requested_input_hash then", schema)
        self.assertIn("existing run_id has a different input hash", schema)
        self.assertIn("return requested_run_id", schema)


if __name__ == "__main__":
    unittest.main()
