# Development Plan — Progress Dashboard V1

## Scope

Build a local web app for daily progress monitoring.

## Files

- `app.py` — local HTTP server and API.
- `web/index.html` — dashboard UI.
- `web/styles.css` — dashboard styling.
- `web/app.js` — client-side filters, upload, export, query.
- `outputs/tongji_summary/build_summary.py` — reusable summary calculation.
- `docs/PRD-progress-dashboard.md` — product spec.

## Implementation Steps

1. Refactor summary calculation into reusable functions.
2. Add server endpoints:
   - `GET /`
   - `GET /api/state`
   - `POST /api/upload`
   - `POST /api/query`
   - `GET /download/summary?scope=latest|all`
   - `GET /download/query`
3. Build dashboard UI:
   - Latest-term KPI cards.
   - Latest-term table by default.
   - Filters.
   - Upload controls.
   - Export buttons.
   - Low-frequency natural-language query entry.
   - Daily broadcast image download entries for `小学`, `初中`, and `高中`.
4. Verify:
   - Summary totals match Excel.
   - Latest-term metrics match expected values.
   - Query example returns `321`.
   - Downloads return files.
   - Broadcast image downloads return valid PNG files.

## Out of Scope for V1

- Login.
- Database.
- Cloud deployment.
- Editable targets.
- Charts.
- Upload history.
- General-purpose natural-language analytics.
