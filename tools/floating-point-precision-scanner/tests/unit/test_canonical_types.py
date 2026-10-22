from floating_point_precision_scanner.canonical_types import (
    canonical_scalar_type,
    from_spellings,
)


def test_desugared_typedef_and_cv_qualifiers_produce_canonical_scalars() -> None:
    value = canonical_scalar_type(
        {"type": {"qualType": "const real64", "desugaredQualType": "const double"}}
    )
    assert value == {
        "category": "floating",
        "canonical": "double",
        "qual_type": "const real64",
        "desugared_qual_type": "const double",
        "source": "desugaredQualType",
    }
    assert from_spellings("volatile unsigned long long")["category"] == "integer"


def test_wrappers_containers_and_missing_types_are_not_scalar_floats() -> None:
    for spelling in (
        "float *",
        "double (&)[4]",
        "float (double)",
        "std::array<float, 4>",
        "float Example::*",
    ):
        value = from_spellings(spelling)
        assert value["category"] == "other"
        assert value["canonical"] == spelling
    assert from_spellings(None)["category"] == "unknown"


def test_extended_floating_and_integer_spellings_are_classified_without_substrings() -> None:
    assert from_spellings("long double")["category"] == "floating"
    assert from_spellings("_Float128")["category"] == "floating"
    assert from_spellings("__int128")["category"] == "integer"
    assert from_spellings("my_double_container")["category"] == "other"
