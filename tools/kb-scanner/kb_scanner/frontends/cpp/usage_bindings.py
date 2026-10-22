"""对标量语法记录建立保守的块级绑定；不是 C++ 名称解析器。"""
from collections import defaultdict


SCOPES = frozenset({"function_definition", "compound_statement", "for_statement",
                    "if_statement", "switch_statement", "while_statement", "catch_clause"})
WRAPPERS = frozenset({"init_declarator", "array_declarator", "pointer_declarator",
                     "reference_declarator", "parenthesized_declarator"})


def bind(records, max_depth=32):
    """输入/输出均为标量；未唯一绑定或深度超限的 identifier 明确 unknown。"""
    rows = {row["key"]: row for row in records}
    declarations, scope_of, scope_parent, depths = {}, {}, {}, {}
    symbols = defaultdict(lambda: defaultdict(list))
    for row in records:
        key, parent = row["key"], row["parent"]
        owner = scope_of.get(parent)
        depths[key] = depths.get(parent, 0) + 1
        if row["kind"] in SCOPES:
            scope_parent[key] = owner
            owner = key
        scope_of[key] = owner
        if row["kind"] != "identifier" or depths[key] > max_depth:
            continue
        declaring = declaration_owner(row, rows)
        if declaring is not None:
            declarations[key] = declaring
            symbols[owner][row["text"]].append(key)
    result = []
    for row in records:
        if row["kind"] != "identifier":
            result.append(dict(row))
            continue
        key, owner = row["key"], scope_of[row["key"]]
        resolved = None
        possible = ()
        if depths[key] <= max_depth:
            cursor = owner
            while cursor is not None:
                visible = [item for item in symbols[cursor].get(row["text"], ()) if item[0] <= key[0]]
                if visible:
                    possible = tuple(visible)
                    resolved = visible[0] if len(visible) == 1 else None
                    break
                cursor = scope_parent.get(cursor)
        parent = rows.get(row["parent"], {})
        # Qualified name 的名字不应退化为同名局部变量；后续可做显式 enum 绑定。
        if parent.get("kind") == "qualified_identifier":
            resolved = None
        if parent.get("kind") == "field_expression" and parent.get("fields", {}).get("argument") != key:
            resolved = None
            if parent.get("fields", {}).get("field") == key:
                # 明确的成员名不是外层同名变量；缺字段信息时仍保留潜在使用。
                possible = ()
        record = dict(row)
        record["binding"] = {"status": "bound" if resolved is not None else "unknown",
            "declaration": resolved, "scope": owner,
            "possibleDeclarations": possible,
            "declarationOwner": declarations.get(resolved),
            "role": "declaration" if key in declarations else _role(row, rows),
            "reason": "usage-binding-depth" if depths[key] > max_depth else
                      "" if resolved is not None else "usage-unresolved-binding"}
        result.append(record)
    return tuple(result)


def declaration_owner(row, rows):
    """只沿 declarator 字段识别声明，不把初始化表达式误认为新声明。"""
    key = row["key"]
    parent = rows.get(row["parent"])
    seen = set()
    while parent is not None and parent["kind"] in WRAPPERS:
        if parent["key"] in seen or parent["fields"].get("declarator") != key:
            return None
        seen.add(parent["key"])
        key, parent = parent["key"], rows.get(parent["parent"])
    if parent is None:
        return None
    if parent["kind"] == "enumerator" and parent["fields"].get("name") == key:
        # scoped enum 不能把成员泄漏到外层词法环境。
        cursor = rows.get(parent["parent"])
        enum = rows.get(cursor["parent"]) if cursor is not None else None
        return parent["key"] if enum is not None and not enum.get("scopedEnum") else None
    if parent["kind"] in {"declaration", "parameter_declaration"}:
        if parent["fields"].get("declarator") == key:
            return parent["key"]
        # Tree-sitter 字段查询只返回第一个 declarator；其他项保守不绑定。
    return None


def _role(row, rows):
    parent = rows.get(row["parent"], {})
    if parent.get("kind") == "assignment_expression" and parent["fields"].get("left") == row["key"]:
        return "write" if parent.get("operator") == "=" else "read_write"
    if parent.get("kind") == "update_expression":
        return "read_write"
    return "read"
