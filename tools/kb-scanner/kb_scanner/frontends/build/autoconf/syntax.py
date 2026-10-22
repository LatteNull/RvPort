"""Copy native syntax into bounded, scanner-owned byte-offset records."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from tree_sitter import Language, Parser
import tree_sitter_bash


@dataclass(frozen=True, slots=True)
class Node:
    kind: str
    start: int
    end: int
    children: tuple[tuple[str | None, "Node"], ...] = ()

    def field(self, name: str) -> "Node | None":
        return next((child for key, child in self.children if key == name), None)

    def fields(self, name: str) -> tuple["Node", ...]:
        return tuple(child for key, child in self.children if key == name)


@dataclass(frozen=True, slots=True)
class Source:
    path: str
    data: bytes
    root: Node
    lines: tuple[int, ...]
    issue: str = ""

    def text(self, node: Node) -> str:
        return self.data[node.start:node.end].decode("utf-8", errors="replace")

    def position(self, node: Node) -> tuple[int, int, int]:
        line = bisect_right(self.lines, node.start)
        offset = self.lines[line - 1]
        stop = self.data.find(b"\n", node.start, node.end)
        end = node.end if stop < 0 else stop
        return line, node.start - offset + 1, end - offset + 1


def parse(source: str, path: str, *, max_nodes: int = 100000, max_depth: int = 64) -> Source:
    if min(max_nodes, max_depth) < 1:
        raise ValueError("Autoconf syntax budgets must be positive")
    data = source.encode("utf-8")
    lines = (0, *(i + 1 for i, byte in enumerate(data) if byte == 10))
    tree = Parser(Language(tree_sitter_bash.language())).parse(data)
    count = 0

    def lower(native, depth):
        nonlocal count
        count += 1
        if count > max_nodes or depth > max_depth:
            raise ValueError("autoconf-syntax-budget")
        if native.is_missing or native.type == "ERROR":
            raise ValueError("autoconf-partial-syntax")
        return Node(native.type, native.start_byte, native.end_byte,
                    tuple((native.field_name_for_child(i), lower(child, depth + 1))
                          for i, child in enumerate(native.children)))

    try:
        if tree.root_node.has_error:
            raise ValueError("autoconf-partial-syntax")
        root = lower(tree.root_node, 0)
        issue = ""
    except ValueError as exc:
        root, issue = Node("unsupported", 0, len(data)), str(exc)
    return Source(path, data, root, lines, issue)
