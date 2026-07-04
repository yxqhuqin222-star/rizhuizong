# Decision: Build V1 as a local file-based dashboard

## Status
decided

## Date
2026-06-25

## Context

The user needs a daily progress dashboard using Excel files. `demo` changes daily and `target` changes weekly. The workflow is currently local and file-based.

## Options considered

1. Local Python web app with file-based storage.
2. Full web app with database and deployment.
3. Static HTML prototype only.

## Decision

Build V1 as a local Python web app with file-based storage.

## Why

This matches the current workflow, avoids unnecessary setup, and lets the user upload Excel files, inspect the latest-term dashboard, and export data quickly.

## Evidence

- User asked for daily `demo` upload, weekly `target` update, summary display, and export in a local dashboard workflow. [source/adhoc/2026-06-25-progress-dashboard-requirements.md](../source/adhoc/2026-06-25-progress-dashboard-requirements.md)
- The validated prototype already represents the desired V1 interface. [source/adhoc/2026-06-25-progress-dashboard-requirements.md](../source/adhoc/2026-06-25-progress-dashboard-requirements.md)

## Explicitly NOT doing

- No login, database, or cloud deployment in V1. [source/adhoc/2026-06-25-progress-dashboard-requirements.md](../source/adhoc/2026-06-25-progress-dashboard-requirements.md)
- No advanced natural-language analysis in V1. [source/adhoc/2026-06-25-progress-dashboard-requirements.md](../source/adhoc/2026-06-25-progress-dashboard-requirements.md)

## What would reverse this

Revisit if the user needs multiple users, long-term upload history, remote access, or scheduled automation.

## Remaining ambiguities

- Whether `target_time` should remain English or be renamed in future source files.
- Whether upload history is needed in V2.

## Linked

- PRD: [docs/PRD-progress-dashboard.md](../docs/PRD-progress-dashboard.md)
