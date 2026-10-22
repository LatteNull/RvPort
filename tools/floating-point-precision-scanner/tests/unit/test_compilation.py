from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.helpers import make_request

from floating_point_precision_scanner.compilation import (
    CompilationInputError,
    ResponseBudget,
    detect_language,
    expand_response_files,
    load_compilation_plan,
    normalize_language_standard,
    parse_command,
    sanitize_arguments,
)
from floating_point_precision_scanner.protocol import SchemaRegistry, parse_request


def parsed(document: dict[str, object]):
    request, errors = parse_request(document, SchemaRegistry())
    assert not errors and request is not None
    return request


@pytest.mark.parametrize(
    ("name", "arguments", "language"),
    [
        ("a.c", ["clang", "-std=c11"], "c"),
        ("a.c", ["clang", "-std=c17"], "c"),
        ("a.cpp", ["clang++", "-std=c++17"], "c++"),
        ("a.cpp", ["clang++", "-std=c++20"], "c++"),
        ("a.txt", ["clang", "-x", "c++"], "c++"),
        ("a.c", ["clang", "-xc", "-xc++"], "c++"),
    ],
)
def test_language_detection(name: str, arguments: list[str], language: str) -> None:
    assert detect_language(arguments, Path(name))[0] == language


def test_language_detection_rejects_unknown() -> None:
    assert detect_language(["clang", "-x", "cuda"], Path("a.c")) == (None, "explicit")
    assert detect_language(["tool"], Path("a.rs")) == (None, "extension")


@pytest.mark.parametrize(
    ("value", "language", "standard", "dialect"),
    [("c89", "c", "c89", "iso"), ("gnu99", "c", "c99", "gnu"),
     ("c++03", "c++", "c++03", "iso"), ("gnu++14", "c++", "c++14", "gnu")],
)
def test_legacy_language_standard_is_preserved(value, language, standard, dialect) -> None:
    context = normalize_language_standard(value, language)
    assert context == {"standard": standard, "dialect": dialect, "standard_source": "explicit",
                       "standard_option": f"-std={value}"}


def test_compiler_default_is_explicitly_identified() -> None:
    context = normalize_language_standard(None, "c")
    assert context["standard"] == "compiler-default"
    assert context["dialect"] == "compiler-default"
    assert context["standard_source"] == "compiler-default"
    assert context["standard_option"] is None


def test_unknown_standard_is_preserved_as_unsupported_context() -> None:
    context = normalize_language_standard("vendor-c", "c")
    assert context["standard"] == "unsupported"
    assert context["standard_option"] == "-std=vendor-c"


def test_parse_command_posix_windows_and_controls() -> None:
    assert parse_command('clang -DNAME="a b" main.c', "posix")[-1] == "main.c"
    assert parse_command('clang "a b.c"', "windows")[-1] == "a b.c"
    with pytest.raises(ValueError, match="platform"):
        parse_command("clang a.c", "other")
    with pytest.raises(ValueError, match="shell"):
        parse_command("clang a.c && whoami", "posix")


def test_response_files_expand_and_detect_failures(tmp_path: Path) -> None:
    (tmp_path / "two.rsp").write_text("-DVALUE=2", encoding="utf-8")
    (tmp_path / "one.rsp").write_text("-Iinclude @two.rsp", encoding="utf-8")
    values, provenance = expand_response_files(["clang", "@one.rsp"], tmp_path, tmp_path, "posix")
    assert values == ["clang", "-Iinclude", "-DVALUE=2"]
    assert provenance[1].startswith("response:")
    (tmp_path / "cycle.rsp").write_text("@cycle.rsp", encoding="utf-8")
    with pytest.raises(ValueError, match="cycle"):
        expand_response_files(["@cycle.rsp"], tmp_path, tmp_path, "posix")
    with pytest.raises(ValueError, match="depth"):
        expand_response_files(
            ["@one.rsp"], tmp_path, tmp_path, "posix", ResponseBudget(max_depth=0)
        )
    with pytest.raises(ValueError, match="budget"):
        expand_response_files(
            ["@one.rsp"], tmp_path, tmp_path, "posix", ResponseBudget(max_bytes=1)
        )
    with pytest.raises(ValueError, match="outside"):
        expand_response_files(["@../outside.rsp"], tmp_path, tmp_path, "posix")


