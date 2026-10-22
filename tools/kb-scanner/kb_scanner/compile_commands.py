from __future__ import annotations

import json
import shlex
from pathlib import Path

from .models import CompileCommandContext


def load_compile_commands(path: Path | None) -> tuple[dict[str, CompileCommandContext], list[str]]:
    if not path:
        return {}, []
    diagnostics: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {}, [f"compile_commands.json 加载失败: {exc}"]

    if not isinstance(payload, list):
        return {}, ["compile_commands.json 格式错误：顶层必须是数组"]

    contexts: dict[str, CompileCommandContext] = {}
    for entry_index, entry in enumerate(payload):
        if not isinstance(entry, dict) or "file" not in entry:
            diagnostics.append("跳过无 file 字段的 compile command")
            continue
        directory = Path(entry.get("directory") or path.parent)
        source = Path(entry["file"])
        if not source.is_absolute():
            source = (directory / source).resolve()

        command = entry.get("command")
        arguments = entry.get("arguments")
        tokens: list[str]
        if isinstance(arguments, list):
            tokens = [str(item) for item in arguments]
            raw_command = " ".join(tokens)
        elif isinstance(command, str):
            try:
                tokens = shlex.split(command, posix=True)
            except ValueError as exc:
                diagnostics.append(f"跳过无法解析命令行的 compile command: {exc}")
                continue
            raw_command = command
        else:
            tokens = []
            raw_command = None

        ctx = CompileCommandContext(
            path=source,
            raw_command=raw_command,
            tokens=tokens,
            entry_index=entry_index,
            compiler=Path(tokens[0]).name if tokens else None,
            directory=directory,
        )
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == "-I" and index + 1 < len(tokens):
                ctx.include_dirs.append(tokens[index + 1])
                index += 2
                continue
            if token.startswith("-I") and len(token) > 2:
                ctx.include_dirs.append(token[2:])
            elif token == "-D" and index + 1 < len(tokens):
                _add_define(ctx, tokens[index + 1])
                index += 2
                continue
            elif token.startswith("-D") and len(token) > 2:
                _add_define(ctx, token[2:])
            elif token.startswith("-std="):
                ctx.language_standard = token.removeprefix("-std=")
            index += 1

        contexts[str(source)] = ctx
    return contexts, diagnostics


def _add_define(ctx: CompileCommandContext, raw: str) -> None:
    if "=" in raw:
        key, value = raw.split("=", 1)
        ctx.defines[key] = value
    else:
        ctx.defines[raw] = None

