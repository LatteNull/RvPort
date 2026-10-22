"""Clang 类型对象到可审计 canonical scalar type 的唯一归一化入口。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal, TypedDict

ScalarCategory = Literal["floating", "integer", "other", "unknown"]


class CanonicalScalarType(TypedDict):
    category: ScalarCategory
    canonical: str | None
    qual_type: str | None
    desugared_qual_type: str | None
    source: str | None


_FLOATING = re.compile(
    r"(?:float|double|long double|__fp16|half|__float128|_Float(?:16|32|64|128)x?)"
)
_INTEGER = re.compile(
    r"(?:(?:signed|unsigned)\s+)?(?:bool|char|short(?:\s+int)?|int|long(?:\s+int)?|"
    r"long\s+long(?:\s+int)?|wchar_t|char8_t|char16_t|char32_t|__int128|_BitInt\(\d+\))"
)
_OUTER_QUALIFIERS = re.compile(r"\b(?:const|volatile|restrict|__restrict|__restrict__)\b")


def canonical_scalar_type(node: Mapping[str, Any]) -> CanonicalScalarType:
    type_node = node.get("type")
    if not isinstance(type_node, Mapping):
        return from_spellings(None, None)
    qual = type_node.get("qualType")
    desugared = type_node.get("desugaredQualType")
    return from_spellings(
        str(qual) if isinstance(qual, str) else None,
        str(desugared) if isinstance(desugared, str) else None,
    )


def from_spellings(
    qual_type: str | None,
    desugared_qual_type: str | None = None,
) -> CanonicalScalarType:
    selected = desugared_qual_type or qual_type
    source = "desugaredQualType" if desugared_qual_type else "qualType" if qual_type else None
    if selected is None or not selected.strip():
        return _result("unknown", None, qual_type, desugared_qual_type, source)
    normalized = " ".join(_OUTER_QUALIFIERS.sub("", selected).split())
    if _FLOATING.fullmatch(normalized):
        return _result("floating", normalized, qual_type, desugared_qual_type, source)
    if _INTEGER.fullmatch(normalized):
        return _result("integer", normalized, qual_type, desugared_qual_type, source)
    return _result("other", normalized, qual_type, desugared_qual_type, source)


def _result(
    category: ScalarCategory,
    canonical: str | None,
    qual_type: str | None,
    desugared_qual_type: str | None,
    source: str | None,
) -> CanonicalScalarType:
    return {
        "category": category,
        "canonical": canonical,
        "qual_type": qual_type,
        "desugared_qual_type": desugared_qual_type,
        "source": source,
    }
