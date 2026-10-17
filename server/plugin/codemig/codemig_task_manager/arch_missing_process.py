from collections import defaultdict
import copy
import re
from difflib import SequenceMatcher
from plugin.codemig.codemig_common import arch_detect

from plugin.codemig.codemig_common.arch_detect import has_arch_and_remainder
from plugin.codemig.codemig_common.arch_detect import OTHER, RISCV, arch_like, arch_others_string, \
    isa_others_string


def find_similar_groups(arch_list):
    groups = {}
    for arch, pattern, dirname in arch_list:
        if pattern not in groups:
            groups[pattern] = []
        groups[pattern].append((arch, dirname))
    return groups


def replace_name(remainder, raw):
    result = []
    matcher = SequenceMatcher(None, remainder, raw)
    replace = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # 相同部分保持不变
            result.append(raw[i1:i2])
        elif replace == 0:
            result.append('riscv')
            replace = 1
    return '.'.join(result)


separators = '_-.#'


def get_split_name(name):
    pattern = f'[{re.escape(separators)}]+'
    parts = re.split(pattern, name)
    parts = [part for part in parts]
    return parts


def find_and_mark_stars(text: str):
    """
    查找字符串中的 * 和 ** 并标记顺序

    规则：
    1. ** 优先于 *（贪婪匹配）
    2. 按照出现的顺序标记
    3. 返回 {顺序索引: "标记"}

    示例：
    "ABC*DEF**aaa**" → {0: "*", 1: "**", 2: "**"}
    """
    # 模式：匹配 ** 或 *
    pattern = r'\*isa\*|\*arch\*'

    # 查找所有匹配
    matches = list(re.finditer(pattern, text))

    # 构建结果字典
    result = []
    for i, match in enumerate(matches):
        result.append('isa' if match.group() == '*isa*' else 'arch')

    return result


def detect_arch(raw_paths: list):
    paths = copy.copy(raw_paths)
    res = {'missing': {}, 'found': {}, 'other': []}
    arch_list = []
    for path in paths:
        match, arch, remainder = has_arch_and_remainder(path)
        if match:
            arch_list.append((arch, remainder, path))
    similar_groups = find_similar_groups(arch_list)
    for pattern, path_list in similar_groups.items():
        g_list = []
        r_set = set()
        found_riscv = False
        for arch, path in path_list:
            if arch == RISCV:
                found_riscv = True
                r_set.add(path)
            else:
                g_list.append(path)
            paths.remove(path)
        # regex = pattern.replace('**', '(.*)').replace('*', '(.*)')
        if found_riscv:
            res['found'][tuple(sorted(r_set))] = (g_list, pattern)
        else:
            res['missing'][pattern.replace('*isa*', 'rv64').replace('*arch*', 'riscv64')] = (g_list,
                                                                                             pattern)
    for key in ['found', 'missing']:
        for risc, value in res[key].items():
            archs, pattern = value
            tags = find_and_mark_stars(pattern)
            regex = pattern.replace('*isa*', '(.+)').replace('*arch*', '(\\w+)')
            others = []
            for path in paths:
                match = re.search(regex, path)
                found = False
                if match:
                    groups = match.groups()
                    for arch in arch_like:
                        for g in groups:
                            if g.startswith(arch):
                                others.append(path)
                                found = True
                                break
                        if found:
                            break
                    if found:
                        continue
                    found_known = True
                    for i, g in enumerate(groups):
                        if tags[i] == 'arch':
                            for arch in arch_others_string:
                                if g.startswith(arch):
                                    found = True
                                    break
                            else:
                                found_known = False
                        else:
                            for isa in isa_others_string:
                                if g.startswith(isa):
                                    found = True
                                    break
                            else:
                                found_known = False
                        if not found_known:
                            break
                    if found_known:
                        archs.append(path)

            paths = [x for x in paths if x not in others]
            paths = [x for x in paths if x not in archs]
            res[key][risc] = (archs, others)

    res['other'] = paths
    return res


classify_suffix = ['.s', '.S', '.asm', '.sh', '.go', '.h', '.c', '.cc', '.cpp', '.hpp', '.h.in',
                   '.c.in', '.cc.in', '.cpp.in', '.hpp.in', '.java', '.py', '.rs', '.pl']


def group_files(filenames):
    if len(filenames) == 0:
        return {}, {}, []
    missing_file = {}
    found_file = {}
    skip_file = []
    classified = defaultdict(list)
    for filename in filenames:
        for s in classify_suffix:
            if filename.endswith(s):
                classified[s].append(filename[:-len(s)])
                break
    for suffix, group in classified.items():
        grouped_files = detect_arch(group)
        for missing, other_list in grouped_files['missing'].items():
            others = [o + suffix for o in other_list[0]]
            missing_file[missing + suffix] = others
            skip_file.extend(others)
            skip_file.extend([o + suffix for o in other_list[1]])
        for found, other_list in grouped_files['found'].items():
            found = tuple(item + suffix for item in found)
            others = [o + suffix for o in other_list[0]] if other_list else []
            found_file[found] = others
            skip_file.extend(others)
            skip_file.extend([o + suffix for o in other_list[1]] if other_list else [])
            skip_file.extend(found)
    return missing_file, found_file, skip_file
