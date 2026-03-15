# -*- coding: utf-8 -*-
"""
统一通知中心 NotifyHub
支持钉钉、企业微信、飞书、邮件四个渠道，通过 conf/config.ini [NOTIFY] 或环境变量配置
根据测试结果动态选择消息内容：失败时附带详细失败用例列表
"""
import os
from common.recordlog import logs


class NotifyHub:
    """
    统一通知入口
    用法：
        hub = NotifyHub(summary)
        hub.send_all()          # 向所有已配置渠道推送
        hub.send('dingtalk')    # 仅推送指定渠道
    """

    CHANNELS = ('dingtalk', 'wecom', 'feishu', 'email')

    def __init__(self, summary: dict):
        """
        :param summary: {
            total, passed, failed, error, skipped, duration,
            failed_cases: list[str]   # 可选，失败用例名列表
        }
        """
        self.summary = summary
        self._load_config()

    def _load_config(self):
        """从环境变量或 config.ini 读取各渠道开关与地址"""
        try:
            from conf.operationConfig import OperationConfig
            conf = OperationConfig()

            def _get(section, key, default=''):
                try:
                    return conf.get_section_for_data(section, key) or default
                except Exception:
                    return default

            self.dingtalk_enabled = _get('NOTIFY', 'dingtalk_enabled', 'false').lower() == 'true'
            self.wecom_enabled = _get('NOTIFY', 'wecom_enabled', 'false').lower() == 'true'
            self.feishu_enabled = _get('NOTIFY', 'feishu_enabled', 'false').lower() == 'true'
            self.email_enabled = _get('NOTIFY', 'email_enabled', 'false').lower() == 'true'
            # 仅在失败时通知（节省打扰）
            self.notify_on_failure_only = _get('NOTIFY', 'notify_on_failure_only', 'false').lower() == 'true'

            self.wecom_webhook = os.getenv('WECOM_WEBHOOK', _get('NOTIFY', 'wecom_webhook'))
            self.feishu_webhook = os.getenv('FEISHU_WEBHOOK', _get('NOTIFY', 'feishu_webhook'))
        except Exception as e:
            logs.warning(f'[NotifyHub] 配置读取异常，使用默认值：{e}')
            # 降级：全关闭
            self.dingtalk_enabled = self.wecom_enabled = self.feishu_enabled = self.email_enabled = False
            self.notify_on_failure_only = False
            self.wecom_webhook = self.feishu_webhook = ''

    def _should_notify(self) -> bool:
        """判断是否需要推送（支持仅失败时通知）"""
        if self.notify_on_failure_only:
            has_failure = (self.summary.get('failed', 0) + self.summary.get('error', 0)) > 0
            return has_failure
        return True

    def send(self, channel: str) -> bool:
        """推送到指定渠道"""
        if not self._should_notify():
            logs.info(f'[NotifyHub] 全部通过，已配置仅失败时通知，跳过推送')
            return False

        if channel == 'dingtalk':
            return self._send_dingtalk()
        elif channel == 'wecom':
            return self._send_wecom()
        elif channel == 'feishu':
            return self._send_feishu()
        elif channel == 'email':
            return self._send_email()
        else:
            logs.warning(f'[NotifyHub] 未知渠道：{channel}')
            return False

    def send_all(self):
        """向所有已启用渠道推送"""
        results = {}
        for ch in self.CHANNELS:
            enabled = getattr(self, f'{ch}_enabled', False)
            if enabled:
                results[ch] = self.send(ch)
        return results

    # ── 各渠道实现 ────────────────────────────────────────────────

    def _send_dingtalk(self) -> bool:
        try:
            from conf.setting import dd_msg
            from common.dingRobot import send_dd_msg
            if not dd_msg:
                logs.info('[NotifyHub] 钉钉通知已关闭（dd_msg=False）')
                return False
            text = self._build_plain_text()
            send_dd_msg(text)
            return True
        except Exception as e:
            logs.error(f'[NotifyHub] 钉钉推送失败：{e}')
            return False

    def _send_wecom(self) -> bool:
        try:
            from common.notify.wecom import send_wecom_msg, build_wecom_markdown
            md = build_wecom_markdown(self.summary)
            return send_wecom_msg(md, webhook_url=self.wecom_webhook, msg_type='markdown')
        except Exception as e:
            logs.error(f'[NotifyHub] 企业微信推送失败：{e}')
            return False

    def _send_feishu(self) -> bool:
        try:
            from common.notify.feishu import send_feishu_msg, build_feishu_card
            card = build_feishu_card(self.summary)
            return send_feishu_msg(card, webhook_url=self.feishu_webhook, msg_type='interactive')
        except Exception as e:
            logs.error(f'[NotifyHub] 飞书推送失败：{e}')
            return False

    def _send_email(self) -> bool:
        try:
            from common.semail import SendEmail
            text = self._build_plain_text()
            SendEmail().build_content(subject='接口自动化测试报告', email_content=text)
            return True
        except Exception as e:
            logs.error(f'[NotifyHub] 邮件推送失败：{e}')
            return False

    def _build_plain_text(self) -> str:
        """纯文本摘要，兼容不支持 Markdown 的渠道"""
        s = self.summary
        total = s.get('total', 0)
        passed = s.get('passed', 0)
        pass_rate = round(passed / total * 100, 1) if total else 0
        failed_cases = s.get('failed_cases', [])

        lines = [
            '【接口自动化测试报告】',
            f'  总用例数：{total}',
            f'  通过数：{passed}',
            f'  失败数：{s.get("failed", 0)}',
            f'  错误数：{s.get("error", 0)}',
            f'  跳过数：{s.get("skipped", 0)}',
            f'  通过率：{pass_rate}%',
            f'  执行耗时：{s.get("duration", 0):.1f}s',
        ]
        if failed_cases:
            lines.append('  失败用例：')
            for c in failed_cases[:10]:
                lines.append(f'    - {c}')
            if len(failed_cases) > 10:
                lines.append(f'    ...共 {len(failed_cases)} 条')
        return '\n'.join(lines)
