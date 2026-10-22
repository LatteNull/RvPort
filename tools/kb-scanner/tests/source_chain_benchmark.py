"""Fixed-input, separate-process before/after benchmark (component, not unit)."""
import argparse
import json
import resource
import time
from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace
from enum import Enum
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from kb_scanner.adapters.cli import StagedContextFactory
from kb_scanner.core import ScanRequest
from kb_scanner.pipeline.default import create_default_profile
from kb_scanner.pipeline.orchestrator import StagedPipelineRunner
from tests.performance.observation import observe


def serializable(value):
    if is_dataclass(value):
        return {field.name: serializable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Enum):
        return value.value
    return value


class Capture:
    def __init__(self, delegate, name, outputs):
        self.delegate, self.name, self.outputs = delegate, name, outputs

    def __getattr__(self, method):
        def run(*a, **kw):
            result = getattr(self.delegate, method)(*a, **kw)
            self.outputs[self.name] = result.value
            return result
        return run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("output", type=Path)
    parser.add_argument("--rules", default="rulesets/riscv-porting")
    parser.add_argument("--instrument", action="store_true", help="Separate diagnostic run; timing wrappers are not used for acceptance baselines")
    parser.add_argument("--snapshots", action="store_true", help="Freeze small-input normalized facts/classifications/assessments for field-level audit")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    events = []
    request = ScanRequest(args.source, args.rules, str(args.output))
    built = StagedContextFactory().build(request)
    if built.value is None:
        raise RuntimeError([d.message for d in built.diagnostics])
    counters = {}
    with ExitStack() as stack:
        if args.instrument:
            from kb_scanner.projection.v2.context import SourceContextProjector
            from kb_scanner.projection.v2.source_chain import SourceChainIndex
            def timed(cls, method, label):
                original = getattr(cls, method)
                def wrapped(instance, *a, **kw):
                    started = time.perf_counter()
                    result = original(instance, *a, **kw)
                    counters[label + 'Seconds'] = counters.get(label + 'Seconds', 0) + time.perf_counter() - started
                    counters[label + 'Calls'] = counters.get(label + 'Calls', 0) + 1
                    if label == 'context':
                        counters['uniqueContextSpans'] = len(instance._projections)
                        counters['fileReadsAndSplits'] = len(instance._cache)
                    if label == 'query':
                        counters['queryVisited'] = counters.get('queryVisited', 0) + result.visited
                        counters['queryPaths'] = counters.get('queryPaths', 0) + result.paths
                    return result
                stack.enter_context(patch.object(cls, method, wrapped))
            timed(SourceContextProjector, 'project', 'context')
            timed(SourceChainIndex, '__init__', 'index')
            timed(SourceChainIndex, 'query', 'query')
        profile = create_default_profile()
        snapshots = {}
        if args.snapshots:
            profile = replace(profile, **{name: Capture(getattr(profile, name), name, snapshots)
                                         for name in ('normalizer', 'classifier', 'assessor')})
        result = StagedPipelineRunner(observe(profile, events.append)).run(built.value, built.diagnostics)
        if args.snapshots:
            (args.output / 'snapshots.json').write_text(json.dumps(serializable(snapshots), sort_keys=True))
    report = args.output / "scan-result.json"
    metrics = {"exitCode": result.exit_code, "maxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               "events": events, "reportBytes": report.stat().st_size if report.exists() else None,
               "instrumented": args.instrument, "counters": counters}
    (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
