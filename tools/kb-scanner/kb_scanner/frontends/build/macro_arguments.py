"""有界 Make 编译参数读取，保持真实 token 来源，不执行项目命令。"""
from dataclasses import replace
from pathlib import PurePosixPath
import re

from .make_effects import MakeEffects
from .make_values import REF, tokens
from .vocabulary import BuildRecord, record_for_token


_SOURCE = re.compile(r"[\w./+-]+\.(?:c|cc|cpp|cxx|C)$")
_MACRO = re.compile(r"([A-Za-z_]\w*)(?:=(.*))?$")
_COMPILERS = {"cc", "c++", "gcc", "g++", "clang", "clang++"}


def parse_macro_recipes(source, path, *, max_expansions=4096, max_tokens=256,
                        sources=None, target_arch="riscv64"):
    inputs = {**(sources or {}), path: source}
    effects = MakeEffects(inputs, path, target_arch, depth=min(32,max_expansions), limit=max_tokens)
    records = []
    for recipe in effects.recipes:
        words = tokens(recipe.text, recipe.path, recipe.line)
        command = words[0].text.lstrip("@")
        compiler_ref = REF.fullmatch(command)
        if command not in _COMPILERS and (compiler_ref is None or (compiler_ref[1] or compiler_ref[2]) not in {"CC","CXX"}):
            continue
        automatic = {"$@": recipe.target}
        if recipe.prerequisites:
            automatic["$<"] = recipe.prerequisites[0]
        resolved = effects.expand(words[1:], automatic)
        names = tuple(t.text for t in resolved or () if _SOURCE.fullmatch(t.text))
        known = (recipe.known and not effects.reasons and resolved is not None
                 and "-c" in [t.text for t in resolved] and len(names) == 1
                 and names[0] in recipe.prerequisites)
        if compiler_ref and (compiler_ref[1] or compiler_ref[2]) in effects.env:
            compiler = effects.expand((replace(words[0],text=command),))
            known &= compiler is not None and len(compiler) == 1 and compiler[0].text in _COMPILERS
        if any(t.text.startswith(("-include","-imacros","-Wp,","-Xpreprocessor","-undef","--")) for t in resolved or ()):
            known = False
        configuration = f"{path}:{recipe.target}:{recipe.line}" if recipe.path == path else f"{path}:{recipe.path}:{recipe.target}:{recipe.line}"
        use_id = f"{path}:{recipe.path}:{recipe.line}:{recipe.target}"
        args, origin_records = [], {}
        index = 0
        while index < len(resolved or ()):
            token = resolved[index]
            index += 1
            if not token.text.startswith(("-D","-U")):
                continue
            operation, value = token.text[:2], token.text[2:]
            pieces = [token]
            end = token.end
            if not value and index < len(resolved):
                other = resolved[index]
                value = other.text
                pieces.append(other)
                index += 1
                if other.path == token.path and other.line == token.line and other.column >= token.end:
                    end = other.end
            match = _MACRO.fullmatch(value)
            if match is None or operation == "-U" and match[2] is not None:
                known = False
                continue
            name, value = match.groups()
            key = f"{token.path}:{token.line}:{token.column}:{end}"
            origins = {span for part in pieces for span in (part.source, *part.origins, *part.via)}
            origin_keys = []
            for origin_path, line, column, finish in sorted(origins):
                origin_key = f"{origin_path}:{line}:{column}:{finish}"
                origin_keys.append(origin_key)
                # 参数主位置已作为真实 Evidence，不重复为来源节点。
                if (origin_path,line,column,finish) == (token.path,token.line,token.column,end):
                    continue
                data = {"role":"origin","key":origin_key,"useId":use_id}
                raw = inputs[origin_path].splitlines()[line-1][column-1:finish-1]
                origin_records[origin_key] = BuildRecord("build_assignment",raw,line,column,finish,
                    {"sourcePath":origin_path,"configuration":configuration,"sourceChain":data})
            data = {"role":"argument","key":key,"macro":name,"operation":operation,
                    "value":value if value is not None else "1","order":len(args),
                    "recipeLine":recipe.line,"target":recipe.target,
                    "viaLines":tuple(span[1] for span in token.via)}
            # 旧简单 token 的合同保留；多来源通过稳定 use identity 关联。
            if len(origins) > 1 or recipe.path != path:
                data.update(useId=use_id, originKeys=tuple(origin_keys))
            args.append(data)
            raw = inputs[token.path].splitlines()[token.line-1][token.column-1:end-1]
            metadata = {"sourceChain":data,"selectionStatus":"unknown","configuration":configuration}
            if token.path != path:
                metadata["sourcePath"] = token.path
            records.append(BuildRecord("build_argument",raw,token.line,token.column,end,metadata))
        records.extend(origin_records.values())
        data = {"role":"recipe","key":f"{path}:{recipe.path}:{recipe.line}","target":recipe.target,
                "targetLine":recipe.target_line,"source":names[0] if len(names)==1 else None,
                "arguments":args,"proven":known}
        if recipe.path != path:
            data['workingDirectory'] = PurePosixPath(path).parent.as_posix()
        if origin_records or recipe.path != path:
            data["useId"] = use_id
        if effects.reasons:
            data["reasonCodes"] = tuple(sorted(effects.reasons))
        metadata = {"sourceChain":data,"selectionStatus":"selected" if known else "unknown",
                    "configuration":configuration}
        if recipe.path != path:
            metadata["sourcePath"] = recipe.path
        records.append(record_for_token("build_configuration",recipe.text.strip(),recipe.line,recipe.text,metadata=metadata))
    return tuple(records)
