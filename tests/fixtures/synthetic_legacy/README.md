# Synthetic legacy fixture

This fixture is intentionally synthetic and contains no workbook, supplier, customer, or production data.

- `legacy_inputs.csv` exercises the documented `legacy_kw34/v1` arithmetic.
- `ITEM_A` matches its calculated order.
- `ITEM_B` has a positive calculated order and a blank observed order, which must produce `UNEXPLAINED_BLANK_ORDER`.
- `ITEM_C` exercises zero demand and stock remaining after a zero bridge.

The real KW33/KW34 golden fixture is a separate human gate. Do not replace this file with workbook-derived rows until `HA-02` in `docs/plans/human_action_register.md` is resolved.
