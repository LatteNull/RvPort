"""Versioned extractor identity shared with the generated C++ protocol header."""

import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "protocols/extractor-protocol.json"


def expected_protocol(path=PATH):
    from .contracts import AnalysisError
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if (not isinstance(value, dict)
                or set(value) != {"protocol_version", "extractor_version", "llvm_version", "facts_version", "report_version", "policy"}
                or value["protocol_version"] != 1 or value["facts_version"] != 2 or value["report_version"] != 2
                or value["extractor_version"] != "0.2.0" or value["llvm_version"] != "21.1.8"
                or not isinstance(value["policy"], dict)
                or set(value["policy"]) != {"version", "max_nodes", "max_references", "max_constant_depth", "max_output_bytes"}
                or not all(type(n) is int and n > 0 for n in value["policy"].values())):
            raise ValueError("Invalid protocol fields")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise AnalysisError("protocol_metadata", "Invalid or missing protocols/extractor-protocol.json") from exc
    return value


def check_worker(worker, cwd, runner):
    from .contracts import AnalysisError
    result = runner([str(worker), "--protocol"], str(cwd), timeout=10)
    try:
        if result["status"] != "completed" or json.loads(result["stdout"]) != expected_protocol():
            raise ValueError("mismatch")
    except (ValueError, KeyError, TypeError) as exc:
        raise AnalysisError("worker_protocol", "Worker LLVM/facts/extractor/policy does not match; rebuild the worker") from exc
    return expected_protocol()
