"""Explicit toolchain probing; a successful Clang compile is not GCC equivalence."""

import json
from pathlib import Path
import re
import shutil

from .contracts import AnalysisError
from .execution import require_success, run
from .protocol import check_worker

LOCK_PATH = Path(__file__).resolve().parents[2] / "config/toolchain.lock.json"
LLVM_TOOLS = ("clang", "clang++", "llvm-config", "opt", "llvm-link", "llvm-dis", "llvm-cov", "llvm-profdata")


def probe_tool(name, *, runner=run, finder=shutil.which, cwd="/tmp"):
    path = finder(name)
    if not path:
        raise AnalysisError("tool_missing", f"Install {name} using Dockerfile.dev")
    version = require_success(runner([path, "--version"], cwd, timeout=10), name).strip()
    match = re.search(r"\b(\d+\.\d+(?:\.\d+)?)\b", version)
    if not match:
        raise AnalysisError("version_unknown", f"Cannot parse version from {name}: {version}")
    # Preserve argv[0]: clang++ may be a symlink whose name selects C++ driver mode.
    return {"path": str(Path(path).absolute()), "resolved_path": str(Path(path).resolve()), "version": match.group(1), "description": version}


def reader_doctor(worker=None, *, runner=run, lock=None):
    """Check only the read-only worker needed by external BC ingestion."""
    lock = lock or json.loads(LOCK_PATH.read_text())
    tools, failures = {}, []
    if not worker:
        failures.append({"code": "tool_missing", "detail": "Pass --worker to check the LLVM reader"})
    else:
        try:
            protocol = check_worker(worker, "/tmp", runner)
            if protocol["llvm_version"] != lock["llvm_version"]:
                raise AnalysisError("toolchain_mismatch", "Worker was built against a different LLVM SDK")
            tools["worker"] = {"path": str(worker), "version": protocol["llvm_version"], "protocol": protocol}
        except AnalysisError as exc:
            failures.append(exc.as_dict())
    return {"mode": "reader", "expected_llvm": lock["llvm_version"], "tools": tools,
            "failures": failures, "ready": not failures}


def development_doctor(worker=None, *, runner=run, finder=shutil.which, lock=None):
    lock = lock or json.loads(LOCK_PATH.read_text())
    tools, failures = {}, []
    for name in (*LLVM_TOOLS, "gcc", "g++"):
        try:
            tools[name] = probe_tool(name, runner=runner, finder=finder)
            if name in LLVM_TOOLS and tools[name]["version"] != lock["llvm_version"]:
                raise AnalysisError("toolchain_mismatch", f"{name}: expected {lock['llvm_version']}, actual {tools[name]['version']}")
        except AnalysisError as exc:
            failures.append(exc.as_dict())
    if worker:
        try:
            tools["worker"] = probe_tool(worker, runner=runner, finder=finder)
            if tools["worker"]["version"] != lock["llvm_version"]:
                raise AnalysisError("toolchain_mismatch", "Worker was built against a different LLVM SDK")
            tools["worker"]["protocol"] = check_worker(tools["worker"]["path"], "/tmp", runner)
        except AnalysisError as exc:
            failures.append(exc.as_dict())
    else:
        failures.append({"code": "tool_missing", "detail": "Pass --worker to check the built LLVM reader"})
    return {"expected_llvm": lock["llvm_version"], "tools": tools, "failures": failures, "ready": not failures}


# Backward-compatible Python API for development/quality callers. The public CLI
# uses reader_doctor and therefore never requires compiler or linker drivers.
doctor = development_doctor
