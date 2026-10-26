"""子测试集的显式映射加载、校验与稳定去重。"""

from pathlib import Path
import unittest


def mapped_suite(root, inventory, *, discover=None, extra_units=(), loader=None):
    """保留目录发现，并在同一覆盖率会话内加载所有主测试和辅助测试。"""
    root = Path(root).resolve()
    unit_root = root / "tests" / "unit"
    modules = inventory.get("modules")
    if not isinstance(modules, dict) or not modules:
        raise ValueError("测试清单必须包含非空 modules 映射")
    paths = list(extra_units)
    for module, mapping in modules.items():
        if not isinstance(mapping, dict) or not mapping.get("unit"):
            raise ValueError(f"模块缺少 unit 映射: {module}")
        supporting = mapping.get("supportingUnits", [])
        if not isinstance(supporting, (list, tuple)):
            raise ValueError(f"supportingUnits 必须是路径列表: {module}")
        paths.extend((mapping["unit"], *supporting))

    names = set()
    for path in paths:
        if not isinstance(path, str) or not path:
            raise ValueError(f"无效单元测试路径: {path!r}")
        candidate = root / path
        resolved = candidate.resolve()
        if (Path(path).is_absolute() or ".." in Path(path).parts
                or not resolved.is_relative_to(unit_root)
                or candidate.suffix != ".py" or not candidate.is_file()):
            raise ValueError(f"单元测试必须是 tests/unit 内存在的 Python 文件: {path}")
        names.add(".".join(candidate.relative_to(root).with_suffix("").parts))

    loader = loader or unittest.TestLoader()
    suites = []
    if discover is not None:
        suites.append(loader.discover(str(discover), pattern="test_*.py", top_level_dir=str(root)))
    for name in sorted(names):
        suite = loader.loadTestsFromName(name)
        if not suite.countTestCases():
            raise ValueError(f"映射没有加载到测试用例: {name}")
        suites.append(suite)
    if loader.errors:
        raise ValueError("测试加载失败:\n" + "\n".join(loader.errors))

    selected = {}

    def collect(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                collect(item)
            else:
                selected[item.id()] = item

    for suite in suites:
        collect(suite)
    return unittest.TestSuite(selected[key] for key in sorted(selected))
