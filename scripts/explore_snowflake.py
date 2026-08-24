"""
Snowflake discovery script for the supply-planning project.

Run steps in order. Each step is independent and prints what it finds.
Nothing here writes to Snowflake — read-only.

    pip install "snowflake-connector-python[pandas]" pandas
    python explore_snowflake.py 1        # run one step
    python explore_snowflake.py all      # run everything

Google SSO opens a browser window on first connect.
"""

import os
import sys
import pandas as pd
import snowflake.connector

pd.set_option("display.max_rows", 200)
pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 200)

ENVIRONMENT_FIELDS = {
    "account": "SNOWFLAKE_ACCOUNT",
    "user": "SNOWFLAKE_USER",
    "role": "SNOWFLAKE_ROLE",
    "warehouse": "SNOWFLAKE_WAREHOUSE",
    "database": "SNOWFLAKE_DATABASE",
}

# KW34 2026 = Mon 17 Aug .. Sat 22 Aug
KW34_START, KW34_END = "2026-08-17", "2026-08-22"

# Tables Joel listed. Schemas unknown — step 2 resolves them.
KEY_TABLES = [
    "fact_cg_sales_daily",
    "fact_cg_sales",
    "fact_cg_sales_hourly",
    "fact_cg_dish_production",
    "fact_cg_waste",
    "fact_cg_oos_ingredient",
    "base_stock_updates",
    "int_unit_day_menu",
    "base_ucs_menu",
]


def connect():
    values = {
        name: os.environ.get(environment_name, "").strip()
        for name, environment_name in ENVIRONMENT_FIELDS.items()
    }
    missing = [
        environment_name
        for name, environment_name in ENVIRONMENT_FIELDS.items()
        if not values[name]
    ]
    if missing:
        raise RuntimeError(
            "Missing Snowflake environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example or set them in the current shell; do not commit values."
        )
    return snowflake.connector.connect(
        account=values["account"],
        user=values["user"],
        authenticator="externalbrowser",
        role=values["role"],
        warehouse=values["warehouse"],
        database=values["database"],
    )


def q(conn, sql):
    return conn.cursor().execute(sql).fetch_pandas_all()


# ---------------------------------------------------------------- step 1
def step1_connection(conn):
    """Confirm the connection works and show what we're connected as."""
    print(q(conn, """
        select current_user()      as user,
               current_role()      as role,
               current_warehouse() as warehouse,
               current_database()  as database,
               current_version()   as version
    """).T)


# ---------------------------------------------------------------- step 2
def step2_schemas(conn):
    """List every schema, and locate the tables Joel named."""
    print("--- schemas in ANALYTICS ---")
    print(q(conn, """
        select schema_name
        from analytics.information_schema.schemata
        order by 1
    """))

    names = ", ".join(f"'{t.upper()}'" for t in KEY_TABLES)
    print("\n--- where Joel's tables actually live ---")
    print(q(conn, f"""
        select table_schema, table_name, table_type, row_count, bytes
        from analytics.information_schema.tables
        where table_name in ({names})
        order by table_schema, table_name
    """))

    print("\n--- anything else that looks relevant ---")
    print(q(conn, """
        select table_schema, table_name, row_count
        from analytics.information_schema.tables
        where table_name ilike any (
            '%SALES%', '%WASTE%', '%OOS%', '%STOCK%', '%MENU%',
            '%DISH%', '%INGREDIENT%', '%RECIPE%', '%ORDER%',
            '%PURCHAS%', '%SUPPLIER%', '%DELIVERY%', '%INVENTORY%'
        )
        order by table_schema, table_name
    """))


# ---------------------------------------------------------------- step 3
def step3_hunt_for_gaps(conn):
    """
    Specifically hunt for the four things Joel's list did NOT cover:
    purchase orders / in-transit, recipes/BOM, item master, supplier terms.
    If these return nothing, they genuinely don't exist in ANALYTICS.
    """
    print("--- candidates for purchase orders / in-transit (gap G4) ---")
    print(q(conn, """
        select table_schema, table_name, row_count
        from analytics.information_schema.tables
        where table_name ilike any (
            '%PURCHASE%', '%_PO_%', '%PO_%', '%PROCUREMENT%',
            '%GOODS%', '%RECEIPT%', '%SHIPMENT%', '%INBOUND%', '%XENTRAL%'
        )
        order by 1, 2
    """))

    print("\n--- candidates for recipes / BOM (gap G1) ---")
    print(q(conn, """
        select table_schema, table_name, row_count
        from analytics.information_schema.tables
        where table_name ilike any (
            '%RECIPE%', '%BOM%', '%COMPONENT%', '%SILO%', '%PREMIX%', '%PRE_MIX%'
        )
        order by 1, 2
    """))

    print("\n--- columns anywhere that mention grams, shelf life, lead time ---")
    print(q(conn, """
        select table_schema, table_name, column_name, data_type
        from analytics.information_schema.columns
        where column_name ilike any (
            '%GRAM%', '%SHELF%', '%LEAD_TIME%', '%MHD%',
            '%BEST_BEFORE%', '%EXPIR%', '%PACK_SIZE%', '%MOQ%'
        )
        order by 1, 2, 3
    """))


