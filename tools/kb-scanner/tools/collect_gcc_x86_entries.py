from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GCC_I386 = ROOT / "vendor" / "gcc" / "gcc" / "config" / "i386"
OUT = ROOT / "rulesets" / "riscv-porting" / "generated" / "gcc-x86-entries.json"

HEADER_NAME_RE = re.compile(r".*intrin\.h$|^immintrin\.h$|^x86intrin\.h$|^cpuid\.h$|^mm_malloc\.h$|^ia32intrin\.h$")
INTRINSIC_RE = re.compile(r"\b(_[A-Za-z][A-Za-z0-9_]*|__rdtsc|__rdtscp|__cpuid|__cpuid_count|__get_cpuid|__get_cpuid_count)\s*\(")
BUILTIN_RE = re.compile(r"\b(__builtin_ia32_[A-Za-z0-9_]+)\b")
VECTOR_TYPE_RE = re.compile(r"\b(__m64|__m128|__m128i|__m128d|__m256|__m256i|__m256d|__m512|__m512i|__m512d)\b")
PLATFORM_MACRO_RE = re.compile(r"\b(__SSE[A-Za-z0-9_]*__|__AVX[A-Za-z0-9_]*__|__MMX__|__FMA__|__BMI[0-9]*__|__AES__|__PCLMUL__|__SHA__|__x86_64__|__i386__)\b")
OPTION_RE = re.compile(r"^(m[A-Za-z0-9][A-Za-z0-9_.+-]*=?)(?:\s|$)")


def main() -> int:
    if not GCC_I386.exists():
        raise SystemExit(f"missing {GCC_I386}; run git sparse checkout for gcc/config/i386 first")

    entries = {
        "source": {
            "name": "GCC i386 backend and intrinsic headers",
            "path": str(GCC_I386),
        },
        "headers": [],
        "intrinsics": [],
        "builtins": [],
        "vectorTypes": [],
        "platformMacros": [],
        "compilerFlags": [],
    }

    header_paths = sorted(path for path in GCC_I386.iterdir() if path.is_file() and HEADER_NAME_RE.match(path.name))
    for path in header_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        entries["headers"].append(path.name)
        entries["intrinsics"].extend(INTRINSIC_RE.findall(text))
        entries["builtins"].extend(BUILTIN_RE.findall(text))
        entries["vectorTypes"].extend(VECTOR_TYPE_RE.findall(text))
        entries["platformMacros"].extend(PLATFORM_MACRO_RE.findall(text))

    opt_path = GCC_I386 / "i386.opt"
    if opt_path.exists():
        for raw_line in opt_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith(";"):
                continue
            match = OPTION_RE.match(line)
            if not match:
                continue
            option = match.group(1)
            if option.endswith("="):
                option = option[:-1]
            entries["compilerFlags"].append(f"-{option}")

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


if __name__ == "__main__":
    raise SystemExit(main())

