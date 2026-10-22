"""Lower CMake native nodes immediately; keep the Tree alive during traversal."""
from bisect import bisect_right
from dataclasses import dataclass

from tree_sitter import Language, Parser
import tree_sitter_cmake


@dataclass(frozen=True)
class Token:
    text: str
    line: int = 1
    column: int = 1
    end_line: int = 1
    end_column: int = 2
    quoted: bool = False


@dataclass(frozen=True)
class Command:
    name: str
    args: tuple[Token, ...]
    token: Token


class PartialSyntaxError(ValueError):
    def __init__(self, commands):
        super().__init__("cmake-partial-syntax")
        self.commands = tuple(commands)


def parse(source, *, max_nodes=100000, max_depth=64, max_bytes=4*1024*1024):
    if min(max_nodes, max_depth, max_bytes) < 1:
        raise ValueError("cmake-invalid-budget")
    data = source.encode("utf-8")
    if len(data) > max_bytes:
        raise ValueError("cmake-input-budget")
    lines = (0, *(i+1 for i, b in enumerate(data) if b == 10))
    parser = Parser(Language(tree_sitter_cmake.language()))
    tree = parser.parse(data)
    partial = tree.root_node.has_error
    commands = []
    count = 0

    def token(node, quoted=False):
        start, end = node.start_byte, node.end_byte
        a, b = bisect_right(lines, start), bisect_right(lines, end)
        text = data[start:end].decode("utf-8")
        return Token(text, a, len(data[lines[a-1]:start].decode("utf-8"))+1,
                     b, len(data[lines[b-1]:end].decode("utf-8"))+1, quoted)

    def arguments(node, depth=0):
        check(depth)
        if node.type == "argument":
            yield token(node, any(n.type in {"quoted_argument", "bracket_argument"} for n in node.children))
        elif node.type in {"(", ")"}:
            yield token(node)
        else:
            for child in node.children:
                yield from arguments(child, depth+1)

    def check(depth):
        nonlocal count
        count += 1
        if count > max_nodes or depth > max_depth:
            raise ValueError("cmake-syntax-budget")

    def walk(node, depth=0):
        check(depth)
        if node.type.endswith("_command"):
            if node.has_error:
                return
            children = node.named_children
            name = data[children[0].start_byte:children[0].end_byte].decode("utf-8").lower()
            args = tuple(t for child in children if child.type == "argument_list" for t in arguments(child, depth+1))
            commands.append(Command(name, args, token(node)))
        else:
            for child in node.named_children:
                walk(child, depth+1)
    walk(tree.root_node)
    if partial:
        raise PartialSyntaxError(commands)
    return tuple(commands)
