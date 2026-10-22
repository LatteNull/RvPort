"""Build immutable compilation profiles shared by AST and BC evidence."""

import os
from pathlib import Path
import shlex

from .contracts import AnalysisError, file_hash, identity
from .source_contracts import diagnostic, source_document
from .language_standards import normalize_standard


def _absolute(value, directory):
    path = Path(value)
    return str((path if path.is_absolute() else directory / path).resolve())


def _argv(record):
    value = record.get("arguments")
    if value is None and isinstance(record.get("command"), str):
        value = shlex.split(record["command"], posix=os.name != "nt")
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise AnalysisError("compile_record", "Compilation record requires non-empty arguments or command")
    return value


def _take(argv, option):
    values = []
    for index, item in enumerate(argv):
        if item == option and index + 1 < len(argv):
            values.append(argv[index + 1])
        elif item.startswith(option) and item != option:
            values.append(item[len(option):])
    return values


def _standard(argv, source):
    values = _take(argv, "-std=")
    language = ("c++" if values and "++" in values[-1]
                else "c++" if Path(source).suffix.lower() in {".cc", ".cpp", ".cxx", ".c++"} else "c")
    return normalize_standard(values[-1] if values else None, language)


def build_profile(record, *, compiler_version, clang_version="21.1.8", include_hashes=None,
                  path_map=None, replay_status="compatible", replay_diagnostics=None):
    directory = Path(record.get("directory", ".")).resolve()
    argv = _argv(record)
    source = _absolute(record.get("file", argv[-1]), directory)
    if not Path(source).is_file():
        raise AnalysisError("source_missing", f"Source file does not exist: {source}")
    compiler_name = Path(argv[0]).name.lower()
    if compiler_name in {"cl", "cl.exe", "clang-cl", "clang-cl.exe"}:
        raise AnalysisError("compiler_unsupported", "Windows MSVC and clang-cl profiles are outside the supported scope")
    if compiler_name in {"gcc", "g++", "cc", "c++"} or "gcc" in compiler_name:
        family = "gcc"
    elif "clang" in compiler_name:
        family = "clang"
    else:
        raise AnalysisError("compiler_unsupported", f"Only GCC and Clang profiles are supported: {argv[0]}")
    standard = _standard(argv, source)
    includes = sorted({_absolute(value, directory) for flag in ("-I", "-isystem") for value in _take(argv, flag)})
    macros = sorted(set(_take(argv, "-D") + ["!" + item for item in _take(argv, "-U")]))
    forced = sorted({_absolute(value, directory) for value in _take(argv, "-include")})
    target = (_take(argv, "--target=") or _take(argv, "-target") or [record.get("target", "x86_64-pc-linux-gnu")])[-1]
    sysroot = (_take(argv, "--sysroot=") or [None])[-1]
    resource = (_take(argv, "-resource-dir=") or _take(argv, "-resource-dir") or [None])[-1]
    optimization = next((item[1:] for item in reversed(argv) if item in {"-O0", "-O1", "-O2", "-O3", "-Os", "-Oz", "-Og"}), "O0")
    diagnostics = replay_diagnostics or []
    source_entry = {"path": source, "sha256": file_hash(source)}
    hashes = sorted(include_hashes or [], key=lambda item: item["path"])
    mapping = sorted(path_map or [], key=lambda item: (item["from"], item["to"]))
    payload = {
        "compiler": {"family": family, "version": compiler_version, "path": argv[0]},
        "replay": {"clang_version": clang_version, "status": replay_status, "diagnostics": diagnostics},
        "language": standard.language, "standard": standard.standard,
        "dialect": standard.dialect, "standard_source": standard.source,
        "standard_option": standard.option, "target": target,
        "abi": record.get("abi", {}), "sysroot": _absolute(sysroot, directory) if sysroot else None,
        "resource_dir": _absolute(resource, directory) if resource else None,
        "includes": includes, "macros": macros, "forced_includes": forced,
        "working_directory": str(directory), "source": source_entry, "include_hashes": hashes,
        "path_map": mapping, "argv": argv, "argv_digest": identity(argv),
        "debug": any(item == "-g" or item.startswith("-g") and item != "-g0" for item in argv),
        "optimization": optimization,
    }
    return source_document("CompilationProfileIdentity", profile_id=identity(payload), **payload)


def replay_failure(code, detail, detail_en):
    return diagnostic(code, detail, detail_en,
                      suggestion="修正编译记录或使用受支持的 Clang 兼容选项",
                      suggestion_en="Repair the compilation record or use supported Clang-compatible options")
