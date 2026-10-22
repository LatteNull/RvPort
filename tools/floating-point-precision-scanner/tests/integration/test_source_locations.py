from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from tests.helpers import make_request
from tests.integration.test_clang21 import CLANG

from floating_point_precision_scanner.application import Scanner
from floating_point_precision_scanner.compilation import load_compilation_plan
from floating_point_precision_scanner.facts import map_ast
from floating_point_precision_scanner.frontend import ClangFrontend
from floating_point_precision_scanner.protocol import SchemaRegistry, parse_request

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not CLANG.is_file(), reason="locked Clang unavailable")]


@pytest.mark.parametrize("standard", ["c89", "c99", "gnu17"])
def test_actual_clang_elided_locations_and_macro_headers(tmp_path: Path, standard: str) -> None:
    source = tmp_path / "main.c"
    (tmp_path / "own.h").write_text(
        "#define SAME(a,b) ((a)==(b))\n"
        "static int check(double a) { return a == 0.25; }\n", encoding="utf-8")
    data = ('#include "own.h"\r\n'
            '// 中文\r\n'
            'int main(void) {\r\n'
            '\tdouble x=0.1;\r\n'
            '\treturn x == 0.2 || SAME(x, 0.3) || check(x);\r\n'
            '}\r\n').encode()
    source.write_bytes(data)
    args = ["clang", f"-std={standard}", "-c", "main.c"]
    request = make_request(tmp_path, [{"file": "main.c", "directory": str(tmp_path),
                                       "arguments": args}])
    ast = json.loads(subprocess.run(
        [str(CLANG), f"-std={standard}", "-Xclang", "-ast-dump=json", "-fsyntax-only", str(source)],
        check=True, capture_output=True, text=True).stdout)
    parsed, errors = parse_request(request, SchemaRegistry())
    assert not errors and parsed is not None
    context = load_compilation_plan(parsed).contexts[0]
    bundle = map_ast(context, ast, tmp_path, request["source_profile"], request["target_profile"])
    comparisons = [fact for fact in bundle["facts"] if fact["fact_kind"] == "comparison"]
    assert comparisons
    points = [fact["location"].get("expansion", fact["location"]) for fact in comparisons]
    assert any(p["path"] == "own.h" and p["line"] == 2 for p in points)
    assert any(p["path"] == "main.c" and p["line"] == 5 and p["column"] == 9 for p in points)
    for fact in comparisons:
        assert fact["source_range"]
    request["rules"] = {"enabled": ["fragile-fp-comparison"]}
    result = Scanner(ClangFrontend(CLANG)).scan(request)
    assert result["findings"]
    assert SchemaRegistry().validate("result", result) == []
    assert all(f["fact"]["primaryLocation"] is not None for f in result["findings"])
    locations = [o["location"] for f in result["findings"] for o in f["occurrences"]]
    assert any(p["file"] == "main.c" and p["line"] == 5 for p in locations)
    assert any(p["file"] == "own.h" and p["line"] == 2 for p in locations)
    steps = [step for finding in result["findings"] for step in finding["evidenceChain"]["steps"]]
    observations = [step for step in steps if step["kind"] == "sourceObservation"]
    assert observations and all("浮点数值比较" in step["title"] for step in observations)
    assert any("main.c:5" in step["reason"] for step in observations)
    assert all("not proof of migration failure" in step["reasonEn"] for step in observations)


def test_external_header_and_line_directive_use_physical_project_location(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    header = tmp_path / "external.h"
    header.write_text("static int ext(double a) { return a == 0.5; }\n", encoding="utf-8")
    source = root / "main.c"
    source.write_text('#include "../external.h"\n#line 900 "virtual.c"\n'
                      'int main(void) { double x=0.1; return x == 0.2 || ext(x); }\n',
                      encoding="utf-8")
    request = make_request(root, [{"file": "main.c", "directory": str(root),
                                  "arguments": ["clang", "-std=c99", "main.c"]}])
    request["rules"] = {"enabled": ["fragile-fp-comparison"]}
    result = Scanner(ClangFrontend(CLANG)).scan(request)
    assert result["findings"]
    locations = [o["location"] for f in result["findings"] for o in f["occurrences"]]
    assert all(p is not None and p["file"] == "main.c" and p["line"] == 3 for p in locations)


def test_real_cpp_pointer_checks_are_not_floating_comparisons(tmp_path: Path) -> None:
    source = tmp_path / "main.cpp"
    source.write_text(
        'typedef double Real;\n'
        'typedef float* FloatPtr;\n'
        'bool check(FloatPtr p, FloatPtr q, Real value, double& ref, float array[4]) {\n'
        '  bool nulls = p == nullptr || nullptr != q || p == 0 || q != __null;\n'
        '  bool pointers = p == q || p < q || array == p;\n'
        '  bool scalar = *p == 0.2f || array[2] == 1.0f || value == 0.25 || ref == 0.5;\n'
        '  return nulls || pointers || scalar;\n'
        '}\n', encoding="utf-8")
    request = make_request(tmp_path, [{"file": "main.cpp", "directory": str(tmp_path),
                                       "arguments": ["clang++", "-std=c++17", "-c", "main.cpp"]}])
    request["rules"] = {"enabled": ["fragile-fp-comparison"]}
    result = Scanner(ClangFrontend(CLANG)).scan(request)
    assert SchemaRegistry().validate("result", result) == []
    assert result["findings"]
    locations = [o["location"] for f in result["findings"] for o in f["occurrences"]]
    assert len(locations) == 4
    assert all(p["file"] == "main.cpp" and p["line"] == 6 for p in locations)
