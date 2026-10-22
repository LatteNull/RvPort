"""Static CMake event evaluation over already collected workspace inputs."""
from dataclasses import replace
from pathlib import PurePosixPath
import posixpath

from ..adapters import AdapterResult
from ..vocabulary import BuildRecord
from .syntax import parse
from .values import both, condition, either, expand, negate
from .test_registration import COMMANDS as TEST_COMMANDS, recover as recover_tests


_TARGETS = {"add_library", "add_executable"}
_ITEMS = {"target_sources": "build_source", "target_compile_options": "build_argument",
          "target_compile_definitions": "build_argument", "target_include_directories": "build_directory",
          "target_link_libraries": "build_dependency"}
_SAFE = {"cmake_minimum_required", "project", "enable_testing", "add_test", "set_tests_properties",
         "add_link_options"}


def analyze_project(sources, target_arch, *, parser=parse, max_commands=10000, max_depth=32):
    if min(max_commands, max_depth) < 1:
        raise ValueError("cmake-invalid-project-budget")
    parsed, records, diagnostics = {}, {p: [] for p in sources}, {p: [] for p in sources}
    for path, source in sorted(sources.items()):
        try:
            parsed[path] = parser(source)
        except (ValueError, RuntimeError, TypeError) as exc:
            parsed[path] = getattr(exc, "commands", ())
            diagnostics[path].append(f"cmake-syntax-unavailable:{type(exc).__name__}")
    visited, targets = set(), {}
    count = 0
    uncertain_usage = False

    def emit_record(path, command, kind, value, token, active, parents=(), **extra):
        key = f"{path}:{token.line}:{token.column}:{kind}:{len(records[path])}"
        info = {"key": key, "parents": tuple(dict.fromkeys(parents)), "order": count, **extra}
        state = "selected" if active is True else "inactive" if active is False else "unknown"
        metadata = {"cmake": info, "selectionStatus": state, "configuration": "cmake:target:"+target_arch,
                    "endLine": token.end_line, "endColumn": token.end_column,
                    "reason": "cmake-static-selection" if active is not None else "cmake-selection-unknown"}
        records[path].append(BuildRecord(kind, value or command.name, token.line, token.column,
                                         token.end_column if token.line == token.end_line else token.column+1, metadata))
        return key

    def poison(variables):
        for name in variables:
            variables[name] = None

    def resolve(path, value, directory=None):
        if value is None:
            return None
        if value.startswith("/__kb_workspace__/"):
            value = value[len("/__kb_workspace__/"):]
        elif value == "/__kb_workspace__":
            value = "."
        elif value.startswith("/") or ":" in value or "\\" in value:
            return None
        else:
            value = str(PurePosixPath(directory if directory is not None else PurePosixPath(path).parent) / value)
        value = posixpath.normpath(value)
        return None if value == ".." or value.startswith("../") else value

    def run(path, variables, origin=(), inherited=True, trail=(), isolated=False, source_directory=None, origins=None):
        nonlocal count, uncertain_usage
        if path not in sources or path in trail or len(trail) >= max_depth:
            return None
        visited.add(path)
        active = inherited
        if diagnostics[path]:
            active = None
            poison(variables)
        list_directory = str(PurePosixPath(path).parent)
        directory = list_directory if source_directory is None else source_directory
        variables["CMAKE_CURRENT_SOURCE_DIR"] = "/__kb_workspace__" + ("/"+directory if directory != "." else "")
        variables["CMAKE_CURRENT_LIST_DIR"] = "/__kb_workspace__" + ("/"+list_directory if list_directory != "." else "")
        stack, parent_keys, terminating, skip = [], origin, False, 0
        tainted = bool(diagnostics[path])
        def emit(path, command, kind, value, token, selected, parents=(), **extra):
            return emit_record(path, command, kind, value, token, None if terminating else selected, parents, **extra)
        var_origins = origins if origins is not None else {}
        for cmd in parsed[path]:
            count += 1
            if count > max_commands:
                diagnostics[path].append("cmake-command-budget")
                poison(variables)
                tainted = True
                active = None
                break
            name = cmd.name
            if name in {"function", "macro", "foreach", "while", "block"}:
                skip += 1
                if active is not False:
                    poison(variables)
                    active = None
                    tainted = True
                emit(path, cmd, "build_unsupported", name, cmd.token, None, parent_keys)
                diagnostics[path].append("cmake-unsupported-control")
                continue
            if name in {"endfunction", "endmacro", "endforeach", "endwhile", "endblock"}:
                skip = max(0, skip-1)
                continue
            if skip:
                if name in TEST_COMMANDS:
                    emit(path, cmd, "build_configuration", cmd.token.text, cmd.token, None, parent_keys,
                         commandName=name, directory=directory, testArguments=tuple(t.text for t in cmd.args),
                         testUnsupportedContext=True)
                continue
            values = [expand(t, variables) for t in cmd.args]
            dependencies = tuple(k for t in cmd.args for variable, keys in var_origins.items()
                                 if "${"+variable+"}" in t.text or variable == t.text for k in keys)
            parents = (*parent_keys, *dependencies)
            if name == "if":
                result = condition(cmd.args, variables)
                key = emit(path, cmd, "build_condition", cmd.token.text, cmd.token, active, parents)
                stack.append([active, result, parent_keys, key])
                active, parent_keys = both(active, result), (*parent_keys, key)
                continue
            if name in {"elseif", "else"}:
                if not stack:
                    active = None
                    diagnostics[path].append("cmake-unmatched-branch")
                    continue
                outer, seen, outer_keys, previous = stack[-1]
                result = condition(cmd.args, variables) if name == "elseif" else True
                key = emit(path, cmd, "build_condition", cmd.token.text, cmd.token, outer,
                           (*outer_keys, previous, *dependencies))
                active = both(outer, both(negate(seen), result))
                stack[-1][1] = either(seen, result)
                stack[-1][3] = key
                parent_keys = (*outer_keys, key)
                continue
            if name == "endif":
                if stack:
                    active, _, parent_keys, _ = stack.pop()
                    if terminating or tainted:
                        active = None
                else:
                    diagnostics[path].append("cmake-unmatched-endif")
                    active = None
                continue
            if terminating:
                active = None
            key = emit(path, cmd, "build_assignment" if name in {"set", "list", "option", "unset"} else
                       "build_target" if name in _TARGETS else "build_configuration", cmd.token.text,
                       cmd.token, active, parents, commandName=name, required=not isolated,
                       directory=directory,
                       target=values[0] if name in _TARGETS and values else None,
                       **({"testArguments": tuple(values)} if name in TEST_COMMANDS else {}),
                       **({"ordinaryExecutable": not any(v in {"ALIAS", "IMPORTED", "EXCLUDE_FROM_ALL"} for v in values[1:])}
                          if name == "add_executable" else {}))
            if name in {"set", "list", "option", "unset"} and values:
                variable = values[0]
                if variable is None or active is False:
                    continue
                value = None
                if active is True and name == "set" and all(v is not None for v in values[1:]) and not set(values[1:]) & {"CACHE", "PARENT_SCOPE"}:
                    value = ";".join(values[1:])
                if active is True and name == "list" and len(values) > 2 and values[0] == "APPEND":
                    variable = values[1]
                    prior = variables.get(variable)
                    if prior is not None and all(v is not None for v in values[2:]):
                        value = ";".join((prior, *values[2:]))
                if variable is not None:
                    variables[variable] = value
                    var_origins[variable] = (key,)
                if "PARENT_SCOPE" in values and active is not False:
                    poison(variables)
                    active = None
                    tainted = True
                continue
            if name == "message" and values and values[0] == "FATAL_ERROR":
                emit(path, cmd, "build_arch_constraint", "FATAL_ERROR", cmd.args[0], active, (key,),
                     rejection=True, required=not isolated, reason="cmake-target-configuration-rejected")
                if active is not False:
                    terminating = True
                    active = None
                continue
            if name in {"include", "add_subdirectory"}:
                target = resolve(path, values[0], directory) if values else None
                target = target + "/CMakeLists.txt" if target and name == "add_subdirectory" else target
                if target not in sources and target and name == "include" and target+".cmake" in sources:
                    target += ".cmake"
                reference = emit(path, cmd, "build_include", target or "unknown", cmd.args[0] if cmd.args else cmd.token,
                                 active, (key,))
                if active is not False:
                    child_vars = dict(variables) if name == "add_subdirectory" else variables
                    result = run(target, child_vars, (reference,), active, (*trail, path), isolated,
                                 directory if name == "include" else None,
                                 var_origins if name == "include" else dict(var_origins)) if target else None
                    if result is not True:
                        active = None
                        terminating = True
                        tainted = True
                        poison(variables)
                        diagnostics[path].append("cmake-include-or-child-incomplete")
                    variables["CMAKE_CURRENT_SOURCE_DIR"] = "/__kb_workspace__" + ("/"+directory if directory != "." else "")
                    variables["CMAKE_CURRENT_LIST_DIR"] = "/__kb_workspace__" + ("/"+list_directory if list_directory != "." else "")
                continue
            if name in _TARGETS or name in _ITEMS:
                target = values[0] if values else None
                state = active
                if state is not False and (not target or name in _TARGETS and target in targets or name not in _TARGETS and target not in targets):
                    state = None
                    diagnostics[path].append("cmake-target-identity-unknown")
                if target and name in _TARGETS and state is not False:
                    targets[target] = (key, state)
                owner, owner_state = (key, state) if name in _TARGETS else targets.get(target, (key, state if state is False else None))
                state = both(state, owner_state)
                visibility = "INTERFACE" if name in _TARGETS and "INTERFACE" in values else "PRIVATE"
                for token, value in zip(cmd.args[1:], values[1:]):
                    if value in {"PUBLIC", "PRIVATE", "INTERFACE"} and name not in _TARGETS:
                        visibility = value
                        continue
                    if name in _TARGETS and value in {"STATIC", "SHARED", "MODULE", "OBJECT", "EXCLUDE_FROM_ALL", "WIN32", "MACOSX_BUNDLE", "INTERFACE"}:
                        continue
                    if value in {"ALIAS", "IMPORTED", "INTERFACE"} and name in _TARGETS:
                        state = None
                    kind = "build_source" if name in _TARGETS else _ITEMS[name]
                    for item in (value or token.text).split(";"):
                        if not item:
                            continue
                        resolved = resolve(path, item, directory) if kind in {"build_source", "build_directory"} else item
                        text = "-D"+item if name == "target_compile_definitions" else resolved or item
                        certain = value is not None and resolved is not None and not (kind == "build_source" and visibility == "INTERFACE")
                        emit(path, cmd, kind, text, token, state if certain else None,
                             (owner, key), target=target or "unknown", visibility=visibility,
                             source=resolved if kind == "build_source" else None)
                continue
            if name in {"add_compile_options", "add_compile_definitions"}:
                for token, value in zip(cmd.args, values):
                    emit(path, cmd, "build_argument", ("-D" if name.endswith("definitions") else "")+(value or token.text),
                         token, active if value is not None else None, (key,), directory=directory, visibility="PRIVATE",
                         commandName=name)
                continue
            if name in _SAFE or name == "message":
                continue
            if active is not False:
                poison(variables)
                active = None
                tainted = True
                diagnostics[path].append("cmake-unsupported-command:"+name)
        if tainted:
            uncertain_usage |= not isolated
            for index, record in enumerate(records[path]):
                if record.kind in {"build_target", "build_source", "build_argument", "build_dependency"}:
                    records[path][index] = replace(record,metadata={**record.metadata,"selectionStatus":"unknown",
                                                                 "reason":"cmake-scope-side-effect-unknown"})
        return None if terminating or active is None or stack else True

    initial = {"CMAKE_SYSTEM_PROCESSOR": target_arch, "CMAKE_SOURCE_DIR": "/__kb_workspace__",
               "CMAKE_CXX_COMPILER_ID": None, "CMAKE_C_COMPILER_ID": None, "CMAKE_SYSTEM_NAME": None}
    if "CMakeLists.txt" in sources:
        run("CMakeLists.txt", dict(initial))
    for path in sorted(sources):
        if path not in visited:
            run(path, dict(initial), inherited=None, isolated=True)
    if uncertain_usage:
        for path in records:
            records[path] = [replace(r, metadata={**r.metadata, "selectionStatus": "unknown",
                                                 "reason": "cmake-project-side-effect-unknown"})
                             if r.kind in {"build_target", "build_source", "build_argument", "build_dependency"} else r
                             for r in records[path]]
    recover_tests(records, diagnostics)
    return {path: AdapterResult(tuple(records[path]), tuple(sorted(set(diagnostics[path]))), bool(diagnostics[path]))
            for path in sorted(sources)}
