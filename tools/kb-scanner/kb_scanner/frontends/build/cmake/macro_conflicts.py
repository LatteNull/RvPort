"""只证明同一选项序列的顺序，不用文件排序代替编译参数顺序。"""
from collections import defaultdict
import re


def macro_conflicts(values):
    groups = defaultdict(list)
    for path, record, _ in values:
        if record.metadata['selectionStatus'] == 'inactive':
            continue
        match = re.fullmatch(r'(-D|-U)([A-Za-z_]\w*)(?:=(.*))?', record.value)
        if match is None:
            continue
        operation, name, value = match.groups()
        groups[name].append((path, record, operation, value if value is not None else '1'))
    conflicts = {}
    for name, items in groups.items():
        if len({(op, value) for _, _, op, value in items}) <= 1:
            continue
        # 仅同一个 target_compile_options 命令内的显式序列可依靠已有 token 顺序。
        ordered = all(record.metadata['cmake'].get('commandName') == 'target_compile_options'
                      for _, record, _, _ in items)
        owners = {(path, r.metadata['cmake'].get('target'), r.metadata['cmake'].get('order'))
                  for path, r, _, _ in items}
        if ordered and len(owners) == 1:
            continue
        reason = 'unknown-argument-order' if len({op for _, _, op, _ in items}) > 1 else 'conflicting-build-macro'
        conflicts[name] = reason
    return conflicts
