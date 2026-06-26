from __future__ import annotations

import csv
import importlib.util
import json
import os
import re
import subprocess
from datetime import datetime
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
OUTPUT_DIR = ROOT / "outputs" / "tongji_summary"
DEMO_PATH = ROOT / "tongji_demo.xlsx"
TARGET_PATH = ROOT / "tongji_target.xlsx"
SUMMARY_SCRIPT = OUTPUT_DIR / "build_summary.py"
WORKBOOK_SCRIPT = OUTPUT_DIR / "build_workbook.mjs"
NODE_BIN = Path("/Users/kityhello/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node")
LAST_QUERY_PATH = OUTPUT_DIR / "query_result.csv"
REPORT_SCRIPT = ROOT / "reports" / "build_daily_report_images.py"
REPORT_EXPORT_SCRIPT = ROOT / "reports" / "export_daily_report_images.mjs"
REPORT_DIR = ROOT / "reports" / "daily_progress"
REPORT_FILES = {
    "primary": REPORT_DIR / "primary_daily_progress.png",
    "middle": REPORT_DIR / "middle_daily_progress.png",
    "high": REPORT_DIR / "high_daily_progress.png",
    "lec1": REPORT_DIR / "lec1_share.png",
}
REPORT_LABELS = {
    "primary": "小学",
    "middle": "初中",
    "high": "高中",
    "lec1": "lec1元占比",
}
DINGTALK_KEYWORD = "成单"
SERVER_DISABLED_PATH = ROOT / ".dashboard-server-disabled"


