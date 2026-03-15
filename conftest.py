# -*- coding: utf-8 -*-
import time
import warnings
import re
from datetime import datetime

import pytest

from common.readyaml import ReadYamlData
from base.removefile import remove_file
from conf.setting import (
    dd_msg,
    TREND_ENABLED,
    AI_ANALYZE_ENABLED,
    NOTIFY_WECOM,
    NOTIFY_FEISHU,
    NOTIFY_EMAIL,
)

yfd = ReadYamlData()

# 全局容器：收集所有失败用例的详细信息，供 AI 分析使用
_failed_reports: list[dict] = []
_custom_markers: list[str] = []
_nodeid_marker_map: dict[str, set[str]] = {}


@pytest.fixture(scope="session", autouse=True)
def clear_extract():
    """会话开始前清理旧数据，禁用干扰告警"""
    warnings.simplefilter("ignore", ResourceWarning)
    yfd.clear_yaml_data()
    remove_file("./report/temp", ["json", "txt", "attach", "properties"])


# ── 收集失败用例详情（供 AI 分析） ─────────────────────────────────


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """拦截每条用例的执行结果，收集失败信息"""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        # 从 item 中尽量提取请求/响应上下文（通过 allure 附件或 item 属性）
        _failed_reports.append(
            {
                "case_name": item.name,
                "nodeid": item.nodeid,
                "assert_detail": str(report.longrepr)[:2000],
                "request_info": getattr(item, "_last_request_info", {}),
                "response_info": getattr(item, "_last_response_info", {}),
            }
        )


# ── 测试结果汇总 ─────────────────────────────────────────────────

_session_start_time: float = 0.0


@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    global _session_start_time
    _session_start_time = time.time()


def _get_custom_markers(config) -> list[str]:
    """读取 pytest.ini 中注册的自定义 markers 名称（按声明顺序）"""
    marker_defs = config.inicfg.get("markers", []) if hasattr(config, "inicfg") else []
    if isinstance(marker_defs, str):
        marker_defs = marker_defs.splitlines()
    if not marker_defs:
        marker_defs = config.getini("markers") or []
    names: list[str] = []
    for item in marker_defs:
        line = str(item).strip()
        if not line or line.startswith("#"):
            continue
        name = line.split(":", 1)[0].split("(", 1)[0].strip()
        if name and name not in names:
            names.append(name)
    return names


def pytest_collection_modifyitems(session, config, items):
    """在收集阶段缓存每条用例的自定义标签，供 summary 按标签聚合"""
    global _custom_markers, _nodeid_marker_map
    _custom_markers = _get_custom_markers(config)
    marker_set = set(_custom_markers)
    _nodeid_marker_map = {}
    for item in items:
        marker_names = {m.name for m in item.iter_markers() if m.name in marker_set}
        _nodeid_marker_map[item.nodeid] = marker_names


def _collect_summary(terminalreporter) -> dict:
    """从 terminalreporter 收集本次执行的完整摘要"""
    collected_total = terminalreporter._numcollected
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    error = len(terminalreporter.stats.get("error", []))
    skipped = len(terminalreporter.stats.get("skipped", []))
    deselected = len(terminalreporter.stats.get("deselected", []))
    duration = time.time() - (_session_start_time or time.time())
    executed_total = passed + failed + error + skipped
    executed_for_rate = passed + failed + error

    # 多维度统计：按自定义标签聚合通过/失败/错误/跳过
    by_tag: dict[str, dict] = {}
    for stat_key, stat_items in terminalreporter.stats.items():
        if stat_key not in ("passed", "failed", "error", "skipped"):
            continue
        for report in stat_items:
            tags = _nodeid_marker_map.get(report.nodeid, set())
            # 无标签用例单独归类，避免统计丢失
            if not tags:
                tags = {"untagged"}
            for tag in tags:
                if tag not in by_tag:
                    by_tag[tag] = {
                        "passed": 0,
                        "failed": 0,
                        "error": 0,
                        "skipped": 0,
                    }
                by_tag[tag][stat_key] = by_tag[tag].get(stat_key, 0) + 1

    return {
        "timestamp": datetime.now().strftime("%m-%d %H:%M"),
        # 向后兼容：total 改为本次执行数，更符合通知和通过率口径
        "total": executed_total,
        "collected_total": collected_total,
        "deselected": deselected,
        "executed_total": executed_total,
        "passed": passed,
        "failed": failed,
        "error": error,
        "skipped": skipped,
        "duration": duration,
        "pass_rate": (
            round(passed / executed_for_rate * 100, 1) if executed_for_rate else 0
        ),
        "failed_cases": [r["case_name"] for r in _failed_reports],
        "by_tag": by_tag,
    }


