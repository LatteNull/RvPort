## ADDED Requirements

### Requirement: E2E 必须覆盖迁移报告模块文件组织能力
独立 API E2E 套件 SHALL 覆盖迁移报告模块、文件、问题类型、finding 和文件联合上下文 API 的正常流程、异常流程与 edge case，并 SHALL 在测试结束后清理创建的数据和对象存储制品。

#### Scenario: 正常流程验证四级组织和联合上下文
- **WHEN** E2E 使用包含多个模块、多个文件和同文件多个 finding 的真实源码 fixture 生成迁移报告
- **THEN** E2E SHALL 依次查询模块、文件、问题类型和 finding API
- **AND** E2E SHALL 校验逐级统计守恒、风险与类型分布、默认行号顺序和分页结果
- **AND** E2E SHALL 校验联合上下文包含首末 finding 的前后最多 20 行及全部高亮
- **AND** E2E SHALL 校验 HTML 与 JSON 报告统计一致

#### Scenario: 正常流程验证依赖独立展示
- **WHEN** 报告同时包含代码 finding 和多个同 provider 软件包的依赖证据
- **THEN** E2E SHALL 校验依赖不出现在代码模块层级
- **AND** E2E SHALL 校验同 provider 的 SO 或 ELF 被聚合为一个依赖主条目

#### Scenario: 异常流程验证权限和路径安全
- **WHEN** 普通用户访问其他项目的报告层级或文件上下文
- **THEN** E2E SHALL 校验请求被拒绝且未泄露报告内容
- **AND** 对路径逃逸或不可读取文件，E2E SHALL 校验返回稳定不可用状态而非服务器绝对路径或底层异常

#### Scenario: Edge case 验证结构化省略和历史版本
- **WHEN** E2E fixture 在同一大文件的远距离行上创建多个 finding，并在报告完成后激活新源码版本
- **THEN** E2E SHALL 校验响应包含可加载的结构化 `OMITTED` block
- **AND** E2E SHALL 校验展开行范围返回真实代码而非省略提示文本
- **AND** E2E SHALL 校验旧报告上下文内容与内容哈希保持不变

#### Scenario: Edge case 验证未定位输入和旧报告兼容
- **WHEN** 报告包含无有效行号的 confirmed finding，且系统中存在没有组织投影的历史报告 fixture
- **THEN** E2E SHALL 校验未定位 finding 仍可查询且不会导致报告失败
- **AND** E2E SHALL 校验历史报告返回组织不可用状态并继续支持平铺输入和制品下载

### Requirement: 迁移报告组织能力必须具有独立单元测试和覆盖率验收
本变更涉及的模块解析、分组聚合、上下文窗口、结构化省略、路径安全和查询逻辑 SHALL 具有不依赖外部服务的单元测试，并 SHALL 满足项目整体与受影响模块的行覆盖率和分支覆盖率至少 90%。

#### Scenario: 单元测试隔离外部连接
- **WHEN** 运行迁移报告组织能力单元测试
- **THEN** 测试 SHALL mock 数据库、对象存储、源码存储及其他 service connection 的返回值
- **AND** 测试 MUST NOT 连接真实数据库、Redis、RabbitMQ、MinIO、SSH 或外部 HTTP 服务

#### Scenario: 覆盖正常异常和边界路径
- **WHEN** 执行本变更的单元测试套件
- **THEN** 测试 SHALL 覆盖正常模块识别与聚合
- **AND** 测试 SHALL 覆盖对象存储失败、路径非法、源码缺失和权限拒绝等异常路径
- **AND** 测试 SHALL 覆盖共享文件、多目标、空报告、空行号、文件边界和远距离 finding 等 edge case

#### Scenario: 覆盖率门槛验收
- **WHEN** 执行项目覆盖率检查
- **THEN** 项目自有可执行代码整体行覆盖率 SHALL 至少为 90%
- **AND** 受影响模块行覆盖率 SHALL 至少为 90%
- **AND** 工具可统计分支覆盖率时，项目整体与受影响模块分支覆盖率 SHALL 至少为 90%
- **AND** 未被测试加载的项目源码 MUST 纳入统计
