# Synthetic improved-file fixture

This fixture is intentionally synthetic and safe to commit. It exercises daily
menu-aware demand, shared-item BOM aggregation, timestamped opening stock,
manual open POs, a receipt inside the horizon, and a receipt after the horizon.
`source_manifest.csv` is the authoritative declaration of dataset provenance;
an empty `open_pos.csv` is never interpreted without that declaration.
