from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_toolchain_and_dependency_locks_are_consistent() -> None:
    lock = json.loads((ROOT / "toolchain.lock.json").read_text(encoding="utf-8"))
    assert lock["platform"] == "linux/amd64"
    assert lock["clang_version"] == "21.1.8"
    assert lock["python_minimum"] == "3.11"
    assert len(lock["llvm_key_sha256"]) == 64
    requirements = (ROOT / "requirements-dev.lock").read_text(encoding="utf-8")
    assert all(
        f"{name}=={version}" in requirements
        for name, version in lock["python_dependencies"].items()
        if name != "jsonschema"
    )
    assert "jsonschema==4.23.0" in requirements


def test_container_and_license_inventory_reference_locked_versions() -> None:
    dockerfile = (ROOT / "Dockerfile.dev").read_text(encoding="utf-8")
    licenses = (ROOT / "docs" / "dependency-licenses.md").read_text(encoding="utf-8")
    assert "ubuntu:24.04@sha256:" in dockerfile
    assert "21.1.8" in dockerfile
    assert "sha256sum -c" in dockerfile
    assert re.search(r"Clang/LLVM\s*\|\s*21\.1\.8", licenses)
    assert "coverage.py | 7.6.12" in licenses
