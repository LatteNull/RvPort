## ADDED Requirements

### Requirement: 自动化测试运行时必须保存有序合并日志
自动化测试运行时 SHALL 在测试执行阶段保存 stdout 和 stderr 的有序合并日志，并 SHALL 将该日志作为测试结果比较的主要日志材料。

#### Scenario: 写入 merged log
- **WHEN** worker 执行自动化测试命令并读取 stdout 或 stderr
- **THEN** 后端 SHALL 按读取顺序写入 merged log
- **AND** 每个日志片段 SHALL 保留 stream 来源，区分 `STDOUT` 和 `STDERR`
- **AND** 后端 MUST NOT 只在任务结束后通过拼接 stdout.log 和 stderr.log 生成 merged log

#### Scenario: 保留原始分流日志
- **WHEN** 自动化测试完成
- **THEN** 后端 MAY 继续保存 stdout.log 和 stderr.log 作为调试材料
- **AND** 测试详情或日志查询 SHALL 能区分 merged log 与分流日志

#### Scenario: 测试比较优先使用 merged log
- **WHEN** 测试结果比较聚合自动化测试日志
- **THEN** 后端 SHALL 优先读取 merged log 作为 agent 输入
- **AND** stdout/stderr 分流日志 SHALL 只作为补充调试材料

#### Scenario: 旧记录没有 merged log
- **WHEN** 历史测试记录没有 merged log
- **THEN** 后端 MAY 回退到既有 stdout/stderr 日志摘要
- **AND** 比较输入 SHALL 记录日志材料发生降级
