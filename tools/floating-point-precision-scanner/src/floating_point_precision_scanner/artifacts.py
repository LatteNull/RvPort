"""共享 LLVM bitcode artifact set 的只读消费与一致性校验。"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import LLVM_VERSION
from .compilation import CompilationPlan, CompileContext
from .diagnostics import Diagnostic, diagnostic
from .protocol import BitcodeArtifactSetRequest, SchemaRegistry


@dataclass(frozen=True, slots=True)
class BitcodeMember:
    document: Mapping[str, Any]
    path: Path
    sidecar_path: Path | None

    @property
    def artifact_key(self) -> str:
        return str(self.document["artifact_key"])

    @property
    def context_id(self) -> str:
        return str(self.document["context_id"])

    @property
    def profile(self) -> str:
        return str(self.document["profile"])


@dataclass(frozen=True, slots=True)
class ArtifactPlan:
    document: Mapping[str, Any]
    members: tuple[BitcodeMember, ...]
    diagnostics: tuple[Diagnostic, ...]
    failed_count: int
    manifest_sha256: str = ""

    @property
    def artifact_set_id(self) -> str:
        return str(self.document["artifact_set_id"])


class ArtifactInputError(ValueError):
    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        super().__init__(diagnostics[0].diagnostic_code if diagnostics else "artifact_error")


class ArtifactNotReady(ArtifactInputError):
    """Manifest 合法但共享制品尚不可消费。"""


def _error(code: str, zh: str, en: str, *, retryable: bool = False) -> ArtifactInputError:
    return ArtifactInputError([diagnostic(code, "bitcode_artifact", zh, en, retryable=retryable)])


def _inside(root: Path, relative: str) -> Path:
    untrusted = Path(relative)
    if untrusted.is_absolute() or "://" in relative or "@" in relative:
        raise _error(
            "artifact_path_not_relative",
            "共享分析产物路径必须是不含 URL 或凭据的相对路径。",
            "A shared analysis artifact path must be relative and contain no URL or credentials.",
        )
    candidate = (root / untrusted).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise _error(
            "artifact_path_escape",
            "共享 BC 路径超出 artifact root。",
            "A shared bitcode path escapes the artifact root.",
        ) from exc
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_file(
    path: Path,
    *,
    expected_size: int,
    expected_sha256: str,
    max_bytes: int,
    kind: str,
) -> None:
    try:
        stat = path.stat()
    except OSError as exc:
        raise _error(
            f"{kind}_missing",
            "共享分析产物不存在。",
            "A shared analysis artifact is missing.",
            retryable=True,
        ) from exc
    if not path.is_file():
        raise _error(
            f"{kind}_not_regular_file",
            "共享分析产物不是普通文件。",
            "A shared analysis artifact is not a regular file.",
        )
    if stat.st_size > max_bytes:
        raise _error(
            f"{kind}_too_large",
            "共享分析产物超过输入大小预算。",
            "A shared analysis artifact exceeds the input size budget.",
        )
    if stat.st_size != expected_size or _sha256(path) != expected_sha256:
        raise _error(
            f"{kind}_integrity_mismatch",
            "共享分析产物的大小或 SHA-256 不匹配。",
            "A shared analysis artifact size or SHA-256 does not match.",
        )


def load_artifact_plan(
    request: BitcodeArtifactSetRequest,
    compilation: CompilationPlan,
    schemas: SchemaRegistry,
    *,
    source_revision: str | None,
    max_bytes: int,
) -> ArtifactPlan:
    root = request.artifact_root.resolve()
    manifest_path = _inside(root, request.manifest)
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise _error(
            "artifact_manifest_missing",
            "共享 BC manifest 不存在。",
            "The shared bitcode manifest is missing.",
            retryable=True,
        ) from exc
    if hashlib.sha256(manifest_bytes).hexdigest() != request.manifest_sha256:
        raise _error(
            "artifact_manifest_integrity_mismatch",
            "共享 BC manifest 的 SHA-256 不匹配。",
            "The shared bitcode manifest SHA-256 does not match.",
        )
    try:
        document = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _error(
            "artifact_manifest_invalid_json",
            "共享 BC manifest 不是有效 JSON。",
            "The shared bitcode manifest is not valid JSON.",
        ) from exc
    if not isinstance(document, Mapping):
        raise _error(
            "artifact_manifest_invalid_json",
            "共享 BC manifest 顶层必须是对象。",
            "The shared bitcode manifest root must be an object.",
        )
    schema_errors = schemas.validate("bitcode_artifact_set", document)
    if schema_errors:
        raise ArtifactInputError(schema_errors)
    analysis_compiler = document["producer"]["analysis_compiler"]
    if (
        str(analysis_compiler["name"]).lower() not in {"clang", "clang++"}
        or analysis_compiler["version"] != LLVM_VERSION
    ):
        raise _error(
            "artifact_toolchain_mismatch",
            "共享 BC 不是由锁定的 Clang/LLVM 21.1.8 生成。",
            "Shared bitcode was not produced by the pinned Clang/LLVM 21.1.8 toolchain.",
        )
    if source_revision and document["source_revision"] != source_revision:
        raise _error(
            "artifact_source_revision_mismatch",
            "共享 BC 与请求的源码修订不一致。",
            "Shared bitcode does not match the requested source revision.",
        )
    if document["compile_commands_sha256"] != compilation.input_digest:
        raise _error(
            "artifact_compile_context_mismatch",
            "共享 BC 与当前编译输入不一致。",
            "Shared bitcode does not match the current compilation input.",
        )

    counts = document["counts"]
    if (
        counts["completed"] != len(document["members"])
        or counts["failed"] != len(document["failures"])
        or counts["planned"] != counts["completed"] + counts["failed"]
    ):
        raise _error(
            "artifact_manifest_count_mismatch",
            "共享 BC manifest 的计数不一致。",
            "Shared bitcode manifest counts are inconsistent.",
        )
    status = str(document["status"])
    expected_status = (
        "READY"
        if counts["completed"] > 0 and counts["failed"] == 0
        else "PARTIAL"
        if counts["completed"] > 0 and counts["failed"] > 0
        else "FAILED"
        if counts["failed"] > 0
        else status
    )
    if status in {"READY", "PARTIAL", "FAILED"} and status != expected_status:
        raise _error(
            "artifact_manifest_status_mismatch",
            "共享 BC manifest 的状态与计数不一致。",
            "Shared bitcode manifest status is inconsistent with its counts.",
        )
    if status not in {"READY", "PARTIAL"}:
        retryable = status in {"MISSING", "QUEUED", "GENERATING"}
        raise ArtifactNotReady(
            [
                diagnostic(
                    "artifact_not_ready" if retryable else "artifact_generation_failed",
                    "bitcode_artifact",
                    "共享 BC 尚未就绪。" if retryable else "共享 BC 生产失败。",
                    "Shared bitcode is not ready."
                    if retryable
                    else "Shared bitcode production failed.",
                    retryable=retryable,
                )
            ]
        )

    raw_members = list(document["members"])
    keys = [str(item["artifact_key"]) for item in raw_members]
    tuples = [(str(item["context_id"]), str(item["profile"])) for item in raw_members]
    if any(value > 1 for value in Counter(keys).values()) or any(
        value > 1 for value in Counter(tuples).values()
    ):
        raise _error(
            "artifact_manifest_duplicate_member",
            "共享 BC manifest 包含重复成员。",
            "The shared bitcode manifest contains duplicate members.",
        )

    contexts: dict[str, CompileContext] = {item.context_id: item for item in compilation.contexts}
    members: list[BitcodeMember] = []
    total_bitcode_bytes = 0
    for item in raw_members:
        if item["profile_version"] != "1.0" or "llvm-fp-facts" not in item["capabilities"]:
            raise _error(
                "artifact_profile_capability_mismatch",
                "共享 BC 成员的 profile 版本或能力不受支持。",
                "A shared bitcode member has an unsupported profile version or capability set.",
            )
        context = contexts.get(str(item["context_id"]))
        if context is None or item["physical_tu_id"] != context.physical_tu_id:
            raise _error(
                "artifact_translation_unit_mismatch",
                "共享 BC 成员无法匹配当前翻译单元。",
                "A shared bitcode member cannot be matched to a current translation unit.",
            )
        if item["language"] != context.language:
            raise _error(
                "artifact_language_mismatch",
                "共享 BC 成员的语言与当前翻译单元不一致。",
                "A shared bitcode member language does not match its translation unit.",
            )
        if item["target"] != context.target or item["abi"] != context.abi:
            raise _error(
                "artifact_target_mismatch",
                "共享 BC 成员的 target 或 ABI 与当前编译上下文不一致。",
                "A shared bitcode member target or ABI does not match its compile context.",
            )
        path = _inside(root, str(item["path"]))
        _verify_file(
            path,
            expected_size=int(item["size_bytes"]),
            expected_sha256=str(item["sha256"]),
            max_bytes=max_bytes,
            kind="bitcode",
        )
        total_bitcode_bytes += int(item["size_bytes"])
        if total_bitcode_bytes > max_bytes:
            raise _error(
                "bitcode_total_too_large",
                "共享 BC 总大小超过输入预算。",
                "The total shared bitcode size exceeds the input budget.",
            )
        sidecar_path = None
        sidecar = item.get("binding_sidecar")
        if isinstance(sidecar, Mapping):
            sidecar_path = _inside(root, str(sidecar["path"]))
            _verify_file(
                sidecar_path,
                expected_size=int(sidecar["size_bytes"]),
                expected_sha256=str(sidecar["sha256"]),
                max_bytes=max_bytes,
                kind="binding_sidecar",
            )
        members.append(BitcodeMember(item, path, sidecar_path))

    available = {(member.context_id, member.profile) for member in members}
    failure_keys = {
        (str(item["context_id"]), str(item["profile"])) for item in document["failures"]
    }
    required = {
        (context.context_id, profile)
        for context in compilation.contexts
        for profile in request.required_profiles
    }
    missing = required - available - failure_keys
    if missing:
        raise _error(
            "artifact_required_profile_missing",
            "共享 BC 缺少请求所需的 profile 成员。",
            "Shared bitcode is missing a required profile member.",
        )
    diagnostics = tuple(
        diagnostic(
            str(item["code"]),
            "bitcode_artifact",
            str(item["detail"]),
            str(item["detail_en"]),
            translation_unit_id=str(item["context_id"]),
        )
        for item in document["failures"]
        if (str(item["context_id"]), str(item["profile"])) in required
    )
    selected = tuple(
        sorted(
            (member for member in members if (member.context_id, member.profile) in required),
            key=lambda member: (
                member.profile,
                str(member.document["physical_tu_id"]),
                member.context_id,
                member.artifact_key,
            ),
        )
    )
    return ArtifactPlan(
        document,
        selected,
        diagnostics,
        len(diagnostics),
        request.manifest_sha256,
    )
