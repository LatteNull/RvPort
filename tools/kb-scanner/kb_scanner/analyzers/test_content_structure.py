"""函数标量清单上的局部测试用途查询，不读取源码或执行代码。"""
from bisect import bisect_right
from collections import defaultdict


_CONTROL = frozenset({"if_statement", "for_statement", "while_statement", "do_statement",
                      "switch_statement", "conditional_expression", "try_statement",
                      "return_statement", "co_return_statement", "goto_statement", "break_statement"})
_NESTED = frozenset({"lambda_expression", "function_definition", "class_specifier", "struct_specifier"})
_FRAMEWORK = frozenset({"TEST", "TEST_F", "TEST_P", "TEST_CASE", "EXPECT_EQ", "ASSERT_EQ", "EXPECT_TRUE", "ASSERT_TRUE"})


def contains(span, point):
    return tuple(span[:2]) <= point < tuple(span[2:])


class FunctionIndex:
    def __init__(self, function):
        self.function = function
        self.rows = {row["key"]: row for row in function["records"]}
        self.positions, self.uses = defaultdict(list), defaultdict(list)
        self.calls = []
        for row in self.rows.values():
            self.positions[tuple(row["span"][:2])].append(row)
            binding = row.get("binding", {})
            if binding.get("status") == "bound" and binding.get("declaration") in self.rows:
                self.uses[binding["declaration"]].append(row)
            if row["kind"] == "call_expression":
                self.calls.append(row)
        self.visits = 0

    def ancestors(self, row, limit=128):
        seen, result = set(), []
        while row is not None and row["key"] not in seen and len(result) < limit:
            seen.add(row["key"])
            result.append(row)
            row = self.rows.get(row["parent"])
            self.visits += 1
        return result, row is None

    def name(self, call):
        callee = self.rows.get(call["fields"].get("function"), {})
        return callee.get("text", "") if callee.get("kind") == "identifier" else ""

    def direct(self, call):
        callee = self.rows.get(call["fields"].get("function"), {})
        parents, complete = self.ancestors(call)
        return (bool(self.name(call)) and callee.get("binding", {}).get("status") != "bound"
                and complete and not any(r["kind"] in _NESTED for r in parents[1:-1]))

    def point(self, point):
        candidates = self.positions.get(point, ())
        return next((r for r in candidates if r["kind"] == "identifier"),
                    candidates[0] if candidates else None)

    def context(self, point):
        if any(contains(span, point) for span in self.function["nestedSpans"]):
            return {"relation": "unknown", "reasonCodes": ("test-nested-callable",)}
        row = self.point(point)
        if row is None:
            return {"relation": "lexical", "reasonCodes": ("test-content-position-unbound",)}
        parents, complete = self.ancestors(row)
        reasons = set()
        if not complete:
            reasons.add("test-binding-budget")
        # Return statements do not make an expression ambiguous, but runtime
        # conditions and preceding control transfers must not prove execution.
        if any(p["kind"] in _CONTROL - {"return_statement", "co_return_statement"} or
               p["kind"].startswith("preproc_") for p in parents):
            reasons.add("test-control-selection-unknown")
        assertion = next((p for p in parents if p["kind"] == "call_expression" and self.name(p) == "assert"), None)
        if assertion is not None:
            return {"relation": "assert-argument", "assertionSpan": assertion["span"],
                    "reasonCodes": tuple(sorted(reasons))}
        init = next((p for p in parents if p["kind"] == "init_declarator"), None)
        if init is not None:
            result = self._binding(init, row)
            if result is not None:
                return {**result, "reasonCodes": tuple(sorted(reasons | set(result["reasonCodes"])))}
        return {"relation": "body", "reasonCodes": tuple(sorted(reasons))}

    def _binding(self, init, anchor):
        identifier = self.rows.get(init["fields"].get("declarator"), {})
        declaration = self.rows.get(init["parent"], {})
        block = self.rows.get(declaration.get("parent"), {})
        typ = self.rows.get(declaration.get("fields", {}).get("type"), {})
        if identifier.get("kind") != "identifier" or typ.get("kind") not in {"primitive_type", "sized_type_specifier"} or block.get("kind") != "compound_statement":
            return {"relation": "unknown", "reasonCodes": ("test-binding-not-local-scalar",)}
        uses = self.uses.get(identifier["key"], ())
        candidates = []
        for use in uses:
            parents, complete = self.ancestors(use)
            assertion = next((p for p in parents if p["kind"] == "call_expression" and self.name(p) == "assert"), None)
            if complete and assertion and assertion["key"][0] > init["key"][1]:
                candidates.append(assertion)
        if not candidates:
            return None
        assertion = min(candidates, key=lambda p: p["key"])
        statement = next((r for r in self.ancestors(assertion)[0] if r["parent"] == block["key"]), None)
        siblings = [self.rows[key] for key in block["children"] if key in self.rows
                    and declaration["key"][0] <= key[0] <= assertion["key"][0]]
        reasons = set()
        if statement is None or len(siblings) > 128:
            reasons.add("test-binding-budget-or-scope")
        # Only straight-line declarations/comments between the definition/use;
        # arbitrary calls, assignments or control flow may escape/change the value.
        if any(s["key"] != declaration["key"] and s["key"] != (statement or {}).get("key")
               and s["kind"] != "comment" for s in siblings):
            reasons.add("test-binding-intervening-statement")
        for use in uses:
            if use["key"] == identifier["key"] or use["key"][0] >= assertion["key"][1]:
                continue
            if use.get("binding", {}).get("role") in {"write", "read_write"}:
                reasons.add("test-binding-reassigned")
            parents, _ = self.ancestors(use)
            if any(p["kind"] in {"pointer_expression", "field_expression"} for p in parents):
                reasons.add("test-binding-escaped")
        return {"relation": "local-value-to-assert" if not reasons else "unknown",
                "assertionSpan": assertion["span"], "definitionSpan": declaration["span"],
                "reasonCodes": tuple(sorted(reasons))}


