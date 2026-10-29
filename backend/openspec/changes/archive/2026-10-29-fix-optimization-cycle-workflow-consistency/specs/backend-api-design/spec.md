## MODIFIED Requirements

### Requirement: API 必须提供优化轮次聚合查询
后端 API SHALL 提供项目级优化轮次概览、列表和详情接口，用于展示多轮优化结果聚合；当前轮次的有效验证摘要 SHALL 复用与项目 overview 和优化 latest 相同的解析规则。

#### Scenario: 查询当前优化概览
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/optimization/overview`
- **THEN** 后端 SHALL 校验用户有权访问该项目
- **AND** 响应 SHALL 返回当前 active 源码版本对应的优化轮次
- **AND** 响应 SHALL 包含迁移输入、报告、复检、源码部署、构建、测试和测试结果比较摘要，并区分当前有效验证事实与原始历史事实
- **AND** 响应 MUST NOT 返回完整日志、完整报告正文、完整 agent 输入、明文凭据或服务器真实路径

#### Scenario: 查询优化轮次列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/optimization/cycles`
- **THEN** 后端 SHALL 返回该项目优化轮次分页列表
- **AND** 列表接口 SHALL 支持按 `sourceRevisionId`、`status` 和时间范围过滤
- **AND** 列表接口 SHALL 支持按 `cycleNumber`、`createdAt`、`updatedAt` 和 `startedAt` 排序
- **AND** 当前轮次 SHALL 使用统一当前摘要，非当前轮次 SHALL 保留历史事实摘要且不参与当前 workflow 完成判断

#### Scenario: 查询优化轮次详情
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/optimization/cycles/{cycleId}`
- **THEN** 后端 SHALL 校验该轮次属于该项目
- **AND** 响应 SHALL 返回轮次元数据、源码版本摘要、聚合摘要和相关资源引用
- **AND** 响应 MUST NOT 返回任何子节点的完整日志正文、对象存储内部 key 或服务器真实路径
- **AND** 失效 SHALL 只改变当前资格，MUST NOT 删除历史事实或隐藏整个历史轮次

#### Scenario: 优化轮次 API 不触发任务
- **WHEN** 用户查询优化概览、轮次列表或轮次详情
- **THEN** 后端 MUST NOT 创建扫描、报告、复检、源码部署、构建、测试或测试比较任务
- **AND** API SHALL 只返回已有事实数据的聚合展示和派生验证状态

## ADDED Requirements

### Requirement: 优化闭环读取必须保持状态与有效结果一致
项目 overview、优化 overview、latest 及当前轮次摘要 SHALL 使用同一有效验证解析，轮次存在或 latest CURRENT MUST NOT 单独构成优化完成条件。

#### Scenario: 源码就绪但未验证
- **WHEN** 项目刚激活源码且尚无当前双端构建和测试
- **THEN** 项目 overview 的 OPTIMIZE SHALL 为 PENDING，优化 latest SHALL 可返回 CURRENT 轮次及未满足验证事实
- **AND** 对应当前摘要 MUST NOT 含可使现有前端判定本轮验证通过的成功组合

#### Scenario: 同一快照读取
- **WHEN** 读取响应期间并发切换源码、环境配置或写入新的验证任务
- **THEN** 单次响应的 Context、结果引用、新鲜度及状态 SHALL 来自同一一致快照
- **AND** 相同数据库快照下各当前读取入口 SHALL 产生相同验证结论
- **AND** 不同请求间真实数据变更导致的差异 MUST NOT 被误判为同次响应允许混用上下文

#### Scenario: optimize readiness 可查看未完成轮次
- **WHEN** 当前 active 源码存在但验证链未完成
- **THEN** optimize readiness 的 ACTIVE_SOURCE SHALL 保持 SATISFIED，允许前端查看缺失或失败事实
- **AND** 后端 MUST NOT 将“可以查看”表达为 workflow DONE，也 MUST NOT 为查看强制要求比较通过
- **AND** readiness SHALL 保留事实项协议，不新增 UI 按钮或动作字段

### Requirement: 优化修复必须兼容现有前端消费字段
后端 SHALL 保留现有 API 路径、latest 外壳、轮次生命周期枚举及 `summary.build/test`、`summary.testComparison` 的字段类型，通过当前有效摘要修正现有前端判定；本 change MUST NOT 修改前端代码或前端 OpenSpec。

#### Scenario: 当前摘要控制下一步
- **WHEN** 现有前端依次判断 build.latestStatus、test.latestStatus 是否为 SUCCEEDED，以及比较 overallStatus 或 status 是否为 EQUIVALENT
- **THEN** 该成功组合 SHALL 当且仅当后端 OPTIMIZE 为 DONE 时出现
- **AND** 后端 SHALL 提供与同一验证事实一致的 nextAction，但 MUST NOT 依赖旧前端消费新增字段才能完成修复

#### Scenario: 双端汇总必须可追溯
- **WHEN** 后端返回当前双端阶段摘要
- **THEN** latestStatus SHALL 表达双端有效阶段状态，单侧成功且另一侧缺失时 MUST NOT 为 SUCCEEDED
- **AND** latestRunId 及时间 SHALL 引用实际代表记录；空状态的代表引用 SHALL 为空
- **AND** 增量验证事实 SHALL 给出决定状态的安全引用及失效原因，历史统计与当前统计 SHALL 明确区分

#### Scenario: 历史页面兼容
- **WHEN** 现有前端按只读记录方式展示历史轮次
- **THEN** 后端 SHALL 保留历史摘要字段可读，且 STALE latest MUST NOT 进入当前结果
- **AND** 对接说明 SHALL 明确既有历史通用标题不代表当前验证通过，新增原因细节展示不属于本次前端修改

#### Scenario: 新增展示字段
- **WHEN** 后端增加 validation、历史摘要或 nextAction 的业务说明
- **THEN** SHALL 同时提供中文和英文字段及稳定原因码
- **AND** MUST NOT 将日志、服务器路径或异常堆栈作为前端业务说明

#### Scenario: 权限与空数据
- **WHEN** 无权限用户请求优化读取，或有权限用户查询尚无子执行的轮次
- **THEN** 无权限请求 SHALL 被拒绝且不泄露轮次存在性
- **AND** 合法空数据请求 SHALL 保持现有成功外壳与空摘要约定，MUST NOT 发生空指针或伪造成功结果

### Requirement: 优化一致性修改必须完成完整 Docker 运行验收
实施交付 SHALL 从仓库根目录完成全部默认服务的 Compose 构建，并以一次 `docker compose up -d --wait` 启动全部默认服务进行运行验收；所有验证 SHALL 使用独立资源并保留证据。

#### Scenario: 隔离完整运行验收
- **WHEN** 后端单元测试和覆盖率门槛通过
- **THEN** SHALL 使用专用 Compose project、测试 env、网络、数据卷及端口顺序构建并设置适当 CPU、内存和并发限制
- **AND** SHALL 检查所有默认服务健康、日志以及首次源码上传但未构建时的 overview/latest/readiness 和历史查询
- **AND** MUST NOT 连接已有部署数据库或真实 SSH，也 MUST NOT 用旧镜像、旧报告替代当前源码验证

#### Scenario: 完整证据与阶段交接
- **WHEN** 汇总验收结果
- **THEN** SHALL 记录命令、退出码、测试数量、覆盖率统计范围和报告位置、服务状态及实际执行的业务场景
- **AND** 单元测试、隔离数据库验证与 Compose 业务验证 SHALL 分别说明，MUST NOT 宣称未执行的真实端到端验证
- **AND** 任一必需任务未完成时 MUST NOT 提示已具备归档条件
