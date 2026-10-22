"""最小 CLI；所有业务判断委托给应用服务。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, NoReturn

from . import (
    BINDING_SIDECAR_SCHEMA_VERSION,
    BITCODE_ARTIFACT_SET_SCHEMA_VERSION,
    BUILD_CONTEXT_SCHEMA_VERSION,
    CACHE_SCHEMA_VERSION,
    CLANG_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    FACTS_SCHEMA_VERSION,
    LLVM_EXTRACTOR_VERSION,
    LLVM_FACTS_SCHEMA_VERSION,
    LLVM_READER_VERSION,
    LLVM_VERSION,
    LLVM_WORKER_PROTOCOL_VERSION,
    PROFILE_SCHEMA_VERSION,
    REQUEST_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
    RULE_REGISTRY_VERSION,
    TOOL_VERSION,
    VALIDATION_SCHEMA_VERSION,
)
from .aggregation import exit_code
from .application import Scanner
from .diagnostics import diagnostic
from .frontend import ClangFrontend
from .ir_worker import IrWorker
from .output import serialize_json, write_atomic
from .profiles import ProfileLookupError, ProfileRegistry
from .protocol import SchemaRegistry
from .result_v2 import failure_result_v2, truncate_result_v2
from .rules import DEFAULT_RULES, RULE_BY_CODE, RULE_REGISTRY_DIGEST
from .validation import main as validation_main


class CLIUsageError(ValueError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CLIUsageError(message)


def build_parser() -> Parser:
    parser = Parser(prog="fp-precision-scanner")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    scan = subparsers.add_parser("scan")
    scan.add_argument("--request", type=Path, required=True)
    scan.add_argument("--output", type=Path, required=True)
    scan.add_argument("--clang", type=Path, default=Path("/usr/lib/llvm-21/bin/clang-21"))
    scan.add_argument("--ir-worker", type=Path, default=Path("/workspace/build/fp-ir-worker"))
    validate = subparsers.add_parser("validate-request")
    validate.add_argument("--request", type=Path, required=True)
    corpus = subparsers.add_parser("validate-corpus")
    corpus.add_argument("--corpus", type=Path, required=True)
    corpus.add_argument("--observed", type=Path, required=True)
    corpus.add_argument("--output", type=Path, required=True)
    profiles = subparsers.add_parser("profiles")
    profile_subparsers = profiles.add_subparsers(
        dest="profile_command", required=True, parser_class=Parser
    )
    profile_subparsers.add_parser("list")
    show = profile_subparsers.add_parser("show")
    show.add_argument("profile_id")
    subparsers.add_parser("version")
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError("request_file_unreadable") from exc
    if not isinstance(document, dict):
        raise ValueError("request_root_must_be_object")
    return document


def _print_json(value: Any, *, stream: Any = None) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True), file=stream or sys.stdout)


def _internal_result(request_id: str) -> dict[str, Any]:
    item = diagnostic(
        "internal_error",
        "scanner",
        "扫描器发生未分类内部错误。",
        "The scanner encountered an unclassified internal error.",
    )
    return failure_result_v2(request_id, "internal_error", [item])


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "version":
            _print_json(
                {
                    "tool_version": TOOL_VERSION,
                    "request_schema_version": REQUEST_SCHEMA_VERSION,
                    "result_schema_version": RESULT_SCHEMA_VERSION,
                    "facts_schema_version": FACTS_SCHEMA_VERSION,
                    "profile_schema_version": PROFILE_SCHEMA_VERSION,
                    "build_context_schema_version": BUILD_CONTEXT_SCHEMA_VERSION,
                    "clang_version": CLANG_VERSION,
                    "llvm_version": LLVM_VERSION,
                    "llvm_reader_version": LLVM_READER_VERSION,
                    "llvm_extractor_version": LLVM_EXTRACTOR_VERSION,
                    "llvm_worker_protocol_version": LLVM_WORKER_PROTOCOL_VERSION,
                    "bitcode_artifact_set_schema_version": BITCODE_ARTIFACT_SET_SCHEMA_VERSION,
                    "llvm_facts_schema_version": LLVM_FACTS_SCHEMA_VERSION,
                    "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
                    "binding_sidecar_schema_version": BINDING_SIDECAR_SCHEMA_VERSION,
                    "rule_registry_version": RULE_REGISTRY_VERSION,
                    "rule_registry_digest": RULE_REGISTRY_DIGEST,
                    "cache_schema_version": CACHE_SCHEMA_VERSION,
                    "validation_schema_version": VALIDATION_SCHEMA_VERSION,
                    "default_rules": list(DEFAULT_RULES),
                    "rules": {code: RULE_BY_CODE[code].version for code in DEFAULT_RULES},
                }
            )
            return 0
        if args.command == "validate-corpus":
            return validation_main(
                [
                    "--corpus",
                    str(args.corpus),
                    "--observed",
                    str(args.observed),
                    "--output",
                    str(args.output),
                ]
            )
        profiles = ProfileRegistry()
        if args.command == "profiles":
            if args.profile_command == "list":
                _print_json([item.summary() for item in profiles.list()])
            else:
                _print_json(profiles.get(args.profile_id).document)
            return 0
        request = _load_json(args.request)
        scanner = Scanner(
            ClangFrontend(getattr(args, "clang", Path("/usr/lib/llvm-21/bin/clang-21"))),
            profiles,
            ir_worker=(IrWorker(args.ir_worker) if args.command == "scan" else None),
        )
        if args.command == "validate-request":
            errors = scanner.validate_request(request)
            _print_json({"valid": not errors, "diagnostics": [item.to_dict() for item in errors]})
            return 0 if not errors else 2
        try:
            result = scanner.scan(request)
        except Exception:
            result = _internal_result(str(request.get("request_id", "invalid-request")))
        result_errors = SchemaRegistry().validate("result", result)
        if result_errors:
            result = failure_result_v2(
                str(request.get("request_id", "invalid-request")),
                "internal_error",
                result_errors,
                request_schema_version=str(request.get("schema_version", "unknown")),
            )
        try:
            maximum = int(request.get("budgets", {}).get("max_result_bytes", 0))
            if maximum and len(serialize_json(result)) > maximum:
                truncated = truncate_result_v2(result, maximum)
                if truncated is None:
                    item = diagnostic(
                        "result_budget_exceeded",
                        "output",
                        "扫描结果超过输出预算，未覆盖既有正式结果。",
                        "The scan result exceeds its output budget; the existing result "
                        "was preserved.",
                    )
                    _print_json(
                        failure_result_v2(
                            str(request.get("request_id", "invalid-request")), "failed", [item]
                        ),
                        stream=sys.stderr,
                    )
                    return 3
                result = truncated
            write_atomic(result, args.output)
        except OSError:
            item = diagnostic(
                "output_write_failed",
                "output",
                "无法原子写出扫描结果。",
                "Unable to atomically publish the scan result.",
            )
            _print_json(
                failure_result_v2(
                    str(request.get("request_id", "invalid-request")), "internal_error", [item]
                ),
                stream=sys.stderr,
            )
            return 5
        return exit_code(str(result["scan"]["status"]))
    except (CLIUsageError, json.JSONDecodeError, ValueError, ProfileLookupError) as exc:
        item = diagnostic(
            "invalid_cli_request",
            "cli",
            "CLI 请求无效。",
            "The CLI request is invalid.",
            suggestion=str(exc),
            suggestion_en=str(exc),
        )
        _print_json(
            failure_result_v2("invalid-request", "invalid_request", [item]),
            stream=sys.stderr,
        )
        return 2
    except Exception:
        item = diagnostic(
            "internal_error",
            "cli",
            "扫描器发生未分类内部错误。",
            "The scanner encountered an unclassified internal error.",
        )
        _print_json(
            failure_result_v2("invalid-request", "internal_error", [item]),
            stream=sys.stderr,
        )
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
