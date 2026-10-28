## MODIFIED Requirements

### Requirement: KB 扫描必须自动复用构建上下文 compile database
KB 扫描运行时 SHALL 使用创建任务时绑定并校验成功的 source/x86 `SOURCE_ONLY` 构建，在其 compile database 可用时自动传给 KB Scanner；MUST NOT 在执行时重新选择其他成功构建。

#### Scenario: 自动使用绑定的成功构建上下文
- **WHEN** worker 执行具有完整上下文且前置校验通过的 `KB_SCAN` 任务
- **AND** 绑定构建的 `build_facts.compileDatabase.available=true`
- **THEN** worker SHALL 从对象存储下载对应 compile database 到受控临时文件
- **AND** worker SHALL 调用 KB Scanner 时传入 `--compile-commands <temp-file>`
- **AND** `kb_scan_runs.summary.compileCommands.mode` SHALL 为 `USED`
- **AND** summary SHALL 记录绑定 build run ID、stored artifact ID、sha256 和 command count

#### Scenario: 成功构建没有编译数据库时降级扫描
- **WHEN** worker 已确认绑定构建成功且仍满足开始执行的前置条件
- **AND** 该构建没有可用 compile database
- **THEN** worker SHALL 不传 `--compile-commands` 并继续源码上下文扫描
- **AND** `kb_scan_runs.summary.compileCommands.mode` SHALL 为 `NOT_AVAILABLE`
- **AND** summary SHALL 保存绑定构建 ID 与安全原因码

#### Scenario: 没有成功构建不得降级执行
- **WHEN** worker 无法证明绑定构建满足项目、源码、源环境、运行环境版本、`SOURCE_ONLY` 范围和成功状态要求
- **THEN** worker SHALL 受控失败并记录安全原因
- **AND** worker MUST NOT 启动 scanner、导入 findings 或标记扫描成功

#### Scenario: artifact 下载失败时降级扫描
- **WHEN** 成功绑定构建的 compile database artifact 缺失、下载失败、所有权不符或内容不可用
- **THEN** worker SHALL 记录 warning 并继续现有路径脱敏和所有权保护
- **AND** worker SHALL 不传 `--compile-commands`，按源码上下文扫描继续执行
- **AND** `kb_scan_runs.summary.compileCommands.mode` SHALL 为 `FALLBACK`
- **AND** summary SHALL 保存绑定构建 ID 与安全原因码
- **AND** worker MUST NOT 改用其他构建的 artifact

#### Scenario: 源码版本隔离
- **WHEN** 项目上传或同步新源码并产生新的 `source_revision_id`
- **THEN** KB 扫描 MUST NOT 复用其他源码版本的 compile database
- **AND** 后端 SHALL 验证绑定构建与本次 scan run 的 `source_revision_id` 一致

#### Scenario: 扫描输出继续脱敏
- **WHEN** KB Scanner 使用 compile database 产生 findings、diagnostics、stdout、stderr 或 artifacts
- **THEN** 后端 SHALL 继续执行现有路径脱敏和输出安全处理
- **AND** API、SSE 和 artifact summary MUST NOT 暴露 compile database 临时路径、远端路径或对象存储 key

### Requirement: 知识库扫描必须提供 latest
知识库扫描领域 SHALL 提供当前 Context 下的 latest 接口，使用完整执行上下文判断当前性，并分别表达执行终态与结果是否仍适用。

#### Scenario: 查询知识库扫描 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/kb-scans/latest`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `context.sourceRevisionId` SHALL 为项目当前 active source revision
- **AND** `CURRENT` 记录 SHALL 匹配当前项目、active source、源环境、运行环境版本和当前选中的成功 `SOURCE_ONLY` 构建 ID
- **AND** `execution` SHALL 指向该有效上下文内最新活动扫描任务，否则指向最近创建的终态扫描任务
- **AND** `result` SHALL 包含对应扫描摘要、finding 数量、artifact 摘要及安全执行上下文
- **AND** 相同创建时间 SHALL 使用 ID 作为稳定排序条件

#### Scenario: 知识库扫描 latest 识别旧源码
- **WHEN** 只有旧源码版本的知识库扫描记录存在
- **THEN** latest SHALL 返回最近创建的历史记录且 `freshness=STALE`
- **AND** 后端 MUST NOT 将该记录标记为 `CURRENT`

