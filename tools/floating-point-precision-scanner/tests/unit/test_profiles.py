from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from tests.helpers import RISCV, X86

from floating_point_precision_scanner.profiles import (
    ProfileLookupError,
    ProfileRegistry,
    ProfileRegistryError,
    profile_context_diagnostic,
)


def test_builtin_profiles_are_sorted_and_bound() -> None:
    registry = ProfileRegistry()
    profiles = registry.list()
    assert [item.reference for item in profiles] == [RISCV, X86]
    source, target = registry.bind(X86, RISCV)
    assert source.target_triple == "x86_64-unknown-linux-gnu"
    assert target.abi == "lp64d"
    assert source.summary()["fingerprint"] == source.fingerprint


def test_unknown_profile_raises() -> None:
    with pytest.raises(ProfileLookupError):
        ProfileRegistry().get("missing@1.0")


def test_profile_fingerprint_ignores_load_path(tmp_path: Path) -> None:
    registry = ProfileRegistry()
    source = registry.get(X86)
    for name in ("a", "b"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "profile.json").write_text(json.dumps(source.document), encoding="utf-8")
    assert (
        ProfileRegistry.from_directory(tmp_path / "a").list()[0].fingerprint
        == ProfileRegistry.from_directory(tmp_path / "b").list()[0].fingerprint
    )


def test_invalid_profile_and_missing_sources() -> None:
    valid = copy.deepcopy(ProfileRegistry().get(X86).document)
    missing = copy.deepcopy(valid)
    del missing["sources"]
    with pytest.raises(ProfileRegistryError) as error:
        ProfileRegistry([missing])
    codes = {item.diagnostic_code for item in error.value.diagnostics}
    assert "schema_validation_error" in codes
    assert "profile_source_missing" in codes


def test_duplicate_profile_is_rejected() -> None:
    document = ProfileRegistry().get(X86).document
    with pytest.raises(ProfileRegistryError) as error:
        ProfileRegistry([document, document])
    assert error.value.diagnostics[-1].diagnostic_code == "duplicate_profile"


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"target": "riscv64-unknown-linux-gnu"}, "target="),
        ({"abi": "lp64d"}, "abi="),
        ({"clang_version": "20.0.0"}, "clang="),
    ],
)
def test_profile_context_conflicts(kwargs: dict[str, str], expected: str) -> None:
    profile = ProfileRegistry().get(X86)
    item = profile_context_diagnostic(profile, **kwargs)
    assert item is not None
    assert expected in item.message_en


def test_profile_context_accepts_matching_or_unknown_values() -> None:
    profile = ProfileRegistry().get(X86)
    assert profile_context_diagnostic(profile) is None
    assert (
        profile_context_diagnostic(
            profile, target=profile.target_triple, abi=profile.abi, clang_version="21.1.8"
        )
        is None
    )