def load_local_env():
    for path in (ROOT / ".env", ROOT / ".env.local"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()
DINGTALK_WEBHOOK = os.environ.get("DINGTALK_WEBHOOK", "")


def load_summary_module():
    spec = importlib.util.spec_from_file_location("build_summary", SUMMARY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Cannot load summary module")
    spec.loader.exec_module(module)
    return module


summary_module = load_summary_module()


def json_safe(value):
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%Y-%m-%d")
    return value


def rows_from_payload(table_payload):
    headers = table_payload["headers"]
    return [
        {headers[index]: json_safe(value) for index, value in enumerate(row)}
        for row in table_payload["rows"]
    ]


def rebuild_outputs():
    summary, payload = summary_module.rebuild(DEMO_PATH, TARGET_PATH, OUTPUT_DIR)
    if NODE_BIN.exists():
        subprocess.run([str(NODE_BIN), str(WORKBOOK_SCRIPT)], cwd=OUTPUT_DIR, check=True)
    return summary, payload


def ensure_daily_report_images():
    subprocess.run(
        [
            "/Users/kityhello/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
            str(REPORT_SCRIPT),
        ],
        cwd=ROOT,
        check=True,
    )
    if NODE_BIN.exists():
        subprocess.run([str(NODE_BIN), str(REPORT_EXPORT_SCRIPT)], cwd=ROOT, check=True)


def ensure_payload():
    payload_path = OUTPUT_DIR / "summary_payload.json"
    if not payload_path.exists():
        rebuild_outputs()
    return json.loads(payload_path.read_text(encoding="utf-8"))


def report_image_url(dept, host):
    public_base = os.environ.get("DINGTALK_REPORT_BASE_URL", "").rstrip("/")
    if public_base:
        return f"{public_base}/download/report?dept={quote(dept)}"
    return f"http://{host}/download/report?dept={quote(dept)}"


def is_local_url(url):
    parsed = urlparse(url)
    return parsed.hostname in {"0.0.0.0", "localhost", "::1"}


def format_report_summary_value(key, value):
    if key in {"完成率", "平均进度"}:
        return f"{float(value) * 100:.0f}%"
    return value


def send_dingtalk_report(dept, host):
    if dept not in REPORT_FILES:
        raise ValueError("未知播报图类型。")
    if not DINGTALK_WEBHOOK:
        raise ValueError("缺少 DINGTALK_WEBHOOK，请在 .env.local 或环境变量中配置钉钉机器人地址。")

    image_path = REPORT_FILES[dept]
    if not image_path.exists():
        ensure_daily_report_images()
    if not image_path.exists():
        raise FileNotFoundError(f"播报图不存在：{image_path.name}，请先下载一次播报图或重新生成 Summary。")

    label = REPORT_LABELS[dept]
    image_url = report_image_url(dept, host)
    cache_bust = int(image_path.stat().st_mtime)
    separator = "&" if "?" in image_url else "?"
    image_url = f"{image_url}{separator}v={cache_bust}"
    title = f"{DINGTALK_KEYWORD} {label}每日招生进度播报"
    local_only_url = is_local_url(image_url)
    manifest = json.loads((REPORT_DIR / "manifest.json").read_text(encoding="utf-8"))
    report_meta = next((item for item in manifest if item["dept"] == label), None)
    summary = report_meta["summary"] if report_meta else {}
    summary_text = "\n".join(
        f"- {key}：{format_report_summary_value(key, value)}" for key, value in summary.items()
    )
    if local_only_url:
        text = (
            f"### {title}\n\n"
            f"{summary_text}\n\n"
            f"> 图片已在本机生成，但当前地址是 0.0.0.0，钉钉群内无法直接渲染。"
            f"请在本机看板下载：{image_url}"
        )
    else:
        text = f"### {title}\n\n{summary_text}\n\n![{title}]({image_url})\n\n[查看/下载图片]({image_url})"
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": text,
        },
    }
    request = Request(
        DINGTALK_WEBHOOK,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        result = json.loads(response.read().decode("utf-8"))

    return {
        "ok": result.get("errcode") == 0,
        "dept": dept,
        "label": label,
        "imageUrl": image_url,
        "localOnlyUrl": local_only_url,
        "dingtalk": result,
    }


def file_info(path):
    if not path.exists():
        return None
    stat = path.stat()
    return {
        "name": path.name,
        "updated_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "size": stat.st_size,
    }


def state_payload():
    payload = ensure_payload()
    return {
        "summary": rows_from_payload(payload["summary"]),
        "latestSummary": rows_from_payload(payload["latest_summary"]),
        "metrics": payload["metrics"],
        "files": {
            "demo": file_info(DEMO_PATH),
            "target": file_info(TARGET_PATH),
        },
    }


def infer_year(demo):
    dates = pd.to_datetime(demo["下单日期"], errors="coerce").dropna()
    if len(dates):
        return int(dates.max().year)
    return datetime.now().year


def parse_query(text, demo):
    year = infer_year(demo)
    date_match = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if date_match:
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        day = int(date_match.group(3))
    else:
        date_match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
        if not date_match:
            raise ValueError("未识别到日期，请输入类似“6月23日”。")
        month = int(date_match.group(1))
        day = int(date_match.group(2))

    last_from_match = re.search(r"(out_[A-Za-z0-9_]+)", text)
    if not last_from_match:
        raise ValueError("未识别到 last_from 编码，请输入类似 out_xxx 的编码。")

    return {
        "date": f"{year:04d}-{month:02d}-{day:02d}",
        "last_from": last_from_match.group(1),
    }


def run_natural_query(text):
    demo = pd.read_excel(DEMO_PATH, sheet_name=summary_module.DEMO_SHEET)
    summary_module.validate_columns(demo, summary_module.DEMO_REQUIRED_COLUMNS, "demo")
    parsed = parse_query(text, demo)

    order_dates = pd.to_datetime(demo["下单日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    mask = order_dates.eq(parsed["date"]) & demo["last_from"].astype(str).eq(parsed["last_from"])
    result = demo.loc[mask].copy()
    total = int(result["成单量"].sum()) if len(result) else 0

    export_cols = ["下单日期", "last_from", "成单量", "年级", "学部", "期次", "线索渠道二级分类", "价体"]
    result[export_cols].to_csv(LAST_QUERY_PATH, index=False, encoding="utf-8-sig")

    preview = result[export_cols].head(20).astype(object).where(pd.notna(result[export_cols]), None)
    return {
        "query": text,
        "conditions": parsed,
        "total": total,
        "matchedRows": int(len(result)),
        "preview": [
            {col: json_safe(row[col]) for col in export_cols}
            for _, row in preview.iterrows()
        ],
    }


def write_csv_response(handler, filename, rows):
    handler.send_response(200)
    handler.send_header("Content-Type", "text/csv; charset=utf-8")
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.end_headers()
    if not rows:
        handler.wfile.write("\ufeff".encode("utf-8"))
        return
    headers = list(rows[0].keys())
    text_rows = []
    sink = TextSink(text_rows)
    writer = csv.DictWriter(sink, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    handler.wfile.write(("\ufeff" + "".join(text_rows)).encode("utf-8"))


def parse_multipart_files(headers, body):
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: "
        + headers.get("Content-Type", "").encode("utf-8")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + body
    )
    files = {}
    for part in message.iter_parts():
        disposition = part.get_params(header="content-disposition", failobj=[])
        params = {key: value for key, value in disposition}
        name = params.get("name")
        filename = params.get("filename")
        if name and filename:
            files[name] = part.get_payload(decode=True) or b""
    return files


class TextSink:
    def __init__(self, rows):
        self.rows = rows

    def write(self, text):
        self.rows.append(text)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type):
        if not path.exists():
            self.send_error(404, "File not found")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/":
                self.send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            elif path in ("/static/styles.css", "/styles.css"):
                self.send_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
            elif path in ("/static/app.js", "/app.js"):
                self.send_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            elif path == "/api/state":
                self.send_json(state_payload())
            elif path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
            elif path == "/download/summary":
                query = parse_qs(parsed.query)
                scope = query.get("scope", ["latest"])[0]
                state = state_payload()
                rows = state["summary"] if scope == "all" else state["latestSummary"]
                write_csv_response(self, f"summary_{scope}.csv", rows)
            elif path == "/download/workbook":
                self.send_file(OUTPUT_DIR / "tongji_summary_current.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            elif path == "/download/query":
                self.send_file(LAST_QUERY_PATH, "text/csv; charset=utf-8")
            elif path == "/download/report":
                query = parse_qs(parsed.query)
                dept = query.get("dept", [""])[0]
                report_path = REPORT_FILES.get(dept)
                if report_path is None:
                    self.send_error(404, "Unknown report")
                    return
                if not report_path.exists():
                    ensure_daily_report_images()
                self.send_file(report_path, "image/png")
            else:
                self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/upload":
                self.handle_upload()
            elif parsed.path == "/api/query":
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                result = run_natural_query(data.get("query", ""))
                self.send_json(result)
            elif parsed.path == "/api/broadcast-report":
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                host = self.headers.get("Host", "0.0.0.0:8766")
                result = send_dingtalk_report(data.get("dept", ""), host)
                if not result["ok"]:
                    self.send_json(result, status=502)
                    return
                self.send_json(result)
            else:
                self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=400)

    def handle_upload(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        files = parse_multipart_files(self.headers, self.rfile.read(content_length))

        changed = []
        for field, target_path in [("demo", DEMO_PATH), ("target", TARGET_PATH)]:
            data = files.get(field)
            if data:
                with target_path.open("wb") as f:
                    f.write(data)
                changed.append(field)

        if not changed:
            raise ValueError("请至少上传 demo 或 target 文件。")

        rebuild_outputs()
        self.send_json({"ok": True, "changed": changed, "state": state_payload()})


def main():
    if SERVER_DISABLED_PATH.exists():
        print(f"Progress dashboard disabled by {SERVER_DISABLED_PATH}")
        return

    ensure_payload()
    server = ThreadingHTTPServer(("0.0.0.0", 8766), Handler)
    print("Progress dashboard: http://0.0.0.0:8766")
    server.serve_forever()


if __name__ == "__main__":
    main()