#### Scenario: 环境或构建变更使旧扫描失效
- **WHEN** 扫描关联的源环境、运行环境版本或构建 ID 与当前有效上下文不同，或当前 x86 构建尚未成功
- **AND** 没有其他当前有效扫描记录
- **THEN** latest SHALL 返回历史记录并标记 `STALE`，提供环境变化、构建变化或构建未就绪的安全原因
- **AND** 后端 MUST NOT 修改历史执行的真实状态

#### Scenario: 缺少上下文的旧扫描
- **WHEN** 历史扫描缺少源环境、运行环境版本或绑定构建 ID
- **THEN** 后端 SHALL 将其视为 `STALE`，原因包含 `KB_SCAN_CONTEXT_UNKNOWN`
- **AND** 后端 MUST NOT 仅根据源码相同、summary 中孤立的构建 ID 或时间接近猜测为当前有效

#### Scenario: 当前失败或活动扫描优先于旧成功
- **WHEN** 同一有效上下文存在活动扫描，或最新终态扫描为失败、取消、超时
- **THEN** latest SHALL 返回活动扫描优先、否则最近终态的记录及真实状态
- **AND** 后端 MUST NOT 回退到更早的成功扫描

#### Scenario: 无 active source 但存在历史
- **WHEN** 项目没有 active source 但存在扫描历史
- **THEN** latest SHALL 返回历史记录且 `freshness=STALE`

#### Scenario: 无扫描记录
- **WHEN** 项目不存在任何扫描记录
- **THEN** latest SHALL 返回 `EMPTY`，`execution` 和 `result` 为 null
- **AND** 后端 MUST NOT 以 404 表达无记录

### Requirement: 知识库扫描 readiness 必须校验 active source 和 x86 构建
项目级 readiness 在 `stageId=kb` 时 SHALL 返回知识库扫描所需的源码与 x86 构建前置条件，并 SHALL 与创建接口和当前结果选择使用同一构建规则。

#### Scenario: active source 已存在
- **WHEN** 项目存在 active source revision
- **THEN** `ACTIVE_SOURCE` prerequisite SHALL 返回 `SATISFIED`
- **AND** `referenceId` SHALL 指向 active source revision

#### Scenario: 当前上下文 x86 构建成功
- **WHEN** 当前源码、源环境和运行环境版本下按活动优先、否则最近创建规则选中的 `SOURCE_ONLY` 构建为成功
- **THEN** `X86_BUILD` prerequisite SHALL 返回 `SATISFIED`
- **AND** `referenceId` SHALL 指向该构建

#### Scenario: 当前上下文 x86 构建尚未成功
- **WHEN** 当前上下文没有 x86 source-only 构建，或选中的构建处于排队、运行、失败、取消或超时状态
- **THEN** `X86_BUILD` prerequisite SHALL 返回对应的 `MISSING`、`RUNNING` 或 `FAILED`
- **AND** 知识库分析 SHALL NOT 被 readiness 表示为可开始
- **AND** 后端 MUST NOT 用更早成功构建、其他环境版本构建或 `BOTH` 构建替代该前置条件

#### Scenario: active source 缺失
- **WHEN** 项目不存在 active source revision
- **THEN** `ACTIVE_SOURCE` prerequisite SHALL 返回 `MISSING`
- **AND** `reasonCode` SHALL 为 `ACTIVE_SOURCE_MISSING`

## ADDED Requirements

### Requirement: KB 创建与 worker 必须固定并校验执行上下文
后端 SHALL 在创建事务内重新校验请求源码的 x86 构建前置条件，并完整保存绑定上下文。worker SHALL 在开始执行前复核该上下文，不自动补绑或切换构建。

#### Scenario: 创建时前置条件不满足
- **WHEN** 请求源码在当前运行环境版本下没有满足条件的成功构建
- **THEN** 后端 SHALL 返回 `409 PREREQUISITE_NOT_SATISFIED`
- **AND** 后端 MUST NOT 留下任务、扫描记录或队列消息

