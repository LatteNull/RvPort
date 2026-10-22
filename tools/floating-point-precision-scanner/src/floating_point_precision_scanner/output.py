"""确定性 JSON 与同目录原子写出。"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any


def serialize_json(document: Mapping[str, Any]) -> bytes:
    text = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    return (text + "\n").encode("utf-8")


def write_atomic(
    document: Mapping[str, Any],
    target: Path,
    *,
    replace: Callable[[str, str], None] = os.replace,
    sync: Callable[[int], None] = os.fsync,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(serialize_json(document))
            stream.flush()
            sync(stream.fileno())
        replace(temporary, str(target))
        temporary = ""
        if os.name != "nt":
            directory_fd = os.open(target.parent, os.O_RDONLY)
            try:
                sync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary:
            with suppress(FileNotFoundError):
                os.unlink(temporary)
