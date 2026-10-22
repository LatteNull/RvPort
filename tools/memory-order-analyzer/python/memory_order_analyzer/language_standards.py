"""C/C++ language standard normalization without semantic upgrades."""

from dataclasses import dataclass

from .contracts import AnalysisError


@dataclass(frozen=True)
class LanguageStandard:
    language: str
    standard: str
    dialect: str
    source: str
    option: str | None


ALIASES = {
    "c89": ("c", "c89"), "c90": ("c", "c89"), "iso9899:1990": ("c", "c89"),
    "iso9899:199409": ("c", "c89"), "gnu89": ("c", "c89"), "gnu90": ("c", "c89"),
    "c99": ("c", "c99"), "c9x": ("c", "c99"), "gnu99": ("c", "c99"), "gnu9x": ("c", "c99"),
    "c11": ("c", "c11"), "c1x": ("c", "c11"), "gnu11": ("c", "c11"), "gnu1x": ("c", "c11"),
    "c17": ("c", "c17"), "c18": ("c", "c17"), "gnu17": ("c", "c17"), "gnu18": ("c", "c17"),
    "c23": ("c", "c23"), "c2x": ("c", "c23"), "gnu23": ("c", "c23"), "gnu2x": ("c", "c23"),
    "c++98": ("c++", "c++98"), "gnu++98": ("c++", "c++98"),
    "c++03": ("c++", "c++03"), "gnu++03": ("c++", "c++03"),
    "c++11": ("c++", "c++11"), "c++0x": ("c++", "c++11"),
    "gnu++11": ("c++", "c++11"), "gnu++0x": ("c++", "c++11"),
    "c++14": ("c++", "c++14"), "c++1y": ("c++", "c++14"),
    "gnu++14": ("c++", "c++14"), "gnu++1y": ("c++", "c++14"),
    "c++17": ("c++", "c++17"), "c++1z": ("c++", "c++17"),
    "gnu++17": ("c++", "c++17"), "gnu++1z": ("c++", "c++17"),
    "c++20": ("c++", "c++20"), "c++2a": ("c++", "c++20"),
    "gnu++20": ("c++", "c++20"), "gnu++2a": ("c++", "c++20"),
    "c++23": ("c++", "c++23"), "c++2b": ("c++", "c++23"),
    "gnu++23": ("c++", "c++23"), "gnu++2b": ("c++", "c++23"),
}

C_STANDARDS = {"c89", "c99", "c11", "c17", "c23"}
CXX_STANDARDS = {"c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23"}


def validate_standard_context(language: str, standard: str, dialect: str,
                              source: str, option: str | None) -> None:
    if language not in {"c", "c++"}:
        raise AnalysisError("language_unsupported", f"Unsupported language: {language}")
    if source == "compiler-default":
        if standard != "compiler-default" or dialect != "compiler-default" or option is not None:
            raise AnalysisError("profile_conflict", "Compiler-default context must not invent a standard")
        return
    if source != "explicit" or dialect not in {"iso", "gnu"} or not option or not option.startswith("-std="):
        raise AnalysisError("profile_conflict", "Explicit language contexts require dialect and -std option")
    supported = C_STANDARDS if language == "c" else CXX_STANDARDS
    if standard not in supported:
        raise AnalysisError("profile_conflict", "Language and standard disagree")


def normalize_standard(raw: str | None, language: str) -> LanguageStandard:
    if raw is None:
        return LanguageStandard(language, "compiler-default", "compiler-default",
                                "compiler-default", None)
    normalized = raw.lower()
    value = ALIASES.get(normalized)
    if value is None or value[0] != language:
        raise AnalysisError("language_unsupported", f"Unsupported language standard: {raw}")
    return LanguageStandard(language, value[1], "gnu" if normalized.startswith("gnu") else "iso",
                            "explicit", f"-std={normalized}")
