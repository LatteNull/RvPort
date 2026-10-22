## Why

阶段 1 已建立 core、pipeline 和 adapter 接缝，但正式 staged pipeline 还没有能够在不完整 C/C++ 项目上工作的真实 Frontend；当前解析能力仍封装在 legacy runner 中。现在需要把已经在独立容器中验证的 Tree-sitter baseline 与可选 Clang enrichment 重写为正式 core Evidence 生产组件，为后续知识匹配、关系分析和分类阶段提供稳定输入，同时停止在旧 frontend 上继续打补丁。

## What Changes

- 新建独立的正式 C/C++ frontend 包，以 Tree-sitter C/C++ 作为覆盖全部受支持源码的必需 baseline，直接产生 core `Entity`、`Evidence` 和结构化 Diagnostic。
- 在存在有效 compilation context 时使用 Clang 18 detailed preprocessing record 作为逐 translation unit 的可选增强，补充宏定义、宏展开、include 和适用的语义实体。
- 为 Clang 参数建立严格的纯解析 allowlist，拒绝 plugin、response file、输出文件、PCH/module 加载及其他可执行或有副作用的参数，并将拒绝项记录为结构化 Diagnostic。
- 以项目相对路径、稳定 source span、领域自然键、producer 和版本生成稳定身份；不同 producer 对同一事实保留独立 Evidence，留给后续 Normalizer 关联，不能丢失任一来源。
- 将正式 frontend 作为 `PipelineProfile` 可注入组件接入并用 staged runner 合同测试验证；由于 Knowledge、Detector、Classifier 和 Report Projector 尚未重写，当前 CLI 默认 profile 继续使用 legacy runner，本阶段不伪造一个不完整的新默认扫描流程。
- 冻结现有 `cpp_frontend.py`、`compile_commands.py`、`models.py`、`rules.py` 和 `report.py` 为只读行为基线；正式实现不得导入或修改这些 legacy 模块。`technology/` spike 只作为选型证据，不直接改造成生产实现。
- 保持现有 `scan-result.json` 的 `schemaVersion: "1.0"`、顶层字段、三个 artifact、CLI 退出码、YAML/`generatedSet` 与 Clang/GCC 事实数据不变。
- 所有实现和测试仅更新独立 `kb-scanner-test` 容器；不安装宿主机依赖，不修改生产镜像、根 Compose，也不执行真实编译或项目测试。

## Capabilities

### New Capabilities

- `kb-scanner-cpp-frontends`: 定义 Tree-sitter baseline、可选 Clang enrichment、安全参数过滤、稳定 Evidence/provenance、降级与确定性输出合同。

### Modified Capabilities

- `kb-scanner-core-pipeline`: 增加正式 Frontend 的 staged 注入与 legacy 冻结迁移要求，明确本阶段默认 CLI 仍保持 legacy-compatible runner。

## Impact

- 新增正式 frontend、Clang adapter、Evidence 构造与前端测试模块；复用测试容器内已锁定的 Tree-sitter 0.26.0、C grammar 0.24.2、C++ grammar 0.23.4 和 Clang/libclang 18.1.3，不新增宿主机或生产依赖。
- `kb_scanner/core` 与 `kb_scanner/pipeline` 只在确有前端合同缺口时做向后兼容的小幅扩展；legacy parser/rule/report 文件保持字节不变。
- 当前后端调用方式、结果消费者和部署拓扑不受影响；本阶段不切换默认报告生产路径，也不产生新的主结果文件。
- 分析范围仍是 C/C++ 软件静态迁移；不覆盖操作系统、内核、驱动、板级迁移，不实现跨文件 Evidence Graph、知识匹配、Finding 分类、readiness、真实 RISC-V 编译或测试执行。
