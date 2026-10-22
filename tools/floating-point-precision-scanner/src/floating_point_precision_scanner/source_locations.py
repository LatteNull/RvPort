"""恢复 Clang JSON 省略的物理源码坐标，不读取项目边界之外的文件。"""

from __future__ import annotations

from array import array
from bisect import bisect_right
from collections.abc import Mapping
from pathlib import Path
from typing import Any

VIRTUAL_SOURCE_NAMES = frozenset(
    {"<scratch space>", "<built-in>", "<command line>", "<invalid sloc>"}
)


def is_virtual_source(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in VIRTUAL_SOURCE_NAMES or (
        normalized.startswith("<") and normalized.endswith(">")
    )


class SourceLocations:
    def __init__(self, root: Path, directory: Path, main_file: Path,
                 max_bytes: int = 16_777_216) -> None:
        self.root = root.resolve()
        self.directory = directory
        self.main_file = main_file
        self.last_file: str | None = None
        self.remaining = max_bytes
        self.indexes: dict[str, tuple[int, array[int]] | None] = {}

    def normalize(self, value: Any) -> None:
        # Clang elides file names relative to the preceding serialized location,
        # including locations in sibling declarations and macro spelling points.
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "loc" and isinstance(child, dict):
                    self.point(child)
                elif key == "range" and isinstance(child, dict):
                    for label in ("begin", "end"):
                        if isinstance(child.get(label), dict):
                            self.point(child[label])
                else:
                    self.normalize(child)
        elif isinstance(value, list):
            for child in value:
                self.normalize(child)

    def point(self, raw: dict[str, Any]) -> None:
        if any(isinstance(raw.get(key), Mapping) for key in ("spellingLoc", "expansionLoc")):
            for key in ("spellingLoc", "expansionLoc"):
                if isinstance(raw.get(key), dict):
                    self.point(raw[key])
            return
        if not raw:
            return
        explicit = raw.get("file")
        if isinstance(explicit, str):
            if is_virtual_source(explicit):
                self.last_file = explicit
                raw["sourceOrigin"] = "virtual"
                raw.pop("line", None)
                raw.pop("col", None)
                return
            self.last_file = explicit
        file = explicit if isinstance(explicit, str) else self.last_file
        if file is None and "includedFrom" not in raw:
            file = str(self.main_file)
        if file is None:
            return
        if is_virtual_source(file):
            raw["file"] = file
            raw["sourceOrigin"] = "virtual"
            raw.pop("line", None)
            raw.pop("col", None)
            return
        path = Path(file)
        path = (path if path.is_absolute() else self.directory / path).resolve()
        raw["file"] = str(path)
        try:
            path.relative_to(self.root)
        except ValueError:
            return
        offset = raw.get("offset")
        complete = all(type(raw.get(key)) is int and raw[key] > 0 for key in ("line", "col"))
        if complete and "presumedLine" not in raw and "presumedFile" not in raw:
            return
        index = self._index(path)
        if index is not None and type(offset) is int and 0 <= offset < index[0]:
            line = bisect_right(index[1], offset)
            raw["line"] = line
            raw["col"] = offset - index[1][line - 1] + 1
        else:
            raw.pop("line", None)
            raw.pop("col", None)

    def _index(self, path: Path) -> tuple[int, array[int]] | None:
        key = str(path)
        if key not in self.indexes:
            self.indexes[key] = None
            try:
                with path.open("rb") as stream:
                    data = stream.read(self.remaining + 1)
                if len(data) > self.remaining:
                    return None
                starts = array("Q", [0])
                for offset, byte in enumerate(data):
                    if byte == 10:
                        starts.append(offset + 1)
                cost = len(data) + starts.itemsize * len(starts)
                if cost > self.remaining:
                    return None
                self.remaining -= cost
                self.indexes[key] = (len(data), starts)
            except OSError:
                pass
        return self.indexes[key]
