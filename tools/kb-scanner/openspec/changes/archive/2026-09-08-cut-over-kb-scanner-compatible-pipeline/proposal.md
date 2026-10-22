## Why

KB Scanner 的新静态分析管线已经能够产生 C/C++、构建、测试、关系、分类和项目评估结果，但默认 CLI 仍走 Legacy，用户尚无法获得新能力。现在需要以现有输出契约为边界完成兼容投影和默认切换，并在有差异证据与等价替代的前提下清理重复旧实现，结束长期双轨维护。

## What Changes

- 实现正式兼容 Projector，将 Classification 投影为现有 `findings[]`，将 Evidence、Knowledge、Relation 和 ProofPath 摘要投影到现有 Finding 字段与 `trace`，将项目 Assessment 投影到可选 `summary.readiness`。
- 保持 `scan-result.json` 的 `schemaVersion: "1.0"`、既有顶层字段和字段语义，继续生成 `scan-result.json`、`scan-report.html`、`scan.log`，不创建第二套主结果结构。
- 建立版本化的 Legacy/new differential oracle，对同一批高价值 x86、guarded/inactive、portable alternative、无命中、部分输入和恶意输入 fixture 比较 rule ID、Finding 类型、严重程度、阻断状态、位置、reason、suggestion、trace、summary、diagnostics、退出码和 artifact。
- 将默认 `kb-scanner scan` 切换到完整 staged pipeline；保留明确的测试/迁移期 Legacy oracle 入口，禁止生产默认路径回退到 Legacy 或读取 Legacy YAML。
- 默认新管线继续直接加载现有 `clang-x86-entries.json`、`gcc-x86-entries.json` 和已审校 curated knowledge；两份 compiler facts 的内容、分类计数、来源和 SHA-256 保持不变，Legacy YAML/`generatedSet` 只作为冻结差异基线，不再成为默认运行时依赖。
- 逐项审计并删除已被正式 adapter 替代的 Legacy parser/evaluator/report bridge、重复正则和无用 `technology/` spike；尚无等价替代的能力必须保留在隔离边界或明确标记 deferred，不能仅为“清理”而丢失检测行为。
- 为每个新增或实质修改的 projector、mapping/policy、default-profile factory、differential oracle 和 cleanup guard 模块补齐隔离单元测试映射，并在唯一 `kb-scanner-test` 容器中执行逐模块 line/branch coverage、组件、兼容、后端消费、无副作用和全量回归门禁。
- 继续只做 C/C++ 软件迁移静态分析；不执行真实编译、构建或测试，不纳入操作系统、内核、系统调用、驱动和板级迁移，也不修改生产镜像或根 Compose。

## Capabilities

### New Capabilities

- `kb-scanner-compatible-projection-and-cutover`: 定义内部 Evidence/Relation/Observation/Classification/Assessment 到现有 schema 1.0 的兼容投影、差异验收、默认入口切换、Legacy 清理及回滚边界。

### Modified Capabilities

- `kb-scanner-core-pipeline`: 将完整 staged pipeline 设为默认 CLI 路径，把 Legacy 从默认实现降为冻结的差异 oracle，并约束切换后的失败、退出码和 artifact 生命周期。
- `kb-scanner-classification-and-assessment`: 将 qualification 内部 Classification/Assessment 接入正式兼容 Projector，同时保持静态范围、保守 readiness 和逐模块测试门禁。
- `kb-scanner-knowledge-and-local-detection`: 让默认新管线只消费正式 JSON knowledge manifest、两份既有 compiler facts 和 accepted curated facts；Legacy YAML/`generatedSet` 退出默认运行时但继续作为冻结兼容基线。

## Impact

- 主要影响 `kb_scanner/pipeline/`、新的兼容 projector/mapping 模块、`kb_scanner/cli.py`、现有 artifact renderer 边界、测试 inventory 与兼容 fixture。
- `kb_scanner/adapters/legacy.py`、`kb_scanner/rules.py`、`kb_scanner/cpp_frontend.py`、`kb_scanner/compile_commands.py`、`kb_scanner/models.py`、`kb_scanner/report.py` 和 `kb_scanner/technology/` 将按引用与差异审计结果保留、隔离或删除，不在无等价证明时整包清除。
- 后端继续读取同一 schema 1.0 JSON 和三个 artifact；新增 `summary.readiness` 与更丰富 `trace` 均为可选兼容字段，旧消费者忽略它们时仍可工作。
- 所有依赖安装和正式验证仅发生在独立 `kb-scanner-test` 容器；不在宿主机安装依赖，不修改 `backend/Dockerfile`、根 Compose 或生产镜像。
