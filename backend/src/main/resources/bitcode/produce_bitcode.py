#!/usr/bin/env python3
"""在 source/x86 构建目录重放 compile database，发布共享 LLVM BC v2 制品。"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import tarfile
import time
from pathlib import Path

KIND = "SharedLlvmBitcodeArtifactSet"
SCHEMA_VERSION = "2.1"
PROFILE = {"name": "source-preserving", "version": "1"}
SOURCE_SUFFIXES = {".c": "c", ".cc": "c++", ".cp": "c++", ".cpp": "c++", ".cxx": "c++", ".c++": "c++"}
COMPILERS = {"cc", "c++", "gcc", "g++", "clang", "clang++", "clang-21", "clang++-21"}
WRAPPERS = {"ccache", "sccache", "distcc"}
PAIR_FLAGS = {"-o", "-MF", "-MT", "-MQ", "-MJ"}
DROP_FLAGS = {"-c", "-S", "-E", "-emit-llvm", "-MD", "-MMD", "-MP", "-MG", "-MM", "-M"}
SHELL_OPERATORS = {";", "&&", "||", "|", ">", ">>", "<", "<<"}
CAPABILITIES = sorted({
    "llvm.ir-readable", "debug.locations", "debug.variables", "source.correlation",
    "fp.operations", "fp.fast-math-flags", "memory.atomic-ordering", "memory.syncscope",
    "memory.fence", "target.triple", "target.data-layout", "symbols.linkage",
})
IMPLICIT_INCLUDE_CACHE: dict[tuple[str, str], list[str]] = {}
COMPILER_INFO_CACHE: dict[str, dict] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for name in ("compile-db", "source-root", "output-dir", "clang", "clangxx", "llvm-dis",
                 "manifest", "bundle", "toolchain-id", "toolchain-version"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--max-tu", type=int, required=True)
    parser.add_argument("--max-tu-bytes", type=int, required=True)
    parser.add_argument("--max-total-bytes", type=int, required=True)
    parser.add_argument("--tu-timeout", type=int, required=True)
    parser.add_argument("--total-timeout", type=int, required=True)
    return parser.parse_args()


def canonical(value, excluded=frozenset()):
    if isinstance(value, dict):
        return {key: canonical(value[key], excluded) for key in sorted(value) if key not in excluded}
    if isinstance(value, list):
        values = [canonical(item, excluded) for item in value]
        return sorted(values, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return value


def digest(value, *excluded: str) -> str:
    payload = json.dumps(canonical(value, frozenset(excluded)), ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def under_root(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("PATH_OUTSIDE_SOURCE_ROOT") from exc
    return resolved


def relative(path: Path, root: Path) -> str:
    return under_root(path, root).relative_to(root).as_posix()


def command_tokens(entry: dict) -> list[str]:
    if isinstance(entry.get("arguments"), list) and entry["arguments"]:
        tokens = [str(value) for value in entry["arguments"]]
    elif isinstance(entry.get("command"), str) and entry["command"].strip():
        command = entry["command"]
        if any(marker in command for marker in ("\n", "\r", "`", "$(")):
            raise ValueError("UNSAFE_COMMAND")
        tokens = shlex.split(command, posix=True)
    else:
        raise ValueError("COMMAND_MISSING")
    if any(token in SHELL_OPERATORS for token in tokens):
        raise ValueError("UNSAFE_COMMAND")
    return tokens


def expand_response_files(tokens: list[str], directory: Path, root: Path, inputs: dict[str, str], depth=0) -> list[str]:
    if depth > 4:
        raise ValueError("RESPONSE_FILE_DEPTH_EXCEEDED")
    expanded: list[str] = []
    for token in tokens:
        if not token.startswith("@") or len(token) == 1:
            expanded.append(token)
            continue
        path = Path(token[1:])
        path = path if path.is_absolute() else directory / path
        path = under_root(path, root)
        if path.stat().st_size > 1024 * 1024:
            raise ValueError("RESPONSE_FILE_SIZE_EXCEEDED")
        inputs[relative(path, root)] = file_digest(path)
        nested = shlex.split(path.read_text(encoding="utf-8", errors="strict"), posix=True)
        expanded.extend(expand_response_files(nested, directory, root, inputs, depth + 1))
    return expanded


def compiler_index(tokens: list[str]) -> int:
    index = 0
    while index < len(tokens) and Path(tokens[index]).name in WRAPPERS:
        index += 1
    if index >= len(tokens) or Path(tokens[index]).name not in COMPILERS:
        raise ValueError("UNSUPPORTED_COMPILER")
    return index


def probe(compiler: str, *arguments: str) -> str:
    try:
        result = subprocess.run([compiler, *arguments], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", timeout=30, check=False)
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def compiler_info(compiler: str) -> dict:
    if compiler not in COMPILER_INFO_CACHE:
        first = probe(compiler, "--version").splitlines()
        family = "clang" if "clang" in Path(compiler).name else "gcc"
        COMPILER_INFO_CACHE[compiler] = {
            "family": family,
            "executable": Path(compiler).name,
            "version": first[0][:240] if first else "unknown",
        }
    return COMPILER_INFO_CACHE[compiler]


def parse_include_search(stderr: str) -> list[str]:
    result: list[str] = []
    collecting = False
    for raw in stderr.splitlines():
        line = raw.strip()
        if line == "#include <...> search starts here:":
            collecting = True
        elif collecting and line == "End of search list.":
            break
        elif collecting and line:
            path = Path(line.removesuffix(" (framework directory)"))
            if path.is_absolute() and path.is_dir():
                result.append(str(path.resolve()))
    return list(dict.fromkeys(result))


def implicit_includes(compiler: str, language: str, directory: Path) -> list[str]:
    lang = "c++" if language == "c++" else "c"
    key = (compiler, lang)
    if key not in IMPLICIT_INCLUDE_CACHE:
        try:
            result = subprocess.run([compiler, "-E", "-x", lang, "-", "-v"], cwd=directory,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", timeout=30, check=False)
            IMPLICIT_INCLUDE_CACHE[key] = parse_include_search(result.stderr)
        except (OSError, subprocess.TimeoutExpired):
            IMPLICIT_INCLUDE_CACHE[key] = []
    return [item for path in IMPLICIT_INCLUDE_CACHE[key] for item in ("-isystem", path)]


def language_standard(arguments: list[str], language: str) -> dict[str, str | None]:
    options = [item for item in arguments if item.startswith("-std=")]
    raw = options[-1].split("=", 1)[1].lower() if options else None
    if raw is None:
        return {"standard": "compiler-default", "dialect": "compiler-default",
                "standard_source": "compiler-default", "standard_option": None}
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
    base = aliases.get(raw)
    if base is None or (language == "c" and base.startswith("c++")) or (language == "c++" and not base.startswith("c++")):
        return {"standard": "unsupported", "dialect": "gnu" if raw.startswith("gnu") else "iso",
                "standard_source": "explicit", "standard_option": f"-std={raw}"}
    return {"standard": base, "dialect": "gnu" if raw.startswith("gnu") else "iso",
            "standard_source": "explicit", "standard_option": f"-std={raw}"}


def optimization(arguments: list[str]) -> str:
    valid = {"-O0", "-O1", "-O2", "-O3", "-Os", "-Oz", "-Ofast"}
    values = [item[1:] for item in arguments if item in valid]
    return values[-1] if values else "unknown"


def normalized_entry(entry: dict, root: Path, output: Path, clang: str, clangxx: str):
    directory = Path(str(entry.get("directory") or root))
    directory = under_root(directory if directory.is_absolute() else root / directory, root)
    source = Path(str(entry.get("file") or ""))
    if not str(source):
        raise ValueError("SOURCE_FILE_MISSING")
    source = under_root(source if source.is_absolute() else directory / source, root)
    language = SOURCE_SUFFIXES.get(source.suffix.lower())
    if language is None:
        raise ValueError("UNSUPPORTED_LANGUAGE")
    inputs: dict[str, str] = {relative(source, root): file_digest(source)}
    tokens = expand_response_files(command_tokens(entry), directory, root, inputs)
    index = compiler_index(tokens)
    original_compiler = tokens[index]
    arguments = tokens[index + 1:]
    normalized: list[str] = []
    skip = False
    for token in arguments:
        if skip:
            skip = False
            continue
        if token in PAIR_FLAGS:
            skip = True
            continue
        if token in DROP_FLAGS or token.startswith("-Wp,-M"):
            continue
        candidate = Path(token)
        if not token.startswith("-"):
            candidate = candidate if candidate.is_absolute() else directory / candidate
            if candidate.resolve(strict=False) == source:
                continue
        normalized.append(token.replace(str(root), "<SOURCE_ROOT>"))
    stable = {"source": relative(source, root), "language": language, "arguments": normalized,
              "directory": relative(directory, root) or ".", "response_inputs": inputs}
    command = [clangxx if language == "c++" else clang]
    command.extend(item.replace("<SOURCE_ROOT>", str(root)) for item in normalized)
    command.extend(implicit_includes(original_compiler, language, directory))
    command.extend(["-emit-llvm", "-c", "-g", "-O0", "-Xclang", "-disable-O0-optnone",
                    str(source), "-o", str(output)])
    return command, directory, source, language, stable, inputs, compiler_info(original_compiler)


def diagnostic(code: str, detail: str, detail_en: str | None = None) -> dict:
    return {"code": code, "detail": detail, "detail_en": detail_en or detail,
            "suggestion": "检查编译上下文后重试", "suggestion_en": "Check the compile context and retry"}


def sanitize(value: str, root: Path, limit=1600) -> str:
    text = (value or "").replace(str(root), "<SOURCE_ROOT>").replace("\r", " ")
    return "\n".join(line for line in text.splitlines()[-12:] if line.strip())[-limit:]


def parse_ir_metadata(llvm_dis: str, output: Path, timeout: int) -> tuple[str, str]:
    result = subprocess.run([llvm_dis, "-o", "-", str(output)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                            timeout=timeout, check=False)
    if result.returncode != 0:
        raise ValueError("LLVM_VERIFY_FAILED: " + result.stderr[-800:])
    triple = re.search(r'^target triple = "([^"]+)"', result.stdout, re.MULTILINE)
    layout = re.search(r'^target datalayout = "([^"]+)"', result.stdout, re.MULTILINE)
    if not triple or not layout:
        raise ValueError("LLVM_TARGET_METADATA_MISSING")
    return triple.group(1), layout.group(1)


def abi_for(triple: str, data_layout: str) -> dict:
    pointer = re.search(r"(?:^|-)p(?::\d+)?:([0-9]+)", data_layout)
    return {"architecture": triple.split("-", 1)[0], "pointer_width": int(pointer.group(1)) if pointer else None,
            "endianness": "little" if data_layout.startswith("e") else "big"}


def stable_record(base: dict, status: str, bitcode: dict | None, error: dict | None) -> dict:
    record = {**base, "status": status, "diagnostic": error, "bitcode": bitcode, "sidecars": []}
    record["semantic_digest"] = digest(record, "semantic_digest", "artifact_key", "diagnostic")
    record["artifact_key"] = digest({"context_id": record["context_id"], "profile": record["profile"],
                                     "producer": record["producer"],
                                     "bitcode_sha256": bitcode["sha256"] if bitcode else None})
    return record


def append_unique_record(records: list[dict], record_ids: set[str], record: dict) -> bool:
    """Append one protocol record; aliases converging on the same final identity are not new work."""
    if record["record_id"] in record_ids:
        return False
    record_ids.add(record["record_id"])
    records.append(record)
    return True


def record_base(source_path: str, source_sha: str, language: str, stable: dict, inputs: dict,
                compiler: dict, producer: dict, target: dict) -> dict:
    physical_tu_id = digest({"source": source_path, "language": language, "sha256": source_sha})
    context_id = digest({"physical_tu_id": physical_tu_id, "compile": stable, "target": target,
                         "profile": PROFILE})
    record_id = digest({"context_id": context_id, "profile": PROFILE})
    gaps = ["header dependency digests are unavailable"]
    standard = language_standard(stable["arguments"], language)
    return {"record_id": record_id, "physical_tu_id": physical_tu_id, "context_id": context_id,
            "artifact_key": "0" * 64, "profile": PROFILE, "production_compiler": compiler,
            "producer": producer, "target": target, "language": language,
            **standard,
            "optimization": optimization(stable["arguments"]), "debug": "full",
            "module_kind": "translation-unit", "source": {"path": source_path, "sha256": source_sha},
            "compile_record_digest": digest(stable), "input_digests": dict(sorted(inputs.items())),
            "provenance": {"completeness": "partial", "gaps": gaps},
            "capabilities": CAPABILITIES}


def add_tar_bytes(tar: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = 0o600
    tar.addfile(info, io.BytesIO(content))


def write_bundle(bundle: Path, manifest_bytes: bytes, records: list[dict], scopes: list[dict], output_dir: Path) -> None:
    with bundle.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as tar:
                add_tar_bytes(tar, "manifest.json", manifest_bytes)
                for record in sorted(records, key=lambda item: item["record_id"]):
                    content = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    add_tar_bytes(tar, f"records/{record['record_id']}.json", (content + "\n").encode())
                    if record["status"] == "produced":
                        add_tar_bytes(tar, record["bitcode"]["path"],
                                      (output_dir / record["bitcode"]["path"]).read_bytes())
                for scope in sorted(scopes, key=lambda item: item["scope_id"]):
                    content = json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    add_tar_bytes(tar, f"scopes/{scope['scope_id']}.json", (content + "\n").encode())


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    root = Path(args.source_root).resolve(strict=True)
    compile_db = Path(args.compile_db)
    raw_compile_sha = file_digest(compile_db)
    database = json.loads(compile_db.read_text(encoding="utf-8"))
    if not isinstance(database, list):
        raise ValueError("COMPILE_DATABASE_NOT_ARRAY")
    output_dir = Path(args.output_dir).resolve(strict=False)
    (output_dir / "bitcode").mkdir(parents=True, exist_ok=True)
    host_triple = probe(args.clang, "-print-target-triple").splitlines()[0]
    producer = {"family": "clang", "version": args.toolchain_version,
                "llvm_version": args.toolchain_version, "host_triple": host_triple}
    records: list[dict] = []
    normalized_contexts: list[dict] = []
    source_identities: list[dict] = []
    seen: set[str] = set()
    record_ids: set[str] = set()
    total_bytes = 0

    candidates = [(index, item) for index, item in enumerate(database) if isinstance(item, dict)
                  and SOURCE_SUFFIXES.get(Path(str(item.get("file") or "")).suffix.lower())]
    for ordinal, (index, item) in enumerate(candidates, start=1):
        raw_file = str(item.get("file") or "")
        language = SOURCE_SUFFIXES.get(Path(raw_file).suffix.lower(), "c")
        fallback_path = Path(raw_file).name or f"tu-{index}.c"
        fallback_sha = hashlib.sha256(fallback_path.encode()).hexdigest()
        fallback_stable = {"source": fallback_path, "language": language, "arguments": [],
                           "directory": ".", "response_inputs": {fallback_path: fallback_sha}}
        fallback_target = {"triple": host_triple, "data_layout": "unknown", "abi": {}}
        base = record_base(fallback_path, fallback_sha, language, fallback_stable,
                           {fallback_path: fallback_sha}, {"family": "unknown", "executable": "unknown",
                           "version": "unknown"}, producer, fallback_target)
        output = output_dir / "bitcode" / f"pending-{index}.bc"
        try:
            if ordinal > args.max_tu:
                raise ValueError("TRANSLATION_UNIT_LIMIT_EXCEEDED")
            if time.monotonic() - started > args.total_timeout:
                raise TimeoutError("TOTAL_TIMEOUT")
            command, directory, source, language, stable, inputs, compiler = normalized_entry(
                item, root, output, args.clang, args.clangxx)
            source_path = relative(source, root)
            source_sha = file_digest(source)
            normalized_contexts.append(stable)
            source_identities.append({"path": source_path, "sha256": source_sha})
            provisional_target = {"triple": host_triple, "data_layout": "unknown", "abi": {}}
            base = record_base(source_path, source_sha, language, stable, inputs, compiler, producer, provisional_target)
            if base["standard"] == "unsupported":
                raise ValueError(f"UNSUPPORTED_LANGUAGE_STANDARD:{base['standard_option']}")
            if base["context_id"] in seen:
                # compile databases may repeat the same effective command for aliases or regenerated targets.
                # A context is the protocol denominator; duplicate rows are not missing analysis records.
                continue
            seen.add(base["context_id"])
            output = output_dir / "bitcode" / f"{base['record_id']}.bc"
            command[-1] = str(output)
            result = subprocess.run(command, cwd=directory, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                    timeout=args.tu_timeout, env=os.environ.copy(), check=False)
            if result.returncode != 0 or not output.is_file() or output.stat().st_size < 4:
                raise ValueError("TRANSLATION_UNIT_FAILED: " + sanitize(result.stderr, root))
            triple, layout = parse_ir_metadata(args.llvm_dis, output, args.tu_timeout)
            target = {"triple": triple, "data_layout": layout, "abi": abi_for(triple, layout)}
            base = record_base(source_path, source_sha, language, stable, inputs, compiler, producer, target)
            final_output = output_dir / "bitcode" / f"{base['record_id']}.bc"
            if output != final_output:
                output.replace(final_output)
                output = final_output
            content_sha = file_digest(output)
            size = output.stat().st_size
            record = stable_record(base, "produced",
                                   {"path": f"bitcode/{base['record_id']}.bc", "bytes": size,
                                    "sha256": content_sha}, None)
            is_new_record = record["record_id"] not in record_ids
            if size > args.max_tu_bytes or is_new_record and total_bytes + size > args.max_total_bytes:
                raise ValueError("OUTPUT_SIZE_LIMIT_EXCEEDED")
            if append_unique_record(records, record_ids, record):
                total_bytes += size
        except subprocess.TimeoutExpired:
            output.unlink(missing_ok=True)
            append_unique_record(records, record_ids, stable_record(
                base, "failed", None, diagnostic("TRANSLATION_UNIT_TIMEOUT", "翻译单元生成超时",
                                                  "Translation unit generation timed out")))
        except TimeoutError:
            output.unlink(missing_ok=True)
            append_unique_record(records, record_ids, stable_record(
                base, "failed", None,
                diagnostic("TOTAL_TIMEOUT", "BC 总生成时间超限", "BC generation timed out")))
        except Exception as exc:
            output.unlink(missing_ok=True)
            detail = sanitize(str(exc), root)
            code = detail.split(":", 1)[0] if detail else "TRANSLATION_UNIT_FAILED"
            append_unique_record(records, record_ids,
                                 stable_record(base, "failed", None, diagnostic(code, detail, detail)))

    records.sort(key=lambda item: item["record_id"])
    source_identity = digest(source_identities)
    normalized_digest = digest(normalized_contexts)
    scopes = []
    grouped: dict[str, list[str]] = {}
    for record in records:
        grouped.setdefault(record["target"]["triple"], []).append(record["record_id"])
    for triple, record_ids in sorted(grouped.items()):
        scope = {"scope_id": "0" * 64, "target_id": digest({"target_triple": triple}),
                 "record_ids": sorted(record_ids), "evidence": "compile-database-planned-set",
                 "closed": False, "external_boundaries": ["unknown-external-boundary"],
                 "target_triple": triple}
        scope["semantic_digest"] = digest(scope, "semantic_digest", "scope_id")
        scope["scope_id"] = digest({"target_id": scope["target_id"], "record_ids": scope["record_ids"],
                                    "closed": scope["closed"], "semantic_digest": scope["semantic_digest"]})
        scopes.append(scope)
    produced = sum(item["status"] == "produced" for item in records)
    missing = sum(item["status"] == "missing" for item in records)
    failed = sum(item["status"] == "failed" for item in records)
    status = "READY" if records and produced == len(records) else "PARTIAL" if produced else "FAILED"
    manifest = {"kind": KIND, "schema_version": SCHEMA_VERSION, "artifact_set_id": "0" * 64,
                "source_identity_digest": source_identity,
                "compile_context": {"raw_compile_commands_sha256": raw_compile_sha,
                                    "normalized_digest": normalized_digest},
                "producer": producer, "status": status,
                "counts": {"planned_contexts": len({item["context_id"] for item in records}),
                           "planned_records": len(records),
                           "produced": produced, "missing": missing, "failed": failed,
                           "total_bytes": total_bytes},
                "records": records, "scopes": scopes,
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")}
    manifest["semantic_digest"] = digest(
        manifest, "semantic_digest", "generated_at", "artifact_set_id", "raw_compile_commands_sha256")
    manifest["artifact_set_id"] = digest(
        manifest, "artifact_set_id", "semantic_digest", "generated_at", "diagnostic",
        "raw_compile_commands_sha256")
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    Path(args.manifest).write_bytes(manifest_bytes)
    write_bundle(Path(args.bundle), manifest_bytes, records, scopes, output_dir)
    print(json.dumps({"planned": len(records), "produced": produced, "missing": missing,
                      "failed": failed, "bytes": total_bytes}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
