## MODIFIED Requirements

### Requirement: 自动呈现批次比较状态和结论

系统 SHALL 依据 `testBatchId` 查询并展示后端自动生成的测试比较。两侧测试未均为终态时系统 MUST 显示等待状态；比较运行中时 MUST 显示进行中；比较完成或不可用时 MUST 显示后端返回的结论、风险/摘要或不可用原因。前端 SHALL 将 `EQUIVALENT`、`DIFFERENT_ACCEPTABLE`、`DIFFERENT_BLOCKING` 和 `INCONCLUSIVE` 映射为中文标签、标题与对应语义色，不得直接展示后端英文枚举。系统 MUST NOT 提供手动发起比较操作。

#### Scenario: 两侧完成后显示自动比较结果

- **WHEN** 同一批次的源端和目标端测试均已结束且后端比较完成
- **THEN** 系统显示该批次的中文比较结论和风险信息

#### Scenario: 比较无法生成

- **WHEN** 后端将该批次比较标记为不可用或返回不可用原因
- **THEN** 系统展示不可用状态及原因，而不把它显示为测试失败
