from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from tests.unit.test_frontend_facts import context

from floating_point_precision_scanner.facts import map_ast
from floating_point_precision_scanner.protocol import SchemaRegistry


def test_loop_identity_declaration_and_nested_scope(tmp_path: Path) -> None:
    compile_context = context(tmp_path)
    path = str(compile_context.absolute_file)

    def loc(line: int, column: int = 1):
        return {"file": path, "line": line, "col": column}

    def update(line: int, declaration: str = "sum", column: int = 1):
        return {
            "kind": "CompoundAssignOperator",
            "opcode": "+=",
            "type": {"qualType": "double"},
            "loc": loc(line, column),
            "inner": [
                {
                    "kind": "ParenExpr",
                    "inner": [{"kind": "DeclRefExpr", "referencedDecl": {"id": declaration}}],
                }
            ],
        }

    def loop(line: int, children: list[dict[str, Any]]):
        return {"kind": "ForStmt", "loc": loc(line), "inner": children}

    def function(name: str, line: int, children: list[dict[str, Any]]):
        return {"kind": "FunctionDecl", "name": name, "loc": loc(line), "inner": children}

    ast = {
        "kind": "TranslationUnitDecl",
        "inner": [
            function(
                "compute",
                1,
                [
                    {
                        "kind": "VarDecl",
                        "id": "sum",
                        "name": "sum",
                        "loc": loc(2),
                        "type": {"qualType": "double"},
                    },
                    {
                        "kind": "VarDecl",
                        "id": "other",
                        "name": "other",
                        "loc": loc(3),
                        "type": {"qualType": "double"},
                    },
                    loop(4, [update(5), update(5, "other", 20), loop(6, [update(7)])]),
                    loop(8, [update(9), function("inner", 10, [update(11)])]),
                    loop(
                        12,
                        [
                            {
                                "kind": "CompoundAssignOperator",
                                "opcode": "+=",
                                "type": {"qualType": "double"},
                                "loc": loc(13),
                                "inner": [{"kind": "ArraySubscriptExpr"}],
                            }
                        ],
                    ),
                ],
            )
        ],
    }
    bundle = map_ast(compile_context, ast, tmp_path, "s", "t")
    assert SchemaRegistry().validate("facts", bundle) == []
    facts = [item for item in bundle["facts"] if item["fact_kind"] == "reduction"]
    assert len(facts) == 5
    by_point = {(f["location"]["line"], f["location"]["column"]): f["payload"] for f in facts}
    assert by_point[5, 1]["loop_id"] == by_point[5, 20]["loop_id"]
    assert by_point[5, 1]["accumulator_id"] != by_point[5, 20]["accumulator_id"]
    assert by_point[5, 1]["accumulator_id"] == by_point[9, 1]["accumulator_id"]
    assert len({by_point[line, 1]["loop_id"] for line in (5, 7, 9)}) == 3
    assert by_point[13, 1]["accumulator_id"] is None
    # Clang 进程地址变更不改变语义；同一源文件相同位置重复映射稳定。
    other = copy.deepcopy(ast)

    def replace_ids(node: Any):
        if isinstance(node, dict):
            if node.get("id") in {"sum", "other"}:
                node["id"] += "-another-process"
            for value in node.values():
                replace_ids(value)
        elif isinstance(node, list):
            for item in node:
                replace_ids(item)

    replace_ids(other)
    assert map_ast(compile_context, other, tmp_path, "s", "t")["facts"] == bundle["facts"]
    old = copy.deepcopy(bundle)
    old["producer"]["mapper_version"] = "1.1"
    old["schema_version"] = "1.4"
    assert SchemaRegistry().validate("facts", old)
