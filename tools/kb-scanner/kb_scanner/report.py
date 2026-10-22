from __future__ import annotations

import html
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import Finding, ProjectFacts
from . import __version__


def write_reports(
    project: ProjectFacts,
    findings: list[Finding],
    output_dir: Path,
    formats: list[str],
    rule_pack_id: str,
    rule_pack_version: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = to_json_payload(project, findings, rule_pack_id, rule_pack_version)
    if "json" in formats:
        (output_dir / "scan-result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if "html" in formats:
        (output_dir / "scan-report.html").write_text(render_html(payload), encoding="utf-8")
    (output_dir / "scan.log").write_text("\n".join(project.diagnostics), encoding="utf-8")


def to_json_payload(
    project: ProjectFacts,
    findings: list[Finding],
    rule_pack_id: str,
    rule_pack_version: str,
) -> dict[str, Any]:
    severity_counts: dict[str, int] = {}
    for finding in findings:
        severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
    hint_count = sum(1 for finding in findings if finding.finding_type == "hint")
    blocking_count = sum(1 for finding in findings if finding.is_blocking)
    portability_gap_count = sum(1 for finding in findings if finding.finding_type == "portability_gap")
    inactive_count = sum(1 for finding in findings if finding.finding_type in {"inactive", "guarded"})
    issue_count = len(findings) - hint_count
    issue_findings = [finding for finding in findings if finding.finding_type != "hint"]
    reference_source_count = sum(1 for finding in issue_findings if finding.is_reference_source)
    reference_count = len(issue_findings) - reference_source_count

    compile_contexts = {
        path: {
            "includeDirs": ctx.include_dirs,
            "defines": ctx.defines,
            "languageStandard": ctx.language_standard,
            "entryIndex": ctx.entry_index,
            "compiler": Path(ctx.compiler).name if ctx.compiler else None,
            "tokenCount": len(ctx.tokens),
        }
        for path, ctx in project.compile_contexts.items()
    }

    return {
        "schemaVersion": "1.0",
        "tool": {"name": "kb-scanner", "version": __version__},
        "rulePack": {"id": rule_pack_id, "version": rule_pack_version},
        "project": {
            "root": str(project.root),
            "scanMode": project.scan_mode,
            "targetArch": project.target_arch,
            "includeInactiveBranches": project.include_inactive_branches,
            "compileCommands": str(project.compile_commands_path) if project.compile_commands_path else None,
            "compileContexts": compile_contexts,
        },
        "summary": {
            "files": len(project.files),
            "findings": len(findings),
            "issues": issue_count,
            "hints": hint_count,
            "blocking": blocking_count,
            "portabilityGaps": portability_gap_count,
            "inactiveOrGuarded": inactive_count,
            "referenceSources": reference_source_count,
            "references": reference_count,
            **severity_counts,
        },
        "findings": [
            {
                **asdict(finding),
                "file": str(finding.file),
                "location": {"file": str(finding.file), "line": finding.line, "column": finding.column},
                "context": {"snippet": finding.snippet},
            }
            for finding in findings
        ],
        "diagnostics": project.diagnostics,
    }


def render_html(payload: dict[str, Any]) -> str:
    rows = []
    for finding in payload["findings"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(finding['severity'])}</td>"
            f"<td>{html.escape(finding.get('finding_type') or 'issue')}</td>"
            f"<td>{html.escape(finding.get('source_kind') or 'code')}</td>"
            f"<td>{'是' if finding.get('is_actionable', True) else '否'}</td>"
            f"<td>{'是' if finding.get('is_blocking', True) else '否'}</td>"
            f"<td>{html.escape(finding.get('arch_reachability') or 'unknown')}</td>"
            f"<td>{html.escape(finding['rule_id'])}</td>"
            f"<td>{'是' if finding.get('is_reference_source') else '否'}</td>"
            f"<td>{html.escape(finding['location']['file'])}:{finding['location']['line']}</td>"
            f"<td>{html.escape(finding.get('symbol') or '')}</td>"
            f"<td>{html.escape(', '.join(finding.get('condition_macros') or []))}</td>"
            f"<td>{html.escape(_compatibility_text(finding))}</td>"
            f"<td><pre>{html.escape(finding['context']['snippet'])}</pre></td>"
            f"<td>{html.escape(finding['reason'])}</td>"
            f"<td>{html.escape(finding.get('reason_en') or '')}</td>"
            f"<td>{html.escape(finding['suggestion'])}</td>"
            f"<td>{html.escape(finding.get('suggestion_en') or '')}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>KB Scanner Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    pre {{ margin: 0; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>KB Scanner Report</h1>
  <p>扫描模式：{html.escape(payload['project']['scanMode'])}</p>
  <p>文件数：{payload['summary']['files']}，Finding：{payload['summary']['findings']}，Issue：{payload['summary'].get('issues', 0)}，阻塞：{payload['summary'].get('blocking', 0)}，迁移缺口：{payload['summary'].get('portabilityGaps', 0)}，已隔离/已兼容：{payload['summary'].get('inactiveOrGuarded', 0)}，Hint：{payload['summary'].get('hints', 0)}，引用源头：{payload['summary'].get('referenceSources', 0)}，引用：{payload['summary'].get('references', 0)}</p>
  <table>
    <thead><tr><th>风险</th><th>类型</th><th>来源</th><th>需处理</th><th>阻塞</th><th>RISC-V 可达性</th><th>规则</th><th>引用源头</th><th>位置</th><th>符号</th><th>条件宏</th><th>兼容路径</th><th>代码</th><th>原因</th><th>Reason EN</th><th>建议</th><th>Suggestion EN</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>"""


def _compatibility_text(finding: dict[str, Any]) -> str:
    parts: list[str] = []
    if finding.get("compatible_sibling_branch"):
        parts.append(f"宏分支: {finding.get('compatible_branch_kind')}")
    alt = finding.get("alternative_impl") or {}
    if alt.get("has_compatible_alternative"):
        parts.append(f"替代实现: {alt.get('matched_by')} {alt.get('matched_path') or ''}".strip())
    build = finding.get("build_context") or {}
    if build.get("source") == "compile_commands.json":
        parts.append(f"构建数据库: included={build.get('included_in_riscv_build')}")
    return "；".join(parts)
