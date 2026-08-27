#!/usr/bin/env python3
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "netlify" / "public"
WEB_DIR = PUBLIC_DIR / "web"
API_DIR = PUBLIC_DIR / "api"
REPORT_DIR = PUBLIC_DIR / "reports"
DOWNLOAD_DIR = PUBLIC_DIR / "downloads"


def rows_from_payload(payload):
    headers = payload["headers"]
    return [dict(zip(headers, row)) for row in payload["rows"]]


def reset_directory(path):
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)


def build():
    payload_path = ROOT / "outputs" / "tongji_summary" / "summary_payload.json"
    metadata_path = ROOT / "outputs" / "tongji_summary" / "upload_metadata.json"
    workbook_path = ROOT / "outputs" / "tongji_summary" / "tongji_summary_current.xlsx"

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    upload_metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata_path.exists()
        else {}
    )

    reset_directory(WEB_DIR)
    reset_directory(API_DIR)
    reset_directory(REPORT_DIR)
    reset_directory(DOWNLOAD_DIR)

    for source in (ROOT / "web").iterdir():
        if source.is_file():
            shutil.copy2(source, WEB_DIR / source.name)

    index_path = WEB_DIR / "index.html"
    index_html = index_path.read_text(encoding="utf-8")
    index_html = index_html.replace(
        '<script src="./app.js',
        '<script>window.DASHBOARD_READ_ONLY = true;</script>\n  <script src="./app.js',
        1,
    )
    index_path.write_text(index_html, encoding="utf-8")

    state = {
        "summary": rows_from_payload(payload["summary"]),
        "latestSummary": rows_from_payload(payload["latest_summary"]),
        "detailLatestSummary": rows_from_payload(
            payload.get("detail_latest_summary", payload["latest_summary"])
        ),
        "metrics": payload["metrics"],
        "files": {
            "demo": {
                "name": "tongji_demo.xlsx",
                "uploaded_at": upload_metadata.get("demo"),
            },
            "target": {
                "name": "tongji_target.xlsx",
                "uploaded_at": upload_metadata.get("target"),
            },
        },
        "reportUrls": {
            "overall": "/reports/overall_progress.png",
            "primary": "/reports/primary_daily_progress.png",
            "middle": "/reports/middle_daily_progress.png",
            "high": "/reports/high_daily_progress.png",
            "zipin": "/reports/zipin_daily_progress.png",
            "lec1": "/reports/lec1_share.png",
        },
    }
    state_json = json.dumps(
        state,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    (API_DIR / "state.json").write_text(
        state_json,
        encoding="utf-8",
    )
    (API_DIR / "state-static.json").write_text(
        state_json,
        encoding="utf-8",
    )

    report_names = (
        "overall_progress.png",
        "primary_daily_progress.png",
        "middle_daily_progress.png",
        "high_daily_progress.png",
        "zipin_daily_progress.png",
        "lec1_share.png",
    )
    for name in report_names:
        shutil.copy2(ROOT / "reports" / "daily_progress" / name, REPORT_DIR / name)
    shutil.copy2(workbook_path, DOWNLOAD_DIR / workbook_path.name)


if __name__ == "__main__":
    build()
