from __future__ import annotations

import html
import json
from collections.abc import Mapping
from typing import Any


def render_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def render_html(payload: Mapping[str, Any]) -> bytes:
    rows = []
    for finding in payload["findings"]:
        rows.append(
            "<tr>"
            f"<td>{_escape(finding['severity'])}</td>"
            f"<td>{_escape(finding['finding_type'])}</td>"
            f"<td>{_escape(finding['source_kind'])}</td>"
            f"<td>{'是' if finding['is_actionable'] else '否'}</td>"
            f"<td>{'是' if finding['is_blocking'] else '否'}</td>"
            f"<td>{_escape(finding['arch_reachability'])}</td>"
            f"<td>{_escape(finding['rule_id'])}</td>"
            f"<td>{_escape(finding['file'])}:{finding['line']}</td>"
            f"<td><pre>{_escape(finding['snippet'])}</pre></td>"
            f"<td>{_escape(finding['reason'])}</td>"
            f"<td>{_escape(finding['suggestion'])}</td>"
            "</tr>"
        )
    readiness = payload["summary"].get("readiness")
    readiness_text = ""
    if readiness:
        readiness_text = (
            f"<p>静态迁移评估：{_escape(readiness['state'])}；"
            "未执行真实编译或测试。</p>"
        )
    diagnostic_rows = "".join(f"<li>{_escape(item)}</li>" for item in payload["diagnostics"])
    diagnostics_html = f"<h2>Diagnostics</h2><ul>{diagnostic_rows}</ul>" if diagnostic_rows else ""
    document = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>KB Scanner Report</title>
<style>body {{ font-family: Arial, sans-serif; margin: 24px; }} table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }} th {{ background: #f5f5f5; }} pre {{ margin: 0; white-space: pre-wrap; }}</style></head>
<body><h1>KB Scanner Report</h1>
<p>扫描模式：{_escape(payload['project']['scanMode'])}</p>
<p>文件数：{payload['summary']['files']}，Finding：{payload['summary']['findings']}，Issue：{payload['summary']['issues']}，阻塞：{payload['summary']['blocking']}，迁移缺口：{payload['summary']['portabilityGaps']}，已隔离/已兼容：{payload['summary']['inactiveOrGuarded']}，Hint：{payload['summary']['hints']}</p>
{readiness_text}{diagnostics_html}<table><thead><tr><th>风险</th><th>类型</th><th>来源</th><th>需处理</th><th>阻塞</th><th>RISC-V 可达性</th><th>规则</th><th>位置</th><th>代码</th><th>原因</th><th>建议</th></tr></thead><tbody>{''.join(rows)}</tbody></table></body></html>"""
    return document.encode("utf-8")


def render_log(payload: Mapping[str, Any]) -> bytes:
    lines = [str(item) for item in payload["diagnostics"]]
    readiness = payload["summary"].get("readiness")
    if readiness:
        lines.append(f"static readiness: {readiness['state']} (compiled=false, testsExecuted=false)")
    return "\n".join(lines).encode("utf-8")


def _escape(value: object) -> str:
    return html.escape(str(value if value is not None else ""))
