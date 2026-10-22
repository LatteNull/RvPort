from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from collections.abc import Iterable
from pathlib import Path

from ..core import ArtifactRef


class AtomicArtifactPublisher:
    def __init__(self, replace=os.replace) -> None:
        self._replace = replace

    def publish(self, output: Path, rendered: dict[str, bytes | Iterable[bytes]]) -> tuple[ArtifactRef, ...]:
        output.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".kb-scanner-stage-", dir=output))
        backup = staging / ".backup"
        backup.mkdir()
        published: list[str] = []
        digests = {}
        try:
            for name, content in rendered.items():
                digest = hashlib.sha256()
                with (staging / name).open("wb", buffering=1024 * 1024) as stream:
                    for chunk in (content,) if isinstance(content, bytes) else content:
                        stream.write(chunk)
                        digest.update(chunk)
                digests[name] = digest.hexdigest()
            for name in rendered:
                target = output / name
                if target.exists():
                    self._replace(target, backup / name)
                self._replace(staging / name, target)
                published.append(name)
            return tuple(ArtifactRef(name, output / name, digests[name]) for name in rendered)
        except Exception:
            rollback_error = None
            for name in reversed(published):
                try:
                    target = output / name
                    if target.exists():
                        target.unlink()
                except OSError as exc:
                    rollback_error = rollback_error or exc
            for name in rendered:
                saved = backup / name
                if saved.exists():
                    try:
                        self._replace(saved, output / name)
                    except OSError as exc:
                        rollback_error = rollback_error or exc
            if rollback_error is not None:
                raise RuntimeError("artifact rollback failed") from rollback_error
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
