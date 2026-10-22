from __future__ import annotations

import json
import re
from pathlib import Path


API_URL = "https://api.github.com/repos/llvm/llvm-project/contents/clang/lib/Headers?ref=main"
RAW_BASE = "https://raw.githubusercontent.com/llvm/llvm-project/main/clang/lib/Headers"
OPTIONS_URL = "https://github.com/llvm/llvm-project/blob/main/clang/include/clang/Options/Options.td"

OUT = Path(__file__).resolve().parents[1] / "rulesets" / "riscv-porting" / "generated" / "clang-x86-entries.json"
LOCAL_HEADERS = Path(__file__).resolve().parents[1] / "vendor" / "llvm-project" / "clang" / "lib" / "Headers"
LOCAL_OPTIONS = (
    Path(__file__).resolve().parents[1]
    / "vendor"
    / "llvm-project"
    / "clang"
    / "include"
    / "clang"
    / "Options"
    / "Options.td"
)

SEED_HEADERS = {"immintrin.h", "x86intrin.h", "ia32intrin.h", "cpuid.h", "mm_malloc.h"}
INCLUDE_RE = re.compile(r"^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]", re.MULTILINE)
INTRINSIC_RE = re.compile(r"\b(_[A-Za-z][A-Za-z0-9_]*|__rdtsc|__rdtscp|__cpuid|__cpuid_count|__get_cpuid|__get_cpuid_count)\s*\(")
BUILTIN_RE = re.compile(r"\b(__builtin_ia32_[A-Za-z0-9_]+)\b")
VECTOR_TYPE_RE = re.compile(r"\b(__m64|__m128|__m128i|__m128d|__m256|__m256i|__m256d|__m512|__m512i|__m512d)\b")
PLATFORM_MACRO_RE = re.compile(r"\b(__SSE[A-Za-z0-9_]*__|__AVX[A-Za-z0-9_]*__|__MMX__|__FMA__|__BMI[0-9]*__|__AES__|__PCLMUL__|__SHA__|__x86_64__|__i386__)\b")
OPTION_DEF_RE = re.compile(r"def\s+\w+\s*:\s*[^;]+;", re.DOTALL)
OPTION_SPELLING_RE = re.compile(r'<\["-"\],\s*"([^"]+)"')


def main() -> int:
    headers = list_headers()
    entries = {
        "source": {
            "name": "LLVM Clang builtin headers",
            "api": API_URL,
            "rawBase": RAW_BASE,
            "options": OPTIONS_URL,
        },
        "headers": [],
        "intrinsics": [],
        "builtins": [],
        "vectorTypes": [],
        "platformMacros": [],
        "compilerFlags": [],
    }

    for header in headers:
        text = (LOCAL_HEADERS / header).read_text(encoding="utf-8", errors="replace")
        entries["headers"].append(header)
        entries["intrinsics"].extend(INTRINSIC_RE.findall(text))
        entries["builtins"].extend(BUILTIN_RE.findall(text))
        entries["vectorTypes"].extend(VECTOR_TYPE_RE.findall(text))
        entries["platformMacros"].extend(PLATFORM_MACRO_RE.findall(text))

    entries["compilerFlags"].extend(collect_compiler_flags())

    for key in ["headers", "intrinsics", "builtins", "vectorTypes", "platformMacros", "compilerFlags"]:
        entries[key] = sorted(set(entries[key]))

    entries["intrinsics"] = [
        item
        for item in entries["intrinsics"]
        if item
        not in {
            "_Pragma",
            "__extension__",
            "__has_attribute",
            "__has_builtin",
            "__has_feature",
            "__attribute__",
            "__cpuid",
            "__cpuid_count",
            "__get_cpuid",
            "__get_cpuid_count",
            "__rdtsc",
            "__rdtscp",
        }
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"headers={len(entries['headers'])}")
    print(f"intrinsics={len(entries['intrinsics'])}")
    print(f"builtins={len(entries['builtins'])}")
    print(f"vectorTypes={len(entries['vectorTypes'])}")
    print(f"platformMacros={len(entries['platformMacros'])}")
    print(f"compilerFlags={len(entries['compilerFlags'])}")
    print(OUT)
    return 0


def collect_compiler_flags() -> list[str]:
    if not LOCAL_OPTIONS.exists():
        raise SystemExit(
            f"missing {LOCAL_OPTIONS}; run git sparse checkout for clang/include/clang/Options/Options.td first"
        )
    text = LOCAL_OPTIONS.read_text(encoding="utf-8", errors="replace")
    flags: set[str] = set()
    for block in OPTION_DEF_RE.findall(text):
        if "m_x86_Features_Group" not in block and "m_x86_AVX10_Features_Group" not in block:
            continue
        spelling = OPTION_SPELLING_RE.search(block)
        if spelling:
            flags.add("-" + spelling.group(1).rstrip("="))
    return sorted(flags)


def list_headers() -> list[str]:
    if not LOCAL_HEADERS.exists():
        raise SystemExit(f"missing {LOCAL_HEADERS}; run git sparse checkout for clang/lib/Headers first")
    seen: set[str] = set()
    pending = list(SEED_HEADERS)
    while pending:
        header = pending.pop()
        if header in seen:
            continue
        path = LOCAL_HEADERS / header
        if not path.exists():
            continue
        seen.add(header)
        text = path.read_text(encoding="utf-8", errors="replace")
        for included in INCLUDE_RE.findall(text):
            if (LOCAL_HEADERS / included).exists() and (included.endswith("intrin.h") or included in SEED_HEADERS):
                pending.append(included)
    return sorted(seen)


if __name__ == "__main__":
    raise SystemExit(main())
