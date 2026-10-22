from __future__ import annotations

import json
from pathlib import Path

from kb_scanner.core import ScanContext
from kb_scanner.projection.v2.models import SchemaV2Report
from tests.unit.compatible_cutover.support import graph


ROOT = Path(__file__).resolve().parents[3]


def report() -> SchemaV2Report:
    payload = json.loads((ROOT / "tests/fixtures/schema-v2/complete.json").read_text(encoding="utf-8"))
    return SchemaV2Report.model_validate(payload)


def context(root: Path, *, version: str = "2.0") -> ScanContext:
    value = graph(root)[0]
    return ScanContext(
        value.input_root, value.output_dir, value.rule_dir, value.languages, value.excludes,
        value.exclude_paths, value.formats, value.context_infer, value.target_arch,
        value.include_inactive_branches, value.include_comment_hints, value.locale,
        value.compile_commands_path, value.compile_contexts, value.scan_mode, value.rule_pack_id,
        value.rule_pack_version, value.knowledge_id, value.scanner_name, value.scanner_version,
        value.knowledge_manifest_name, version,
    )


def graph_with_source(root: Path):
    source = root / "src/main.c"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("\n" * 6 + "  _mm_add_ps();\n", encoding="utf-8")
    values = list(graph(root))
    values[0] = context(root)
    return tuple(values)
