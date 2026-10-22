## Why

默认 V2 报告的 `conclusion.suggestion` 仍使用硬编码英文，未体现默认中文展示；同一通用建议还会让 unknown 或 inactive 结果看起来像已确认需要补充实现。用户要求建议全部使用中文，同时在 V2 增加 `suggestion_en`，保留语义一致的英文建议供消费者选用。

## What Changes

- 新生成 V2 Finding 的 `conclusion.suggestion` 固定为中文，新增同级 `suggestion_en` 固定为英文，两者均为非空建议，不随 `--locale` 交换字段含义。
- 根据已有结论区分已确认问题、非阻断问题/迁移缺口、已排除路径、提示及 unknown/partial/ambiguous；文案不得把候选当作确定依赖，或暗示静态扫描已经完成编译和测试。
- 更新 V2 模型、JSON Schema、合同测试及示例：新 producer 始终输出双语字段，更新后的 reader 允许历史结果缺少 `suggestion_en`；不回写历史结果或依赖 V1 生成 V2。
- HTML 默认展示中文建议，英文保留在 JSON；本次不汉化 title、reason、证据节点说明、诊断、状态码和日志，也不新增语言切换 UI。
- 保留默认 V2、显式 V1 及三个 artifact。V1 的 `suggestion`/`suggestion_en` 不变，两份编译器事实及分类、评估、ID、源码链和上下文不变。
- **BREAKING（旧严格 V2 校验器）**：旧 `conclusion.additionalProperties=false` 会拒绝新字段，严格消费者须升级 Schema/模型；不能把新 reader 读取旧报告的兼容性说成旧 reader 一定接受新报告。
- 每个新增/实质修改业务模块同步补隔离单测；在独立测试容器验证项目整体及每个受影响模块至少 90% 行/90% 分支覆盖率，统计包含未被测试加载的自有源码。

## Capabilities

### New Capabilities

无；扩展现有报告能力，不引入新扫描阶段或新主结果。

### Modified Capabilities

- `kb-scanner-report-schema-v2`：规定双语建议字段、基于已有结论的保守建议、历史读取与新 producer 合同、中文 HTML 展示和隔离测试验收。

## Impact

- 预计修改 `kb_scanner/projection/v2/mapper.py`、`models.py`，新增纯展示策略模块 `suggestions.py`；若 producer 校验需要接线到 `projector.py`/`validation.py`，一并登记隔离单测。`renderers.py` 当前直接展示 suggestion，先验证无需修改，若修改也须补其隔离单测。
- 更新 V2 Schema/vocabulary、建议相关 unit inventory、代表性报告、差异账本及消费者迁移文档；只批准建议字段和文案引起的 V2 字节变化，不批量覆盖无法解释的 golden。
- 不增加依赖，不修改 backend/frontend、Compose、生产容器或其他任务目录；不安装本机依赖。范围限 C/C++ x86→RISC-V 静态迁移报告，不涉及操作系统迁移、真实编译或测试执行。
- 原 `clang-x86-entries.json`、`gcc-x86-entries.json` 的内容、哈希和 provenance 原样保留，不修改或重新采集知识数据。
