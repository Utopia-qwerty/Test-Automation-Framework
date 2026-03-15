import logging
import os
import sys

DIR_BASE = os.path.dirname(os.path.dirname(__file__))
sys.path.append(DIR_BASE)

# log日志输出级别
LOG_LEVEL = logging.DEBUG  # 文件
STREAM_LOG_LEVEL = logging.DEBUG  # 控制台

# 接口超时时间，单位/s
API_TIMEOUT = 60

# excel文件的sheet页，默认读取第一个sheet页的数据，int类型，第一个sheet为0，以此类推0.....9
SHEET_ID = 0

# 生成的测试报告类型，可以生成两个风格的报告，allure或tm
REPORT_TYPE = "allure"

# 是否发送钉钉消息（保留原有开关，兼容旧代码）
dd_msg = False

# ── 多渠道通知开关（也可通过 conf/config.ini [NOTIFY] 配置） ─────────
NOTIFY_WECOM = False  # 企业微信
NOTIFY_FEISHU = False  # 飞书
NOTIFY_EMAIL = False  # 邮件
NOTIFY_ON_FAILURE_ONLY = True  # True = 仅失败时通知

# ── 趋势分析 ────────────────────────────────────────────────────
TREND_ENABLED = False  # 每次执行后自动保存趋势数据并生成趋势报告

# ── AI 功能开关 ─────────────────────────────────────────────────
AI_ANALYZE_ENABLED = (
    True  # True = 执行后对失败用例进行 AI 根因分析（需配置 AI_API_KEY）
)

# ── pytest-xdist 并发执行 ────────────────────────────────────────
# 0 = 不并发（串行）；正整数 = 指定 worker 数；'auto' = 自动（CPU 核心数）
PARALLEL_WORKERS = 0

# 文件路径
FILE_PATH = {
    "CONFIG": os.path.join(DIR_BASE, "conf/config.ini"),
    "LOG": os.path.join(DIR_BASE, "logs"),
    "YAML": os.path.join(DIR_BASE),
    "TEMP": os.path.join(DIR_BASE, "report/temp"),
    "TMR": os.path.join(DIR_BASE, "report/tmreport"),
    "EXTRACT": os.path.join(DIR_BASE, "extract.yaml"),
    "XML": os.path.join(DIR_BASE, "data/sql"),
    "RESULTXML": os.path.join(DIR_BASE, "report"),
    "EXCEL": os.path.join(DIR_BASE, "data", "测试数据.xls"),
    "TREND": os.path.join(DIR_BASE, "report", "trend_data.json"),
}

# 默认请求头信息
LOGIN_HEADER = {
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
}
