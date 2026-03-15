# -*- coding: utf-8 -*-
"""
企业微信群机器人推送
Webhook 地址格式：https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
文档：https://developer.work.weixin.qq.com/document/path/91770
"""
import os
import requests
from common.recordlog import logs


def send_wecom_msg(content: str, webhook_url: str = None, msg_type: str = "text") -> bool:
    """
    向企业微信群机器人推送消息
    :param content: 消息正文（text 类型）或 Markdown 内容（markdown 类型）
    :param webhook_url: Webhook 地址，优先使用参数，其次读环境变量 WECOM_WEBHOOK
    :param msg_type: 消息类型，"text" 或 "markdown"
    :return: 是否推送成功
    """
    url = webhook_url or os.getenv('WECOM_WEBHOOK', '')
    if not url:
        logs.warning('[WeCom] WECOM_WEBHOOK 未配置，跳过推送')
        return False

    if msg_type == 'markdown':
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": content}
        }
    else:
        payload = {
            "msgtype": "text",
            "text": {"content": content, "mentioned_list": ["@all"]}
        }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()
        if result.get('errcode') == 0:
            logs.info('[WeCom] 推送成功')
            return True
        logs.error(f'[WeCom] 推送失败：{result}')
    except Exception as e:
        logs.error(f'[WeCom] 推送异常：{e}')
    return False


def build_wecom_markdown(summary: dict) -> str:
    """
    将测试摘要字典渲染为企业微信 Markdown 格式
    :param summary: keys: total, passed, failed, error, skipped, duration, failed_cases
    """
    total = summary.get('total', 0)
    passed = summary.get('passed', 0)
    failed = summary.get('failed', 0)
    error = summary.get('error', 0)
    skipped = summary.get('skipped', 0)
    duration = summary.get('duration', 0)
    pass_rate = round(passed / total * 100, 1) if total else 0
    failed_cases = summary.get('failed_cases', [])

    status_icon = '✅' if failed == 0 and error == 0 else '❌'
    color = 'info' if failed == 0 and error == 0 else 'warning'

    lines = [
        f'## {status_icon} 接口自动化测试报告',
        f'> **通过率：<font color="{color}">{pass_rate}%</font>**',
        '',
        f'| 指标 | 数值 |',
        f'|:---|:---|',
        f'| 总用例数 | {total} |',
        f'| 通过 ✅ | {passed} |',
        f'| 失败 ❌ | {failed} |',
        f'| 错误 🔥 | {error} |',
        f'| 跳过 ⏭ | {skipped} |',
        f'| 执行耗时 | {duration:.1f}s |',
    ]

    if failed_cases:
        lines += ['', '**失败用例：**']
        for case in failed_cases[:10]:   # 最多展示 10 条
            lines.append(f'- `{case}`')
        if len(failed_cases) > 10:
            lines.append(f'- ...共 {len(failed_cases)} 条，详见报告')

    return '\n'.join(lines)