# ---------------------------------------------------------------- step 4
def step4_columns(conn):
    """Dump columns for each key table. This is what reveals the true grain."""
    names = ", ".join(f"'{t.upper()}'" for t in KEY_TABLES)
    cols = q(conn, f"""
        select table_schema, table_name, ordinal_position, column_name, data_type
        from analytics.information_schema.columns
        where table_name in ({names})
        order by table_schema, table_name, ordinal_position
    """)
    for (schema, table), grp in cols.groupby(["TABLE_SCHEMA", "TABLE_NAME"]):
        print(f"\n=== {schema}.{table} ===")
        print(grp[["COLUMN_NAME", "DATA_TYPE"]].to_string(index=False))


# ---------------------------------------------------------------- step 5
def step5_profile(conn, schema, table, date_col):
    """
    Date range, row count and daily volume for one table.
    Call with the schema and date column you found in steps 2 and 4, e.g.
        step5_profile(conn, "MARTS", "FACT_CG_SALES_DAILY", "SALES_DATE")
    """
    print(f"--- {schema}.{table} ---")
    print(q(conn, f"""
        select min({date_col})   as first_date,
               max({date_col})   as last_date,
               count(*)          as rows,
               count(distinct {date_col}) as days
        from analytics.{schema}.{table}
    """).T)

    print("\nlast 14 days:")
    print(q(conn, f"""
        select {date_col} as d, count(*) as rows
        from analytics.{schema}.{table}
        where {date_col} >= dateadd(day, -14, current_date())
        group by 1 order by 1
    """))

    print("\nsample:")
    print(q(conn, f"select * from analytics.{schema}.{table} limit 5"))


# ---------------------------------------------------------------- step 6
def step6_validate_kw34(conn, schema="MARTS", table="FACT_CG_SALES_DAILY"):
    """
    TEST A — is Demand/Silo Load a sales figure or a loading figure?

    The KW34 sheet says: Penne Arrabbiata 30/day, Getrüffelte Penne 30,
    Rührei mit Speck 15, Brownies 35, Penne Bolognese 30, Gelbes Curry 30,
    Kartoffelcremesuppe 15, Udon Bowl 30, Rotes Curry 30, Quinoa Bowl 15.

    Adjust column names to whatever step 4 revealed.
    """
    print(f"--- actual sales, KW34 ({KW34_START} .. {KW34_END}) ---")
    print(q(conn, f"""
        select dish_name,
               count(distinct sales_date)        as days_on_menu,
               sum(quantity)                     as total_portions,
               round(avg(daily_qty), 1)          as avg_per_day,
               max(daily_qty)                    as max_day,
               min(daily_qty)                    as min_day
        from (
            select dish_name, sales_date, sum(quantity) as daily_qty, sum(quantity) as quantity
            from analytics.{schema}.{table}
            where sales_date between '{KW34_START}' and '{KW34_END}'
            group by 1, 2
        )
        group by 1
        order by total_portions desc
    """))
    print("""
Read the result like this:
  avg_per_day ~= the sheet's number   -> it is a demand estimate
  avg_per_day consistently below it   -> it is a loading level, not demand
  max_day pinned at exactly the number -> silo capacity is binding
""")


# ---------------------------------------------------------------- step 7
def step7_oos_and_waste(conn):
    """
    TEST C — how often is demand censored, and what does waste look like?
    Adjust schema/column names from step 4 before running.
    """
    print("--- OOS events, last 12 weeks ---")
    print(q(conn, """
        select date_trunc('week', event_date) as week,
               count(*)                       as oos_events,
               count(distinct ingredient_name) as ingredients_affected
        from analytics.MARTS.FACT_CG_OOS_INGREDIENT
        where event_date >= dateadd(week, -12, current_date())
        group by 1 order by 1
    """))

    print("\n--- worst waste offenders, last 12 weeks ---")
    print(q(conn, """
        select ingredient_name,
               count(distinct waste_date) as days_with_waste,
               sum(quantity)              as total_wasted
        from analytics.MARTS.FACT_CG_WASTE
        where waste_date >= dateadd(week, -12, current_date())
        group by 1
        order by total_wasted desc
        limit 25
    """))


# ---------------------------------------------------------------- runner
STEPS = {
    "1": step1_connection,
    "2": step2_schemas,
    "3": step3_hunt_for_gaps,
    "4": step4_columns,
    "6": step6_validate_kw34,
    "7": step7_oos_and_waste,
}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "1"
    conn = connect()
    try:
        if which == "all":
            for k in sorted(STEPS):
                print(f"\n{'=' * 70}\nSTEP {k}\n{'=' * 70}")
                try:
                    STEPS[k](conn)
                except Exception as e:
                    print(f"step {k} failed: {e}")
        else:
            STEPS[which](conn)
    finally:
        conn.close()
