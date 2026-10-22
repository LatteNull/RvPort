"""无 shell 的编译上下文摄取与 C/C++ 选择。"""

from __future__ import annotations

import hashlib
import json
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import normalize_repo_path, semantic_digest, stable_id
from .diagnostics import Diagnostic, aggregate_diagnostics, diagnostic
from .protocol import ScanRequest

SUPPORTED_LANGUAGES = {"c", "c-header", "c++", "c++-header"}
EXTENSION_LANGUAGES = {
    ".c": "c",
    ".h": "c-header",
    ".cc": "c++",
    ".cp": "c++",
    ".cpp": "c++",
    ".cxx": "c++",
    ".c++": "c++",
    ".hh": "c++-header",
    ".hpp": "c++-header",
    ".hxx": "c++-header",
}
SHELL_CONTROL = {"&&", "||", ";", "|", ">", ">>", "<"}
DROP_WITH_VALUE = {"-o", "-MF", "-MT", "-MQ", "--output"}
DROP_SINGLE = {"-c", "-MD", "-MMD", "-MP", "-MM", "-M", "-S", "-emit-llvm"}


@dataclass(frozen=True, slots=True)
class CompileContext:
    translation_unit_id: str
    file: str
    absolute_file: Path
    directory: Path
    language: str
    standard: str | None
    target: str | None
    abi: str | None
    arguments: tuple[str, ...]
    semantic_arguments: tuple[str, ...]
    provenance: tuple[str, ...]

    @property
    def context_id(self) -> str:
        return self.translation_unit_id

    @property
    def physical_tu_id(self) -> str:
        return stable_id("physical_tu", {"file": self.file, "language": self.language})

    def public_dict(self) -> dict[str, Any]:
        standard_context = normalize_language_standard(self.standard, self.language)
        return {
            "translation_unit_id": self.translation_unit_id,
            "context_id": self.context_id,
            "physical_tu_id": self.physical_tu_id,
            "file": self.file,
            "language": self.language,
            "standard": self.standard,
            "base_standard": standard_context["standard"],
            "dialect": standard_context["dialect"],
            "standard_source": standard_context["standard_source"],
            "standard_option": standard_context["standard_option"],
            "target": self.target,
            "abi": self.abi,
            "semantic_arguments": list(self.semantic_arguments),
            "effective_fp_options": normalize_fp_options(self.semantic_arguments),
            "semantic_digest": semantic_digest(list(self.semantic_arguments)),
        }


@dataclass(frozen=True, slots=True)
class CompilationPlan:
    contexts: tuple[CompileContext, ...]
    diagnostics: tuple[Diagnostic, ...]
    failed_count: int = 0
    input_digest: str = ""


@dataclass(slots=True)
class ResponseBudget:
    max_depth: int = 8
    max_files: int = 32
    max_bytes: int = 1_048_576
    files: int = 0
    bytes: int = 0


class CompilationInputError(ValueError):
    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        super().__init__("invalid_compilation_input")


def normalize_language_standard(value: str | None, language: str) -> dict[str, str | None]:
    aliases = {
        "c89": "c89", "c90": "c89", "iso9899:1990": "c89", "iso9899:199409": "c89",
        "gnu89": "c89", "gnu90": "c89", "c99": "c99", "c9x": "c99", "gnu99": "c99",
        "gnu9x": "c99", "c11": "c11", "c1x": "c11", "gnu11": "c11", "gnu1x": "c11",
        "c17": "c17", "c18": "c17", "gnu17": "c17", "gnu18": "c17",
        "c23": "c23", "c2x": "c23", "gnu23": "c23", "gnu2x": "c23",
        "c++98": "c++98", "gnu++98": "c++98", "c++03": "c++03", "gnu++03": "c++03",
        "c++11": "c++11", "c++0x": "c++11", "gnu++11": "c++11", "gnu++0x": "c++11",
        "c++14": "c++14", "c++1y": "c++14", "gnu++14": "c++14", "gnu++1y": "c++14",
        "c++17": "c++17", "c++1z": "c++17", "gnu++17": "c++17", "gnu++1z": "c++17",
        "c++20": "c++20", "c++2a": "c++20", "gnu++20": "c++20", "gnu++2a": "c++20",
        "c++23": "c++23", "c++2b": "c++23", "gnu++23": "c++23", "gnu++2b": "c++23",
    }
    if value is None:
        return {"standard": "compiler-default", "dialect": "compiler-default",
                "standard_source": "compiler-default", "standard_option": None}
    raw = value.lower()
    base = aliases.get(raw, "unsupported")
    return {"standard": base, "dialect": "gnu" if raw.startswith("gnu") else "iso",
            "standard_source": "explicit", "standard_option": f"-std={raw}"}