class ContentIndex:
    def __init__(self, data):
        self.data = data
        self.functions = sorted(data.get("functions", ()), key=lambda f: f["span"][:2])
        self.starts = [tuple(f["span"][:2]) for f in self.functions]
        self.by_name = defaultdict(list)
        for function in self.functions:
            self.by_name[function["name"]].append(function)
        self.cache = {}
        self.queries = 0

    def index(self, function):
        key = tuple(function["span"])
        if key not in self.cache:
            self.cache[key] = FunctionIndex(function)
        return self.cache[key]

    def resolve(self, point):
        self.queries += 1
        at = bisect_right(self.starts, point)-1
        if at < 0 or not contains(self.functions[at]["span"], point):
            return {"relation": "file", "entryStatus": "unknown", "reasonCodes": ("test-owner-not-found",)}
        function = self.functions[at]
        index = self.index(function)
        result = {**index.context(point), "function": function["name"],
                  "functionEvidenceId": function.get("evidenceId"), "entryStatus": "unknown"}
        reasons = set(result["reasonCodes"]) | set(self.data.get("reasonCodes", ())) | set(function["reasonCodes"])
        if not function["plain"]:
            reasons.add("test-function-binding-unknown")
        if function["name"] in _FRAMEWORK:
            reasons.add("test-framework-unsupported")
        mains = self.by_name.get("main", ())
        if len(mains) == 1 and mains[0]["plain"] and function["plain"] and self.data["status"] == "complete":
            main = mains[0]
            result["entryEvidenceId"] = main.get("evidenceId")
            if main is function:
                result["entryStatus"] = "complete"
            elif len(self.by_name[function["name"]]) == 1:
                caller = self.index(main)
                if function["name"] in self.data.get("declaredNames", ()):
                    reasons.add("test-function-declaration-binding-unknown")
                if self.data.get("hasIncludes"):
                    reasons.add("test-function-include-binding-unknown")
                if any(index.name(call) == function["name"] for call in index.calls):
                    reasons.add("test-recursive-call-unsupported")
                calls = [call for call in caller.calls if caller.name(call) == function["name"] and caller.direct(call)]
                if len(calls) == 1:
                    result["entryStatus"] = "complete"
                    result["callSpan"] = calls[0]["span"]
                    parents, _ = caller.ancestors(calls[0])
                    if any(p["kind"] in _CONTROL for p in parents):
                        reasons.add("test-control-selection-unknown")
                else:
                    reasons.add("test-entry-call-not-unique")
            else:
                reasons.add("test-function-name-not-unique")
        else:
            reasons.add("test-entry-not-proven")
        if result["relation"] == "unknown" or reasons:
            result["entryStatus"] = "unknown"
        result["reasonCodes"] = tuple(sorted(reasons))
        return result
