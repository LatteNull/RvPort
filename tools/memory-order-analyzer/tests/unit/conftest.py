from pathlib import Path
import pytest

from memory_order_analyzer.contracts import document
from memory_order_analyzer.protocol import expected_protocol


@pytest.fixture
def fixture_context(tmp_path):
    source = tmp_path / "input.c"
    source.write_text("int value;\n")
    return document("TUManifest", context_id="a" * 64, source=str(source), directory=str(tmp_path),
                    original={}, effective_argv=["clang", "-g", "-O0", "-emit-llvm", "-c", str(source)],
                    production={}, analysis={"path": "clang", "version": "21.1.8"}, adaptations=[],
                    response_files={}, environment={}, language="c", abi={})


@pytest.fixture
def fixture_module():
    return document("ModuleFacts", artifact_key="a" * 64, module_hash="b" * 64, target="x86_64-pc-linux-gnu",
                    layout="e-p:64:64", producer=[], functions=[], globals=[], events=[], calls=[],
                    capabilities={}, source_mapping="unavailable", values=[], protocol=expected_protocol(),
                    extraction={"status": "complete", "roots": 0, "nodes": 0, "references": 0, "unknown": 0, "diagnostics": []})


@pytest.fixture
def fixture_artifact(tmp_path):
    return document("BCArtifact", artifact_key="a" * 64, context_id="c" * 64, path=str(tmp_path / "input.bc"),
                    sha256="b" * 64, profile="source-preserving", provenance="verified", inputs={},
                    toolchain={}, lineage=[])


def success(stdout="", stderr="", code=0):
    return {"status": "completed" if not code else "failed", "code": None if not code else "nonzero_exit",
            "exit_code": code, "stdout": stdout, "stderr": stderr}
