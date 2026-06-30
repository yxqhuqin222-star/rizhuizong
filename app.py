from __future__ import annotations

import csv
import importlib.util
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
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
CHANNEL_ALIAS_PATH = ROOT / "config" / "channel_aliases.csv"
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
_query_demo_cache = None
_query_target_cache = None
_query_knowledge_cache = None


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
REPORT_IMAGE_UPLOAD_URL = os.environ.get("REPORT_IMAGE_UPLOAD_URL", "")
REPORT_UPLOAD_TOKEN = os.environ.get("REPORT_UPLOAD_TOKEN", "")


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
    ensure_daily_report_images()
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


def ensure_report_image_current(image_path):
    source_paths = (
        DEMO_PATH,
        TARGET_PATH,
        OUTPUT_DIR / "tongji_summary_current.xlsx",
        REPORT_SCRIPT,
        REPORT_EXPORT_SCRIPT,
    )
    latest_source_mtime = max(path.stat().st_mtime for path in source_paths)
    needs_refresh = (
        not image_path.exists()
        or image_path.stat().st_mtime < latest_source_mtime
        or datetime.fromtimestamp(image_path.stat().st_mtime).date() < datetime.now().date()
    )
    if needs_refresh:
        ensure_daily_report_images()


def ensure_payload():
    payload_path = OUTPUT_DIR / "summary_payload.json"
    if not payload_path.exists():
        rebuild_outputs()
    return json.loads(payload_path.read_text(encoding="utf-8"))