#### Scenario: 显式历史源码执行
- **WHEN** 有权限用户显式指定本项目历史源码，且该源码在当前运行环境下满足同一构建前置规则
- **THEN** 后端 SHALL 允许创建并绑定该源码的成功构建
- **AND** 结果 MUST NOT 占用其他 active source 的当前状态
- **AND** 跨项目源码请求 SHALL 继续按既有权限策略拒绝且不泄露其他项目资源细节

#### Scenario: 创建事务内上下文变化
- **WHEN** 前置校验后、事务提交前选中构建或运行环境版本发生变化
- **THEN** 后端 SHALL 通过事务锁或条件重验拒绝不一致写入并回滚全部任务创建副作用

#### Scenario: 排队期间执行前置变化或旧任务缺失上下文
- **WHEN** worker 开始时当前环境版本或针对绑定源码选中的构建与记录不一致，或旧任务没有完整绑定上下文
- **THEN** worker SHALL 受控失败并保存安全原因
- **AND** worker MUST NOT 启动 scanner 或自行查找其他成功构建执行

#### Scenario: 排队期间仅切换 active source
- **WHEN** active source 已切换但绑定源码仍存在，且该源码的绑定构建及环境版本仍满足执行前置条件
- **THEN** worker SHALL 允许按固定历史源码执行
- **AND** 该运行 SHALL 在当前项目查询中判为历史而非当前结果

#### Scenario: 执行期间上下文变化
- **WHEN** scanner 启动后项目切换源码、环境版本变化或出现新的 x86 构建
- **THEN** worker SHALL 保持原绑定输入并保存真实执行终态
- **AND** 对当前上下文的查询 SHALL 将该运行判为历史，不以其成功覆盖当前工作流状态

### Requirement: KB 当前结果消费者必须遵守统一有效性
后端 SHALL 将同一有效性选择应用于默认当前扫描列表、当前性标记、报告 KB 前置条件和新报告的 KB 来源自动选择；历史详情、确认记录和既有报告快照 SHALL 保留。

#### Scenario: 报告不得隐式复用过期 KB
- **WHEN** 当前仅有过期 KB 扫描或其历史 confirmed finding 引用
- **THEN** 报告 readiness 的 KB 前置 SHALL 不满足
- **AND** 新报告输入解析 MUST NOT 自动将这些结果当作当前有效 KB 证据
- **AND** 通过既有错误机制拒绝或明确过滤过期来源时 SHALL 保留历史记录以供审计

#### Scenario: 当前列表和当前性标记
- **WHEN** 用户查询默认 `currentOnly` 列表或扫描的当前性标记
- **THEN** 后端 SHALL 使用完整有效上下文判定，不能仅比较源码 ID

#### Scenario: 历史详情仍然可用
- **WHEN** 用户查询有权限的历史列表、详情或下载
- **THEN** 后端 SHALL 保留原状态、findings 与 artifact 的查询能力，并表达是否仍适用于当前上下文

### Requirement: KB 工作流一致性必须通过单元测试和覆盖率验收
实施 SHALL 在 Docker 中维护和运行覆盖正常、边界与异常路径的单元测试，整体及受影响模块的行覆盖率和可用分支覆盖率均至少 90%，并保留更严格门槛。

#### Scenario: 自动验收覆盖率
- **WHEN** 从当前源码构建专用测试镜像并执行后端完整单元验证
- **THEN** JaCoCo SHALL 统计全部自有 Java 可执行源码，包括未加载类，并自动校验 BUNDLE 和各 PACKAGE 的 LINE/BRANCH 门槛
- **AND** 排除项 SHALL 仅包含有明确理由的生成类型和第三方实现，不能排除自有业务逻辑
- **AND** 后端资源 Python SHALL 使用现有独立统计入口验收，不以 Java 通过代替

#### Scenario: 失败或历史缺口
- **WHEN** 单元测试失败、覆盖率未达标或环境阻塞导致检查未执行
- **THEN** 交付记录 SHALL 列出实际命令、退出状态、行/分支指标、统计范围和报告位置，未取得指标标为不可用
- **AND** 质量验收任务 SHALL 保持未完成
- **AND** 需要大规模无关改造时 SHALL 报告差距并请求扩大范围，不能缩小分母或降低门槛
