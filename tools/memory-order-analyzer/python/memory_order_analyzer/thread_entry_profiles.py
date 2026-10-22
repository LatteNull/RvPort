"""Thread-entry model profiles and exact profile adoption rules."""

from copy import deepcopy
import json
from pathlib import Path

from .contracts import AnalysisError, identity
from .thread_entry_contracts import model_profile_digest, validate_model_profile


REGISTRY = Path(__file__).resolve().parents[2] / "models/thread-entry-models.json"


def model_profile(*, api_family, vendor, version, language, standards, target,
                  data_layout, abi, canonical_entities=(), header_digests=(), brokers=(),
                  status="verified"):
    fields = {
        "api_family": api_family, "vendor": vendor, "version": str(version),
        "language": language, "standards": sorted(set(standards)), "target": target,
        "data_layout": data_layout, "abi": abi,
        "canonical_entities": sorted((deepcopy(item) for item in canonical_entities), key=lambda item: item["id"]),
        "header_digests": sorted((deepcopy(item) for item in header_digests), key=lambda item: (item["kind"], item["id"])),
        "brokers": sorted((deepcopy(item) for item in brokers), key=lambda item: (item.get("role", ""), item.get("symbol", ""))),
        "status": status,
    }
    profile_id = identity(fields)
    result = {"id": profile_id, **fields, "digest": "pending"}
    result["digest"] = model_profile_digest(result)
    return validate_model_profile(result)


def c_api_profile(api_family, target, data_layout):
    if api_family == "pthread":
        return model_profile(
            api_family="pthread", vendor="posix", version="direct-v1", language="c",
            standards=("c11", "c17"), target=target, data_layout=data_layout, abi="c",
            canonical_entities=({"id": "pthread_create", "qualified_name": "pthread_create", "origin": "pthread.h"},),
            brokers=({"role": "create", "symbol": "pthread_create", "callback_index": 2,
                      "argument_index": 3, "handle_index": 0, "success": "result==0"},))
    if api_family == "c11-thread":
        return model_profile(
            api_family="c11-thread", vendor="iso-c", version="c11-v1", language="c",
            standards=("c11", "c17"), target=target, data_layout=data_layout, abi="c",
            canonical_entities=({"id": "thrd_create", "qualified_name": "thrd_create", "origin": "threads.h"},),
            brokers=({"role": "create", "symbol": "thrd_create", "callback_index": 1,
                      "argument_index": 2, "handle_index": 0, "success": "result==thrd_success"},))
    raise AnalysisError("model_profile_invalid", f"Unsupported built-in C API family: {api_family}")


def import_cpp_thread_profile(profile):
    """Reference A3 evidence without mutating its profile document."""
    entities = ({"id": "std-thread", "qualified_name": "std::thread",
                 "origin": profile["header_digests"][0]["id"]},)
    brokers = tuple({
        "role": item["role"], "symbol": item["symbol"],
        "signature_digest": item["digest"], "parameter_roles": item["parameter_roles"],
    } for item in profile["wrapper_signatures"])
    return model_profile(
        api_family="std-thread", vendor=profile["vendor"], version=profile["version"],
        language="c++", standards=(profile["cxx_standard"],), target=profile["target"],
        data_layout=profile["data_layout"], abi=profile["cxx_abi"],
        canonical_entities=entities, header_digests=profile["header_digests"], brokers=brokers)


def adopt_model(member, model, *, target=None, data_layout=None):
    validate_model_profile(model)
    mismatches = []
    if member["language"] != model["language"]:
        mismatches.append("language")
    if member["standard"] not in model["standards"]:
        mismatches.append("standard")
    if target is not None and target != model["target"]:
        mismatches.append("target")
    if data_layout is not None and data_layout != model["data_layout"]:
        mismatches.append("data_layout")
    if model["status"] != "verified":
        mismatches.append("verification_status")
    return (None, sorted(mismatches)) if mismatches else (deepcopy(model), [])


def broker_for_symbol(profile, symbol):
    validate_model_profile(profile)
    matches = [item for item in profile["brokers"] if item.get("symbol") == symbol]
    if len(matches) != 1:
        return None
    return deepcopy(matches[0])


def load_model_registry(path=REGISTRY):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise AnalysisError("model_registry_invalid", f"Invalid thread-entry model registry: {path}") from exc
    if (set(value) != {"schema_version", "kind", "profiles"}
            or value["schema_version"] != 1 or value["kind"] != "ThreadEntryModelRegistry"):
        raise AnalysisError("model_registry_invalid", "Thread-entry model registry envelope is invalid")
    profiles = [validate_model_profile(item) for item in value["profiles"]]
    if profiles != sorted(profiles, key=lambda item: item["id"]):
        raise AnalysisError("model_registry_invalid", "Thread-entry model profiles must be sorted")
    if len({item["id"] for item in profiles}) != len(profiles):
        raise AnalysisError("model_registry_invalid", "Thread-entry model profile ids must be unique")
    return deepcopy(profiles)
