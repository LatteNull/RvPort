"""Versioned, bounded lexical templates. No filesystem or compiler knowledge."""
from dataclasses import dataclass
from pathlib import PurePosixPath
import re

VERSION = 1
_ROLES = {
    **dict.fromkeys(("x86", "x86_64", "i386", "i686", "amd64", "x64", "avx", "avx2", "avx512", "sse", "sse2", "sse3", "ssse3", "sse4", "sse4_1", "sse4_2"), "x86"),
    **dict.fromkeys(("riscv", "riscv32", "riscv64"), "riscv"),
    **dict.fromkeys(("generic", "portable", "scalar", "fallback"), "generic"),
    **dict.fromkeys(("arm", "arm64", "aarch64"), "foreign"),
}
_WORDS = "|".join(re.escape(word) for word in sorted(_ROLES, key=lambda w: (-len(w), w)))
_PREFIX = re.compile(rf"^({_WORDS})[_.-](.+)$", re.I)
_SUFFIX = re.compile(rf"^(.+?)[_.-]({_WORDS})$", re.I)


@dataclass(frozen=True)
class PathCandidate:
    path: str
    key: str
    role: str
    token: str
    rule: str
    ambiguous: bool = False


def candidates(raw):
    path = raw.replace("\\", "/")
    parts = path.split("/")
    if not path or any(p in {"", ".", ".."} for p in parts) or ":" in parts[0]:
        return ()
    pure = PurePosixPath(path)
    slots = []
    for index, part in enumerate(parts[:-1]):
        if part.casefold() in _ROLES:
            key = "/".join((*parts[:index], "{architecture}", *parts[index+1:]))
            slots.append(PathCandidate(path, "directory:" + key, _ROLES[part.casefold()], part, "directory-slot-v1"))
    prefix, suffix = _PREFIX.fullmatch(pure.stem), _SUFFIX.fullmatch(pure.stem)
    for match, token_index, stem_index in ((prefix, 1, 2), (suffix, 2, 1)):
        if match:
            token, stem = match[token_index], match[stem_index]
            slots.append(PathCandidate(path, "filename:" + str(pure.with_name(stem + pure.suffix)),
                                       _ROLES[token.casefold()], token, "filename-affix-v1"))
    if len(slots) > 1:
        # Retain an isolated conflict, never bridge templates transitively.
        return (PathCandidate(path, "ambiguous:" + path, "x86" if any(s.role == "x86" for s in slots) else "unknown",
                              ",".join(s.token for s in slots), "multiple-role-slots-v1", True),)
    if slots:
        return tuple(slots)
    return (PathCandidate(path, "filename:" + path, "unlabelled", "", "unlabelled-v1"),)
