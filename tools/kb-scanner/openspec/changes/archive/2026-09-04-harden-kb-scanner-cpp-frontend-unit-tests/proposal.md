## Why

正式 C/C++ frontend 已有 38 项新增测试，但其中混合了组件、libclang 集成、staged 集成和边界合同测试，不能据此证明每个新模块的异常分支与纯转换逻辑都具有隔离单元覆盖。需要在后续 Knowledge/Detector 开发前补齐可快速定位回归的模块级单元测试，并用可重复的覆盖度证据避免再以“全量测试数量”代替单元覆盖质量。

## What Changes

- 逐模块建立 `vocabulary.py`、`workspace.py`、`compilation_database.py`、`arguments.py`、`tree_sitter_adapter.py`、`clang_adapter.py` 和 `frontend.py` 的单元测试矩阵，明确区分 unit、component/integration 与 compatibility tests。
- 补齐稳定 ID/排序、非法 vocabulary、路径和输入错误、compilation database 无效 shape/token、语言选择、Tree-sitter 初始化失败、Clang 初始化/游标/diagnostic 异常、Frontend 状态传播、Diagnostic 去重顺序和多 context provenance 等当前未覆盖分支。
- 对 Tree-sitter、libclang 和文件系统边界使用 `unittest.mock` 或轻量 fake，隔离测试不依赖真实 parser 成功；保留现有真实 grammar/libclang 测试作为独立组件/集成验证。
- 在独立 `kb-scanner-test` 容器中增加仅测试使用的行/分支覆盖度采集与最低门槛，并输出模块级覆盖摘要；覆盖工具不得进入生产镜像或宿主机环境。
- 如测试隔离确有需要，仅允许对正式 frontend 增加行为保持不变的显式依赖注入 seam，不改变 Evidence、Diagnostic、StageResult、默认 CLI 或报告行为。
- 保留当前 120 项测试，新增单元测试后继续验证旧结果结构、三项 artifact、legacy 字节冻结以及 Clang/GCC 两份事实数据的内容、六类计数、source、哈希和 `generatedSet` 引用。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `kb-scanner-cpp-frontends`: 增加正式前端各模块必须具有隔离单元测试矩阵、异常与降级路径覆盖、测试分层标识及容器内覆盖度质量门槛的要求。

## Impact

- 主要影响 `tools/kb-scanner/tests/`、正式 C/C++ frontend 测试 fixture、测试专用依赖锁与独立测试容器入口。
- 可能对 `kb_scanner/frontends/cpp/` 做最小、行为保持不变的可测试性重构；不得修改 legacy `compile_commands.py`、`cpp_frontend.py`、`models.py`、`rules.py` 或 `report.py`。
- 不引入新的扫描能力，不切换默认 CLI，不加载或转换 x86 知识事实，不执行真实编译/项目测试，也不扩大到操作系统、内核、驱动或板级迁移。
- `scan-result.json` 继续使用 `schemaVersion: "1.0"` 和既有顶层字段，`scan-report.html`、`scan.log` 及现有 Finding 语义保持兼容。