def upload_report_image(dept, image_path):
    if not REPORT_IMAGE_UPLOAD_URL or not REPORT_UPLOAD_TOKEN:
        raise ValueError("缺少 REPORT_IMAGE_UPLOAD_URL 或 REPORT_UPLOAD_TOKEN，无法上传播报图。")
    separator = "&" if "?" in REPORT_IMAGE_UPLOAD_URL else "?"
    request = Request(
        f"{REPORT_IMAGE_UPLOAD_URL}{separator}dept={quote(dept)}",
        data=image_path.read_bytes(),
        headers={
            "Authorization": f"Bearer {REPORT_UPLOAD_TOKEN}",
            "Content-Type": "image/png",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    image_url = result.get("url")
    if not image_url:
        raise RuntimeError("图片存储服务未返回公开地址。")
    return image_url


def format_report_summary_value(key, value):
    if key in {"完成率", "平均进度"}:
        return f"{float(value) * 100:.0f}%"
    return value


def send_dingtalk_report(dept):
    if dept not in REPORT_FILES:
        raise ValueError("未知播报图类型。")
    if not DINGTALK_WEBHOOK:
        raise ValueError("缺少 DINGTALK_WEBHOOK，请在 .env.local 或环境变量中配置钉钉机器人地址。")

    image_path = REPORT_FILES[dept]
    ensure_report_image_current(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"播报图不存在：{image_path.name}，请先下载一次播报图或重新生成 Summary。")

    label = REPORT_LABELS[dept]
    image_url = upload_report_image(dept, image_path)
    title = f"{DINGTALK_KEYWORD} {label}每日招生进度播报"
    manifest = json.loads((REPORT_DIR / "manifest.json").read_text(encoding="utf-8"))
    report_meta = next((item for item in manifest if item["dept"] == label), None)
    summary = report_meta["summary"] if report_meta else {}
    summary_text = "\n".join(
        f"- {key}：{format_report_summary_value(key, value)}" for key, value in summary.items()
    )
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
        "localOnlyUrl": False,
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


def load_query_demo():
    global _query_demo_cache
    stat = DEMO_PATH.stat()
    cache_key = (stat.st_mtime_ns, stat.st_size)
    if _query_demo_cache and _query_demo_cache[0] == cache_key:
        return _query_demo_cache[1]
    demo = pd.read_excel(DEMO_PATH, sheet_name=summary_module.DEMO_SHEET)
    _query_demo_cache = (cache_key, demo)
    return demo


def load_query_target():
    global _query_target_cache
    stat = TARGET_PATH.stat()
    cache_key = (stat.st_mtime_ns, stat.st_size)
    if _query_target_cache and _query_target_cache[0] == cache_key:
        return _query_target_cache[1]
    target = pd.read_excel(TARGET_PATH, sheet_name=summary_module.TARGET_SHEET)
    _query_target_cache = (cache_key, target)
    return target


def normalize_query_text(value):
    return re.sub(r"[\s_-]+", "", str(value).lower())


def load_channel_aliases():
    with CHANNEL_ALIAS_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    aliases = []
    names_by_code = {}
    codes_by_alias = {}
    for row in rows:
        code = row["last_from"].strip()
        channel_name = row["channel_name"].strip()
        existing_name = names_by_code.get(code)
        if existing_name and existing_name != channel_name:
            raise ValueError(f"同一 last_from 配置了多个渠道名称：{code}")
        names_by_code[code] = channel_name
        values = [channel_name, *row.get("aliases", "").split("|")]
        for value in values:
            normalized = normalize_query_text(value)
            if normalized:
                existing_code = codes_by_alias.get(normalized)
                if existing_code and existing_code != code:
                    raise ValueError(f"渠道别名重复：{value}")
                codes_by_alias[normalized] = code
                aliases.append((normalized, code, channel_name))
    aliases.sort(key=lambda item: len(item[0]), reverse=True)
    return aliases, names_by_code


def parse_query_date(text, demo):
    if "昨天" in text:
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if "今天" in text:
        return datetime.now().strftime("%Y-%m-%d")

    year = infer_year(demo)
    date_match = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if date_match:
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        day = int(date_match.group(3))
    else:
        date_match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
        if not date_match:
            date_match = re.search(r"(?<!\d)(\d{1,2})[./-](\d{1,2})(?!\d)", text)
        if not date_match:
            return None
        month = int(date_match.group(1))
        day = int(date_match.group(2))
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("日期无效，请输入类似“6月27日”。") from exc


QUERY_MEASURE_COLUMNS = {"成单量", "折算单量", "目标"}
QUERY_DATE_COLUMNS = {"下单日期", "target_time", "进量日期", "支付时间", "外呼日期", "外呼时间"}
QUERY_SHARED_DIMENSIONS = ["学部", "期次", "线索渠道二级分类", "价体", "年级"]
QUERY_UNLABELED_MAX_UNIQUES = 200
DEPARTMENT_GROUP = ["小学", "初中", "高中"]


def canonical_query_value(field, value):
    if field == "线索渠道二级分类":
        value = summary_module.normalize_channel(value)
    if isinstance(value, str):
        return value.strip()
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def build_query_knowledge(demo, target):
    global _query_knowledge_cache
    uses_cached_sources = (
        _query_demo_cache
        and _query_target_cache
        and demo is _query_demo_cache[1]
        and target is _query_target_cache[1]
    )
    cache_key = (id(demo), id(target))
    if (
        uses_cached_sources
        and _query_knowledge_cache
        and _query_knowledge_cache[:2] == cache_key
    ):
        return _query_knowledge_cache[2]

    knowledge = {}
    all_fields = list(dict.fromkeys([*demo.columns, *target.columns]))
    for field in all_fields:
        if field in QUERY_MEASURE_COLUMNS or field in QUERY_DATE_COLUMNS:
            continue
        values = []
        for source in (demo, target):
            if field not in source.columns:
                continue
            values.extend(
                canonical_query_value(field, value)
                for value in source[field].dropna().unique().tolist()
            )
        unique_values = []
        seen = set()
        for value in values:
            if value is None or str(value).strip() == "":
                continue
            normalized = normalize_query_text(value)
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_values.append(value)
        knowledge[field] = unique_values
    if uses_cached_sources:
        _query_knowledge_cache = (*cache_key, knowledge)
    return knowledge


def extract_query_filters(text, demo, target):
    normalized_text = normalize_query_text(text)
    knowledge = build_query_knowledge(demo, target)
    candidates = []

    for field, values in knowledge.items():
        normalized_field = normalize_query_text(field)
        field_is_named = normalized_field in normalized_text
        allow_unlabeled = len(values) <= QUERY_UNLABELED_MAX_UNIQUES
        for value in values:
            normalized_value = normalize_query_text(value)
            if len(normalized_value) < 2 or normalized_value not in normalized_text:
                continue
            if normalized_value.isdigit() and not field_is_named:
                continue
            if field_is_named or allow_unlabeled:
                candidates.append(
                    {
                        "field": field,
                        "value": value,
                        "normalized": normalized_value,
                        "explicit": field_is_named,
                    }
                )

    longest_candidates = []
    for candidate in candidates:
        if candidate["explicit"]:
            longest_candidates.append(candidate)
            continue
        if any(
            len(other["normalized"]) > len(candidate["normalized"])
            and candidate["normalized"] in other["normalized"]
            for other in candidates
        ):
            continue
        longest_candidates.append(candidate)

    dimension_priority = {field: index for index, field in enumerate(QUERY_SHARED_DIMENSIONS)}
    by_normalized_value = {}
    for candidate in longest_candidates:
        by_normalized_value.setdefault(candidate["normalized"], []).append(candidate)

    deduplicated = []
    for same_value_candidates in by_normalized_value.values():
        explicit_candidates = [item for item in same_value_candidates if item["explicit"]]
        if explicit_candidates:
            deduplicated.extend(explicit_candidates)
            continue
        deduplicated.append(
            min(
                same_value_candidates,
                key=lambda item: dimension_priority.get(item["field"], len(dimension_priority)),
            )
        )

    filters = {}
    for field in {item["field"] for item in deduplicated}:
        field_candidates = [item for item in deduplicated if item["field"] == field]
        field_candidates.sort(key=lambda item: len(item["normalized"]), reverse=True)
        selected = field_candidates[0]
        conflicting = [
            item
            for item in field_candidates[1:]
            if item["normalized"] not in selected["normalized"]
        ]
        if conflicting:
            values = "、".join(str(item["value"]) for item in field_candidates)
            return {}, f"检测到多个{field}值（{values}），你想查询哪一个？"
        filters[field] = selected["value"]

    return filters, None


def parse_grouping_intent(text):
    normalized = normalize_query_text(text)
    requests_department_group = any(
        phrase in normalized
        for phrase in ("小初高", "小学高三个学部", "三个学部", "各学部")
    )
    requests_breakdown = any(word in text for word in ("分别", "各", "按学部"))
    if requests_department_group and requests_breakdown:
        return "学部", DEPARTMENT_GROUP
    return None, None


def parse_query(text, demo, context=None, target=None):
    if target is None:
        target = pd.DataFrame()
    aliases, names_by_code = load_channel_aliases()
    parsed = {"metric": "成单量"}

    if isinstance(context, dict):
        context_date = str(context.get("date", ""))
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", context_date):
            parsed["date"] = context_date
        context_code = str(context.get("last_from", ""))
        if re.fullmatch(r"out_[A-Za-z0-9_]+", context_code):
            parsed["last_from"] = context_code
            parsed["channel_name"] = names_by_code.get(context_code, context_code)
        if context.get("metric") == "成单量":
            parsed["metric"] = "成单量"
        if context.get("metric") == "目标":
            parsed["metric"] = "目标"
        context_filters = context.get("filters")
        if isinstance(context_filters, dict):
            parsed["filters"] = dict(context_filters)
        if context.get("group_by") == "学部":
            parsed["group_by"] = "学部"
        if context.get("channel_field") == "线索渠道二级分类":
            parsed.setdefault("filters", {})["线索渠道二级分类"] = str(
                context.get("channel_value", "")
            )
            parsed["channel_name"] = str(
                context.get("channel_name", context.get("channel_value", ""))
            )
        if str(context.get("payment", "")).isdigit():
            parsed.setdefault("filters", {})["价体"] = int(context["payment"])

    query_date = parse_query_date(text, demo)
    if query_date:
        parsed["date"] = query_date

    if re.search(r"目标", text, re.IGNORECASE):
        parsed["metric"] = "目标"

    dynamic_filters, filter_question = extract_query_filters(text, demo, target)
    if filter_question:
        return {
            "status": "needs_clarification",
            "missingField": "filter",
            "question": filter_question,
            "context": parsed,
        }
    if dynamic_filters:
        parsed.setdefault("filters", {}).update(dynamic_filters)

    group_by, group_values = parse_grouping_intent(text)
    if group_by:
        parsed["group_by"] = group_by
        parsed.setdefault("filters", {}).pop("年级", None)
        parsed["filters"][group_by] = group_values

    if re.search(r"llm(?:外呼|渠道)?", text, re.IGNORECASE):
        parsed.setdefault("filters", {})["线索渠道二级分类"] = "LLM外呼"
        parsed["channel_name"] = "LLM外呼"
        if re.search(r"9[.]9|9元9|\b990\b", text, re.IGNORECASE):
            parsed.setdefault("filters", {})["价体"] = 990

    last_from_match = re.search(r"(out_[A-Za-z0-9_]+)", text)
    if last_from_match:
        code = last_from_match.group(1)
        parsed["last_from"] = code
        parsed["channel_name"] = names_by_code.get(code, code)
    else:
        normalized_text = normalize_query_text(text)
        matched_channels = {
            code: channel_name
            for alias, code, channel_name in aliases
            if alias in normalized_text
        }
        if len(matched_channels) > 1:
            return {
                "status": "needs_clarification",
                "missingField": "last_from",
                "question": "检测到多个渠道，你想查询哪一个？",
                "context": parsed,
            }
        if matched_channels:
            code, channel_name = next(iter(matched_channels.items()))
            parsed["last_from"] = code
            parsed["channel_name"] = channel_name

    if "last_from" not in parsed and not parsed.get("filters"):
        return {
            "status": "needs_clarification",
            "missingField": "filter",
            "question": (
                "你想查询哪个渠道？"
                if "渠道" in text
                else "你想按哪个字段或业务范围查询？"
            ),
            "context": parsed,
        }
    if parsed["metric"] == "成单量" and "date" not in parsed:
        return {
            "status": "needs_clarification",
            "missingField": "date",
            "question": "你想查询哪个时间段的？",
            "context": parsed,
        }

    conditions = {
        "channelName": parsed.get(
            "channel_name",
            parsed.get("filters", {}).get("线索渠道二级分类", "全部"),
        ),
        "metric": parsed["metric"],
        "filters": parsed.get("filters", {}),
    }
    if "date" in parsed:
        conditions["date"] = parsed["date"]
    if "last_from" in parsed:
        conditions["last_from"] = parsed["last_from"]
    if "线索渠道二级分类" in conditions["filters"]:
        conditions["channel_field"] = "线索渠道二级分类"
        conditions["channel_value"] = conditions["filters"]["线索渠道二级分类"]
    if "价体" in conditions["filters"]:
        conditions["payment"] = conditions["filters"]["价体"]
    if parsed.get("group_by"):
        conditions["groupBy"] = parsed["group_by"]

    return {
        "status": "complete",
        "conditions": conditions,
    }


def run_natural_query(
    text,
    context=None,
    page=1,
    page_size=10,
    demo=None,
    export_path=LAST_QUERY_PATH,
    target=None,
):
    demo_was_provided = demo is not None
    if demo is None:
        demo = load_query_demo()
    if target is None:
        target = pd.DataFrame() if demo_was_provided else load_query_target()
    summary_module.validate_columns(demo, summary_module.DEMO_REQUIRED_COLUMNS, "demo")
    if len(target):
        summary_module.validate_columns(target, summary_module.TARGET_REQUIRED_COLUMNS, "target")
    parsed = parse_query(text, demo, target=target, context=context)
    if parsed["status"] == "needs_clarification":
        return parsed

    conditions = parsed["conditions"]
    metric = conditions["metric"]
    source = demo if metric == "成单量" else target
    if metric == "目标" and not len(target):
        raise ValueError("当前没有可用的 target 数据。")

    mask = pd.Series(True, index=source.index)
    date_field = None
    if "date" in conditions:
        date_field = "下单日期" if metric == "成单量" else (
            "进量日期" if "进量日期" in text else "target_time"
        )
        source_dates = pd.to_datetime(source[date_field], errors="coerce").dt.strftime("%Y-%m-%d")
        mask &= source_dates.eq(conditions["date"])
    if "last_from" in conditions:
        if "last_from" not in source.columns:
            mask &= False
        else:
            mask &= source["last_from"].astype(str).eq(conditions["last_from"])
    for field, value in conditions["filters"].items():
        if field not in source.columns:
            mask &= False
            continue
        if isinstance(value, list):
            source_values = source[field].map(lambda item: canonical_query_value(field, item))
            mask &= source_values.astype(str).isin([str(item) for item in value])
        elif field == "线索渠道二级分类" and value == "外部微转-*":
            mask &= source[field].astype(str).str.startswith("外部微转-")
        elif isinstance(value, (int, float)):
            mask &= pd.to_numeric(source[field], errors="coerce").eq(value)
        else:
            source_values = source[field].map(lambda item: canonical_query_value(field, item))
            mask &= source_values.astype(str).eq(str(value))

    result = source.loc[mask].copy()
    total = int(pd.to_numeric(result[metric], errors="coerce").fillna(0).sum())
    breakdown = []
    group_by = conditions.get("groupBy")
    if group_by:
        grouped = (
            result.assign(_metric=pd.to_numeric(result[metric], errors="coerce").fillna(0))
            .groupby(group_by)["_metric"]
            .sum()
        )
        requested_values = conditions["filters"].get(group_by, [])
        breakdown = [
            {"label": label, "value": int(grouped.get(label, 0))}
            for label in requested_values
        ]

    if metric == "成单量":
        export_cols = [
            "下单日期",
            "last_from",
            "成单量",
            "年级",
            "学部",
            "期次",
            "线索渠道二级分类",
            "价体",
        ]
    else:
        export_cols = [
            "target_time",
            "进量日期",
            "目标",
            "年级",
            "学部",
            "期次",
            "线索渠道二级分类",
            "价体",
        ]
    if export_path is not None:
        result[export_cols].to_csv(export_path, index=False, encoding="utf-8-sig")

    page_size = int(page_size) if str(page_size).isdigit() else 10
    if page_size not in (10, 20, 50):
        page_size = 10
    page = int(page) if str(page).isdigit() else 1
    total_pages = max(1, (len(result) + page_size - 1) // page_size)
    page = min(max(1, page), total_pages)
    start = (page - 1) * page_size

    page_rows = result[export_cols].iloc[start:start + page_size]
    page_rows = page_rows.astype(object).where(pd.notna(page_rows), None)
    scope_name = "、".join(
        "、".join(str(item) for item in value) if isinstance(value, list) else str(value)
        for value in conditions["filters"].values()
    )
    if not scope_name:
        scope_name = conditions["channelName"]
    answer = (
        f"{conditions.get('date', '')}{'，' if conditions.get('date') else ''}"
        f"{scope_name}的{metric}是{total}，命中{len(result)}行。"
    )
    if breakdown:
        parts = "，".join(f"{item['label']}{item['value']}" for item in breakdown)
        answer = (
            f"{conditions.get('date', '')}{'，' if conditions.get('date') else ''}"
            f"{parts}；合计{total}。"
        )

    return {
        "status": "complete",
        "query": text,
        "conditions": conditions,
        "total": total,
        "matchedRows": int(len(result)),
        "answer": answer,
        "breakdown": breakdown,
        "columns": export_cols,
        "dateField": date_field,
        "metricColumn": metric,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
        "rows": [
            {col: json_safe(row[col]) for col in export_cols}
            for _, row in page_rows.iterrows()
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
            elif path == "/outputs/tongji_summary/summary_payload.json":
                self.send_file(OUTPUT_DIR / "summary_payload.json", "application/json; charset=utf-8")
            elif path == "/api/state":
                self.send_json(state_payload())
            elif path == "/favicon.ico":
                self.send_file(WEB_DIR / "favicon.ico", "image/x-icon")
            elif path == "/favicon.png":
                self.send_file(WEB_DIR / "favicon.png", "image/png")
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
                ensure_report_image_current(report_path)
                self.send_file(report_path, "image/png")
            else:
                self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path != "/download/report":
                self.send_error(404)
                return
            dept = parse_qs(parsed.query).get("dept", [""])[0]
            report_path = REPORT_FILES.get(dept)
            if report_path is None:
                self.send_error(404, "Unknown report")
                return
            ensure_report_image_current(report_path)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(report_path.stat().st_size))
            self.end_headers()
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/upload":
                self.handle_upload()
            elif parsed.path == "/api/reload-demo":
                if not DEMO_PATH.exists():
                    raise FileNotFoundError(f"固定 demo 文件不存在：{DEMO_PATH}")
                rebuild_outputs()
                self.send_json({"ok": True, "changed": ["demo"], "state": state_payload()})
            elif parsed.path == "/api/query":
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                result = run_natural_query(
                    data.get("query", ""),
                    context=data.get("context"),
                    page=data.get("page", 1),
                    page_size=data.get("pageSize", 10),
                )
                self.send_json(result)
            elif parsed.path == "/api/broadcast-report":
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                result = send_dingtalk_report(data.get("dept", ""))
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
