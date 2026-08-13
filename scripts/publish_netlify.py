#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_BASE_URL = "https://kityhello.dpdns.org"
PRODUCTION_STATE_URL = f"{PRODUCTION_BASE_URL}/api/state"
PROJECT_PYTHON = Path(
    "/Users/kityhello/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/python/bin/python3"
)
PYTHON_BIN = str(PROJECT_PYTHON if PROJECT_PYTHON.exists() else Path(sys.executable))
DEPARTMENTS = ("小学", "初中", "高中")
PUBLISH_PATHS = (
    "tongji_demo.xlsx",
    "tongji_target.xlsx",
    "outputs/tongji_summary",
    "reports/daily_progress",
)


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


def git_lines(*args: str) -> list[str]:
    output = run("git", *args, capture=True)
    return [line for line in output.splitlines() if line]


def parse_porcelain_paths(output: str) -> list[str]:
    paths = []
    entries = [entry for entry in output.split("\0") if entry]
    index = 0
    while index < len(entries):
        entry = entries[index]
        status = entry[:2]
        path = entry[3:]
        if "R" in status or "C" in status:
            index += 1
            path = entries[index]
        paths.append(path)
        index += 1
    return paths


def changed_worktree_paths() -> list[str]:
    output = run(
        "git",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        capture=True,
    )
    return parse_porcelain_paths(output)


def rows_from_payload(table: dict) -> list[dict]:
    headers = table["headers"]
    return [dict(zip(headers, row)) for row in table["rows"]]


