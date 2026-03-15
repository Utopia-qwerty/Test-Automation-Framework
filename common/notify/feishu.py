# -*- coding: utf-8 -*-
"""
飞书群机器人推送
Webhook 地址格式：https://open.feishu.cn/open-apis/bot/v2/hook/xxx
文档：https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
"""
import os
import requests
from common.recordlog import logs


def send_feishu_msg(content: str, webhook_url: str = None, msg_type: str = "text") -> bool:
    """
    向飞书群机器人推送消息
    :param content: 消息正文（text）或富文本 JSON 字符串（interactive）
    :param webhook_url: Webhook 地址，优先使用参数，其次读环境变量 FEISHU_WEBHOOK
    :param msg_type: "text" 或 "interactive"（卡片消息）
    :return: 是否推送成功
    """
    url = webhook_url or os.getenv('FEISHU_WEBHOOK', '')
    if not url:
        logs.warning('[Feishu] FEISHU_WEBHOOK 未配置，跳过推送')
        return False

    payload = {
        "msg_type": msg_type,
        "content": {"text": content} if msg_type == "text" else content
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()
        if result.get('StatusCode') == 0 or result.get('code') == 0:
            logs.info('[Feishu] 推送成功')
            return True
        logs.error(f'[Feishu] 推送失败：{result}')
    except Exception as e:
        logs.error(f'[Feishu] 推送异常：{e}')
    return False


def build_feishu_card(summary: dict) -> dict:
    """
    构建飞书卡片消息（interactive 类型）
    :param summary: keys: total, passed, failed, error, skipped, duration, failed_cases
    :return: 飞书卡片 JSON dict（作为 content 字段传入）
    """
    total = summary.get('total', 0)
    passed = summary.get('passed', 0)
    failed = summary.get('failed', 0)
    error = summary.get('error', 0)
    skipped = summary.get('skipped', 0)
    duration = summary.get('duration', 0)
    pass_rate = round(passed / total * 100, 1) if total else 0
    failed_cases = summary.get('failed_cases', [])

    header_color = 'green' if failed == 0 and error == 0 else 'red'
    status_text = '✅ 全部通过' if failed == 0 and error == 0 else f'❌ 存在 {failed + error} 条失败'

    elements = [
        {
            "tag": "div",
            "fields": [
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**总用例**\n{total}"}},
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**通过率**\n{pass_rate}%"}},
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**通过 ✅**\n{passed}"}},
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**失败 ❌**\n{failed}"}},
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**错误 🔥**\n{error}"}},
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**耗时**\n{duration:.1f}s"}},
            ]
        }
    ]

    if failed_cases:
        case_list = '\n'.join(f'- {c}' for c in failed_cases[:10])
        if len(failed_cases) > 10:
            case_list += f'\n- ...共 {len(failed_cases)} 条'
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**失败用例：**\n{case_list}"}
        })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"接口自动化测试报告 | {status_text}"},
            "template": header_color
        },
        "elements": elements
    }
