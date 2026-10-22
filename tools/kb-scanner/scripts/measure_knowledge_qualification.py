from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from kb_scanner.pipeline import create_knowledge_detection_qualification_profile
from tests.unit.knowledge_detection.support import make_context


def measure(input_root: Path, rule_dir: Path) -> dict[str, object]:
    profile = create_knowledge_detection_qualification_profile()
    context = make_context(input_root, rule_dir=rule_dir)
    workspace = profile.workspace_collector.collect(context).value
    knowledge = profile.knowledge_provider.load(context).value
    frontend = profile.frontend.analyze(context, workspace).value
    normalized = profile.normalizer.normalize(context, frontend).value
    analysis = profile.analyzer.analyze(context, normalized).value
    detected = profile.detector.detect(context, normalized, analysis, knowledge)
    observations = detected.value.observations
    fact_by_id = {item.id: item for item in normalized.facts}
    samples = []
    for observation in observations:
        if observation.kind not in {
            "x86_assembly_instruction", "x86_register_reference", "x86_cpu_platform_api",
            "x86_target_feature", "fixed_vector_width_candidate", "x86_architecture_alias",
        }:
            continue
        fact = fact_by_id.get(observation.metadata.get("factId"))
        if fact is not None and len(samples) < 8:
            samples.append({"kind": observation.kind, "value": fact.canonical_value[:160]})
    return {
        "files": len(workspace.files),
        "evidence": len(frontend.evidence),
        "facts": len(normalized.facts),
        "observations": len(observations),
        "byStatus": dict(sorted(Counter(item.status for item in observations).items())),
        "byKind": dict(sorted(Counter(item.kind for item in observations).items())),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rule-dir", type=Path, required=True)
    parser.add_argument("inputs", type=Path, nargs="+")
    args = parser.parse_args()
    print(json.dumps({str(path): measure(path, args.rule_dir) for path in args.inputs}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
