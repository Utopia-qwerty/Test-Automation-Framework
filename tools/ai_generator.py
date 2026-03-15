# -*- coding: utf-8 -*-
"""
AI 测试用例自动生成工具
基于接口文档（OpenAPI/Swagger JSON 或手工描述的接口信息），
调用 AI 大模型自动生成符合本框架 YAML 规范的测试用例。

使用方式（命令行）：
    # 基于 OpenAPI JSON 文件生成：
    python tools/ai_generator.py --spec path/to/openapi.json --output testcase/Single interface/

    # 基于接口描述文字生成：
    python tools/ai_generator.py --desc "POST /api/user/add, 参数: username, password, role" --output testcase/

    # 指定模块和接口名：
    python tools/ai_generator.py --spec openapi.json --tag "用户管理" --output testcase/user/

环境变量：
    AI_API_KEY  - 必需，API 密钥
    AI_API_BASE - 可选，API Base URL（默认 OpenAI）
    AI_MODEL    - 可选，模型名称（默认 gpt-4o-mini）
"""
import os
import sys
import json
import argparse
import requests
import yaml
from datetime import datetime

# 加入项目根目录到 path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


# ── YAML 用例模板 ──────────────────────────────────────────────
_YAML_TEMPLATE_EXAMPLE = """
- baseInfo:
    api_name: 新增用户
    url: /api/user/add
    method: POST
    header:
      Content-Type: application/json
      token: ${get_extract_data(token)}
  testCase:
    - case_name: 正常新增用户
      json:
        username: testuser_001
        password: Test@1234
        role: viewer
      validation:
        - contains: {'status_code': 200}
        - contains: {'msg': '新增成功'}
    - case_name: 用户名为空-必填校验
      json:
        username: ''
        password: Test@1234
        role: viewer
      validation:
        - contains: {'status_code': 400}
        - contains: {'msg': '用户名不能为空'}
    - case_name: SQL注入防护验证
      json:
        username: "' OR 1=1 --"
        password: any
        role: viewer
      validation:
        - contains: {'status_code': 400}
"""


def _call_ai(prompt: str, api_key: str, api_base: str, model: str) -> str:
    """调用讯飞星火 OpenAI 兼容接口"""
    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,  # 星火范围 [0,2]，低值保证输出稳定
        "max_tokens": 4096,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _build_prompt_from_spec(spec: dict, tag_filter: str = "") -> str:
    """从 OpenAPI JSON 构建生成提示词"""
    # 仅提取指定 tag 的接口，避免 prompt 太长
    paths_info = []
    for path, methods in spec.get("paths", {}).items():
        for method, detail in methods.items():
            tags = detail.get("tags", [])
            if tag_filter and tag_filter not in tags:
                continue
            summary = detail.get("summary", "")
            params = detail.get("parameters", [])
            req_body = detail.get("requestBody", {})
            paths_info.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "summary": summary,
                    "parameters": params[:10],
                    "requestBody": str(req_body)[:500],
                }
            )

    api_json = json.dumps(paths_info[:20], ensure_ascii=False, indent=2)  # 限制大小

    return f"""你是一位资深测试工程师，精通接口自动化测试。
请根据以下接口文档，为每个接口生成完整的 YAML 格式测试用例。

【YAML 格式规范要求】
{_YAML_TEMPLATE_EXAMPLE}

规范说明：
1. baseInfo.header 中 token 统一使用 ${{get_extract_data(token)}} 模板占位
2. 每个接口至少包含：正常场景、必填参数缺失、边界值、安全测试（SQL注入/XSS）四类用例
3. validation 使用 contains 断言，支持 status_code 和 msg 字段验证
4. 用例名称（case_name）要清晰描述场景，如"正常创建订单"、"金额为负数-边界值"
5. 输出纯 YAML 内容，不要加代码块标记，不要解释

【接口文档】
{api_json}

请生成测试用例 YAML："""


