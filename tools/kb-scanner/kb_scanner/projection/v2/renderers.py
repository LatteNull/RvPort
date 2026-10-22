from __future__ import annotations

import html
import json

from .models import SchemaV2Report
from .families import render_family_summary
from .multiversion import render_multiversion_summary
from .candidate_usage import render_usage_summary
from .test_content import render_test_content


def render_json(report: SchemaV2Report) -> bytes:
    return b"".join(render_json_chunks(report))


def render_json_chunks(report: SchemaV2Report):
    # finding 自包含上下文可能很大；逐项序列化，避免一次复制整份模型为字典。
    payload = report.model_dump(mode="json", exclude_none=True, exclude={"findings"})
    payload["findings"] = report.findings
    encode = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    yield b"{"
    for ordinal, key in enumerate(sorted(payload)):
        if ordinal:
            yield b","
        yield encode(key) + b":"
        if key == "findings":
            yield b"["
            for number, finding in enumerate(report.findings):
                if number:
                    yield b","
                yield encode(finding.model_dump(mode="json", exclude_none=True))
            yield b"]"
        else:
            yield encode(payload[key])
    yield b"}\n"


def render_html(report: SchemaV2Report) -> bytes:
    return b"".join(render_html_chunks(report))


def render_html_chunks(report: SchemaV2Report):
    yield (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>KB Scanner V2</title></head><body>"
        f"<h1>KB Scanner V2</h1><p>Findings: {report.summary.findings}; readiness: {_e(report.summary.readiness)}</p><section>"
    ).encode("utf-8")
    for finding in report.findings:
        source = finding.fact.primaryLocation
        path = " → ".join(finding.evidenceChain.primaryPath)
        occurrences = "".join(f"<li>{_e(item.location.file)}:{item.location.span.start.line}</li>" for item in finding.occurrences)
        breaks = "".join(f"<li>{_e(item.stage)}: {_e(item.reasonCode)}</li>" for item in finding.evidenceChain.breaks)
        yield (
            f"<article><h2>{_e(finding.conclusion.title)}</h2>"
            f"<p>{_e(source.file)}:{source.span.start.line} · {_e(finding.conclusion.severity)} · {_e(finding.conclusion.status)}</p>"
            f"<p>{_e(finding.conclusion.reason)}</p><p>{_e(finding.conclusion.suggestion)}</p>"
            f"<p>Primary path: {_e(path)}</p><ul>{occurrences}</ul><ul>{breaks}</ul>{render_usage_summary(finding.fact.extensions)}{render_test_content(finding.fact.extensions)}</article>"
        ).encode("utf-8")
    diagnostics = "".join(f"<li>{_e(item.severity)} {_e(item.code)} ({item.count})</li>" for item in report.diagnostics)
    yield (
        f"</section>{render_family_summary(report.extensions)}{render_multiversion_summary(report.extensions)}{render_usage_summary(report.extensions)}<h2>Diagnostics</h2><ul>{diagnostics}</ul></body></html>"
    ).encode("utf-8")


def render_log(report: SchemaV2Report) -> bytes:
    lines = [
        f"schema=2.0 files={report.summary.files} findings={report.summary.findings} readiness={report.summary.readiness}",
        "scope staticAnalysisOnly=true compiled=false linked=false testsExecuted=false",
    ]
    lines.extend(f"finding {item.id} {item.conclusion.status} {item.fact.primaryLocation.file}:{item.fact.primaryLocation.span.start.line}" for item in report.findings)
    lines.extend(f"diagnostic {item.severity} {item.code} stage={item.stage} count={item.count} reasons={','.join(item.reasonCodes)}" for item in report.diagnostics)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)
