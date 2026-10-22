## Context

当前后端已有 `migration_input_sets` 和 `migration_input_refs`，用于把 KB finding、依赖分析结果和历史 SBOM result 统一成报告输入 reference。报告生成只读取 `CONFIRMED` reference，这个模型仍然有效。

问题在于“迁移输入合并”作为独立节点存在额外流程：用户需要先在分析节点查看结果，再去合并节点选择来源、自动合并、确认状态。现在产品决策改为在各分析节点内完成确认，独立合并节点不再作为主流程存在。

## Goals / Non-Goals

**Goals:**
- 移除独立迁移输入合并节点和自动合并主流程。
- 保留 `migration_input_refs` 作为报告输入事实来源，降低报告、复检、归档和历史报告改动面。
- 让 KB、依赖分析等节点在结果产生后创建或维护 migration input reference。
- 统一默认确认策略：`CRITICAL`、`HIGH`、`MEDIUM`、`INFO`、`COMMENT` 默认进入报告；`LOW` 默认不进入报告。
- 节点结果列表支持人工撤回和人工加入，最终仍通过 `CONFIRMED` 控制报告输入。
- 新流程删除 SBOM 前序入口，SBOM 只保留历史数据兼容。

**Non-Goals:**
- 不删除 `migration_input_sets` 和 `migration_input_refs` 数据表。
- 不实现新的冲突合并算法。
- 不把测试比较、优化闭环等非迁移输入来源强行纳入报告输入。
- 不迁移或重写历史报告快照。

## Decisions

### 保留 reference 表，不保留独立合并节点

`migration_input_refs` 继续作为报告输入统一层。各节点把结果映射为 reference，报告、复检和比较继续读取 reference，而不是直接读取所有来源表。

替代方案是让报告直接读取 KB、依赖分析等原始结果表。该方案会让报告逻辑耦合每个节点，并且难以保存用户确认状态和备注，因此不采用。

### 默认确认状态由风险等级决定

导入或自动维护 reference 时，后端根据风险等级设置默认状态：

- `CRITICAL`、`HIGH`、`MEDIUM`、`INFO`、`COMMENT` -> `CONFIRMED`
- `LOW` -> `CANDIDATE`

`EXCLUDED` 只表示用户明确撤回或排除，不作为自动默认值。

风险等级需要先归一化：KB 使用 `finding.severity`；依赖分析使用 `riskLevel`；历史 SBOM 兼容读取使用 `riskLevel`。依赖分析写入 `detectedLevel` 时仍保留 `riskLevel + "/" + targetMatchStatus`，默认确认判断只使用 `/` 前的风险 token。

### 节点内确认复用通用状态更新能力

各节点可以提供节点作用域的“加入报告/撤回报告”操作，也可以复用通用 `PATCH /api/migration-inputs/{id}`。前端不再需要独立合并页，但仍可以通过 reference ID 修改状态和备注。

### SBOM 从新流程中移除

新流程不再创建 `SBOM_RESULT` migration input，不再默认展示 SBOM 作为前序可选来源。已有 `SBOM_RESULT` 数据只用于旧报告快照和历史详情兼容，后续看到新流程 SBOM 自动合并入口可以删除。

## Risks / Trade-offs

- [Risk] 自动默认 `INFO/COMMENT` 进入报告可能带来报告内容偏多。  
  Mitigation: 用户可在节点内撤回；后续可增加批量撤回和过滤。

- [Risk] KB severity 当前是字符串，大小写和未知值可能不一致。  
  Mitigation: 实现时增加统一风险 token normalization，未知值默认按 `INFO` 或显式 `COMMENT` 处理并记录测试。

- [Risk] 删除自动合并入口会影响旧 E2E 或调试脚本。  
  Mitigation: change 中同步调整 E2E；如保留 API，也必须标记 deprecated 且新主流程不使用。

- [Risk] 历史 SBOM reference 仍存在，可能在页面中误认为新流程能力。  
  Mitigation: API 响应和文档明确 `SBOM_RESULT` 仅历史兼容，新建和自动生成逻辑不再产生。

## Migration Plan

1. 保留数据库结构。
2. 修改 migration input 创建逻辑，支持按风险等级设置默认状态。
3. 在 KB 扫描和依赖分析任务完成后创建或同步对应 reference。
4. 调整 API 文档和 E2E，移除独立 auto-merge 主流程覆盖。
5. 保留历史 SBOM 详情解析，禁止新流程自动创建 `SBOM_RESULT` reference。

Rollback 可以恢复旧 auto-merge API 调用路径，因为底层 reference 表未删除。
