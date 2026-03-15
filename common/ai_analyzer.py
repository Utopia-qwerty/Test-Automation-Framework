# -*- coding: utf-8 -*-
"""
AI 失败日志根因分析模块
结合失败的接口请求/响应日志与被测代码库上下文，
调用 AI 大模型（OpenAI 兼容接口）自动定位问题根因，
并给出修复建议，追加到 Allure 报告附件中。

配置方式（任选一）：
  1. 环境变量：AI_API_KEY / AI_API_BASE / AI_MODEL
  2. conf/config.ini [AI] 节点
"""
import os
import json
import requests
from common.recordlog import logs


class AIAnalyzer:
    """AI 根因分析器"""

    # 支持讯飞星火及其他兼容 OpenAI 协议的接口
    # 星火模型：lite / generalv3(Pro) / generalv3.5(Max) / max-32k / 4.0Ultra
    DEFAULT_BASE = "https://spark-api-open.xf-yun.com/v1/chat/completions"
    DEFAULT_MODEL = "lite"

    def __init__(self):
        self.api_key, self.api_base, self.model = self._load_config()

    def _load_config(self):
        """按优先级：环境变量 > config.ini"""
        api_key = os.getenv("AI_API_KEY", "")
        api_base = os.getenv("AI_API_BASE", "")
        model = os.getenv("AI_MODEL", "")

        if not api_key:
            try:
                from conf.operationConfig import OperationConfig

                conf = OperationConfig()
                api_key = conf.get_section_for_data("AI", "api_key") or ""
                api_base = conf.get_section_for_data("AI", "api_base") or api_base
                model = conf.get_section_for_data("AI", "model") or model
            except Exception:
                pass

        return api_key, api_base or self.DEFAULT_BASE, model or self.DEFAULT_MODEL

    def is_available(self) -> bool:
        return bool(self.api_key)

    def analyze_failure(
        self,
        case_name: str,
        request_info: dict,
        response_info: dict,
        assert_detail: str = "",
        code_context: str = "",
    ) -> str:
        """
        分析单条用例失败的根因
        :param case_name:       失败用例名称
        :param request_info:    请求信息字典 {url, method, headers, body}
        :param response_info:   响应信息字典 {status_code, body}
        :param assert_detail:   断言失败详情字符串
        :param code_context:    可选的相关源码片段（接口实现/路由代码）
        :return: AI 分析结论字符串
        """
        if not self.is_available():
            logs.warning("[AI] AI_API_KEY 未配置，跳过根因分析")
            return ""

        prompt = self._build_prompt(
            case_name, request_info, response_info, assert_detail, code_context
        )
        return self._call_llm(prompt)

    def batch_analyze(self, failed_reports: list[dict]) -> str:
        """
        批量分析多条失败用例，生成汇总报告
        :param failed_reports: list of {case_name, request_info, response_info, assert_detail}
        :return: 汇总分析字符串（Markdown 格式）
        """
        if not self.is_available() or not failed_reports:
            return ""

        sections = []
        for item in failed_reports:
            result = self.analyze_failure(
                case_name=item.get("case_name", "未知用例"),
                request_info=item.get("request_info", {}),
                response_info=item.get("response_info", {}),
                assert_detail=item.get("assert_detail", ""),
                code_context=item.get("code_context", ""),
            )
            if result:
                sections.append(f"### {item.get('case_name', '未知用例')}\n\n{result}")

        if not sections:
            return ""
        return "\n\n---\n\n".join(sections)

    def _build_prompt(
        self, case_name, request_info, response_info, assert_detail, code_context
    ) -> str:
        parts = [
            "你是一位资深的测试工程师和后端开发专家。",
            "请根据以下自动化测试失败信息，分析根本原因并给出修复建议。",
            "要求：",
            "1. 根因分析要具体，明确指出是接口返回值错误、数据问题还是代码 Bug。",
            "2. 修复建议要可操作，包含具体步骤。",
            "3. 结论简洁，使用 Markdown 格式输出。",
            "",
            f"## 失败用例：{case_name}",
            "",
            "## 请求信息",
            f"```json\n{json.dumps(request_info, ensure_ascii=False, indent=2)}\n```",
            "",
            "## 响应信息",
            f"```json\n{json.dumps(response_info, ensure_ascii=False, indent=2)}\n```",
        ]
        if assert_detail:
            parts += ["", "## 断言失败详情", f"```\n{assert_detail}\n```"]
        if code_context:
            parts += ["", "## 被测相关代码（供参考）", f"```\n{code_context}\n```"]
        parts += [
            "",
            "## 请输出：",
            "**根因分析（Root Cause）：**\n",
            "**修复建议（Fix Suggestion）：**\n",
        ]
        return "\n".join(parts)

    def _call_llm(self, prompt: str) -> str:
        """调用 OpenAI 兼容接口"""
        url = f"{self.api_base.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,  # 星火范围 [0,2]，低值保证分析严谨
            "max_tokens": 1024,
        }
        logs.debug(f"[AI] 请求地址：{url}")
        logs.debug(
            f"[AI] 请求头：Authorization=Bearer {self.api_key[:6]}***  Content-Type=application/json"
        )
        logs.debug(
            f'[AI] 请求体：model={self.model}, max_tokens={payload["max_tokens"]}, temperature={payload["temperature"]}'
        )
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            logs.debug(f"[AI] 响应状态码：{resp.status_code}")
            logs.debug(f"[AI] 响应内容（前500字）：{resp.text[:500]}")
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            logs.info(f'[AI] 根因分析完成，tokens 消耗：{data.get("usage", {})}')
            return content
        except requests.Timeout:
            logs.error("[AI] 请求超时（60s），请检查网络或 API 地址")
        except requests.HTTPError as e:
            logs.error(
                f"[AI] HTTP 错误：{e.response.status_code} {e.response.text[:200]}"
            )
            logs.debug(f"[AI] 完整响应内容：{e.response.text}")
        except (KeyError, IndexError) as e:
            logs.error(f"[AI] 响应解析失败：{e}")
            logs.debug(
                f'[AI] 原始响应数据：{resp.text if "resp" in dir() else "无响应对象"}'
            )
        except Exception as e:
            logs.error(f"[AI] 未知错误：{e}")
        return ""
