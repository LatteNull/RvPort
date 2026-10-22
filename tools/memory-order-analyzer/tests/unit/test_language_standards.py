import pytest

from memory_order_analyzer.contracts import AnalysisError
from memory_order_analyzer.language_standards import normalize_standard, validate_standard_context


@pytest.mark.parametrize(
    ("raw", "language", "standard", "dialect"),
    [("c89", "c", "c89", "iso"), ("gnu90", "c", "c89", "gnu"),
     ("c99", "c", "c99", "iso"), ("gnu++03", "c++", "c++03", "gnu"),
     ("c++11", "c++", "c++11", "iso"), ("gnu++14", "c++", "c++14", "gnu")],
)
def test_normalizes_legacy_and_gnu_aliases(raw, language, standard, dialect):
    value = normalize_standard(raw, language)
    assert (value.standard, value.dialect, value.source, value.option) == (
        standard, dialect, "explicit", f"-std={raw}")


def test_compiler_default_is_not_presented_as_explicit_upgrade():
    value = normalize_standard(None, "c")
    assert value.standard == "compiler-default"
    assert value.dialect == "compiler-default"
    assert value.source == "compiler-default"
    assert value.option is None


@pytest.mark.parametrize(("raw", "language"), [("c++20", "c"), ("c17", "c++"), ("vendor-c", "c")])
def test_rejects_unknown_or_cross_language_standard(raw, language):
    with pytest.raises(AnalysisError, match="Unsupported language standard"):
        normalize_standard(raw, language)


def test_preserves_c23_and_cpp23_contexts():
    assert normalize_standard("c23", "c").standard == "c23"
    assert normalize_standard("gnu++23", "c++").standard == "c++23"


def test_validates_explicit_and_compiler_default_contexts():
    validate_standard_context("c", "c99", "gnu", "explicit", "-std=gnu99")
    validate_standard_context("c++", "compiler-default", "compiler-default", "compiler-default", None)
    with pytest.raises(AnalysisError, match="Unsupported language"):
        validate_standard_context("objc", "c99", "iso", "explicit", "-std=c99")
    with pytest.raises(AnalysisError, match="must not invent"):
        validate_standard_context("c", "c17", "compiler-default", "compiler-default", None)
    with pytest.raises(AnalysisError, match="require dialect"):
        validate_standard_context("c", "c99", "iso", "explicit", None)
    with pytest.raises(AnalysisError, match="Language and standard disagree"):
        validate_standard_context("c", "c++03", "iso", "explicit", "-std=c++03")
