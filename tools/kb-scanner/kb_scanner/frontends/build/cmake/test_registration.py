"""有界 CMake 测试注册恢复；只消费 evaluator 已复制的记录。"""
from collections import defaultdict
from dataclasses import replace
from pathlib import PurePosixPath

from .values import truth


COMMANDS = frozenset({"enable_testing", "add_test", "set_tests_properties"})


def _info(record):
    return record.metadata.get("cmake", {})


def _active(record):
    return record.metadata.get("selectionStatus", "unknown")


def _scope(record):
    return str(_info(record).get("directory", "."))


def _test_name(values):
    if len(values) >= 2 and values[0] == "NAME":
        return values[1] or "unknown"
    return values[0] if values and values[0] else "unknown"


def _ancestors(directory):
    yield directory
    yield from (str(p) for p in PurePosixPath(directory).parents)


def recover(records, diagnostics):
    """注释/字符串不作为命令；不改变既有 target/source 的编译选择。"""
    targets, enables, properties, registrations = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for path, items in records.items():
        for index, item in enumerate(items):
            info = _info(item)
            command = info.get("commandName")
            if item.kind == "build_target":
                targets[info.get("target")].append(item)
            elif command == "enable_testing":
                enables[_scope(item)].append(item)
            elif command == "set_tests_properties":
                args = info.get("testArguments", ())
                if "PROPERTIES" in args:
                    cut = args.index("PROPERTIES")
                    for name in args[:cut]:
                        properties[(_scope(item), name)].append(item)
                else:
                    properties[(_scope(item), "*")].append(item)
            elif command == "add_test":
                registrations[(_scope(item), _test_name(info.get("testArguments", ())))].append((path, index, item))

    for (directory, name), entries in registrations.items():
        live = [item for _, _, item in entries if _active(item) != "inactive"]
        for path, index, item in entries:
            info, reasons = _info(item), set()
            args = info.get("testArguments", ())
            state = _active(item)
            source_keys = [info["key"]]
            supported = (not info.get("testUnsupportedContext") and len(args) >= 4 and args[0] == "NAME" and args[2] == "COMMAND"
                         and all(isinstance(v, str) and v for v in args)
                         and not any(v in {"COMMAND_EXPAND_LISTS", "CONFIGURATIONS", "WORKING_DIRECTORY"} for v in args[4:]))
            target = args[3] if supported else None
            if not supported:
                reasons.add("test-registration-unsupported")
            # A literal extra argument is provenance, not proof of runtime filtering.
            if supported and len(args) > 4:
                reasons.add("test-command-arguments-uninterpreted")
            candidates = targets.get(target, ()) if target else ()
            candidates = [v for v in candidates if _active(v) != "inactive"]
            owner = candidates[0] if len(candidates) == 1 else None
            valid_owner = owner is not None and _info(owner).get("commandName") == "add_executable" and _info(owner).get("ordinaryExecutable") is True
            if not valid_owner:
                reasons.add("test-target-not-unique-local-executable")
            elif _active(owner) != "selected":
                reasons.add("test-target-selection-unknown")
            if owner is not None:
                source_keys.append(_info(owner)["key"])
            enabled = [v for scope in _ancestors(directory) for v in enables.get(scope, ()) if _active(v) == "selected"]
            if not enabled:
                reasons.add("test-enable-not-proven")
            source_keys.extend(_info(v)["key"] for v in enabled)
            if len(live) > 1 and state != "inactive":
                reasons.add("test-registration-conflict")
            if state == "unknown":
                reasons.add("test-registration-selection-unknown")
            disabled = False
            applicable = sorted((*properties.get((directory, name), ()), *properties.get((directory, "*"), ())),
                                key=lambda value: _info(value)["order"])
            for prop in applicable:
                if _active(prop) == "inactive":
                    continue
                source_keys.append(_info(prop)["key"])
                values = _info(prop).get("testArguments", ())
                tail = values[values.index("PROPERTIES")+1:] if "PROPERTIES" in values else ()
                if _info(prop)["order"] <= info["order"]:
                    reasons.add("test-property-order-unknown")
                if _active(prop) != "selected" or len(tail) != 2 or tail[0] != "DISABLED" or truth(tail[1]) is None:
                    reasons.add("test-property-unsupported-or-unknown")
                else:
                    disabled = truth(tail[1])
            # Inactive registration is excluded regardless of its unexecuted command,
            # but invalid/unknown prerequisites must never imply compile exclusion.
            status = "inactive" if state == "inactive" else "unknown" if reasons else "not_selected" if disabled else "selected"
            details = {"name": name, "directory": directory, "target": target,
                       "registrationStatus": status, "disabled": disabled,
                       "buildStatus": _active(owner) if valid_owner else "unknown",
                       "role": "confirmed" if supported and valid_owner else "candidate",
                       "reasonCodes": tuple(sorted(reasons)), "sourceKeys": tuple(dict.fromkeys(source_keys)),
                       "arguments": tuple(args), "configuration": item.metadata.get("configuration", "unknown")}
            records[path][index] = replace(item, metadata={**item.metadata, "cmake": {**info, "testRegistration": details}})
            if reasons and state != "inactive":
                diagnostics[path].append("cmake-test-registration-unknown")
    return records
