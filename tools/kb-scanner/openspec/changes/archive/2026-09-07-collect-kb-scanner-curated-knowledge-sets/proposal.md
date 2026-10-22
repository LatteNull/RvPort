## Why

当前新 Knowledge/Local Detection 路径只有 Clang/GCC 两份既有 generated facts，x86 汇编指令与寄存器、CPU/平台 API、target feature、架构别名和固定向量宽度语义仍被标记为 `needs-curated-knowledge`。这些缺口不能靠空 `curatedSets`、旧 YAML 正则或隐藏词表补齐；需要一个独立 change 先从版本固定的编译器、汇编器和有限的链接器结构化定义中确定性提取可生成事实，再对无法由工具链直接证明的剩余语义进行逐条溯源和人工审校。

## What Changes

- 建立“自动生成优先、人工审校兜底”的知识生产流程：先审计每类缺口的可提取性，再把可复现的工具链事实写入新的 generated source，仅把需要判断、别名归一或来源冲突处理的内容写入 curated source。
- 新增版本固定、来源可审计的 x86 指令/寄存器、target feature、架构名称以及适用 CPU API 数据源；现有 `clang-x86-entries.json` 和 `gcc-x86-entries.json` 保持字节、格式、哈希和来源合同不变。
- 为 curated 数据定义严格 JSON schema 和稳定身份，记录 canonical value、fact kind、architecture scope、权威引用、上游版本/修订、许可证、采集日期与审校状态；同时记录 rejected/deferred 候选，避免未收录原因丢失。
- 将旧 YAML、RVPT 对比结果和现有 fixture 仅作为候选发现输入；confirmed 数据必须追溯到编译器、汇编器、链接器、ISA 或 API 的权威版本化来源。
- 扩展 manifest 与 Knowledge Provider，使其在保留 generated-only v1 输入兼容的前提下显式加载新增 generated/curated sources，并保留来源类型及完整 provenance。
- 更新行为验收矩阵和 Local Detector 的知识映射：只有权威事实支持的局部依赖可升级为 `confirmed_local`；固定向量宽度等非 x86 专属信号仍保持 candidate/deferred，不能因进入数据集自动成为阻断结论。
- 为每个新增或实质修改的生产模块、schema、Provider 和 matcher 建立隔离单元测试映射，并在独立 `kb-scanner-test` 容器中执行行/分支覆盖门禁、数据 lint、确定性生成和完整兼容回归。
- 保持 `scan-result.json` 的 `schemaVersion: "1.0"`、既有顶层字段、Finding 语义和三个 artifact，不增加第二套主结果结构；范围继续限定为 C/C++ 软件迁移，不纳入操作系统、内核、系统调用、驱动或板级迁移。

## Capabilities

### New Capabilities

- `kb-scanner-knowledge-data-production`: 定义工具链来源审计、确定性事实提取、人工 curated 审校、provenance、拒绝/延后记录、版本化与数据质量门禁。

### Modified Capabilities

- `kb-scanner-knowledge-and-local-detection`: 从 generated-facts-only 扩展为兼容加载既有 generated facts、新增 generated sources 和已审校 curated sources，并用新增知识缩小明确的 deferred 能力。
- `kb-scanner-containerized-toolchain`: 将知识提取器、schema/lint、确定性生成和 Provider 回归纳入唯一独立测试容器，禁止向宿主机或生产镜像安装采集依赖。

## Impact

- 新增或修改 `rulesets/riscv-porting` 下的 knowledge manifest、generated/curated 数据、来源清单、schema 与行为验收矩阵。
- 新增可复现的数据采集/审校工具，并修改 `kb_scanner/knowledge`、必要的 detector 定义/匹配映射及其测试 inventory。
- 测试只通过 `tools/kb-scanner/Dockerfile.test` 和 `compose.test.yml` 执行；扫描运行时不得启动 compiler、assembler、linker，也不得执行被扫描项目代码。
- 不修改现有两份 compiler facts、legacy YAML、默认 legacy CLI、根 Compose、生产镜像或后端消费合同。
