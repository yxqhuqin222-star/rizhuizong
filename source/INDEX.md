# Source — verbatim originals

This directory preserves original requirement evidence before it is summarized in the PRD or a decision record.

## Why this exists

Summaries are lossy. `source/` provides the audit anchor for checking what was originally requested. Existing source files are not edited after creation.

## Layout

```
source/
└── adhoc/        # original requirements and other uncategorized evidence
```

## Naming

`source/<kind>/YYYY-MM-DD-<slug>.md`

## Rules

- **Verbatim only.** No edits, no cleanup, no commentary. Wrap the original content in a fenced block if it's anything other than plain prose.
- **Header is metadata-only.** Source URL, retrieval timestamp, and participant when applicable.
- **One file per artifact.** Do not concatenate sources.
- **Never delete from `source/`.** Even after a hypothesis is killed and its ingestion record is archived, the source stays.