def test_sanitize_arguments_removes_side_effects(tmp_path: Path) -> None:
    source = tmp_path / "a.c"
    arguments = [
        "clang",
        "-std=c17",
        "-c",
        str(source),
        "-o",
        "a.o",
        "-MMD",
        "-MF",
        "a.d",
        "-DOK=1",
    ]
    assert sanitize_arguments(arguments, source) == ("-std=c17", "-DOK=1")


def test_explicit_units_are_normalized_and_distinct(tmp_path: Path) -> None:
    source = tmp_path / "same.c"
    source.write_text("double x;", encoding="utf-8")
    units = [
        {
            "file": "same.c",
            "directory": str(tmp_path),
            "arguments": ["clang", "-std=c11", "-DMODE=1", "same.c"],
        },
        {
            "file": "same.c",
            "directory": str(tmp_path),
            "arguments": ["clang", "-std=c17", "-DMODE=2", "same.c"],
        },
    ]
    plan = load_compilation_plan(parsed(make_request(tmp_path, units)))
    assert len(plan.contexts) == 2
    assert len({item.translation_unit_id for item in plan.contexts}) == 2
    assert [item.standard for item in plan.contexts] == ["c11", "c17"]


def test_compile_database_prefers_arguments_and_excludes_languages(tmp_path: Path) -> None:
    (tmp_path / "a.c").write_text("double x;", encoding="utf-8")
    (tmp_path / "b.rs").write_text("fn main() {}", encoding="utf-8")
    database = [
        {
            "directory": str(tmp_path),
            "file": "a.c",
            "arguments": ["clang", "-c", "a.c"],
            "command": "bad && bad",
        },
        {"directory": str(tmp_path), "file": "b.rs", "command": "rustc b.rs"},
    ]
    (tmp_path / "compile_commands.json").write_text(json.dumps(database), encoding="utf-8")
    document = make_request(tmp_path)
    document["input"] = {"compile_commands": "compile_commands.json"}
    plan = load_compilation_plan(parsed(document))
    assert len(plan.contexts) == 1
    assert {item.diagnostic_code for item in plan.diagnostics} == {
        "compile_record_arguments_preferred",
        "unsupported_language",
    }


def test_no_supported_language_is_invalid(tmp_path: Path) -> None:
    source = tmp_path / "a.rs"
    source.write_text("fn main() {}", encoding="utf-8")
    document = make_request(
        tmp_path, [{"file": "a.rs", "directory": str(tmp_path), "arguments": ["rustc", "a.rs"]}]
    )
    with pytest.raises(CompilationInputError) as error:
        load_compilation_plan(parsed(document))
    assert error.value.diagnostics[-1].diagnostic_code == "no_supported_translation_units"


def test_missing_source_is_failed_unit(tmp_path: Path) -> None:
    document = make_request(
        tmp_path,
        [{"file": "missing.c", "directory": str(tmp_path), "arguments": ["clang", "missing.c"]}],
    )
    plan = load_compilation_plan(parsed(document))
    assert plan.failed_count == 1
    assert plan.contexts == ()
    assert plan.diagnostics[0].diagnostic_code == "source_file_missing"


def test_project_root_escape_is_invalid_request(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.c"
    outside.write_text("double x;", encoding="utf-8")
    document = make_request(
        tmp_path,
        [
            {
                "file": str(outside),
                "directory": str(tmp_path),
                "arguments": ["clang", str(outside)],
            }
        ],
    )
    with pytest.raises(CompilationInputError) as error:
        load_compilation_plan(parsed(document))
    assert error.value.diagnostics[0].diagnostic_code == "path_outside_project_root"


@pytest.mark.parametrize("content", ["{}", "not-json"])
def test_invalid_compile_database(tmp_path: Path, content: str) -> None:
    (tmp_path / "compile_commands.json").write_text(content, encoding="utf-8")
    document = make_request(tmp_path)
    document["input"] = {"compile_commands": "compile_commands.json"}
    with pytest.raises(CompilationInputError):
        load_compilation_plan(parsed(document))
