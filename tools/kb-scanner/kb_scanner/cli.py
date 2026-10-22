from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .adapters.cli import StagedContextFactory, scan_request_from_namespace
from .bundle import BundleError, load_bundle_descriptor
from .core import ScanRequest
from .knowledge import GeneratedFactsKnowledgeProvider
from .pipeline.default import create_default_application
from .projection import DEFAULT_PROJECTION_POLICY


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kb-scanner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="执行扫描")
    scan.add_argument("--input", required=True)
    scan.add_argument("--language", default="c,cpp")
    scan.add_argument("--rules", required=True)
    scan.add_argument("--compile-commands")
    scan.add_argument("--exclude", default=".git,build")
    scan.add_argument(
        "--exclude-path",
        action="append",
        default=[],
        help="按项目根目录下的精确目录路径排除，可重复传入；例如 --exclude-path third_party/simd --exclude-path vendor/foo",
    )
    scan.add_argument("--output", required=True)
    scan.add_argument("--format", default="json,html")
    scan.add_argument("--context-infer", choices=["auto", "off"], default="auto")
    scan.add_argument("--target-arch", default="riscv64")
    scan.add_argument("--include-inactive-branches", action="store_true")
    scan.add_argument("--no-comment-hints", action="store_true", help="关闭注释中的架构线索扫描")
    scan.add_argument("--locale", default="zh-CN")
    scan.add_argument(
        "--schema-version", choices=["1.0", "2.0"], default="2.0",
        help="输出合同版本；默认 2.0，旧消费者可显式选择 1.0",
    )

    validate = subparsers.add_parser("validate-rules", help="校验规则包")
    validate.add_argument("--rules", required=True)

    list_rules_parser = subparsers.add_parser("list-rules", help="列出规则")
    list_rules_parser.add_argument("--rules", required=True)

    subparsers.add_parser("version", help="显示版本")

    args = parser.parse_args(argv)
    if args.command == "scan":
        return run_scan(args)
    if args.command == "validate-rules":
        return validate_rules(Path(args.rules))
    if args.command == "list-rules":
        return list_rules(Path(args.rules))
    if args.command == "version":
        print(__version__)
        return 0
    return 2


def run_scan(args: argparse.Namespace) -> int:
    result = create_default_application().run(scan_request_from_namespace(args))
    return result.exit_code


def validate_rules(rule_dir: Path) -> int:
    try:
        descriptor = load_bundle_descriptor(rule_dir)
    except BundleError as exc:
        print(f"规则包无效: {exc}")
        return 1
    request = ScanRequest(str(rule_dir), str(rule_dir), str(rule_dir))
    context = StagedContextFactory().build(request)
    if context.value is None:
        for item in context.diagnostics:
            print(item.message)
        return 1
    knowledge = GeneratedFactsKnowledgeProvider().load(context.value)
    for item in knowledge.diagnostics:
        print(item.message)
    missing = DEFAULT_PROJECTION_POLICY.validate_completeness()
    if missing:
        print(f"投影策略缺少: {', '.join(missing)}")
        return 1
    print(f"规则数量: {len(DEFAULT_PROJECTION_POLICY.rule_ids)}")
    print(f"知识包: {descriptor.rule_pack_id}@{descriptor.rule_pack_version}")
    return 0 if knowledge.value is not None else 1


def list_rules(rule_dir: Path) -> int:
    if validate_rules(rule_dir) != 0:
        return 1
    for rule_id in DEFAULT_PROJECTION_POLICY.rule_ids:
        print(f"{rule_id}\tcode-owned\tversion={DEFAULT_PROJECTION_POLICY.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
