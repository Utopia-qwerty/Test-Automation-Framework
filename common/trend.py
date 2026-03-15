# -*- coding: utf-8 -*-
"""
测试趋势分析模块
每次执行完成后将本次结果追加到 report/trend_data.json，
并生成 report/trend_report.html 趋势图（内嵌 ECharts，零依赖）
"""
import json
import os
from datetime import datetime
from common.recordlog import logs


_TREND_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'report', 'trend_data.json')
_MAX_HISTORY = 30   # 最多保留最近 30 次数据


def save_trend_data(summary: dict):
    """
    将本次测试结果追加保存到 trend_data.json
    :param summary: {total, passed, failed, error, skipped, duration, pass_rate, timestamp, ...}
    """
    os.makedirs(os.path.dirname(_TREND_FILE), exist_ok=True)
    history = _load_history()

    record = {
        'timestamp': summary.get('timestamp', datetime.now().strftime('%m-%d %H:%M')),
        'total': summary.get('total', 0),
        'passed': summary.get('passed', 0),
        'failed': summary.get('failed', 0),
        'error': summary.get('error', 0),
        'skipped': summary.get('skipped', 0),
        'duration': round(summary.get('duration', 0), 1),
        'pass_rate': round(
            summary.get('passed', 0) / summary.get('total', 1) * 100, 1
        ),
        # 多维度统计（如果 summary 中有按模块数据则保存）
        'by_module': summary.get('by_module', {}),
    }
    history.append(record)
    # 只保留最近 N 次
    history = history[-_MAX_HISTORY:]

    try:
        with open(_TREND_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        logs.info(f'[Trend] 趋势数据已保存：{_TREND_FILE}')
    except Exception as e:
        logs.error(f'[Trend] 趋势数据保存失败：{e}')


def generate_trend_report() -> str:
    """
    生成内嵌 ECharts 的 HTML 趋势报告
    :return: 报告文件路径
    """
    history = _load_history()
    if not history:
        logs.warning('[Trend] 暂无历史数据，跳过生成趋势报告')
        return ''

    report_path = os.path.join(os.path.dirname(_TREND_FILE), 'trend_report.html')

    labels = [r['timestamp'] for r in history]
    pass_rates = [r['pass_rate'] for r in history]
    passed_list = [r['passed'] for r in history]
    failed_list = [r['failed'] for r in history]
    error_list = [r['error'] for r in history]
    durations = [r['duration'] for r in history]

    html = _build_html(labels, pass_rates, passed_list, failed_list, error_list, durations)

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        logs.info(f'[Trend] 趋势报告已生成：{report_path}')
    except Exception as e:
        logs.error(f'[Trend] 趋势报告生成失败：{e}')
        return ''

    return report_path


def _load_history() -> list:
    if os.path.exists(_TREND_FILE):
        try:
            with open(_TREND_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _build_html(labels, pass_rates, passed_list, failed_list, error_list, durations) -> str:
    """内嵌 ECharts CDN 生成完整 HTML 页面"""
    labels_json = json.dumps(labels, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>测试趋势报告</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #f5f7fa; color: #333; padding: 20px; }}
    h1 {{ text-align: center; padding: 20px 0; color: #2c3e50; font-size: 22px; }}
    .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 1400px; margin: 0 auto; }}
    .chart-card {{ background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,.08);
                   padding: 16px; }}
    .chart {{ width: 100%; height: 320px; }}
    @media (max-width: 900px) {{ .charts-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <h1>📊 接口自动化测试趋势报告</h1>
  <div class="charts-grid">
    <div class="chart-card"><div id="passRateChart" class="chart"></div></div>
    <div class="chart-card"><div id="countChart"   class="chart"></div></div>
    <div class="chart-card"><div id="durationChart" class="chart"></div></div>
    <div class="chart-card"><div id="stackChart"   class="chart"></div></div>
  </div>
<script>
const labels   = {labels_json};
const passRate = {json.dumps(pass_rates)};
const passed   = {json.dumps(passed_list)};
const failed   = {json.dumps(failed_list)};
const errors   = {json.dumps(error_list)};
const duration = {json.dumps(durations)};

function initChart(id, option) {{
  echarts.init(document.getElementById(id)).setOption(option);
}}

// 1. 通过率趋势
initChart('passRateChart', {{
  title: {{ text: '通过率趋势（%）', left: 'center', top: 8 }},
  tooltip: {{ trigger: 'axis', formatter: p => p[0].name + '<br/>通过率：' + p[0].value + '%' }},
  xAxis: {{ type: 'category', data: labels, axisLabel: {{ rotate: 30, fontSize: 11 }} }},
  yAxis: {{ type: 'value', min: 0, max: 100, axisLabel: {{ formatter: '{{value}}%' }} }},
  series: [{{ data: passRate, type: 'line', smooth: true, areaStyle: {{}},
              markLine: {{ data: [{{ type: 'average', name: '均值' }}] }},
              itemStyle: {{ color: '#5cb85c' }} }}]
}});

// 2. 用例数量趋势
initChart('countChart', {{
  title: {{ text: '用例数量趋势', left: 'center', top: 8 }},
  tooltip: {{ trigger: 'axis' }},
  legend: {{ top: 30, data: ['通过', '失败', '错误'] }},
  xAxis: {{ type: 'category', data: labels, axisLabel: {{ rotate: 30, fontSize: 11 }} }},
  yAxis: {{ type: 'value' }},
  series: [
    {{ name: '通过', data: passed,  type: 'line', smooth: true, itemStyle: {{ color: '#5cb85c' }} }},
    {{ name: '失败', data: failed,  type: 'line', smooth: true, itemStyle: {{ color: '#d9534f' }} }},
    {{ name: '错误', data: errors,  type: 'line', smooth: true, itemStyle: {{ color: '#f0ad4e' }} }},
  ]
}});

// 3. 执行耗时趋势
initChart('durationChart', {{
  title: {{ text: '执行耗时趋势（秒）', left: 'center', top: 8 }},
  tooltip: {{ trigger: 'axis', formatter: p => p[0].name + '<br/>耗时：' + p[0].value + 's' }},
  xAxis: {{ type: 'category', data: labels, axisLabel: {{ rotate: 30, fontSize: 11 }} }},
  yAxis: {{ type: 'value', axisLabel: {{ formatter: '{{value}}s' }} }},
  series: [{{ data: duration, type: 'bar', itemStyle: {{ color: '#5bc0de' }} }}]
}});

// 4. 堆叠柱状图（通过/失败/错误比例）
initChart('stackChart', {{
  title: {{ text: '用例结果分布', left: 'center', top: 8 }},
  tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }} }},
  legend: {{ top: 30, data: ['通过', '失败', '错误'] }},
  xAxis: {{ type: 'category', data: labels, axisLabel: {{ rotate: 30, fontSize: 11 }} }},
  yAxis: {{ type: 'value' }},
  series: [
    {{ name: '通过', type: 'bar', stack: 'total', data: passed,  itemStyle: {{ color: '#5cb85c' }} }},
    {{ name: '失败', type: 'bar', stack: 'total', data: failed,  itemStyle: {{ color: '#d9534f' }} }},
    {{ name: '错误', type: 'bar', stack: 'total', data: errors,  itemStyle: {{ color: '#f0ad4e' }} }},
  ]
}});
</script>
</body>
</html>"""
