from copy import deepcopy

import pytest

import memory_order_analyzer.cpp_thread_cache as cache_module
from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.cpp_thread_cache import CppThreadCache, cache_key
from memory_order_analyzer.cpp_thread_contracts import cpp_thread_document
from memory_order_analyzer.cpp_thread_contracts import read_cpp_thread_document
from memory_order_analyzer.cpp_thread_profiles import (
    adopt_profile, build_library_profile, normalize_wrapper_calls,
)


def compilation(standard="c++17", family="gcc"):
    return {"language": "c++", "standard": standard, "target": "x86_64-pc-linux-gnu",
            "compiler": {"family": family, "version": "13.3.0", "path": "g++"}}


def probe(vendor="libstdc++", *, symbol="broker", layout="v1"):
    macro = {"__GLIBCXX__": "20230818"} if vendor == "libstdc++" else {"_LIBCPP_VERSION": "180000"}
    return {
        "macros": macro, "data_layout": "e-p:64:64", "pointer_width": 64,
        "toolchain_lineage": f"locked-{vendor}",
        "headers": [{"path": f"/usr/include/{vendor}/thread", "sha256": "a" * 64}],
        "wrappers": [{"role": "entry-broker", "symbol": symbol,
                      "calling_convention": "ccc", "parameter_roles": ["callable"],
                      "layout": layout}],
        "provenance": ["compile-only", "llvm-ir"],
    }


def local(profile):
    return cpp_thread_document(
        "CppThreadLocalFacts", scope_id="scope", physical_tu_id="tu",
        profile_id="b" * 64, language="c++", standard=profile["cxx_standard"],
        status="complete", library_profile_id=profile["profile_id"],
        callables=[], operations=[], dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)


def test_build_and_adopt_exact_libstdcpp_and_libcpp_profiles():
    gnu = build_library_profile(compilation(), probe())
    libcxx = build_library_profile(compilation("c++20", "clang"), probe("libc++"))
    assert (gnu["vendor"], libcxx["vendor"]) == ("libstdc++", "libc++")
    assert adopt_profile(gnu, deepcopy(gnu)) == (gnu, None)
    changed = build_library_profile(compilation(), probe(layout="v2"))
    adopted, gap = adopt_profile(changed, gnu)
    assert adopted is None and gap["code"] == "abi-wrapper-mismatch"


def test_profile_detection_rejects_c_ambiguous_missing_and_invalid_wrapper():
    with pytest.raises(AnalysisError, match=r"C\+\+17"):
        build_library_profile({"language": "c", "standard": "c17", "target": "x"}, probe())
    ambiguous = probe(); ambiguous["macros"]["_LIBCPP_VERSION"] = "1"
    with pytest.raises(AnalysisError, match="Exactly one"):
        build_library_profile(compilation(), ambiguous)
    missing = probe(); missing["wrappers"] = []
    with pytest.raises(AnalysisError, match="requires wrapper"):
        build_library_profile(compilation(), missing)
    invalid = probe(); invalid["wrappers"][0]["role"] = "magic"
    with pytest.raises(AnalysisError, match="Unsupported wrapper"):
        build_library_profile(compilation(), invalid)


def test_normalize_wrapper_calls_requires_symbol_convention_and_digest():
    profile = build_library_profile(compilation(), probe())
    signature = profile["wrapper_signatures"][0]
    calls = [
        {"id": "a", "symbol": "broker", "calling_convention": "ccc",
         "signature_digest": signature["digest"], "contains_pthread": True, "evidence": ["ir", "ast"]},
        {"id": "b", "symbol": "broker", "calling_convention": "ccc",
         "signature_digest": "f" * 64, "contains_pthread": True},
        {"id": "c", "symbol": "lookalike", "calling_convention": "ccc",
         "signature_digest": signature["digest"]},
    ]
    normalized, diagnostics = normalize_wrapper_calls(calls, profile)
    assert normalized == [{"call_id": "a", "role": "entry-broker", "profile_id": profile["profile_id"],
                           "model_owned_pthread": True, "evidence": ["ast", "ir"]}]
    assert [item["code"] for item in diagnostics] == ["abi-wrapper-mismatch", "abi-wrapper-mismatch"]


def test_a3_cache_isolated_loads_rejects_stale_transient_and_collision(tmp_path, monkeypatch):
    profile = build_library_profile(compilation(), probe())
    value = local(profile)
    cache = CppThreadCache(tmp_path / "artifacts")
    key = cache_key("local-facts", {"profile": profile["profile_id"]}, ["b", "a"])
    assert key == cache_key("local-facts", {"profile": profile["profile_id"]}, ["a", "b"])
    path = cache.publish("local-facts", key, value)
    assert cache.publish("local-facts", key, value) == path
    assert "cpp-thread-lifecycle-v1" in str(path)
    assert cache.load("local-facts", key, value["kind"], dependencies=[]) == value
    assert cache.load("local-facts", "missing", value["kind"]) is None
    with pytest.raises(AnalysisError, match="stale"):
        cache.load("local-facts", key, value["kind"], dependencies=[{"kind": "x", "id": "y", "digest": "a" * 64}])
    with pytest.raises(AnalysisError, match="not cacheable"):
        cache.publish("local-facts", "x", value, stability="transient")
    with pytest.raises(AnalysisError, match="must be documents"):
        cache.publish("local-facts", "x", [])
    failed = deepcopy(value); failed["status"] = "failed"
    from memory_order_analyzer.cpp_thread_contracts import semantic_digest
    failed["semantic_digest"] = semantic_digest(failed)
    with pytest.raises(AnalysisError, match="not cacheable"):
        cache.publish("local-facts", "failed", failed)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid A3 cache"):
        cache.load("local-facts", key, value["kind"])
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid A3 cache"):
        cache.load("local-facts", key, value["kind"])

    path.unlink()
    cache.publish("local-facts", key, value)
    changed = deepcopy(value); changed["status"] = "partial"
    changed["semantic_digest"] = semantic_digest(changed)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("local-facts", key, changed)
    with pytest.raises(AnalysisError, match="escapes"):
        cache._path("../escape", key)

    path.unlink()
    def racing(source, destination):
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        raise FileExistsError
    monkeypatch.setattr(cache_module.os, "link", racing)
    assert cache.publish("local-facts", key, value).is_file()
    path.unlink()
    def conflicting(source, destination):
        destination.write_text("different", encoding="utf-8")
        raise FileExistsError
    monkeypatch.setattr(cache_module.os, "link", conflicting)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("local-facts", key, value)


def test_profile_update_changes_profile_and_cache_identity():
    original = build_library_profile(compilation(), probe())
    changed = build_library_profile(compilation(), probe(symbol="broker-v2"))
    assert original["profile_id"] != changed["profile_id"]
    assert cache_key("profile", {}, [identity(original)]) != cache_key("profile", {}, [identity(changed)])


def test_checked_in_verified_vendor_profiles_are_strict_and_distinct():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "cpp-thread-profiles"
    values = [read_cpp_thread_document(path, "CppThreadLibraryProfile")
              for path in sorted(root.glob("*.json"))]
    assert {item["vendor"] for item in values} == {"libstdc++", "libc++"}
    assert len({item["profile_id"] for item in values}) == 3
    assert {(item["vendor"], item["cxx_standard"]) for item in values} >= {
        ("libstdc++", "c++17"), ("libstdc++", "c++20"), ("libc++", "c++20")}
    assert all({item["role"] for item in value["wrapper_signatures"]} == {
        "construct-attempt", "entry-broker", "join-attempt", "detach-attempt", "handle-transfer"
    } for value in values)
