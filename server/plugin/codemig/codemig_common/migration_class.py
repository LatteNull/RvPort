from enum import Enum


class MigrationClass(Enum):
    TEXT = (0, "源码扫描")
    DYNAMIC_LINK_LIBRARY = (1, "软件包扫描")
    MISSING_ARCH_FILE = (2, "缺失架构文件")
    UNKNOWN = (3, "未知")

    def __new__(cls, value, description):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.description = description
        return obj

    def __str__(self):
        return self.description
