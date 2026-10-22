"""Small RPM expression grammar and three-valued control state (no eval)."""
from __future__ import annotations
import re


def conjunction(left: bool | None, right: bool | None) -> bool | None:
    if left is False or right is False:
        return False
    return True if left is True and right is True else None


def negate(value: bool | None) -> bool | None:
    return None if value is None else not value


def status(value: bool | None) -> str:
    return "unknown" if value is None else "selected" if value else "inactive"


def evaluate(expression: str | None) -> bool | None:
    if expression is None or len(expression) > 65536:
        return None
    tokens = re.findall(r'"[^"\\]*"|\d+|==|!=|&&|\|\||[!()]|\S', expression)
    if len(tokens) > 512:
        return None
    cursor = 0

    def atom():
        nonlocal cursor
        if cursor >= len(tokens):
            raise ValueError("missing operand")
        token = tokens[cursor]
        cursor += 1
        if token == "!":
            return not truth(atom())
        if token == "(":
            result = expr(0)
            if cursor >= len(tokens) or tokens[cursor] != ")":
                raise ValueError("missing close")
            cursor += 1
            return result
        if token.isdecimal():
            return int(token)
        if token.startswith('"'):
            return token[1:-1]
        raise ValueError("unsupported term")

    def truth(value):
        if isinstance(value, str):
            raise ValueError("bare string condition")
        return bool(value)

    def expr(level):
        nonlocal cursor
        if level == 3:
            return atom()
        operators = ({"||"}, {"&&"}, {"==", "!="})[level]
        left = expr(level + 1)
        while cursor < len(tokens) and tokens[cursor] in operators:
            operator = tokens[cursor]
            cursor += 1
            right = expr(level + 1)
            if operator in {"==", "!="}:
                if isinstance(left, str) != isinstance(right, str):
                    raise ValueError("mixed operands")
                left = (left == right) if operator == "==" else (left != right)
            elif operator == "&&":
                left = truth(left) & truth(right)
            else:
                left = truth(left) | truth(right)
        return left

    try:
        result = expr(0)
        return truth(result) if cursor == len(tokens) else None
    except (ValueError, RecursionError):
        return None
