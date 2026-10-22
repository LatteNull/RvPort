"""隔离的 LLVM 21 worker 进程适配器。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import (
    LLVM_EXTRACTOR_VERSION,
    LLVM_READER_VERSION,
    LLVM_VERSION,
    LLVM_WORKER_PROTOCOL_VERSION,
    TOOL_VERSION,
)
from .artifacts import ArtifactPlan, BitcodeMember
from .diagnostics import diagnostic, sanitize_text
from .frontend import ProcessRunner, SubprocessRunner


class IrWorkerFailure(RuntimeError):
    def __init__(self, item: Any) -> None:
        self.diagnostic = item
        super().__init__(item.diagnostic_code)


class IrWorker:
    def __init__(
        self,
        executable: Path,
        runner: ProcessRunner | None = None,
        *,
        timeout: float = 60.0,
        output_limit: int = 16_777_216,
    ) -> None:
        self.executable = executable
        self.runner = runner or SubprocessRunner()
        self.timeout = timeout
        self.output_limit = output_limit

    def _run(
        self,
        arguments: Sequence[str],
        cwd: Path,
        *,
        cpu_seconds: float | None = None,
        memory_bytes: int | None = None,
        timeout: float | None = None,
        output_limit: int | None = None,
    ) -> Any:
        try:
            return self.runner.run(
                arguments,
                cwd=cwd,
                timeout=timeout if timeout is not None else self.timeout,
                output_limit=output_limit if output_limit is not None else self.output_limit,
                cpu_seconds=cpu_seconds,
                memory_bytes=memory_bytes,
            )
        except subprocess.TimeoutExpired as exc:
            raise IrWorkerFailure(
                diagnostic(
                    "ir_worker_timeout",
                    "ir_worker",
                    "LLVM IR worker 分析超时。",
                    "LLVM IR worker analysis timed out.",
                    retryable=True,
                )
            ) from exc
        except OSError as exc:
            raise IrWorkerFailure(
                diagnostic(
                    "ir_worker_unavailable",
                    "ir_worker",
                    "无法启动 LLVM IR worker。",
                    "Unable to start the LLVM IR worker.",
                )
            ) from exc

    def verify(self) -> None:
        if not self.executable.is_file():
            raise IrWorkerFailure(
                diagnostic(
                    "ir_worker_unavailable",
                    "ir_worker",
                    "LLVM IR worker 不存在。",
                    "The LLVM IR worker does not exist.",
                )
            )
        result = self._run([str(self.executable), "--version-json"], self.executable.parent)
        parse_error: json.JSONDecodeError | None
        try:
            version = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            version = {}
            parse_error = exc
        else:
            parse_error = None
        expected = {
            "tool_version": TOOL_VERSION,
            "llvm_version": LLVM_VERSION,
            "reader_version": LLVM_READER_VERSION,
            "extractor_version": LLVM_EXTRACTOR_VERSION,
            "worker_protocol_version": LLVM_WORKER_PROTOCOL_VERSION,
        }
        if (
            result.returncode != 0
            or not isinstance(version, Mapping)
            or any(version.get(key) != value for key, value in expected.items())
        ):
            raise IrWorkerFailure(
                diagnostic(
                    "ir_worker_version_mismatch",
                    "ir_worker",
                    "LLVM IR worker 版本与扫描器锁定版本不一致。",
                    "LLVM IR worker versions do not match the scanner lock.",
                )
            ) from parse_error

    @staticmethod
    def _normalize_debug_paths(document: dict[str, Any], project_root: Path) -> None:
        facts = document.get("facts")
        unknowns = document.get("unknowns")
        if not isinstance(facts, list) or not isinstance(unknowns, list):
            return
        root = project_root.resolve()
        for fact in facts:
            if not isinstance(fact, Mapping):
                continue
            location = fact.get("debug_location")
            if not isinstance(location, dict):
                continue
            points = [location]
            inline_chain = location.get("inlined_at")
            if isinstance(inline_chain, list):
                points.extend(item for item in inline_chain if isinstance(item, dict))
            outside = False
            for point in points:
                raw = point.get("path")
                if not isinstance(raw, str):
                    continue
                candidate = Path(raw)
                if candidate.is_absolute():
                    try:
                        normalized = candidate.resolve().relative_to(root).as_posix()
                    except (OSError, ValueError):
                        normalized = candidate.name
                        outside = True
                else:
                    normalized = Path(raw.replace("\\", "/")).as_posix()
                point["path"] = normalized
            if outside:
                unknowns.append(
                    {
                        "kind": "debug_location_outside_project",
                        "fact_id": str(fact.get("fact_id", "")),
                        "blocking": False,
                    }
                )

    def extract(
        self,
        plan: ArtifactPlan,
        member: BitcodeMember,
        *,
        max_facts: int,
        max_use_edges: int = 1000,
        max_summary_depth: int = 3,
        max_summary_call_edges: int = 1000,
        project_root: Path,
        cpu_seconds: float | None = None,
        memory_bytes: int | None = None,
        timeout: float | None = None,
        output_limit: int | None = None,
    ) -> dict[str, Any]:
        arguments = [
            str(self.executable),
            "--input",
            str(member.path),
            "--protocol-version",
            LLVM_WORKER_PROTOCOL_VERSION,
            "--artifact-set-id",
            plan.artifact_set_id,
            "--artifact-key",
            member.artifact_key,
            "--physical-tu-id",
            str(member.document["physical_tu_id"]),
            "--context-id",
            member.context_id,
            "--profile",
            member.profile,
            "--sha256",
            str(member.document["sha256"]),
            "--max-facts",
            str(max_facts),
            "--max-use-edges",
            str(max_use_edges),
            "--max-summary-depth",
            str(max_summary_depth),
            "--max-summary-call-edges",
            str(max_summary_call_edges),
        ]
        result = self._run(
            arguments,
            member.path.parent,
            cpu_seconds=cpu_seconds,
            memory_bytes=memory_bytes,
            timeout=timeout,
            output_limit=output_limit,
        )
        if result.returncode != 0:
            safe = sanitize_text(result.stderr, member.path.parent)
            raise IrWorkerFailure(
                diagnostic(
                    "ir_worker_failed",
                    "ir_worker",
                    "LLVM IR worker 无法读取共享 BC。",
                    "LLVM IR worker could not read shared bitcode.",
                    suggestion=safe or "请检查 BC 兼容性。",
                    suggestion_en=safe or "Check bitcode compatibility.",
                    translation_unit_id=member.context_id,
                )
            )
        active_output_limit = output_limit if output_limit is not None else self.output_limit
        if result.stdout_truncated or len(result.stdout.encode("utf-8")) > active_output_limit:
            raise IrWorkerFailure(
                diagnostic(
                    "ir_worker_output_too_large",
                    "ir_worker",
                    "LLVM IR worker 输出超过预算。",
                    "LLVM IR worker output exceeds its budget.",
                    translation_unit_id=member.context_id,
                )
            )
        try:
            document = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise IrWorkerFailure(
                diagnostic(
                    "ir_worker_invalid_json",
                    "ir_worker",
                    "LLVM IR worker 输出不是有效 JSON。",
                    "LLVM IR worker output is not valid JSON.",
                    translation_unit_id=member.context_id,
                )
            ) from exc
        if not isinstance(document, dict):
            raise IrWorkerFailure(
                diagnostic(
                    "ir_worker_invalid_json",
                    "ir_worker",
                    "LLVM IR worker 输出顶层必须是对象。",
                    "LLVM IR worker output root must be an object.",
                    translation_unit_id=member.context_id,
                )
            )
        artifact = document.get("artifact")
        facts = document.get("facts")
        if isinstance(artifact, Mapping) and isinstance(facts, list):
            material = str(artifact.get("artifact_key", ""))
            for item in facts:
                if isinstance(item, Mapping):
                    material += "\n" + str(item.get("fact_id", ""))
            expected_digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if document.get("semantic_digest") != expected_digest:
                raise IrWorkerFailure(
                    diagnostic(
                        "ir_worker_semantic_digest_mismatch",
                        "ir_worker",
                        "LLVM IR worker 输出的语义摘要不匹配。",
                        "LLVM IR worker output semantic digest does not match.",
                        translation_unit_id=member.context_id,
                    )
                )
        self._normalize_debug_paths(document, project_root)
        return document
