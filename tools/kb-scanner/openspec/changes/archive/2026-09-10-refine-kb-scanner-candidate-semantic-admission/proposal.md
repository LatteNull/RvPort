## Why

本 change 按用户最新澄清区分事实采集与迁移判断：架构相关 fact 必须保留；后续有足够证据证明不是执行架构依赖时过滤迁移结论，无法判断则保持 unknown，由后续机制补齐。libarchive 基线仍存在 2 个确认/候选重叠及普通调用误标 intrinsic，不应通过删除事实或强制保留所有 Finding 处理。

## What Changes

- 保留 Frontend、Normalizer、matcher、基础图和 FactProofDemand 的全部原事实与需求。
- 在 Classifier 入口消费同 fact、配置与 occurrence 范围的完整 semantic-role proof：证明为 algorithm/data_format/output_platform 才排除对应候选分类；无证据、partial 或冲突均不能据此排除。
- 明确定义内部排除 proof 合同，当前不新增跨函数用途推理或外部机制接入；现有项目无该类证明的项仍 unknown，不宣称已识别 codec 语义。
- 将所有未决 candidate 的分类 completeness 正确表达为 unknown，不再只对 enum 生效。
- 同 fact 确认知识完全覆盖的 identifier candidate 去重；保留未知 token/其他位置配置。
- 修正普通调用 intrinsic 标签与没有 proof 的 alternative_to 展示；不新增候选选项页面/字段。

## Capabilities

### New Capabilities

- `kb-scanner-candidate-semantic-admission`: 非破坏性、证据驱动的候选分类准入与完整重复覆盖。

### Modified Capabilities

- `kb-scanner-knowledge-and-local-detection`: 保留原名称事实/候选范围，分类排除不能倒灌采集。
- `kb-scanner-classification-and-assessment`: 完整语义排除、未决 unknown 与证明驱动影响。
- `kb-scanner-report-schema-v2`: 正确 unknown 和 intrinsic/alternative 标签，保持现有结构。

## Impact

修改 detector 去重、Classifier 准入/完整性与 V2 投影，不开发用途推理引擎。默认 V2、显式 V1、固定 scan-result.json/scan-report.html/scan.log、Clang/GCC 两份原事实字节/provenance 均保持。不恢复 Legacy，不修改后端/生产镜像/Compose、本机依赖。每个修改业务模块在独立测试容器达到 90% line / 80% branch；仅 C/C++ 静态迁移，不执行项目、不分析 OS、不建模 uname 交叉编译误选。
