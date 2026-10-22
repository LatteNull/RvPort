## MODIFIED Requirements

### Requirement: 分类评估必须保持输出兼容并通过独立容器门禁
本 capability 的每个新增或实质修改业务模块 SHALL 映射到隔离单元测试，并 SHALL 在唯一 `kb-scanner-test` 容器中通过逐模块至少 90% line / 80% branch 门禁、测试选择/分类/评估 component tests、无副作用测试和完整回归。Default staged profile SHALL 把 Classification/Assessment 交给正式 Compatible Report Projector，并 SHALL 保持 `schemaVersion: "1.0"`、既有顶层字段、三个 artifact、Finding/summary 兼容语义及 Clang/GCC 两份事实 JSON 不变；Legacy YAML/`generatedSet` SHALL 只作为冻结 oracle 资产而不得被新分类、评估或投影读取。

#### Scenario: 审计测试清单
- **WHEN** 新增、删除或重命名 test analyzer/detector、classifier、assessor、policy/lattice、projection 或组合 profile 模块
- **THEN** 机器可读 inventory SHALL 同步映射隔离 unit suite、fake/mock 边界和适用高层测试
- **AND** 缺失映射、未执行模块或覆盖不足 SHALL 使容器门禁失败

#### Scenario: 验证恶意测试命令
- **WHEN** fixture 含 CTest command、Make test recipe、RPM `%check`、wrapper、plugin、response file 或其他可执行文本
- **THEN** scanner 和测试 SHALL 只恢复静态 Evidence 并保持 marker/workspace/外部状态不变
- **AND** 它们 MUST NOT 启动 compiler、build tool、test runner、项目命令或网络访问

#### Scenario: default profile 产生分类和评估
- **WHEN** 新 Classifier/Assessor 在 default staged profile 中运行
- **THEN** Compatible Report Projector SHALL 将 Classification 投影为现有 Finding，并将项目 Assessment 投影到可选 `summary.readiness`
- **AND** 它 MUST NOT 写入第二套主结果、把 provisional/unknown 升级为 ready 或声称已真实编译/测试

#### Scenario: qualification 保持无副作用
- **WHEN** 同一 Classifier/Assessor 在 qualification profile 中运行
- **THEN** recording/no-op Projector SHALL 观察内部 Classification/Assessment 且返回零 artifact
- **AND** qualification MUST NOT 覆盖 default scan 的正式输出
