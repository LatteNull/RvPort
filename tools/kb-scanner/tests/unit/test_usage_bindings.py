"""合成标量语法树覆盖词法作用域、读写及不确定绑定。"""
import unittest

from kb_scanner.frontends.cpp.usage_bindings import bind, declaration_owner


def row(kind, start, parent=None, text="", fields=None, **extra):
    return {"key": (start, start+1, kind), "parent": parent, "kind": kind,
            "text": text, "fields": fields or {}, "children": (), "operator": "", **extra}


def fixture():
    function = row("function_definition", 0)
    block = row("compound_statement", 1, function["key"])
    declaration = row("declaration", 2, block["key"])
    name = row("identifier", 3, declaration["key"], "X86")
    declaration["fields"] = {"declarator": name["key"]}
    read = row("identifier", 4, block["key"], "X86")
    return [function, block, declaration, name, read]


class UsageBindingTests(unittest.TestCase):
    def test_local_declaration_read_and_unresolved_names(self):
        rows = fixture()
        rows.append(row("identifier", 5, rows[1]["key"], "absent"))
        result = bind(rows)
        self.assertEqual("declaration", result[3]["binding"]["role"])
        self.assertEqual(rows[3]["key"], result[4]["binding"]["declaration"])
        self.assertEqual(rows[2]["key"], result[4]["binding"]["declarationOwner"])
        self.assertEqual("unknown", result[-1]["binding"]["status"])
        self.assertNotIn("binding", rows[3])

    def test_shadowed_name_does_not_escape_inner_block(self):
        rows = fixture()
        inner = row("compound_statement", 5, rows[1]["key"])
        declaration = row("declaration", 6, inner["key"])
        name = row("identifier", 7, declaration["key"], "X86")
        declaration["fields"] = {"declarator": name["key"]}
        inner_read = row("identifier", 8, inner["key"], "X86")
        outer_read = row("identifier", 9, rows[1]["key"], "X86")
        result = bind(rows+[inner, declaration, name, inner_read, outer_read])
        self.assertEqual(name["key"], result[-2]["binding"]["declaration"])
        self.assertEqual(rows[3]["key"], result[-1]["binding"]["declaration"])
        self.assertEqual(rows[3]["key"], result[4]["binding"]["declaration"])

    def test_assignment_and_update_usage_roles(self):
        rows = fixture()
        for kind, operator, expected in (("assignment_expression", "=", "write"),
                                          ("assignment_expression", "+=", "read_write"),
                                          ("update_expression", "++", "read_write")):
            expression = row(kind, 5, rows[1]["key"], operator=operator)
            use = row("identifier", 6, expression["key"], "X86")
            expression["fields"] = {"left": use["key"]}
            self.assertEqual(expected, bind(rows+[expression, use])[-1]["binding"]["role"])

    def test_duplicate_declarations_and_depth_are_unknown(self):
        rows = fixture()
        declaration = row("declaration", 5, rows[1]["key"])
        name = row("identifier", 6, declaration["key"], "X86")
        declaration["fields"] = {"declarator": name["key"]}
        use = row("identifier", 7, rows[1]["key"], "X86")
        self.assertEqual("unknown", bind(rows+[declaration, name, use])[-1]["binding"]["status"])
        self.assertEqual("usage-binding-depth", bind(rows, max_depth=2)[-1]["binding"]["reason"])
        for kind in ("qualified_identifier", "field_expression"):
            parent = row(kind, 5, rows[1]["key"])
            use = row("identifier", 6, parent["key"], "X86")
            self.assertEqual("unknown", bind(rows+[parent, use])[-1]["binding"]["status"])

    def test_wrapped_declaration_and_initializer_are_distinct(self):
        rows = fixture()[:3]
        wrapper = row("init_declarator", 3, rows[2]["key"])
        name = row("identifier", 4, wrapper["key"], "X86")
        value = row("identifier", 5, wrapper["key"], "other")
        rows[2]["fields"] = {"declarator": wrapper["key"]}
        wrapper["fields"] = {"declarator": name["key"], "value": value["key"]}
        result = bind(rows+[wrapper, name, value])
        self.assertEqual("declaration", result[-2]["binding"]["role"])
        self.assertEqual("read", result[-1]["binding"]["role"])
        self.assertEqual("unknown", result[-1]["binding"]["status"])
        cyclic = {wrapper["key"]: {**wrapper, "parent": wrapper["key"], "fields": {"declarator": wrapper["key"]}}}
        self.assertIsNone(declaration_owner(wrapper, cyclic))

    def test_enum_members_are_local_but_scoped_enum_is_not_flattened(self):
        rows = fixture()[:2]
        enum = row("enum_specifier", 2, rows[1]["key"])
        body = row("enumerator_list", 3, enum["key"])
        member = row("enumerator", 4, body["key"])
        name = row("identifier", 5, member["key"], "X86")
        member["fields"] = {"name": name["key"]}
        use = row("identifier", 6, rows[1]["key"], "X86")
        tree = rows+[enum, body, member, name, use]
        self.assertEqual(name["key"], bind(tree)[-1]["binding"]["declaration"])
        enum["scopedEnum"] = True
        self.assertEqual("unknown", bind(tree)[-1]["binding"]["status"])

    def test_field_object_member_and_ambiguous_use_remain_distinct(self):
        rows = fixture()
        expression = row("field_expression", 5, rows[1]["key"])
        use = row("identifier", 6, expression["key"], "X86")
        for fields, status, possible in (
            ({"argument": use["key"]}, "bound", (rows[3]["key"],)),
            ({"field": use["key"]}, "unknown", ()),
            ({}, "unknown", (rows[3]["key"],)),
        ):
            expression["fields"] = fields
            binding = bind(rows+[expression, use])[-1]["binding"]
            self.assertEqual(status, binding["status"])
            self.assertEqual(possible, binding["possibleDeclarations"])
