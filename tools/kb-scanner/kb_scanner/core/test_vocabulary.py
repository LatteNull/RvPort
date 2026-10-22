from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from .metadata import JsonValue, freeze_metadata


class TestRole(str, Enum):
    SUITE = "test_suite"
    TARGET = "test_target"
    SOURCE = "test_source"
    CANDIDATE = "test_candidate"


class TestRoleStrength(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"


class TestSelectionStatus(str, Enum):
    SELECTED = "selected"
    INACTIVE = "inactive"
    NOT_SELECTED = "not_selected"
    UNKNOWN = "unknown"


class CoverageStatus(str, Enum):
    COVERED = "covered"
    GAP = "gap"
    CANDIDATE = "candidate"
    UNKNOWN = "unknown"


_TEST_SEGMENT = re.compile(r"(?i)(?:^|/)(?:test|tests)(?:/|$)")
_TEST_STEM = re.compile(r"(?i)(?:^test[_-].+|.+[_-]test)$")
_NON_TEST_SEGMENT = re.compile(r"(?i)(?:^|/)(?:benchmark|benchmarks|example|examples|tool|tools)(?:/|$)")


@dataclass(frozen=True, slots=True)
class TestRoleEvidence:
    role: TestRole
    strength: TestRoleStrength
    basis: str
    selection: TestSelectionStatus = TestSelectionStatus.UNKNOWN
    configuration: str = "default"
    metadata: Mapping[str, JsonValue] | None = None

    def __post_init__(self) -> None:
        if not self.basis or not self.configuration:
            raise ValueError("test role basis and configuration must not be empty")
        if self.strength is TestRoleStrength.CANDIDATE and self.role is not TestRole.CANDIDATE:
            raise ValueError("candidate strength cannot be promoted to a confirmed test role")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))


def candidate_test_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized or _NON_TEST_SEGMENT.search(normalized):
        return False
    stem = normalized.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return bool(_TEST_SEGMENT.search(normalized) or _TEST_STEM.fullmatch(stem))


def explicit_test_target(name: str, input_kind: str = "") -> bool:
    normalized = name.strip().lower()
    if input_kind == "ctest":
        return bool(normalized)
    return normalized in {"test", "tests", "check", "check-local", "test-all"} or normalized.startswith(
        ("test-", "check-")
    )
