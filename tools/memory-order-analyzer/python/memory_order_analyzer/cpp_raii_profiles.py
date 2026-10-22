"""Exact libstdc++/libc++ synchronization profiles for the bounded A4 model."""

from copy import deepcopy

from .contracts import AnalysisError, identity
from .cpp_raii_contracts import (
    WRAPPER_ROLES, cpp_raii_document, diagnostic, synchronization_profile_id,
    validate_cpp_raii_document,
)


PROFILE_FIELDS = (
    "vendor", "version", "cxx_standard", "cxx_abi", "target", "data_layout",
    "pointer_width", "exceptions", "rtti", "thread_backend", "toolchain_lineage",
    "model_version", "lifecycle_profile_id",
)


def _vendor(probe):
    macros = probe.get("macros", {})
    candidates = []
    if macros.get("__GLIBCXX__"):
        candidates.append(("libstdc++", str(macros["__GLIBCXX__"])))
    if macros.get("_LIBCPP_VERSION"):
        candidates.append(("libc++", str(macros["_LIBCPP_VERSION"])))
    if len(candidates) != 1:
        raise AnalysisError("library_profile_unsupported", "Exactly one C++ standard-library macro is required")
    return candidates[0]


def build_synchronization_profile(compilation_profile, probe, *, status="verified"):
    if compilation_profile.get("language") != "c++" or compilation_profile.get("standard") not in {"c++17", "c++20"}:
        raise AnalysisError("profile_conflict", "A4 profiles require C++17 or C++20")
    vendor, version = _vendor(probe)
    wrappers = []
    for item in probe.get("wrappers", []):
        if item.get("role") not in WRAPPER_ROLES:
            raise AnalysisError("abi_wrapper_mismatch", f"Unsupported A4 wrapper role: {item.get('role')}")
        signature = {
            "role": item["role"], "symbol": item["symbol"],
            "calling_convention": item.get("calling_convention", "ccc"),
            "parameter_roles": sorted(set(item.get("parameter_roles", []))),
            "exception_behavior": item.get("exception_behavior", "unknown"),
        }
        signature["digest"] = identity({**signature, "layout": item.get("layout")})
        wrappers.append(signature)
    wrappers.sort(key=lambda item: (item["role"], item["symbol"]))
    if not {"mutex-lock", "mutex-unlock"} <= {item["role"] for item in wrappers}:
        raise AnalysisError("abi_wrapper_mismatch", "A4 profiles require actual lock and unlock wrappers")
    headers = sorted(({"kind": "Header", "id": item["path"], "digest": item["sha256"]}
                      for item in probe.get("headers", [])), key=lambda item: (item["kind"], item["id"]))
    fields = {
        "profile_id": "pending", "vendor": vendor, "version": version,
        "cxx_standard": compilation_profile["standard"], "cxx_abi": probe.get("cxx_abi", "itanium"),
        "target": compilation_profile["target"], "data_layout": probe["data_layout"],
        "pointer_width": probe["pointer_width"], "exceptions": bool(probe.get("exceptions", True)),
        "rtti": bool(probe.get("rtti", True)), "thread_backend": "pthread",
        "toolchain_lineage": probe["toolchain_lineage"], "header_digests": headers,
        "wrapper_signatures": wrappers, "model_version": "cpp-raii-sync-library-v1",
        "status": status, "provenance": sorted(set(probe.get("provenance", ["compile-only", "llvm-ir"]))),
        "lifecycle_profile_id": probe.get("lifecycle_profile_id"), "semantic_digest": None,
    }
    envelope = {"schema_version": 1, "kind": "CppRaiiSynchronizationProfile",
                "analysis_version": "0.1.0", "policy_id": "cpp-raii-synchronization-v1", **fields}
    fields["profile_id"] = synchronization_profile_id(envelope)
    return cpp_raii_document("CppRaiiSynchronizationProfile", **fields)


def adopt_synchronization_profile(actual, registered):
    validate_cpp_raii_document(actual, "CppRaiiSynchronizationProfile")
    validate_cpp_raii_document(registered, "CppRaiiSynchronizationProfile")
    mismatches = [name for name in PROFILE_FIELDS if actual[name] != registered[name]]
    if actual["header_digests"] != registered["header_digests"]:
        mismatches.append("header_digests")
    if actual["wrapper_signatures"] != registered["wrapper_signatures"]:
        mismatches.append("wrapper_signatures")
    if actual["status"] != "verified" or registered["status"] != "verified":
        mismatches.append("verification_status")
    if mismatches:
        code = ("abi-wrapper-mismatch" if any(name in mismatches for name in
                ("wrapper_signatures", "cxx_abi", "data_layout", "pointer_width"))
                else "library-profile-mismatch")
        return None, diagnostic(
            code, f"C++ RAII 同步 profile 不匹配：{', '.join(sorted(set(mismatches)))}",
            f"The C++ RAII synchronization profile differs in: {', '.join(sorted(set(mismatches)))}",
            suggestion="使用精确匹配且实测的同步 profile，或保留为 unknown",
            suggestion_en="Use an exactly matching verified synchronization profile or keep the result unknown",
            source={"actual": actual["profile_id"], "registered": registered["profile_id"]},
        )
    return deepcopy(registered), None


def normalize_synchronization_calls(calls, profile):
    validate_cpp_raii_document(profile, "CppRaiiSynchronizationProfile")
    signatures = {(item["symbol"], item["calling_convention"]): item for item in profile["wrapper_signatures"]}
    normalized, diagnostics = [], []
    for call in calls:
        signature = signatures.get((call.get("symbol"), call.get("calling_convention", "ccc")))
        if signature is None or call.get("signature_digest") != signature["digest"]:
            diagnostics.append(diagnostic(
                "abi-wrapper-mismatch", "调用与已验证的 RAII 同步 wrapper 不匹配",
                "The call does not match a verified RAII synchronization wrapper",
                suggestion="保留原始调用并降级为 unknown",
                suggestion_en="Keep the raw call and degrade it to unknown",
                source={"call_id": call.get("id"), "symbol": call.get("symbol")},
            ))
            continue
        normalized.append({
            "call_id": call["id"], "role": signature["role"], "profile_id": profile["profile_id"],
            "exception_behavior": signature["exception_behavior"],
            "evidence": sorted(set(call.get("evidence", []))),
        })
    return sorted(normalized, key=lambda item: item["call_id"]), diagnostics
