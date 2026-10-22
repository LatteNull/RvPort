"""一次构建局部使用/控制索引；对值流采用保守的双向关联闭包。"""
from collections import defaultdict
import re


TRANSPARENT = frozenset({"function_definition", "compound_statement", "enum_specifier", "enumerator_list"})
SUPPORTED = frozenset({"declaration", "init_declarator", "array_declarator", "enumerator",
    "identifier", "primitive_type", "sized_type_specifier", "type_qualifier", "number_literal",
    "char_literal", "character", "escape_sequence", "assignment_expression", "binary_expression",
    "if_statement", "condition_clause", "parenthesized_expression", "expression_statement",
    "subscript_expression", "subscript_argument_list", "comment"})
INTEGERS = frozenset({"bool", "_Bool", "char", "int", "short", "long", "unsigned", "signed",
    "unsigned char", "signed char", "unsigned int", "signed int", "long long", "unsigned long",
    "unsigned long long", "unsigned short", "short int", "long int", "long long int"})


class ScopeIndex:
    def __init__(self, scope):
        self.scope = scope
        self.rows = {row["key"]: row for row in scope["records"]}
        self.edges = defaultdict(set)
        self.reasons = defaultdict(set)
        self.positions = defaultdict(list)
        self.uses = defaultdict(set)
        owner_of = {}
        for row in scope["records"]:
            key, kind = row["key"], row["kind"]
            owner = owner_of.get(row["parent"])
            if kind == "function_definition":
                owner = None
            if kind in TRANSPARENT:
                owner_of[key] = owner
                continue
            self.positions[row["span"][:2]].append(key)
            owner_of[key] = key
            self.edges[key]  # 无边节点也计入索引。
            if owner is not None:
                self.link(key, owner)
            self.reasons[key].update(self._reasons(row))
            if kind == "identifier":
                binding = row.get("binding", {})
                declaration = binding.get("declaration")
                if binding.get("status") == "bound" and declaration in self.rows:
                    self.link(key, declaration)
                    self.uses[declaration].add(key)
                else:
                    self.reasons[key].add(binding.get("reason") or "usage-unresolved-binding")
                    # 不能把未知绑定当成没有使用；这些边只能阻止排除。
                    for possible in binding.get("possibleDeclarations", ()):
                        if possible in self.rows:
                            self.link(key, possible)
        # 相同作用域的不同根仍独立执行预算查询，但不重复排序或分配同一条边。
        canonical = {tuple(sorted((key, other))) for key, neighbors in self.edges.items()
                     for other in neighbors}
        edge_lookup = {edge: edge for edge in canonical}
        self.adjacency = {key: tuple((other, edge_lookup[tuple(sorted((key, other)))])
                                    for other in sorted(neighbors))
                          for key, neighbors in self.edges.items()}

    def link(self, left, right):
        if left != right:
            self.edges[left].add(right)
            self.edges[right].add(left)

    def _reasons(self, row):
        kind = row["kind"]
        if kind not in SUPPORTED:
            return {"usage-unknown-call" if kind == "call_expression" else
                    "usage-return-escape" if kind == "return_statement" else
                    "usage-address-escape" if kind == "pointer_expression" else
                    "usage-external-write" if kind == "field_expression" else "usage-unsupported-syntax"}
        if kind == "binary_expression" and row["operator"] not in {"==", "!=", "<", "<=", ">", ">="}:
            return {"usage-unsupported-operator"}
        if kind == "assignment_expression" and row["operator"] != "=":
            return {"usage-unsupported-operator"}
        if kind == "type_qualifier" and row["text"] != "const":
            return {"usage-unsupported-type"}
        if kind in {"primitive_type", "sized_type_specifier"} and row["text"] not in INTEGERS:
            return {"usage-unsupported-type"}
        if kind == "number_literal" and not re.fullmatch(r"(?:0[xX][0-9a-fA-F]+|[0-9]+)[uUlL]*", row["text"]):
            return {"usage-noninteger-value"}
        if kind == "declaration":
            type_row = self.rows.get(row["fields"].get("type"), {})
            if type_row.get("kind") not in {"primitive_type", "sized_type_specifier"}:
                return {"usage-unsupported-type"}
        if kind == "subscript_expression" and not self._local_array(row):
            return {"usage-array-binding-unknown"}
        return set()

    def _local_array(self, row):
        base = self.rows.get(row["fields"].get("argument"), {})
        declaration = self.rows.get(base.get("binding", {}).get("declarationOwner"), {})
        declarator = self.rows.get(declaration.get("fields", {}).get("declarator"), {})
        size = self.rows.get(declarator.get("fields", {}).get("size"), {})
        return (declarator.get("kind") == "array_declarator" and size.get("kind") == "number_literal"
                and bool(re.fullmatch(r"[1-9][0-9]*", size.get("text", ""))))

    def roots_at(self, span):
        """只使用精确命中开始位置；不凭同名去别处借用绑定。"""
        return tuple(key for key in self.positions.get(tuple(span[:2]), ())
                     if self.rows[key]["kind"] == "identifier")