def _resolve_inside(path: str | Path, base: Path, root: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = base / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("path_outside_project_root") from exc
    return candidate


def parse_command(command: str, platform: str) -> list[str]:
    if platform not in {"posix", "windows"}:
        raise ValueError("unsupported_command_platform")
    parsed = shlex.split(command, posix=platform == "posix")
    cleaned = [
        arg[1:-1] if platform == "windows" and len(arg) >= 2 and arg[0] == arg[-1] == '"' else arg
        for arg in parsed
    ]
    if any(arg in SHELL_CONTROL for arg in cleaned):
        raise ValueError("ambiguous_shell_control")
    return cleaned


def expand_response_files(
    arguments: Sequence[str],
    directory: Path,
    root: Path,
    platform: str,
    budget: ResponseBudget | None = None,
    stack: tuple[Path, ...] = (),
) -> tuple[list[str], list[str]]:
    active = budget or ResponseBudget()
    expanded: list[str] = []
    provenance: list[str] = []
    for argument in arguments:
        if not argument.startswith("@") or argument == "@":
            expanded.append(argument)
            provenance.append("command")
            continue
        response_path = _resolve_inside(argument[1:], directory, root)
        if response_path in stack:
            raise ValueError("response_file_cycle")
        if len(stack) >= active.max_depth:
            raise ValueError("response_file_depth_exceeded")
        raw = response_path.read_bytes()
        active.files += 1
        active.bytes += len(raw)
        if active.files > active.max_files or active.bytes > active.max_bytes:
            raise ValueError("response_file_budget_exceeded")
        nested = parse_command(raw.decode("utf-8"), platform)
        values, origins = expand_response_files(
            nested, response_path.parent, root, platform, active, (*stack, response_path)
        )
        expanded.extend(values)
        provenance.extend(f"response:{normalize_repo_path(response_path, root)}" for _ in origins)
    return expanded, provenance


def detect_language(arguments: Sequence[str], file: Path) -> tuple[str | None, str]:
    explicit: str | None = None
    index = 0
    while index < len(arguments):
        arg = arguments[index]
        if arg == "-x" and index + 1 < len(arguments):
            explicit = arguments[index + 1]
            index += 2
            continue
        if arg.startswith("-x") and len(arg) > 2:
            explicit = arg[2:]
        index += 1
    if explicit is not None:
        return (explicit if explicit in SUPPORTED_LANGUAGES else None), "explicit"
    language = EXTENSION_LANGUAGES.get(file.suffix.lower())
    return language, "extension"


def _effective_value(
    arguments: Sequence[str], short: str, long_prefix: str | None = None
) -> str | None:
    value: str | None = None
    index = 0
    while index < len(arguments):
        arg = arguments[index]
        if arg == short and index + 1 < len(arguments):
            value = arguments[index + 1]
            index += 2
            continue
        if long_prefix and arg.startswith(long_prefix):
            value = arg[len(long_prefix) :]
        index += 1
    return value


def sanitize_arguments(arguments: Sequence[str], source: Path) -> tuple[str, ...]:
    result: list[str] = []
    index = 1 if arguments and not arguments[0].startswith("-") else 0
    while index < len(arguments):
        arg = arguments[index]
        if arg in DROP_WITH_VALUE:
            index += 2
            continue
        if arg in DROP_SINGLE or arg == str(source) or Path(arg).name == source.name:
            index += 1
            continue
        result.append(arg)
        index += 1
    return tuple(result)


def normalize_fp_options(arguments: Sequence[str]) -> dict[str, Any]:
    """Normalize Clang floating-point options using last-option-wins semantics."""
    state: dict[str, Any] = {
        "reassociation": False,
        "no_nans": False,
        "no_infs": False,
        "no_signed_zeros": False,
        "reciprocal_math": False,
        "approx_functions": False,
        "finite_math_only": False,
        "fp_contract": "on",
        "math_errno": True,
        "trapping_math": True,
        "rounding_math": False,
        "excess_precision": "standard",
        "x87_enabled": False,
    }
    provenance: dict[str, str] = {key: "clang-default" for key in state}

    def set_value(key: str, value: Any, option: str) -> None:
        state[key] = value
        provenance[key] = option

    for option in arguments:
        if option in {"-ffast-math", "-Ofast"}:
            for key in (
                "reassociation",
                "no_nans",
                "no_infs",
                "no_signed_zeros",
                "reciprocal_math",
                "approx_functions",
                "finite_math_only",
            ):
                set_value(key, True, option)
            set_value("fp_contract", "fast", option)
            set_value("math_errno", False, option)
            set_value("trapping_math", False, option)
        elif option == "-fno-fast-math":
            for key in (
                "reassociation",
                "no_nans",
                "no_infs",
                "no_signed_zeros",
                "reciprocal_math",
                "approx_functions",
                "finite_math_only",
            ):
                set_value(key, False, option)
            set_value("fp_contract", "on", option)
            set_value("math_errno", True, option)
            set_value("trapping_math", True, option)
        elif option in {"-fassociative-math", "-fno-associative-math"}:
            set_value("reassociation", option == "-fassociative-math", option)
        elif option in {"-fno-honor-nans", "-fhonor-nans"}:
            set_value("no_nans", option == "-fno-honor-nans", option)
        elif option in {"-fno-honor-infinities", "-fhonor-infinities"}:
            set_value("no_infs", option == "-fno-honor-infinities", option)
        elif option in {"-fno-signed-zeros", "-fsigned-zeros"}:
            set_value("no_signed_zeros", option == "-fno-signed-zeros", option)
        elif option in {"-freciprocal-math", "-fno-reciprocal-math"}:
            set_value("reciprocal_math", option == "-freciprocal-math", option)
        elif option in {"-fapprox-func", "-fno-approx-func"}:
            set_value("approx_functions", option == "-fapprox-func", option)
        elif option in {"-ffinite-math-only", "-fno-finite-math-only"}:
            enabled = option == "-ffinite-math-only"
            set_value("finite_math_only", enabled, option)
            set_value("no_nans", enabled, option)
            set_value("no_infs", enabled, option)
        elif option.startswith("-ffp-contract="):
            set_value("fp_contract", option.split("=", 1)[1], option)
        elif option in {"-fmath-errno", "-fno-math-errno"}:
            set_value("math_errno", option == "-fmath-errno", option)
        elif option in {"-ftrapping-math", "-fno-trapping-math"}:
            set_value("trapping_math", option == "-ftrapping-math", option)
        elif option in {"-frounding-math", "-fno-rounding-math"}:
            set_value("rounding_math", option == "-frounding-math", option)
        elif option.startswith("-fexcess-precision="):
            set_value("excess_precision", option.split("=", 1)[1], option)
        elif option == "-mfpmath=387":
            set_value("x87_enabled", True, option)
        elif option == "-mfpmath=sse":
            set_value("x87_enabled", False, option)
    return {**state, "provenance": provenance}


def _record_arguments(record: Mapping[str, Any], platform: str) -> tuple[list[str], bool]:
    arguments = record.get("arguments")
    command = record.get("command")
    if isinstance(arguments, list) and all(isinstance(item, str) for item in arguments):
        return list(arguments), command is not None
    if isinstance(command, str):
        return parse_command(command, platform), False
    raise ValueError("compile_record_has_no_arguments")


def _records(request: ScanRequest) -> list[Mapping[str, Any]]:
    if "compile_commands" in request.input:
        database = _resolve_inside(
            str(request.input["compile_commands"]), request.project_root, request.project_root
        )
        document = json.loads(database.read_text(encoding="utf-8"))
        if not isinstance(document, list) or not all(
            isinstance(item, Mapping) for item in document
        ):
            raise ValueError("compile_commands_must_be_array")
        return list(document)
    units = request.input.get("translation_units")
    if isinstance(units, list):
        return list(units)
    raise ValueError("input_selector_conflict")


def load_compilation_plan(request: ScanRequest) -> CompilationPlan:
    input_digest = ""
    try:
        if "compile_commands" in request.input:
            database = _resolve_inside(
                str(request.input["compile_commands"]),
                request.project_root,
                request.project_root,
            )
            input_digest = hashlib.sha256(database.read_bytes()).hexdigest()
        records = _records(request)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise CompilationInputError(
            [
                diagnostic(
                    "invalid_compilation_database",
                    "compilation_input",
                    "无法加载编译输入。",
                    "Unable to load compilation input.",
                    suggestion=str(exc),
                    suggestion_en=str(exc),
                )
            ]
        ) from exc
    contexts: list[CompileContext] = []
    diagnostics: list[Diagnostic] = []
    failed = 0
    for record in records:
        platform = str(record.get("platform", "posix"))
        try:
            directory = _resolve_inside(
                str(record.get("directory", request.project_root)),
                request.project_root,
                request.project_root,
            )
            source = _resolve_inside(str(record["file"]), directory, request.project_root)
            args, conflict = _record_arguments(record, platform)
            limits = ResponseBudget(
                max_depth=int(request.budgets.get("max_response_depth", 8)),
                max_files=int(request.budgets.get("max_files", 32)),
                max_bytes=int(request.budgets.get("max_response_bytes", 1_048_576)),
            )
            args, origins = expand_response_files(
                args, directory, request.project_root, platform, limits
            )
            language, language_source = detect_language(args, source)
            if language is None:
                diagnostics.append(
                    diagnostic(
                        "unsupported_language",
                        "compilation_input",
                        "已排除非 C/C++ 编译条目。",
                        "Excluded a non-C/C++ compile entry.",
                        severity="info",
                        suggestion="无需操作；该条目不属于扫描范围。",
                        suggestion_en="No action is required; this entry is outside scanner scope.",
                    )
                )
                continue
            if not source.is_file():
                failed += 1
                diagnostics.append(
                    diagnostic(
                        "source_file_missing",
                        "compilation_input",
                        "C/C++ 源文件不存在。",
                        "C/C++ source file does not exist.",
                    )
                )
                continue
            semantic = sanitize_arguments(args, source)
            standard = _effective_value(semantic, "-std", "-std=")
            target = _effective_value(semantic, "-target", "--target=")
            abi = _effective_value(semantic, "-mabi", "-mabi=")
            relative = normalize_repo_path(source, request.project_root)
            identity = stable_id(
                "translation_unit",
                {
                    "file": relative,
                    "directory": normalize_repo_path(directory, request.project_root),
                    "language": language,
                    "arguments": semantic,
                },
            )
            contexts.append(
                CompileContext(
                    identity,
                    relative,
                    source,
                    directory,
                    language,
                    standard,
                    target,
                    abi,
                    tuple(args),
                    semantic,
                    tuple([f"language:{language_source}", *origins]),
                )
            )
            if conflict:
                diagnostics.append(
                    diagnostic(
                        "compile_record_arguments_preferred",
                        "compilation_input",
                        "编译记录同时包含 arguments 和 command，已使用 arguments。",
                        "The compile record contains both arguments and command; "
                        "arguments was used.",
                        severity="warning",
                    )
                )
        except (KeyError, OSError, UnicodeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc) == "path_outside_project_root":
                raise CompilationInputError(
                    [
                        diagnostic(
                            "path_outside_project_root",
                            "compilation_input",
                            "编译输入路径超出项目根目录。",
                            "A compilation input path is outside the project root.",
                        )
                    ]
                ) from exc
            failed += 1
            diagnostics.append(
                diagnostic(
                    "compile_record_invalid",
                    "compilation_input",
                    "编译记录无效。",
                    "Compile record is invalid.",
                    suggestion=str(exc),
                    suggestion_en=str(exc),
                )
            )
    unique = {(context.translation_unit_id, context): context for context in contexts}
    ordered = tuple(sorted(unique.values(), key=lambda item: (item.file, item.translation_unit_id)))
    aggregated = tuple(aggregate_diagnostics(diagnostics))
    if not ordered and failed == 0:
        raise CompilationInputError(
            [
                *aggregated,
                diagnostic(
                    "no_supported_translation_units",
                    "compilation_input",
                    "输入中没有 C/C++ 翻译单元。",
                    "No C/C++ translation units were found.",
                ),
            ]
        )
    if not input_digest:
        input_digest = semantic_digest([context.public_dict() for context in ordered])
    return CompilationPlan(ordered, aggregated, failed, input_digest)