def _build_prompt_from_desc(desc: str) -> str:
    """从自然语言描述构建生成提示词"""
    return f"""你是一位资深测试工程师，精通接口自动化测试。
请根据以下接口描述，生成完整的 YAML 格式测试用例。

【YAML 格式规范示例】
{_YAML_TEMPLATE_EXAMPLE}

规范说明：
1. baseInfo.header 中 token 统一使用 ${{get_extract_data(token)}} 模板占位
2. 每个接口至少包含：正常场景、必填参数缺失、边界值、安全测试（SQL注入）四类用例
3. validation 使用 contains 断言
4. 输出纯 YAML，不要加代码块标记，不要解释

【接口描述】
{desc}

请生成测试用例 YAML："""


def _extract_yaml_content(raw: str) -> str:
    """从 AI 响应中提取纯 YAML 内容（去除可能的代码块标记）"""
    raw = raw.strip()
    for marker in ("```yaml", "```yml", "```"):
        if raw.startswith(marker):
            raw = raw[len(marker) :]
            break
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def _validate_yaml(content: str) -> bool:
    """校验生成的 YAML 是否合法"""
    try:
        yaml.safe_load(content)
        return True
    except yaml.YAMLError as e:
        print(f"[Warning] 生成的 YAML 格式有误：{e}")
        return False


def generate_from_spec(
    spec_path: str,
    output_dir: str,
    tag_filter: str,
    api_key: str,
    api_base: str,
    model: str,
):
    """从 OpenAPI JSON 文件生成测试用例"""
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    print(f'[AI Generator] 正在分析接口文档，共 {len(spec.get("paths", {}))} 个路径...')
    prompt = _build_prompt_from_spec(spec, tag_filter)
    print("[AI Generator] 调用 AI 生成用例（可能需要 30~60 秒）...")
    raw = _call_ai(prompt, api_key, api_base, model)
    content = _extract_yaml_content(raw)

    if not _validate_yaml(content):
        print("[AI Generator] 警告：YAML 格式校验失败，已保存原始内容供手动修复")

    _save_output(content, output_dir, tag_filter or "generated")


def generate_from_desc(
    desc: str, output_dir: str, api_key: str, api_base: str, model: str
):
    """从接口描述文字生成测试用例"""
    print("[AI Generator] 调用 AI 生成用例...")
    raw = _call_ai(_build_prompt_from_desc(desc), api_key, api_base, model)
    content = _extract_yaml_content(raw)

    if not _validate_yaml(content):
        print("[AI Generator] 警告：YAML 格式校验失败，请手动检查输出文件")

    _save_output(content, output_dir, "generated_from_desc")


def _save_output(content: str, output_dir: str, name: str):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ai_generated_{name}_{timestamp}.yaml"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[AI Generator] ✅ 用例已保存至：{filepath}")
    print("[AI Generator] 请人工 Review 后再加入测试套件，AI 生成内容需验证！")


def main():
    parser = argparse.ArgumentParser(description="AI 测试用例自动生成工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--spec", help="OpenAPI/Swagger JSON 文件路径")
    group.add_argument("--desc", help="接口描述文字（自然语言）")
    parser.add_argument(
        "--output", default="testcase/", help="输出目录（默认 testcase/）"
    )
    parser.add_argument(
        "--tag", default="", help="按 OpenAPI tag 过滤接口（仅 --spec 生效）"
    )
    args = parser.parse_args()

    api_key = os.getenv("AI_API_KEY", "")
    api_base = os.getenv(
        "AI_API_BASE", "https://spark-api-open.xf-yun.com/v1/chat/completions"
    )
    model = os.getenv("AI_MODEL", "lite")

    if not api_key:
        try:
            from conf.operationConfig import OperationConfig

            conf = OperationConfig()
            api_key = conf.get_section_for_data("AI", "api_key") or ""
            api_base = conf.get_section_for_data("AI", "api_base") or api_base
            model = conf.get_section_for_data("AI", "model") or model
        except Exception:
            pass

    if not api_key:
        print(
            "[Error] 未找到 AI_API_KEY，请设置环境变量或在 conf/config.ini [AI] 中配置"
        )
        sys.exit(1)

    if args.spec:
        generate_from_spec(args.spec, args.output, args.tag, api_key, api_base, model)
    else:
        generate_from_desc(args.desc, args.output, api_key, api_base, model)


if __name__ == "__main__":
    main()
