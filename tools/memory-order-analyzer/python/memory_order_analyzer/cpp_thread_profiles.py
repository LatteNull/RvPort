"""Exact libstdc++/libc++ fingerprints and conservative A3 model adoption."""

from copy import deepcopy

from .contracts import AnalysisError, identity
from .cpp_thread_contracts import (
    cpp_thread_document, diagnostic, library_profile_id,
    validate_cpp_thread_document,
)


ROLES = {
    "construct-attempt", "entry-broker", "join-attempt", "detach-attempt",
    "handle-transfer",
}
PROFILE_FIELDS = (
    "vendor", "version", "cxx_standard", "cxx_abi", "target", "data_layout",
    "pointer_width", "exceptions", "rtti", "thread_backend", "toolchain_lineage",
    "model_version",
)


def _vendor(probe):
    macros = probe.get("macros", {})
    candidates = []
    if macros.get("__GLIBCXX__"):
        candidates.append(("libstdc++", str(macros["__GLIBCXX__"])))
    if macros.get("_LIBCPP_VERSION"):
        candidates.append(("libc++", str(macros["_LIBCPP_VERSION"])))
    if len(candidates) != 1:
        raise AnalysisError("library_profile_unsupported", "Exactly one verified C++ standard-library macro is required")
    return candidates[0]


def build_library_profile(compilation_profile, probe, *, status="verified"):
    if compilation_profile.get("language") != "c++" or compilation_profile.get("standard") not in {"c++17", "c++20"}:
        raise AnalysisError("profile_conflict", "A3 library profiles require C++17 or C++20")
    vendor, version = _vendor(probe)
    wrappers = []
    for item in probe.get("wrappers", []):
        role = item.get("role")
        if role not in ROLES:
            raise AnalysisError("abi_wrapper_mismatch", f"Unsupported wrapper role: {role}")
        roles = sorted(set(item.get("parameter_roles", [])))
        signature = {
            "role": role, "symbol": item["symbol"],
            "calling_convention": item.get("calling_convention", "ccc"),
            "parameter_roles": roles,
        }
        signature["digest"] = identity({**signature, "layout": item.get("layout")})
        wrappers.append(signature)
    wrappers.sort(key=lambda item: (item["role"], item["symbol"]))
    if not wrappers:
        raise AnalysisError("abi_wrapper_mismatch", "A verified profile requires wrapper signatures")
    headers = sorted(({
        "kind": "Header", "id": item["path"], "digest": item["sha256"],
    } for item in probe.get("headers", [])), key=lambda item: (item["kind"], item["id"]))
    fields = {
        "profile_id": "pending", "vendor": vendor, "version": version,
        "cxx_standard": compilation_profile["standard"],
        "cxx_abi": probe.get("cxx_abi", "itanium"),
        "target": compilation_profile["target"],
        "data_layout": probe["data_layout"], "pointer_width": probe["pointer_width"],
        "exceptions": bool(probe.get("exceptions", True)), "rtti": bool(probe.get("rtti", True)),
        "thread_backend": "pthread", "toolchain_lineage": probe["toolchain_lineage"],
        "header_digests": headers, "wrapper_signatures": wrappers,
        "model_version": "cpp-thread-library-v1", "status": status,
        "provenance": sorted(set(probe.get("provenance", ["compile-only", "llvm-ir"]))),
        "semantic_digest": None,
    }
    envelope = {"schema_version": 1, "kind": "CppThreadLibraryProfile",
                "analysis_version": "0.1.0", "policy_id": "cpp-thread-lifecycle-v1", **fields}
    fields["profile_id"] = library_profile_id(envelope)
    return cpp_thread_document("CppThreadLibraryProfile", **fields)


def adopt_profile(actual, registered):
    validate_cpp_thread_document(actual, "CppThreadLibraryProfile")
    validate_cpp_thread_document(registered, "CppThreadLibraryProfile")
    mismatches = [name for name in PROFILE_FIELDS if actual[name] != registered[name]]
    if actual["header_digests"] != registered["header_digests"]:
        mismatches.append("header_digests")
    if actual["wrapper_signatures"] != registered["wrapper_signatures"]:
        mismatches.append("wrapper_signatures")
    if actual["status"] != "verified" or registered["status"] != "verified":
        mismatches.append("verification_status")
    if mismatches:
        code = "abi-wrapper-mismatch" if any(name in mismatches for name in ("wrapper_signatures", "cxx_abi", "data_layout", "pointer_width")) else "library-profile-unsupported"
        return None, diagnostic(
            code, f"C++ 线程标准库 profile 不匹配：{', '.join(sorted(set(mismatches)))}",
            f"The C++ thread library profile differs in: {', '.join(sorted(set(mismatches)))}",
            suggestion="使用精确匹配且已实测的标准库 profile，或保留为 unknown",
            suggestion_en="Use an exactly matching verified library profile or keep the result unknown",
            source={"actual": actual["profile_id"], "registered": registered["profile_id"]},
        )
    return deepcopy(registered), None


def normalize_wrapper_calls(calls, profile):
    validate_cpp_thread_document(profile, "CppThreadLibraryProfile")
    signatures = {(item["symbol"], item["calling_convention"]): item for item in profile["wrapper_signatures"]}
    normalized, diagnostics = [], []
    for call in calls:
        item = signatures.get((call.get("symbol"), call.get("calling_convention", "ccc")))
        if item is None or call.get("signature_digest") != item["digest"]:
            diagnostics.append(diagnostic(
                "abi-wrapper-mismatch", "调用与已验证的标准库 wrapper 不匹配",
                "The call does not match a verified standard-library wrapper",
                suggestion="保留原始调用并降级为 unknown", suggestion_en="Keep the raw call and degrade it to unknown",
                source={"call_id": call.get("id"), "symbol": call.get("symbol")},
            ))
            continue
        normalized.append({
            "call_id": call["id"], "role": item["role"], "profile_id": profile["profile_id"],
            "model_owned_pthread": bool(call.get("contains_pthread")),
            "evidence": sorted(set(call.get("evidence", []))),
        })
    return sorted(normalized, key=lambda item: item["call_id"]), diagnostics
