# Ingestion — Progress Dashboard Requirements

Source: [source/adhoc/2026-06-25-progress-dashboard-requirements.md](../../source/adhoc/2026-06-25-progress-dashboard-requirements.md)
Date: 2026-06-25

## Observations

- The user needs a daily operational dashboard, not a generic analytics site.
- The default view must prioritize the latest `期次` for each `学部`; older terms stay available through filters.
- The user wants upload-driven refresh: daily `demo`, weekly `target`.
- The user wants exports for latest-term view, full summary, and query details.
- Natural-language querying is valuable but low-frequency, so it should be a compact entry rather than a large persistent panel.
- The current data calculation rules are already validated in Excel outputs.

## Interpretations

- V1 should optimize for speed of daily inspection: upload, regenerate, scan KPI cards, inspect latest-term table, export.
- V1 should keep data processing local and file-based. A database or login system adds cost without solving a current problem.
- The natural-language query should remain rule-based in V1. It only needs to answer date + `last_from` + `成单量` questions.

## Product Requirements Routed

- Create PRD for the local progress dashboard.
- Create a feature file for the dashboard build.
- Create a decision record for V1 architecture: local Python web app with file-based storage.

