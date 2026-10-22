"""Offline acceptance contracts. All external boundaries are injectable."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter


ARTIFACTS = {"scan-result.json", "scan-report.html", "scan.log"}
PACKAGES = ("tree-sitter", "tree-sitter-c", "tree-sitter-cpp")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_inputs(root, files, manifest, provenance, read=lambda p: p.read_bytes()):
    if provenance.get("manifestDigest") != digest(manifest) or len(manifest) != provenance.get("files"):
        raise ValueError("invalid fixture provenance")
    if set(files) != set(manifest):
        raise ValueError("fixture input set mismatch")
    base = root.resolve()
    for name, expected in manifest.items():
        path = (base / name).resolve()
        if not path.is_relative_to(base):
            raise ValueError("fixture path escape")
        if hashlib.sha256(read(path)).hexdigest() != expected:
            raise ValueError("fixture content mismatch: " + name)
    return digest(manifest)


def runtime_metadata(package_version, read, image_id, scanner_revision, source_paths=()):
    versions = {name: package_version(name) for name in PACKAGES}
    if not image_id or not scanner_revision or not all(versions.values()):
        raise ValueError("missing runtime identity")
    knowledge = {name: hashlib.sha256(read(Path("rulesets/riscv-porting") / name)).hexdigest()
                 for name in ("knowledge-manifest.json", "generated/clang-x86-entries.json", "generated/gcc-x86-entries.json")}
    return {"python": sys.version, "packages": versions, "imageId": image_id,
            "scannerRevision": scanner_revision, "knowledge": knowledge,
            "sourceDigest": digest({str(path): hashlib.sha256(read(path)).hexdigest() for path in source_paths})}


def verify_limits(read):
    try:
        cpu = read(Path("/sys/fs/cgroup/cpu.max")).split()
        memory = read(Path("/sys/fs/cgroup/memory.max")).strip()
        swap = read(Path("/sys/fs/cgroup/memory.swap.max")).strip()
    except FileNotFoundError:
        cpu = [read(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")).strip(),
               read(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")).strip()]
        memory = read(Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")).strip()
        total = read(Path("/sys/fs/cgroup/memory/memory.memsw.limit_in_bytes")).strip()
        swap = str(int(total) - int(memory))
    if len(cpu) != 2 or cpu[0] == "max" or int(cpu[0]) != 2 * int(cpu[1]) or memory != "2147483648" or swap != "0":
        raise ValueError("performance container must enforce 2 CPU / 2 GiB / no swap")
    return {"cpu": 2, "memoryBytes": int(memory), "swapBytes": int(swap)}


def run_process(command, stdout, stderr, *, timeout=300, execute=subprocess.run, clock=perf_counter):
    started = clock()
    try:
        result = execute(command, stdout=stdout, stderr=stderr, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        # subprocess.run kills AND waits for its direct scanner child.
        return {"status": "timeout", "exitCode": 124, "elapsedSeconds": clock() - started}
    code = result.returncode
    status = "normal" if code == 0 else "native-signal" if code < 0 or code == 139 else "nonzero"
    return {"status": status, "exitCode": code, "elapsedSeconds": clock() - started}


def verify_report(output, expected_files, *, load=None):
    if {p.name for p in output.iterdir()} != ARTIFACTS:
        raise ValueError("incomplete or unexpected report artifacts")
    if load is None:
        from kb_scanner.projection.v2.models import SchemaV2Report
        from kb_scanner.projection.v2.validation import V2ReferentialIntegrityValidator
        def load(payload):
            model = SchemaV2Report.model_validate(payload)
            V2ReferentialIntegrityValidator().validate(model)
    payload = json.loads((output / "scan-result.json").read_text(encoding="utf-8"))
    load(payload)
    if payload["schemaVersion"] != "2.0" or payload["summary"]["files"] != expected_files:
        raise ValueError("report input coverage/schema mismatch")
    return {"findings": len(payload["findings"]), "summary": payload["summary"],
            "semanticDigest": digest(payload)}


def accept_run(outcome, events, expected_files):
    if outcome["status"] != "normal" or outcome["elapsedSeconds"] >= 300:
        raise ValueError("scan failed or exceeded performance budget")
    stages = ("workspace_collector", "knowledge_provider", "frontend", "normalizer",
              "analyzer", "detector", "classifier", "assessor", "report_projector")
    ends = [x for x in events if x.get("event") == "end"]
    if [x["stage"] for x in ends] != list(stages):
        raise ValueError("incomplete stage trace")
    if ends[0]["output"]["files"] != expected_files:
        raise ValueError("workspace coverage mismatch")
    resources = [x for x in events if x.get("event") == "resource"]
    if len(resources) != 1 or resources[0].get("maxRssKiB") is None:
        raise ValueError("peak resource unavailable")
    return resources[0]
