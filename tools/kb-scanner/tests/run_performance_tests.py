"""Explicit full-project gate; never included implicitly in ordinary unit runs."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import sys

from kb_scanner.adapters.cli import StagedContextFactory
from kb_scanner.core import ScanRequest
from kb_scanner.frontends.build import ProjectWorkspaceCollector
from tests.performance.support import accept_run, run_process, runtime_metadata, verify_inputs, verify_report, verify_limits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--fixture-dir", type=Path, default=Path("tests/fixtures/large-project-performance"))
    parser.add_argument("--profile", action="store_true", help="diagnostic only; cannot pass acceptance")
    args = parser.parse_args()
    source, output = Path(args.source), Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    fixture = args.fixture_dir
    provenance = json.loads((fixture / "PROVENANCE.json").read_text())
    manifest = json.loads((fixture / provenance["inputManifest"]).read_text())
    if "baseInputManifest" in provenance:
        base_manifest = json.loads((fixture / provenance["baseInputManifest"]).read_text())
        if set(base_manifest).intersection(manifest):
            raise ValueError("additional input manifest must not replace historical inputs")
        manifest = {**base_manifest, **manifest}
    runtime = runtime_metadata(version, lambda p: p.read_bytes(), args.image_id, args.revision,
                               tuple(sorted(Path("kb_scanner").rglob("*.py"))))
    runtime["limits"] = verify_limits(lambda p: p.read_text())
    context = StagedContextFactory().build(ScanRequest(str(source), "rulesets/riscv-porting", str(output / "preflight")))
    if context.value is None or context.value.compile_commands_path is not None:
        raise ValueError("fixture/context missing or unexpected compilation database")
    workspace = ProjectWorkspaceCollector().collect(context.value)
    if workspace.value is None:
        raise ValueError("workspace unavailable")
    fingerprint = verify_inputs(source, workspace.value.files, manifest, provenance)
    record = {"runtime": runtime, "fixtureDigest": fingerprint, "budget": provenance["budget"],
              "mode": "profile" if args.profile else "acceptance", "runs": [], "passed": False}
    metadata_path = output / "performance.json"
    metadata_path.write_text(json.dumps(record, indent=2))
    for index in range(1 if args.profile else 2):
        run = output / str(index + 1)
        run.mkdir()
        report = run / "report"
        command = [sys.executable, "-m", "tests.performance.child", str(source), str(report)]
        if args.profile:
            command.append("--profile")
        with (run / "events.jsonl").open("w") as events_file, (run / "stderr.log").open("w") as stderr:
            outcome = run_process(command, events_file, stderr)
        events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
        record["runs"].append({"outcome": outcome, "events": events})
        metadata_path.write_text(json.dumps(record, indent=2))
        if args.profile:
            return 1
        resources = accept_run(outcome, events, provenance["files"])
        record["runs"][-1].update(resources=resources, report=verify_report(report, provenance["files"]))
        metadata_path.write_text(json.dumps(record, indent=2))
    record["passed"] = True
    metadata_path.write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