def optional_float(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    if value in (None, "", "<NA>"):
        return None
    number = float(value)
    return None if math.isnan(number) else number


def department_snapshot(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["学部"]].append(row)

    snapshot = {}
    for department in DEPARTMENTS:
        department_rows = grouped[department]
        if not department_rows:
            raise ValueError(f"{department}没有最新期次数据")

        terms = {row["期次"] for row in department_rows}
        progress_values = {
            float(row["进度"])
            for row in department_rows
            if row.get("进度") not in (None, "")
        }
        if len(terms) != 1:
            raise ValueError(f"{department}最新明细包含多个期次：{sorted(terms)}")
        if len(progress_values) > 1:
            raise ValueError(
                f"{department}最新明细进度不唯一：{sorted(progress_values)}"
            )

        target = sum(float(row.get("目标") or 0) for row in department_rows)
        current = sum(float(row.get("现状") or 0) for row in department_rows)
        progress = next(iter(progress_values)) if progress_values else None
        snapshot[department] = {
            "term": next(iter(terms)),
            "target": int(target),
            "current": int(current),
            "completion": current / target if target else None,
            "progress": progress,
        }
    return snapshot


def validate_outputs() -> tuple[dict, dict[str, dict]]:
    output_dir = ROOT / "outputs" / "tongji_summary"
    report_dir = ROOT / "reports" / "daily_progress"
    payload = json.loads(
        (output_dir / "summary_payload.json").read_text(encoding="utf-8")
    )
    latest_rows = rows_from_payload(payload["latest_summary"])
    snapshot = department_snapshot(latest_rows)

    manifest = json.loads((report_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest_by_department = {item["dept"]: item for item in manifest}
    for department, expected in snapshot.items():
        report = manifest_by_department.get(department)
        if report is None:
            raise ValueError(f"播报图清单缺少{department}")
        summary = report["summary"]
        actual = {
            "term": report["term"],
            "target": int(summary["目标"]),
            "current": int(summary["成单量"]),
            "completion": optional_float(summary["完成率"]),
            "progress": optional_float(summary["平均进度"]),
        }
        for key in ("term", "target", "current"):
            if actual[key] != expected[key]:
                raise ValueError(
                    f"{department}{key}不一致：明细={expected[key]}，播报图={actual[key]}"
                )
        for key in ("completion", "progress"):
            if actual[key] is None and expected[key] is None:
                continue
            if actual[key] is None or expected[key] is None or abs(actual[key] - expected[key]) > 1e-9:
                raise ValueError(
                    f"{department}{key}不一致：明细={expected[key]}，播报图={actual[key]}"
                )

    required_files = (
        output_dir / "tongji_summary_current.xlsx",
        report_dir / "overall_progress.png",
        report_dir / "primary_daily_progress.png",
        report_dir / "middle_daily_progress.png",
        report_dir / "high_daily_progress.png",
        report_dir / "lec1_share.png",
    )
    for path in required_files:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"发布文件缺失或为空：{path.relative_to(ROOT)}")

    return payload, snapshot


def print_snapshot(snapshot: dict[str, dict]) -> None:
    for department in DEPARTMENTS:
        item = snapshot[department]
        completion = (
            f"{item['completion']:.1%}"
            if item["completion"] is not None
            else "--"
        )
        progress = f"{item['progress']:.1%}" if item["progress"] is not None else "--"
        print(
            f"{department} {item['term']}："
            f"目标={item['target']}，现状={item['current']}，"
            f"完成率={completion}，进度={progress}"
        )


def rebuild_and_test() -> tuple[dict, dict[str, dict]]:
    run(
        PYTHON_BIN,
        "-c",
        "import app; app.rebuild_outputs()",
    )
    run(
        PYTHON_BIN,
        "-m",
        "unittest",
        "tests.test_summary_progress",
        "tests.test_netlify_readonly",
        "tests.test_publish_netlify",
    )
    return validate_outputs()


def assert_only_publish_paths_changed() -> None:
    unrelated = []
    for path in changed_worktree_paths():
        if not any(
            path == allowed or path.startswith(f"{allowed}/")
            for allowed in PUBLISH_PATHS
        ):
            unrelated.append(path)
    if unrelated:
        details = "\n".join(unrelated)
        raise RuntimeError(f"存在非数据改动，一键发布已停止：\n{details}")


def assert_publish_preconditions() -> None:
    branch = run("git", "branch", "--show-current", capture=True)
    if branch != "main":
        raise RuntimeError(f"请先切换到 main；当前分支是 {branch}")

    run("git", "fetch", "origin", "main")
    head = run("git", "rev-parse", "HEAD", capture=True)
    origin_main = run("git", "rev-parse", "origin/main", capture=True)
    if head != origin_main:
        raise RuntimeError("本地 main 与 origin/main 不一致，请先同步后再发布")

    staged = git_lines("diff", "--cached", "--name-only")
    if staged:
        details = "\n".join(staged)
        raise RuntimeError(f"暂存区已有文件，一键发布已停止：\n{details}")
    assert_only_publish_paths_changed()


def wait_for_production(expected_payload: dict) -> None:
    expected_rows = rows_from_payload(expected_payload["latest_summary"])
    for attempt in range(1, 31):
        try:
            with urlopen(f"{PRODUCTION_STATE_URL}?check={int(time.time())}", timeout=10) as response:
                remote = json.load(response)
            if (
                remote.get("latestSummary") == expected_rows
                and remote.get("metrics") == expected_payload["metrics"]
            ):
                print(f"Netlify 已更新并验证通过（第 {attempt} 次检查）")
                return
        except (URLError, TimeoutError, json.JSONDecodeError):
            pass
        time.sleep(4)
    raise RuntimeError("GitHub 已更新，但 Netlify 在限定时间内未同步到最新数据")


def publish() -> None:
    assert_publish_preconditions()
    payload, snapshot = rebuild_and_test()
    assert_only_publish_paths_changed()
    print_snapshot(snapshot)

    run("git", "add", "-A", "--", *PUBLISH_PATHS)
    staged = git_lines("diff", "--cached", "--name-only")
    if not staged:
        print("没有需要发布的新数据。")
        return

    print("将发布以下文件：")
    for path in staged:
        print(f"- {path}")
    answer = input("确认生成提交、合并到 main 并发布 Netlify？[y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        run("git", "restore", "--staged", "--", *PUBLISH_PATHS)
        print("已取消，文件内容未改变。")
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"codex/publish-data-{timestamp}"
    run("git", "switch", "-c", branch)
    run("git", "commit", "-m", f"Publish dashboard data {timestamp}")
    run("git", "push", "-u", "origin", branch)

    pr_url = run(
        "gh",
        "pr",
        "create",
        "--repo",
        "yxqhuqin222-star/rizhuizong",
        "--base",
        "main",
        "--head",
        branch,
        "--title",
        f"发布看板数据 {timestamp}",
        "--body",
        "自动生成并校验看板数据、工作簿和播报图。",
        capture=True,
    )
    print(f"已创建发布 PR：{pr_url}")
    run(
        "gh",
        "pr",
        "checks",
        pr_url,
        "--repo",
        "yxqhuqin222-star/rizhuizong",
        "--watch",
        "--interval",
        "10",
    )
    run(
        "gh",
        "pr",
        "merge",
        pr_url,
        "--repo",
        "yxqhuqin222-star/rizhuizong",
        "--merge",
        "--delete-branch",
    )
    run("git", "switch", "main")
    run("git", "pull", "--ff-only", "origin", "main")
    wait_for_production(payload)
    print(f"发布完成：{PRODUCTION_BASE_URL}/web/index.html")


def main() -> None:
    parser = argparse.ArgumentParser(description="生成、校验并发布 Netlify 只读看板")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="只验证当前生成产物，不提交或发布",
    )
    args = parser.parse_args()

    if args.validate_only:
        _, snapshot = validate_outputs()
        print_snapshot(snapshot)
        print("产物验证通过")
        return
    publish()


if __name__ == "__main__":
    main()