def _extract_markers_from_expr(markexpr: str | None) -> list[str]:
    """从 -m 表达式里提取项目自定义标签名，仅用于展示过滤。"""
    if not markexpr:
        return []
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", markexpr)
    keywords = {"and", "or", "not", "True", "False"}
    custom_set = set(_custom_markers)
    selected: list[str] = []
    for token in tokens:
        if token in keywords:
            continue
        if token in custom_set and token not in selected:
            selected.append(token)
    return selected


def _print_summary(summary: dict, config):
    """控制台打印摘要"""
    print(
        f"""
╔══════════════════════════════════════════════════╗
║            接口自动化测试执行结果摘要              ║
╠══════════════════════════════════════════════════╣
║  收集总数：{summary['collected_total']:<6} 执行数：{summary['executed_total']:<6} 筛除：{summary['deselected']}
║  通过率(执行口径)：{summary['pass_rate']}%
║  通过 [OK]  ：{summary['passed']:<6} 失败 [FAIL]：{summary['failed']:<5} 错误 [ERR] ：{summary['error']}
║  跳过 [SKIP]：{summary['skipped']:<4} 耗时：{summary['duration']:.1f}s
╚══════════════════════════════════════════════════╝"""
    )

    if summary["by_tag"]:
        markexpr = getattr(config.option, "markexpr", "") if config else ""
        selected_tags = _extract_markers_from_expr(markexpr)
        display_by_tag = summary["by_tag"]
        if selected_tags:
            display_by_tag = {
                t: summary["by_tag"].get(t)
                for t in selected_tags
                if t in summary["by_tag"]
            }

        print("\n  [统计] 多维度统计（按标签）：")
        tag_order = {name: idx for idx, name in enumerate(_custom_markers)}
        sorted_tags = sorted(
            display_by_tag.keys(),
            key=lambda t: (tag_order.get(t, 10**6), t),
        )
        for tag in sorted_tags:
            stats = display_by_tag[tag]
            total_t = (
                stats.get("passed", 0) + stats.get("failed", 0) + stats.get("error", 0)
            )
            rate = round(stats.get("passed", 0) / total_t * 100, 1) if total_t else 0
            print(f"    {tag:<30} 通过率：{rate}%  ({stats})")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """所有用例执行完毕后的总结钩子：趋势保存 → 多渠道通知 → AI 分析"""
    summary = _collect_summary(terminalreporter)
    _print_summary(summary, config)

    # 1. 保存趋势数据 & 生成趋势图
    if TREND_ENABLED:
        try:
            from common.trend import save_trend_data, generate_trend_report

            save_trend_data(summary)
            report_path = generate_trend_report()
            if report_path:
                print(f"  📈 趋势报告：{report_path}")
        except Exception as e:
            print(f"  [Trend] 趋势模块异常：{e}")

    # 2. 多渠道通知
    try:
        from common.notify.notify_hub import NotifyHub

        hub = NotifyHub(summary)
        # 钉钉（沿用老开关，保持向后兼容）
        if dd_msg:
            hub.send("dingtalk")
        # 企业微信
        if NOTIFY_WECOM:
            hub.send("wecom")
        # 飞书
        if NOTIFY_FEISHU:
            hub.send("feishu")
        # 邮件
        if NOTIFY_EMAIL:
            hub.send("email")
    except Exception as e:
        print(f"  [Notify] 通知模块异常：{e}")

    # 3. AI 根因分析（仅当有失败且已开启）
    if AI_ANALYZE_ENABLED and _failed_reports:
        try:
            from common.ai_analyzer import AIAnalyzer

            analyzer = AIAnalyzer()
            if analyzer.is_available():
                print(f"\n  🤖 AI 正在分析 {len(_failed_reports)} 条失败用例的根因...")
                analysis = analyzer.batch_analyze(_failed_reports)
                if analysis:
                    # 写入文件，供人工查阅
                    import os

                    ai_report_path = os.path.join("report", "ai_analysis.md")
                    with open(ai_report_path, "w", encoding="utf-8") as f:
                        f.write(
                            f'# AI 失败根因分析报告\n\n生成时间：{summary["timestamp"]}\n\n'
                        )
                        f.write(analysis)
                    print(f"  🤖 AI 分析报告：{ai_report_path}")
                    # 同时附加到 Allure（如果有 allure 环境）
                    try:
                        import allure

                        allure.attach(
                            analysis,
                            name="AI根因分析",
                            attachment_type=allure.attachment_type.MARKDOWN,
                        )
                    except Exception:
                        pass
        except Exception as e:
            print(f"  [AI] 分析模块异常：{e}")
