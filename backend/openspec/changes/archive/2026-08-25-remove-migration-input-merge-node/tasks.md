## 1. 迁移输入默认确认规则

- [x] 1.1 增加统一风险等级归一化逻辑，支持 `CRITICAL`、`HIGH`、`MEDIUM`、`LOW`、`INFO`、`COMMENT`，并处理大小写和未知值。
- [x] 1.2 调整 migration input candidate 或 repository 插入逻辑，使新 reference 可按风险等级写入默认状态。
- [x] 1.3 实现默认状态规则：`CRITICAL/HIGH/MEDIUM/INFO/COMMENT` 写入 `CONFIRMED`，`LOW` 写入 `CANDIDATE`。
- [x] 1.4 保证 `EXCLUDED` 只由人工撤回或显式更新产生，不作为自动默认状态。

## 2. 节点内确认能力

- [x] 2.1 在 KB 扫描成功写入 findings 后，为当前源码版本创建或维护 `KB_FINDING` migration input reference。
- [x] 2.2 在依赖分析成功写入 result items 后，为当前源码版本创建或维护 `DEPENDENCY_RESULT` migration input reference。
- [x] 2.3 支持节点结果通过已有 migration input 状态更新能力进行人工加入、撤回和备注更新。
- [x] 2.4 确保重复创建同一 `sourceType + sourceRefId` 时幂等跳过或更新，不产生重复 reference。

## 3. 移除独立合并主流程

- [x] 3.1 将 `migration-inputs:auto-merge` 从新主流程中移除，返回 deprecated 业务错误或保留受控兼容响应。
- [x] 3.2 禁止新流程通过 `SBOM_RESULT` 创建 migration input reference。
- [x] 3.3 保留历史 `SBOM_RESULT` 详情读取兼容，避免旧报告快照或历史数据查询失败。
- [x] 3.4 更新 API 文档，明确迁移输入列表和详情是节点内确认与报告审计能力，不再对应独立合并节点。

## 4. 报告链路

- [x] 4.1 确认报告生成仍只读取 `status=CONFIRMED` 的 reference。
- [x] 4.2 确认默认 `LOW/CANDIDATE` 不进入报告，人工加入后可以进入报告。
- [x] 4.3 确认默认 `CONFIRMED` 的 `CRITICAL/HIGH/MEDIUM/INFO/COMMENT` 可以进入报告，人工撤回后不进入报告。
- [x] 4.4 确认报告输入快照继续保存 reference 展示字段、确认状态、备注和真实来源详情。

## 5. 测试

- [x] 5.1 补充风险等级归一化和默认状态规则单元测试，覆盖正常流程、异常流程和 edge case。
- [x] 5.2 补充 KB 节点内确认测试，覆盖默认确认、低风险候选、人工加入和人工撤回。
- [x] 5.3 补充依赖分析节点内确认测试，覆盖组合 `detectedLevel`、默认确认、低风险候选和幂等创建。
- [x] 5.4 更新 E2E，移除对独立自动合并主流程的依赖，并覆盖节点内确认到报告生成链路。
- [x] 5.5 运行 `mvn test`。
- [x] 5.6 运行相关 E2E 模块并确认清理逻辑不会留下脏数据。

## 6. OpenSpec 与文档验证

- [x] 6.1 更新 `backend/docs/API_DESIGN.md` 和相关覆盖文档，删除新流程中的 SBOM 前序和独立合并节点说明。
- [x] 6.2 运行 `openspec validate remove-migration-input-merge-node --strict`。
- [x] 6.3 运行 `openspec validate --specs --strict`。
