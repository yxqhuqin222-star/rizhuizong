# Archive — target-latest-term-baseline

Created at: 2026-06-25 18:40:35 CST

## Purpose

Rollback snapshot for the accepted version where latest-term display and broadcast images use the latest term from the target table, not demo-only terms.

## Included

- Local dashboard app: app.py, web/
- Summary generation: outputs/tongji_summary/
- Daily broadcast image generation and exported PNG/HTML: reports/
- Product docs and PM Brain records: docs/, knowledge/, decisions/, source/, ingestion/, INDEX.md, AGENTS.md, README.md
- Current input workbooks: tongji_demo.xlsx, tongji_target.xlsx

## Current Latest-Term Scope

- 初中: 暑_10
- 小学: 暑_8
- 高中: 暑_10

## Current Latest Metrics

- 目标: 28,430
- 现状: 9,432
- 完成率: 33.2%
- 明细行数: 79
- 落后项: 22

## Restore Note

To restore manually, copy the needed files/folders from this archive back to the project root. This archive is a filesystem snapshot because the project directory is not currently a git repository.
