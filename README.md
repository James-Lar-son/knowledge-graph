# Knowledge graph — Taguette ingestion, viewer, public site

Read `ARCHITECTURE.md` first (design, privacy boundary, runbooks).
Day-to-day coding: `TAGUETTE_CHEATSHEET.md`. Ingest protocol:
`INGESTION.md`. Edge-derivation audit: `EDGE_INFERENCE_AUDIT.md`.

- Canonical data: `graph.working.json` (the original upload is untouched elsewhere)
- Ingest: `python3 ingest_taguette.py --input <export.csv|.sqlite3>` (dry run), then `--apply`
- Local viewer: `python3 build_viewer.py` → `graph-viewer.html`
- Public site: `python3 build_viewer.py --public-only --out deploy/index.html` (leak-gated)
