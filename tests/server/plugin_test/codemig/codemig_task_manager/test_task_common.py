import pytest
from enum import Enum

from plugin.codemig.codemig_task_manager.task_common import (
    TaskStatus,
    TaskDependenceStatus,
    DependencePackagesStatus,
)


class TestTaskStatus:

    def test_is_enum(self):
        assert issubclass(TaskStatus, Enum)

    def test_members_count(self):
        assert len(TaskStatus) == 5

    @pytest.mark.parametrize(
        "name, value",
        [
            ("CREATED", 0),
            ("PROCESSING", 1),
            ("SUCCESS", 2),
            ("FAILED", 3),
            ("DELETED", 4),
        ],
    )
    def test_value(self, name, value):
        assert TaskStatus[name].value == value

    def test_name_access(self):
        for member in TaskStatus:
            assert member.name in {
                "CREATED", "PROCESSING", "SUCCESS", "FAILED", "DELETED"
            }

    def test_value_access_round_trip(self):
        for member in TaskStatus:
            assert TaskStatus(member.value) is member

    def test_unique_values(self):
        values = [m.value for m in TaskStatus]
        assert len(values) == len(set(values))


class TestTaskDependenceStatus:

    def test_is_enum(self):
        assert issubclass(TaskDependenceStatus, Enum)

    def test_members_count(self):
        assert len(TaskDependenceStatus) == 4

    @pytest.mark.parametrize(
        "name, value",
        [
            ("CREATED", 0),
            ("PROCESSING", 1),
            ("SUCCESS", 2),
            ("FAILED", 3),
        ],
    )
    def test_value(self, name, value):
        assert TaskDependenceStatus[name].value == value

    def test_name_access(self):
        for member in TaskDependenceStatus:
            assert member.name in {
                "CREATED", "PROCESSING", "SUCCESS", "FAILED"
            }

    def test_value_access_round_trip(self):
        for member in TaskDependenceStatus:
            assert TaskDependenceStatus(member.value) is member

    def test_unique_values(self):
        values = [m.value for m in TaskDependenceStatus]
        assert len(values) == len(set(values))

    def test_no_deleted_member(self):
        assert not hasattr(TaskDependenceStatus, "DELETED")


class TestDependencePackagesStatus:

    def test_is_enum(self):
        assert issubclass(DependencePackagesStatus, Enum)

    def test_members_count(self):
        assert len(DependencePackagesStatus) == 2

    @pytest.mark.parametrize(
        "name, value",
        [
            ("FAILED", 0),
            ("SUCCESS", 1),
        ],
    )
    def test_value(self, name, value):
        assert DependencePackagesStatus[name].value == value

    def test_name_access(self):
        for member in DependencePackagesStatus:
            assert member.name in {"FAILED", "SUCCESS"}

    def test_value_access_round_trip(self):
        for member in DependencePackagesStatus:
            assert DependencePackagesStatus(member.value) is member

    def test_unique_values(self):
        values = [m.value for m in DependencePackagesStatus]
        assert len(values) == len(set(values))

    def test_failed_before_success(self):
        assert DependencePackagesStatus.FAILED.value < DependencePackagesStatus.SUCCESS.value
