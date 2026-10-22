from kb_scanner.frontends.build.autoconf.syntax import Node, Source


def leaf(kind, text):
    return kind, text


def group(kind, *children):
    return kind, children


def word(text):
    return leaf("word", text)


def variable(text):
    return leaf("simple_expansion", "$" + text)


def command(name, *args):
    return group("command", ("name", group("command_name", (None, word(name)))),
                 *(("argument", arg if isinstance(arg, tuple) else word(arg)) for arg in args))


def assignment(name, expression):
    return group("variable_assignment", ("name", leaf("variable_name", name)), (None, leaf("=", "=")), ("value", expression))


def substitution(*commands):
    return group("command_substitution", (None, leaf("$(", "$(")),
                 *((None, item) for item in commands), (None, leaf(")", ")")))


def arm(pattern, *body):
    patterns = pattern if isinstance(pattern, list) else [pattern]
    return group("case_item", *(("value", item if isinstance(item, tuple) else leaf("extglob_pattern", item)) for item in patterns),
                 (None, leaf(")", ")")), *((None, item) for item in body), (None, leaf(";;", ";;")))


def case(selector, *arms):
    return group("case_statement", (None, leaf("case", "case")), ("value", selector),
                 (None, leaf("in", "in")), *((None, item) for item in arms), (None, leaf("esac", "esac")))


def condition(test, yes, no=(), elifs=()):
    return group("if_statement", (None, leaf("if", "if")), ("condition", test), (None, leaf("then", "then")),
                 *((None, item) for item in yes),
                 *((None, group("elif_clause", (None, check), *((None, item) for item in body))) for check, body in elifs),
                 (None, group("else_clause", *((None, item) for item in no))), (None, leaf("fi", "fi")))


def source(*statements, path="config.guess", issue=""):
    data = bytearray()

    def build(tree):
        kind, content = tree
        start = len(data)
        children = []
        if isinstance(content, str):
            data.extend(content.encode())
        else:
            for index, (field, child) in enumerate(content):
                if index:
                    data.extend(b"\n" if kind == "program" else b" ")
                children.append((field, build(child)))
        return Node(kind, start, len(data), tuple(children))

    root = build(group("program", *((None, item) for item in statements)))
    return Source(path, bytes(data), root, (0, *(i + 1 for i, byte in enumerate(data) if byte == 10)), issue)
