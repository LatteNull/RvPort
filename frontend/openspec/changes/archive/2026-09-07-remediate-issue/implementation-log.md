# Implementation Log

本文件按发生顺序记录 `remediate-issue` 完善周期内的实际改动。日志只追加、不覆盖；目标状态和剩余工作以 `tasks.md` 为准，契约和决策以 `design.md`、`specs/` 为准。

每次修改至少记录：

- 日期与顺序。
- 对应 task。
- 实际改动及影响范围。
- 验证结果。
- 是否仍有后端依赖或后续纠偏。

## 2026-09-02

### 01. 当前运行环境改为 overview 单一读取来源

- 对应任务：7.1、7.2、7.3。
- 将环境、SBOM、构建、依赖分析和自动化测试 Drawer 迁移到 overview 已有运行环境数据。
- 删除 frontend `useProjectRuntimeEnvironments` 和 GET `/runtime-environments` 请求封装。
- PATCH 当前运行环境、编辑或检查当前环境后刷新 overview 及当前 Context 下游查询。
- 后续：后端联调完成后删除 GET Controller 路由，见 2.7、8.8。

### 02. 当前源码改为 overview 单一读取来源

- 对应任务：7.4。
- 源码管理与归档共享 overview 当前源码，删除 `active=true&pageSize=1` 对当前源码的重复推算。
- 后续：目标 overview 改为 `currentContext.activeSourceRevision` 后更新类型和转换，见 8.1。

### 03. 统一阶段状态与操作层级

- 对应任务：7.6 至 7.10。
- 新增共享前置条件提示和 `StageStateNotice`，统一前置条件不满足、暂无数据、执行中、执行失败和接口失败状态。
- 知识库扫描、依赖分析和评估报告完成迁移。
- 核心业务操作保持唯一主按钮，重新执行使用普通按钮，查看历史记录置于末尾并使用文字链接。
- 后续：SBOM、归档等页面继续迁移，见 8.7。

### 04. 知识库扫描历史记录

- 对应任务：7.5。
- 增加查看历史记录入口、分页历史、当前/历史 Context 标识和扫描详情/产物查看。
- 当前使用既有 List 接口。
- 后续：后端 latest 和稳定 `createdAt` 倒序可用后切换当前记录与排序，见 8.3、8.6。

### 05. 依赖自动修复

- 对应任务：7.11 至 7.13。
- 增加候选项 API、选择交互、自动修复任务创建和修复后重新分析选项。
- 覆盖默认提交、空候选项和失败状态测试。
- 后续：切换到 dependency latest 与 `TARGET_ENVIRONMENT` prerequisite，见 8.9。

### 06. 报告纳入状态单条操作

- 对应任务：7.14、7.15。
- 在当前知识库 finding 与依赖结果详情展示纳入状态，将“纳入报告 / 排除”放入 Drawer Footer。
- 更新成功后刷新详情与来源列表，历史依赖分析详情保持只读。
- 后续：后端批量接口可用后增加批量操作，并统一刷新 `INCLUDED_FINDINGS`，见 6.x、8.10。

### 07. 项目任务 SSE frontend 可靠性

- 对应任务：7.16 至 7.21、7.24、7.31。
- 使用 overview `latestTaskEventId` 建立项目级 SSE，增加事件 ID 去重、断线续传、指数退避、可见性刷新和定时刷新兜底。
- 集中 task type、Query Key 失效和终态 notification；新增应用级 notification 注册桥接。
- 当前 progress 仍兼容写入现有 overview 任务缓存。
- 后续：统一后端 envelope 后按 `stageId/resource` 更新领域 latest，不再把任务进度写入 overview，见 3.x、8.5、8.12。

### 08. 统一历史列表与只读详情导航

- 对应任务：7.25 至 7.29。
- 新增 `RecordViewTitle`。
- 补充 SBOM、自动化测试、优化轮次和归档的当前结果、历史列表、历史只读详情、返回路径和刷新入口。
- 自动化测试补充批次历史、日志、比较结果、前置条件和配置区。
- 优化闭环补充历史轮次和 `nextAction`；归档补充归档项下载。
- 后续：完成统一状态组件、latest 语义和历史只读复核，见 8.3、8.7、8.11。

### 09. 现有源码重新部署兼容实现

- 对应任务：7.30。
- 在当前分离式源码部署契约下增加强制重新部署请求和 x86 Drawer 入口。
- 该实现仅用于当前接口兼容，不属于目标业务设计。
- 后续：后端合并源码部署与 x86 构建后删除独立部署操作，切换复合 `X86_BUILD`，见 1.x、8.2。

### 10. 后端目标架构定稿与任务重写

- 对应任务：1.x 至 5.x、8.x。
- 确定源码部署与 x86 构建合并为一个复合 `X86_BUILD`。
- 确定 overview 为 `project/currentContext/workflow/latestTaskEventId`。
- 确定所有项目级异步任务统一接入一个 SSE，并使用统一生命周期和 envelope。
- 确定各领域提供统一外壳的 latest，严格绑定当前 Context。
- 确定 readiness 使用 `stageId` 返回 prerequisites，不返回整体 ready、actions 或按钮。
- 重写 `tasks.md`，保留已完成实现记录，并为临时兼容或不符合目标契约的实现增加明确纠偏任务。
- 验证：`openspec validate remediate-issue --strict` 通过。

### 11. 建立完善阶段时间轴记录机制

- 对应任务：任务管理规则。
- 新增本日志，并在 `tasks.md` 顶部声明任务清单与时间轴日志的职责边界。
- 后续每次实际修改必须同时更新任务状态和追加一条日志；只讨论、未落地的方案不记为实现完成。

### 12. 审计并修复 Agent Runtime 初始化数据

- 对应任务：10.1 至 10.3。
- 只读核对 Liquibase INSERT 与当前 PostgreSQL：默认管理员存在，4 个源码版本对应的 4 条 optimization cycle 完整，默认 Model Profile 为条件式迁移且当前没有旧 `codex-provider` 配置。
- 确认 `0106-agent-runtime-selection` 已执行，但 `agent_runtimes` 当前为 0 条，缺少 CODEX、DEEPSEEK_HARNESS、OPENCODE。
- 新增 `0118-restore-default-agent-runtimes.sql` 幂等恢复缺失项，已有类型不覆盖用户配置，并加入 master changelog。
- 验证：重建并启动 backend/backend-worker，Liquibase 成功记录 `0118-restore-default-agent-runtimes`；数据库恢复 CODEX/Codex/`codex`、DEEPSEEK_HARNESS/DeepSeek Harness/`dsh`、OPENCODE/OpenCode/`opencode` 三条启用记录。
- 接口与页面验证：使用现有超级管理员会话刷新模型配置页，Agent 运行时下拉通过 GET `/api/admin/agent-runtimes` 展示 `Codex · CODEX`、`DeepSeek Harness · DEEPSEEK_HARNESS`、`OpenCode · OPENCODE`。

## 2026-09-03

### 13. 报告纳入与排除互斥展示

- 对应任务：7.32。
- 依据后端 `migrationInputStatus=CANDIDATE/CONFIRMED/EXCLUDED` 三态模型收紧共享操作组。
- 列表操作列仅展示下一步可执行动作：`CANDIDATE` 和 `EXCLUDED` 都仅提供“纳入报告”，`CONFIRMED` 仅提供“排除”，不再重复展示状态 Tag；后端三态仍保留“从未纳入/明确排除”的业务区分，Drawer Footer 使用相同的互斥转换规则。
- 补充三种状态的组件测试，确认互斥操作和 PATCH 目标状态。
- 验证：共享组件、依赖分析和知识库页面 21 项测试通过；相关文件 ESLint、frontend typecheck 及 `openspec validate remediate-issue --strict` 通过。

### 14. 依赖分析 Drawer 导航层级收敛

- 对应任务：7.33。
- 删除最新条目详情返回时额外生成的 `analysis(returnTo=latest)` 中间视图，改为直接返回最新分析。
- 将原有 `returnTo` 推算状态拆分为 `latest-result/history-analysis/history-result`，使标题、返回文案、只读状态和 Footer 操作均由明确视图语义决定。
- 导航路径固定为“最新分析 → 最新条目详情 → 最新分析”以及“历史列表 → 历史分析详情 → 历史条目详情 → 历史分析详情”。
- 验证：依赖分析 Drawer 8 项测试、ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 15. 构建页面适配内置源码部署

- 对应任务：7.34；纠偏历史兼容实现 7.30，收缩 8.2 剩余范围。
- 依据后端提交 `aa349b4 feat: 构建验证内置源码部署`，移除 x86 构建 Drawer 的“部署当前源码/重新部署”和成功部署前置门禁；`SOURCE_ONLY` 构建直接创建任务。
- 同步移除正式构建验证 Drawer 对 x86/RISC-V 两侧成功部署记录的门禁；`BOTH` 构建只校验当前源码和完整运行环境，页面明确说明源码由构建任务自动准备。
- 删除 frontend `getProjectSourceDeployments/createProjectSourceDeployments`、部署 Query Key 及独立 `SOURCE_DEPLOY` SSE 失效映射；新流程只跟踪 `BUILD_VALIDATION` 构建任务。
- 验证：x86 构建、正式构建、依赖分析、SSE 和 API 契约 56 项测试通过；frontend typecheck、相关文件 ESLint 及 `openspec validate remediate-issue --strict` 通过。

### 16. x86 构建前置条件紧凑化

- 对应任务：7.35。
- 内置源码部署后，就绪状态不再使用“成功提示 + 独立环境事实区”的高卡片，收紧为 44px 最小高度的单行摘要：“构建环境已就绪 · 当前源码 · x86 源环境 · 架构”。
- 前置条件不满足时仍使用完整 `PrerequisiteNotice`，保留原因和“前往环境/源码管理”恢复操作。
- 验证：x86 构建 Drawer 8 项测试、ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 17. x86 构建就绪摘要显式呈现两个前置条件

- 对应任务：7.36。
- 保留紧凑高度，但将原本未标注的值串改为两个明确事实：“当前源码：{revision}”和“x86 源环境：{name} / {architecture}”。
- 长源码/环境名称使用省略与 Tooltip，移动端改为每个前置条件独立换行，避免紧凑布局导致语义丢失。
- 验证：x86 构建 Drawer 8 项测试、ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 18. x86 构建就绪信息调整为三行事实结构

- 对应任务：7.37。
- 第一行仅用状态图标和文案表达前置条件是否满足，第二、三行分别展示“当前源码”和“当前环境”。
- 当前源码使用业务名称：Git 来源从仓库地址提取仓库名，上传来源使用源码包文件名，不再显示 revision ID 或版本摘要。
- 验证：源码名称规则及 x86 构建 Drawer 共 11 项测试、ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 19. x86 构建就绪信息改为轻量双栏布局

- 对应任务：7.38。
- 状态结论保留独立首行，当前源码和当前环境收进下一行双栏信息块；弱化大面积状态底色与表格式分割线，使用留白、浅色信息面和轻阴影建立层级。
- Git 来源的仓库名称作为链接在新窗口打开仓库地址；上传源码仍以普通文本展示文件名。
- 验证：源码名称规则及 x86 构建 Drawer 共 11 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 20. x86 构建就绪卡片补充渐变状态氛围

- 对应任务：7.39。
- 在双栏信息结构不变的基础上，加入低饱和绿色渐变、半透明事实块和成功色轻阴影；融合旧版明确的成功状态感与新版轻量的信息层级。
- 验证：x86 构建 Drawer 8 项测试、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过；项目未配置 Stylelint 命令。

### 21. 对照旧版结构重新融合 x86 构建就绪卡片

- 对应任务：7.40；纠偏任务 7.39 的整卡渐变与独立信息块方案。
- 恢复旧版“一张完整卡片，上层状态、下层事实”的结构：渐变仅用于状态带，当前源码和当前环境在白底区域横向并列，以细分隔线区分。
- 保留新版的紧凑高度、源码业务名称和 Git 仓库跳转能力。
- 验证：x86 构建 Drawer 8 项测试、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 22. x86 构建就绪区域恢复最初视觉基线

- 对应任务：7.41；暂时回退 7.35 至 7.40 的就绪态视觉方案，等待基于页面截图重新确认设计。
- 恢复完整绿色成功提示和下方执行环境事实区；保留“构建任务内置源码部署”的现行业务，未恢复部署目录、部署按钮或部署门禁。
- 验证：构建前置辅助逻辑及 x86 构建 Drawer 共 10 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 23. 基于最初视觉基线定稿源码与环境双栏

- 对应任务：7.42。
- 保持截图中的完整成功提示和卡片尺度，下方事实区改为“当前源码 / 当前环境”左右两栏；小屏幕回落为上下排列。
- 成功提示使用由上到下的浅绿纵向渐变；Git 来源展示可跳转的仓库名，上传来源展示源码包文件名。
- 验证：源码名称规则及 x86 构建 Drawer 共 11 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 24. 移除就绪卡片外边框并精简事实行

- 对应任务：7.43。
- 移除与状态图标、渐变语义重复的绿色外边框，改用轻阴影维持卡片边界。
- 当前源码和当前环境均收为“标签 + 内容”两行；环境名称与架构合并显示，源码来源类型不再单独占行。
- 验证：源码名称规则及 x86 构建 Drawer 共 11 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 25. 就绪态渐变扩展至整个容器

- 对应任务：7.44。
- 删除“构建任务会在 x86 源环境中自动部署或复用当前源码”说明，只保留状态图标和“可以开始构建”。
- 纵向浅绿渐变由外层容器统一承载，覆盖状态头和下方源码/环境双栏；内嵌成功提示改为透明背景，避免渐变在状态区结束。
- 验证：x86 构建 Drawer 8 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 26. x86 构建阻断态改为双栏恢复结构

- 对应任务：7.45。
- 黄色阻断容器沿用状态头加源码/环境双栏结构，各栏独立展示是否满足；不再将多个缺失条件压缩成一句话和单一入口。
- 当前源码或当前环境未满足时，在对应栏内展示管理按钮；两项同时缺失时同时提供“前往源码管理”和“前往环境管理”。
- 验证：x86 构建 Drawer 9 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 27. 三个构建相关节点统一响应式前置条件网格

- 对应任务：7.46。
- 新增共享 `PrerequisitePanel`，条件项通过数组驱动，使用 `auto-fit + minmax(280px, 1fr)` 根据容器宽度决定实际栏数并自动换行；状态色纵向渐变覆盖完整容器。
- x86 构建展示当前源码、x86 源环境；构建验证展示当前源码、x86 源环境、RISC-V 目标环境；自动化测试展示 x86 与 RISC-V 两侧构建验证。
- 未满足条件的恢复按钮位于对应栏目：源码前往源码管理，环境前往环境管理，缺少有效构建前往构建验证。
- 验证：共享组件、x86 构建、构建验证和自动化测试共 21 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 28. 响应式前置条件网格移除分割线

- 对应任务：7.47。
- 移除条件栏之间的竖向分割线及移动端横向分割线，改用一致的行列间距形成信息分组，避免 `auto-fit` 动态换行时出现断裂边界。
- 验证：共享前置条件组件 2 项测试、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 29. 三个构建相关节点统一环境变量输入高度

- 对应任务：7.48。
- x86 构建、构建验证和自动化测试的桌面配置区改为等高双栏，环境变量输入框填满超时时间下方的剩余空间，与左侧命令编辑器底部对齐。
- 移除环境变量的内容驱动自动高度，防止默认状态出现无意义留白；窄屏下固定为 160px，避免纵向占用过大。
- 验证：x86 构建、构建验证和自动化测试共 19 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 30. 报告纳入状态同步与 Footer 按钮尺寸修复

- 对应任务：7.49。
- 报告纳入/排除成功后，除失效查询外同步修补来源列表与详情缓存中的 `migrationInputRefId/migrationInputStatus`，避免列表已排除而详情仍读取旧的已纳入快照；知识库和依赖分析行操作均传入列表、详情 Query Key。
- Footer 单条操作恢复 Ant Design 默认中号按钮，表格行内操作继续使用小号按钮。
- 列表缓存按 Query Key 前缀批量更新，覆盖带分页和筛选参数的所有当前实例，而非只处理一个精确缓存项。
- 验证：共享报告操作、知识库和依赖分析共 23 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 31. 环境变量输入框改为固定八行

- 对应任务：7.50；纠偏任务 7.48 的 Flex 等高填充方案。
- 撤销环境变量输入框填满剩余高度的嵌套 Flex 样式，避免 Ant Form 内部容器将输入框推至底部并产生更大空档。
- x86 构建、构建验证和自动化测试统一使用 `rows={8}`，保持稳定默认高度并随正常文档流排列。
- 验证：三个页面补充固定 8 行断言，共 19 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 32. 环境列表增加当前运行环境快捷设置

- 对应任务：7.51。
- 在环境列表“操作”列前新增“当前配置”列：x86 源环境提供“设为当前源环境”，RISC-V 目标环境提供“设为当前目标环境”，跳板机不参与项目运行环境选择。
- 已选环境使用蓝色状态 Tag 直接标识；未启用或未完成成功检查的候选环境禁用设置按钮并提示恢复条件。
- 快捷设置沿用现有 PATCH `/runtime-environments` 的单字段部分更新能力；确认文案明确提示 Context 切换影响，成功后即时更新 overview，并失效所有依赖当前运行环境的下游查询。
- 顶部成组配置入口继续保留，用于一次性查看和调整源/目标环境组合。
- 验证：环境列表 6 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 33. 当前环境配置收敛到环境列表

- 对应任务：7.52；调整任务 7.51 中暂时保留顶部成组配置入口的方案。
- 依据后端现有固定角色校验，x86 源环境只提供“设为当前源环境”，RISC-V 目标环境只提供“设为当前目标环境”，跳板机不提供当前配置操作。
- 删除环境列表上方的“当前运行环境”展示、编辑入口、双 Select 配置表单以及相关查询和组件状态；当前选择与切换全部由表格“当前配置”列承载。
- 保留现有单字段 PATCH、Context 变更确认、overview 即时更新和下游查询失效逻辑。
- 验证：环境列表 5 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 34. 恢复当前环境只读概览并收紧行内操作

- 对应任务：7.53；纠正任务 7.52 将当前环境展示与成组编辑区域一并移除的问题。
- 当 overview 已返回当前源环境或目标环境时，在环境列表上方展示只读双卡片概览；不恢复编辑图标、双 Select 表单或独立保存操作。
- 删除表格“当前配置”列，将“设为当前源环境/目标环境”改为操作列首个图标按钮；当前项显示蓝色选中图标，跳板机不显示该操作。
- 保留固定角色、环境可用性、切换确认、overview 同步与下游查询失效规则。
- 验证：环境列表 5 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 35. x86 构建记录按状态筛选

- 对应任务：7.54。
- 构建记录标题独占一行，下一行仅显示“全部状态”筛选控件；查询仍固定在当前源码、当前 x86 源环境和 `SOURCE_ONLY` 范围，未增加环境、范围或时间筛选。
- 状态值进入构建记录请求与 Query Key；创建或取消任务以不带状态的当前上下文 key 失效全部筛选缓存。
- 统一任务状态语义：失败为红、取消为灰、超时为橙。
- 验证：显示工具与 x86 构建 Drawer 共 16 项测试、frontend typecheck、ESLint、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 38. x86 构建配置输入高度固定

- 对应任务：7.59。
- 按页面量得的配置网格 282px 与构建命令标签 26px，CodeMirror 编辑器及其滚动容器固定为 256px。
- 环境变量保持 `rows={8}`，显式关闭 `autoSize` 并禁用浏览器的拖拽缩放，避免用户下拉扩高破坏布局。
- 验证：x86 构建 Drawer 测试、Prettier 及 `openspec validate remediate-issue --strict` 待本次变更后重新执行。

### 36. 当前环境概览移除重复连接状态

- 对应任务：7.55。
- 环境管理上方概览只回答“当前选择了哪些环境”，保留源/目标角色、环境名称和架构，连接状态与最近检查继续由下方环境列表承载。
- 为共享 `RuntimeEnvironmentCards` 增加可选的连接状态展示模式；仅环境管理使用精简模式，SBOM 等需要环境可用性信息的页面保持默认完整模式。
- 验证：共享环境卡片与环境列表共 7 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 37. 当前环境操作移至环境检查之后

- 对应任务：7.56。
- 环境列表操作统一为“修改环境 → 环境检查 → 设为当前环境 → 运行脚本 → 执行记录”，让操作顺序与环境从配置、验证到投入使用的业务顺序一致。
- 验证：增加环境检查与设置按钮 DOM 顺序断言；环境列表 5 项测试、相关文件 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 39. 删除生产入口不可达的 frontend 遗留实现

- 对应任务：7.57。
- 以 `src/main.tsx` 的生产导入关系、Workflow 拓扑和 StageDrawer 映射为依据，删除已明确退役且没有生产入口的知识库 AI、迁移输入合并、SBOM、源码对比四组 Drawer，以及仅由这些页面消费的 API、领域类型和组件测试。
- 删除已由 `useProjectTaskEvents` 取代的旧 Workflow realtime hook、转换逻辑及测试；同时移除 SBOM/源码复检对应的无消费者 Query Key 与 SSE 缓存失效分支。后端若短期仍推送旧 task type，通用任务通知名称仍然保留。
- 删除评估报告中未被引用的状态常量文件和迁移输入历史兼容类型；保留 `retiredPanels`，让旧书签和历史 URL 仍能被识别并清理为规范地址。
- 验证：frontend typecheck、全量 ESLint、受影响的 API/Panel/SSE 共 40 项测试和生产构建通过；构建仅保留既有大 chunk 提示。

### 40. 未配置时保留当前运行环境占位

- 对应任务：7.58。
- 环境管理列表页始终保留“当前运行环境”区域，不再因为源环境和目标环境均为空而隐藏整个模块。
- 未配置角色继续使用共享环境卡片展示“待配置”和空架构占位；任一角色完成配置后在相同位置展示实际环境，保持页面层级和用户认知稳定。
- 验证：补充未配置源/目标环境占位测试；相关测试、ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 41. 当前环境状态改用线性图标

- 对应任务：7.60。
- 环境列表中“当前源环境/当前目标环境”由蓝色实心 `CheckCircleFilled` 改为线性 `CheckCircleOutlined`，与修改、检查、运行脚本和执行记录等线性操作图标保持一致。
- 状态仍占用“设为当前环境”的固定位置，并保留蓝色语义色、无点击行为、可访问名称和 Tooltip；未改变任何环境设置业务逻辑。
- 验证：补充线性视觉标记断言；环境列表测试、相关 ESLint、frontend typecheck、Prettier 及 `openspec validate remediate-issue --strict` 通过。

### 42. 补充传统 favicon 路径兼容资源

- 对应任务：7.61。
- 将 `index.html` 的唯一 favicon 声明锁定为 `/favicon.ico`，并由原品牌 SVG 生成标准 32×32、32 位 ICO 资源；删除不再使用的 `/favicon.svg` 文件与入口，避免双路径产生歧义。
- 该调整只消除静态资源 404，不改变应用路由、接口代理或认证请求。
- 验证：ICO 文件格式与构建产物一致性、frontend 生产构建、Prettier、`git diff --check` 及 `openspec validate remediate-issue --strict` 通过。

### 43. 评估报告改为决策型信息视图

- 对应任务：7.62；后端联调任务：8.13。
- 将成功报告从平铺统计和重复问题列表重构为“报告状态与操作、迁移结论、核心指标、评估构成、优先处理队列、建议处理顺序、报告范围与追溯”的决策层级；Drawer 扩展至 1040px，为报告型内容提供稳定阅读宽度。
- 明确区分执行事实与业务结论：现有 `SUCCEEDED` 只显示“报告已生成”，不再由 frontend 根据风险等级推导迁移结论；后端尚未提供的结论摘要、阻断项、人工确认总量、工作量细分和生成时 Context 快照统一显示“待后端提供”。
- 将 `priorityIssues` 与 `dependencySubstitutionNotes` 去重合并为一个可按高风险、依赖、源码和人工确认筛选的处理队列；将复合风险统计键按真实风险等级聚合，避免同一“提示”标签重复出现。
- 操作层级调整为：重新生成与 HTML/JSON 下载放在报告头部，Footer 只保留当前阶段唯一主操作“进入人工修复”；保留空数据、生成中、失败和接口失败的既有统一状态展示。
- 验证：评估报告 7 项测试、相关文件 ESLint、frontend typecheck、生产构建、Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过；并在已登录 Chrome 页面核对真实报告数据下的布局、风险聚合、队列内容和 Footer 主操作。

### 44. 评估报告问题复用来源详情并补齐 Tab 数量

- 对应任务：7.63。
- 为全部、高风险、依赖问题、源码问题和人工确认五个筛选 Tab 分别计算并展示数量；分类允许业务语义重叠，因此单项数量之和不要求等于全部数量。
- 报告问题行改为可访问的整行点击入口，通过后端已返回的 migration input ID 请求 `/migration-inputs/{id}`，再依据 `reference.sourceType/sourceRefId` 打开知识库 Finding 或依赖分析结果内容；其他历史来源使用只读来源数据兜底。
- 抽取依赖结果纯内容组件，并为知识库 Finding 内容增加可选的纳入状态显示开关；原知识库和依赖分析 Drawer 继续复用同一内容，评估报告只加载内容组件，不打开或嵌套原 Drawer。
- 报告内二级详情固定为只读，不渲染纳入/排除 Footer；返回评估报告后保留原筛选 Tab。详情模块按点击时懒加载，避免 Monaco/CodeMirror 提前进入评估报告首屏依赖。
- 验证：评估报告、知识库扫描和依赖分析共 26 项测试、相关文件 ESLint、frontend typecheck、生产构建、Prettier、`git diff --check` 和 `openspec validate remediate-issue --strict` 通过；构建结果确认报告详情单独产出懒加载 chunk。

### 45. 评估报告数量改用完整输入快照

- 对应任务：7.64。
- 定位数量偏小的根因：报告摘要中的 `priorityIssues` 和 `dependencySubstitutionNotes` 受后端 `PRIORITY_LIMIT = 10` 限制，只是 Top 摘要而不是报告问题全集；将两者合并去重后计算 Tab 数量会系统性漏计。
- 复用后端现有 GET `/api/reports/{reportId}/inputs`，先读取第一页与总量，再并发追平其余分页；处理队列和全部、高风险、依赖、源码、人工确认数量统一由完整报告输入快照计算，加载期间以 `…` 表达未知，不短暂显示错误的 0。
- `priorityIssues` 和 `dependencySubstitutionNotes` 仍只用于报告概览，不再承担完整列表或分类计数职责；本次无需后端改动。
- 验证：评估报告、知识库扫描、依赖分析与 API 共 45 项测试、相关文件 ESLint、frontend typecheck、生产构建、Prettier、`git diff --check` 和 `openspec validate remediate-issue --strict` 通过；构建仅保留既有大 chunk 提示。

### 46. 评估报告处理队列按筛选维度重构

- 对应任务：7.65。
- 纠正原 Tab 同时混用来源、风险和处理要求三个维度的问题：主 Tab 只保留互斥的来源分类，稳定展示“全部 / 知识库扫描 / 依赖分析 / SBOM 分析”及各自数量，未知来源出现时追加“其他来源”，因此可直接核对来源子项与全部数量。
- 将“高风险”调整为风险等级下拉筛选，将“需人工确认”调整为独立勾选项；两者可与来源组合过滤，不再通过一组互斥 Tab 制造分类可相加的错误认知。
- 来源、风险和人工确认状态由评估报告 Drawer 统一持有，打开只读问题详情再返回时保持不变；关闭 Drawer 时统一恢复默认筛选。
- 验证：评估报告 8 项测试、相关文件 ESLint、frontend typecheck、生产构建、Prettier、`git diff --check` 和 `openspec validate remediate-issue --strict` 通过；构建仅保留既有大 chunk 提示。

### 47. 联调后端项目级 SSE 节点与上下文元数据

- 对应任务：7.66；剩余联调任务：8.5。
- 以刚合入的后端 `0c04069` 实际契约为准扩展 frontend 事件模型，接收 `projectId/stageId/resource/changedFields` 与允许为空的 `taskId/taskType`；任务 API 的 resource 类型同步支持 `mode/environmentRole`。
- 任务生命周期事件优先按 `stageId` 和 `resource.type/mode` 刷新环境、x86 构建、知识库、依赖分析、评估报告、构建验证、自动化测试及归档查询；旧历史事件缺少元数据时继续回退到 `taskType` 映射。
- 新增 `project.context.changed` 监听：active source 变化刷新 overview、知识库和所有下游 Context 数据；运行环境选择或当前环境配置变化同时刷新环境列表/选项和环境相关下游；未知 Context 字段保守刷新全部 Context 数据。
- payload 明确携带其他 `projectId` 时在推进游标前直接忽略；继续保留递增游标去重、断线续传、指数退避、不可用期间 overview 轮询、页面恢复可见刷新及任务终态 notification。
- 后端本次尚未提供领域 latest、readiness、复合构建 `resource.step` 和无上限连续追平，因此 progress 暂时继续更新 overview 当前任务，8.5 保留上述剩余联调范围。
- 验证：项目事件 Hook 与 API 共 36 项测试、相关文件 ESLint、frontend typecheck、生产构建、Prettier、`git diff --check` 和 `openspec validate remediate-issue --strict` 通过；构建仅保留既有大 chunk 提示。

### 48. SSE 删除旧 taskType 推断与 progress 本地合并

- 对应任务：7.67；纠正任务 7.66 中暂时保留旧事件兼容的实现。
- 删除全部 `taskType -> Query Key` 旧映射，任务领域刷新只接受新契约的 `stageId` 与 `resource`；`taskType` 仅用于终态通知的人类可读任务名称，不再决定数据刷新范围。
- 缺少 `stageId` 的不完整任务事件在完成游标校验与推进后停止处理，不刷新 overview、不刷新领域数据，也不产生终态通知；避免新旧契约并存时产生两套业务判断。
- 删除 `task.progress` 对 overview `recentTasks` 的客户端合并；progress 只触发 overview 重读，等领域 latest 可用后再按 8.5 将进度刷新迁移到对应 latest。
- 验证：项目事件 Hook 17 项测试、相关文件 ESLint、frontend typecheck、生产构建、Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过；构建仅保留既有大 chunk 提示。

### 49. SSE 断开后不再轮询 overview

- 对应任务：7.68。
- 删除 SSE 连接错误时立即刷新并每 10 秒轮询 `/overview` 的降级路径；断线后只按最后已处理事件 ID 指数退避重连，由后端事件补发恢复状态。
- 保留页面重新可见时的一次性 overview 刷新，用于恢复浏览器后台期间可能陈旧的项目快照；该行为不是定时轮询。
- 后端 API 与 Worker 的进程内 `TaskSseBroker` 无法跨进程广播属于服务端缺陷，frontend 不再以 overview 轮询掩盖该问题。
- 验证：项目事件 Hook 18 项测试、相关文件 ESLint、frontend typecheck、Prettier 与 `openspec validate remediate-issue --strict` 通过。

### 50. 知识库 Finding 风险语义统一

- 对应任务：7.69。
- 将 `critical/high/medium/low/info` 的排序、文案、Tag 色和分布色收敛到同一份 frontend 配置，补齐列表中 `critical -> 严重` 的显示和筛选。
- 将扫描器 `summary.blocking` 的页面名称从“阻塞项”改为“需处理项”，避免与 Workflow `BLOCKED` 或任务失败混淆，不改动后端计数口径。
- Finding 详情头卡按风险等级切换边界、浅色背景与状态图标色；风险色仅集中在头卡，代码、规则和建议区保持原有中性层级。
- 验证：知识库 Drawer 10 项测试、相关文件 ESLint、frontend typecheck、Prettier 与 `openspec validate remediate-issue --strict` 通过。

### 51. Finding 详情报告操作与定位信息收敛

- 对应任务：7.70。
- 将“报告状态 + 已纳入/已排除/未纳入”与当前唯一可执行的“排除/纳入报告”收进同一 Footer 操作组；当前可编辑详情头卡不再跨区重复报告状态，历史只读详情仍在头卡保留状态。
- 定位与规则中的文件路径和规则 ID 改为独占整行，所有字段取消单行省略并允许长内容完整换行展示。
- 验证：共享报告操作和知识库 Drawer 共 15 项测试、相关文件 ESLint、frontend typecheck、Prettier 与 `openspec validate remediate-issue --strict` 通过。

### 52. 构建与测试配置高度统一

- 对应任务：7.71。
- 构建验证和自动化测试的命令编辑器由旧的 280px 统一为 x86 构建使用的 256px，并让组件高度参数与 CSS 固定高度保持一致，不再依赖样式覆盖修正不一致的 248px 参数；三处命令、超时和环境变量统一使用纵向 `Form.Item` 结构，使标签占位和控件间距一致。
- 三个 Drawer 的环境变量输入框统一保持 8 行、关闭 `autoSize` 并禁止拖拽缩放，避免配置区高度在页面之间跳变。
- 验证：构建验证和自动化测试 Drawer 共 10 项测试、相关 ESLint、frontend typecheck、Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过；并在已登录 Chrome 页面逐一打开 x86 构建、构建验证和自动化测试 Drawer，确认左右输入区顶部与底部对齐。

### 53. 自动化测试区块节奏对齐构建 Drawer

- 对应任务：7.72。
- 自动化测试的前置条件、测试配置、本次测试结果和测试结果对比统一接入与 x86 构建、构建验证相同的 section 骨架：区块内部使用 16px 间距，相邻区块使用 24px 顶部留白和语义分隔线。
- 测试配置的标题与说明收进同一标题组，折叠按钮保持在标题行右侧；x86/RISC-V 双结果卡片继续保留，作为测试阶段独有的双端结果表达。
- 验证：自动化测试 Drawer 5 项测试、相关 ESLint、frontend typecheck、Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过；Chrome 页面确认测试前置条件、测试配置和本次测试结果之间已呈现与构建 Drawer 一致的分隔线和留白。

### 54. 构建与测试当前结果视图统一

- 对应任务：7.73；后端联调任务：8.3。
- x86 构建和构建验证不再在默认页面直接铺开全部记录表格，改为与自动化测试一致的“当前结果 + 查看历史记录”结构；历史页与日志页保留明确返回路径，关闭 Drawer 后恢复当前结果。
- 新增共享当前执行结果卡：x86 构建展示单卡，构建验证和自动化测试展示 x86/RISC-V 双卡；当前结果按当前源码、当前环境和构建范围筛选，后续领域 latest 可用后替换临时 List 读取。
- 测试结果对比改为语义结论卡，集中展示一致性结论、状态、风险、摘要和处理建议；失败态使用面向用户的恢复提示，不再把 Agent 原始错误输出作为摘要铺满页面。
- 验证：x86 构建、构建验证和自动化测试相关 4 个测试文件共 24 项测试通过；相关 ESLint、frontend typecheck、Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过。Chrome 实际页面确认当前测试结果、测试结果对比和历史记录三层展示正常，失败对比卡未透出 Agent 原始输出。

### 55. 测试结果对比日志

- 对应任务：7.74。
- 测试结果对比卡增加“查看对比日志”入口；日志页展示对比状态、风险、对比记录 ID、测试批次和执行时间，并复用任务日志的合并输出、标准输出和标准错误切换。任务日志未持久化时，合并输出使用对比记录的 `errorMessage` 作为只读兜底。
- 日志页根据入口保留“返回最新测试结果”或“返回测试记录概览”路径，原始 Agent 输出只在用户主动打开日志后展示。
- 验证：自动化测试 Drawer 6 项测试通过，包含任务日志和 `errorMessage` 兜底两条路径；相关 ESLint、frontend typecheck、Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过。Chrome 实际页面确认失败对比可进入日志页，当任务日志为空时合并输出能展示对比记录保留的原始错误内容。

### 56. 精简当前构建结果

- 对应任务：7.75。
- x86 构建和构建验证的当前结果卡移除退出码，仅保留用于快速判断当前结果的环境、状态、目录、架构和创建时间；日志详情中的退出码保留。
- 验证：x86 构建和构建验证相关 3 个测试文件共 18 项测试通过；相关 ESLint、frontend typecheck、Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过。

### 57. 统一构建与测试模块边界

- 对应任务：7.76。
- 共享 `PrerequisitePanel` 移除阴影，就绪态改为成功色边框，阻塞态改为警告色边框；当前结果继续使用中性边框，测试结果对比继续使用状态色边框，配置区不增加额外容器。
- 验证：x86 构建、构建验证和自动化测试相关 4 个测试文件共 24 项测试通过；Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过。Chrome 实际页面确认前置条件已使用语义色边框并移除阴影，与当前结果和结果对比的边界表达一致。

### 58. 优化闭环收敛视图

- 对应任务：7.77。
- 当前轮次改为“本轮结论 -> 闭环进度 -> 问题收敛 / 验证结果 -> 待处理事项”。结论卡集中展示轮次、源码版本、下一步原因、开始时间和历史入口；中间以四个检查点、收敛指标和验证证据帮助用户判断是否可归档。
- 待处理事项仅汇总高风险、当前下一步和测试对比建议；缺失值统一标记为“缺失数据”，并分别指出缺失源码复检、风险收敛或测试结果对比数据，“尚未执行”仅用于确实没有执行记录的阶段。构建与测试成功但对比未生成或未一致时，下一步仍指向自动化测试，不允许进入归档。
- 验证：OptimizationCycle 5 项测试、相关 ESLint、frontend typecheck、Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过；Chrome 实际页面确认本轮结论、四步进度、问题收敛、验证结果、待处理事项和单一 Footer 操作在滚动状态下展示正常。

### 59. 归档交付视图

- 对应任务：7.78。
- 归档默认页重构为交付结论、交付快照、完整性信息和交付清单；成功归档直接展示源码、交付项、包大小、生成时间、记录 ID 和 SHA-256，每项交付物提供格式下载，原始元数据默认折叠。
- 最近归档与当前激活源码不一致时明确显示“当前源码尚未归档”，Footer 引导归档当前源码，旧归档下载下沉为次级操作；当前源码归档成功时 Footer 的唯一主操作为下载归档包。历史页不再携带创建归档 Footer。
- 缺失源码版本、归档包、包大小、完整性校验或交付项时均指出具体缺失数据，不使用模糊占位。
- 验证：Archive 5 项测试、相关 ESLint、frontend typecheck、Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过；Chrome 真实项目确认旧归档与当前源码不一致时使用警告色结论、同时提供旧归档下载和“归档当前源码”单一 Footer 主操作，交付清单滚动与元数据折叠正常。

### 60. 项目 overview 刷新合并

- 对应任务：7.79。
- 项目级 SSE 将 `created/queued/started/progress`、终态和 `project.context.changed` 的 overview 失效统一收进 250ms 固定批次；批次窗口内只发起一次 overview 权威读取，领域 Query Key 仍按事件立即失效，任务通知和日志边界保持不变。
- 删除 Git Sync 提交、知识库扫描创建、构建请求失败、依赖自动修复创建、归档创建和运行环境切换中的重复 overview 失效。同步上传使用接口返回的源码版本更新 overview 缓存，随后仍由上下文 SSE 完成权威校准；评估报告改为复用共享 overview hook，并关闭 observer 挂载、窗口聚焦和网络重连的隐式 refetch。用户主动刷新继续立即请求。
- 验证：SSE、评估报告、知识库、构建、归档、依赖分析/自动修复和环境相关 10 个测试文件共 65 项测试通过；相关 ESLint、frontend typecheck、Prettier、`git diff --check` 与 `openspec validate remediate-issue --strict` 通过。新增测试确认相邻 lifecycle、progress、context 和 terminal 事件只产生一次 overview 失效。

## 2026-09-04

### 61. 项目顶部改为迁移上下文轨道

- 对应任务：7.80。
- 将项目工作台顶部从项目、当前阶段、当前任务和下一步四张统计卡重构为单一迁移上下文面板：左侧保留项目与架构方向，中部按“当前源码 → x86 源环境 → RISC-V 目标环境”展示当前 Context，右侧保留当前任务。
- 当前源码与环境直接复用 overview 缓存，不新增请求；源码或环境缺失时在原位置展示“待配置”。动态 Workflow 契约完成联调前，顶部不再展示由旧项目阶段或推荐操作推算的“当前阶段/下一步”。
- 增加页面测试覆盖当前源码、双环境和隐藏旧摘要；验证：Prettier、相关 ESLint、frontend typecheck、项目详情页面 7 项测试与 `git diff --check` 通过。浏览器只读验收因本地页面要求登录而未进入项目详情，未使用或猜测用户凭据。

### 63. 项目与任务摘要融入迁移轨道

- 对应任务：7.82。
- 删除项目区域的独立背景插画和当前任务区域的灰色卡片底色，让整个顶部面板共享低饱和蓝绿上下文底色；左右区域改用与中间源码、环境节点一致的圆形端点图标和三层文字结构。
- 保留左右结构分隔线以及项目架构、任务状态和进度信息，使项目、迁移上下文和当前任务形成一条连续轨道，同时不增加新状态或数据请求。
- 验证：Prettier、相关 ESLint、frontend typecheck、项目详情页面测试、`git diff --check` 与 `openspec validate remediate-issue --strict`。

### 64. 环境管理刷新收敛

- 对应任务：7.83。
- 环境管理标题增加按当前视图命名的图标刷新入口：环境列表只失效环境列表查询，执行记录只失效当前环境的记录查询，执行日志只重读详情与日志内容；所有入口均不附带 overview 请求，创建、编辑和脚本表单不展示刷新按钮。
- 删除环境检查提交后的立即列表重载，以及环境保存、脚本运行提交后的冗余查询失效。列表或记录视图重新挂载时自然读取一次，异步任务完成后继续由项目 SSE 即时失效环境领域数据并在合并窗口内刷新 overview。
- 环境编辑表单的跳板机选项请求增加前端语义角色 `JUMP_HOST`；API 适配器按既有后端契约映射为 `GENERAL_EXECUTION`，与 `AVAILABLE`、`pageSize=200` 一起交给后端筛选，前端仅排除当前编辑项。
- 验证：环境列表、环境标题与项目 SSE 3 个测试文件共 26 项测试通过，相关 ESLint 通过。

### 65. 迁移轨道收敛为两个主层级

- 对应任务：7.84。
- 将中部迁移轨道从源码、x86 源环境、RISC-V 目标环境三个平级节点收敛为“当前源码 → 当前环境配置”两个主层级；源环境和目标环境作为同一个配置节点内的并列配置项展示。
- 删除源码节点的来源类型与版本说明行以及两个环境节点各自的架构说明行，减少重复层级并扩大环境名称的可用空间；空值继续原位显示“待配置”。
- 验证：Prettier、相关 ESLint、frontend typecheck、项目详情页面测试、`git diff --check` 与 `openspec validate remediate-issue --strict`。

### 66. 顶部三张上下文卡片对齐

- 对应任务：7.85。
- 将原先一个大容器的三段式布局改为项目上下文、当前迁移上下文和执行上下文三张独立等高卡片，统一标题行高度、顶部内边距、圆角、边框和阴影，使三个标题保持同一水平基线。
- 宽度按信息密度调整为约 21%/52%/27%，中间卡获得主要空间；当前环境配置内的 x86 源环境和 RISC-V 目标环境由并列双栏改为两行展示，长环境名称保留省略与 title 提示。
- 验证：Prettier、相关 ESLint、frontend typecheck、项目详情页面测试、`git diff --check` 与 `openspec validate remediate-issue --strict`。

### 67. 三张上下文卡片使用连续蓝绿背景

- 对应任务：7.86。
- 明确项目上下文为信息链起点：项目卡使用低饱和蓝色渐变，当前迁移上下文从同一蓝色过渡到绿色，执行上下文使用与中间卡最右端完全相同的绿色底色，消除原暖色任务背景造成的断裂。
- 执行上下文图标同步改用成功绿色；任务的真实运行、成功和失败语义继续由状态标签表达，不通过卡片底色暗示当前任务状态。
- 验证：Prettier、相关 ESLint、frontend typecheck、项目详情页面测试、`git diff --check` 与 `openspec validate remediate-issue --strict`。

### 68. 当前迁移上下文使用蓝绿渐变边框

- 对应任务：7.87。
- 当前迁移上下文卡片保留原有蓝绿背景，只通过遮罩伪元素生成 1px 低对比度渐变边框：左端延续项目卡蓝色边界，右端过渡到执行卡绿色边界，不让边框实现改变内容区底色。
- 验证：Prettier、相关 ESLint、frontend typecheck、项目详情页面测试、`git diff --check` 与 `openspec validate remediate-issue --strict`。

### 69. 顶部执行上下文纵向收敛

- 对应任务：7.88。
- 将执行状态与进度移入“执行上下文”标题行，正文收敛为当前任务、任务名称和单行消息；消息过长时使用省略展示，减少多层信息堆叠造成的纵向膨胀。
- 三张上下文卡片统一降低最小高度并收紧上下内边距和标题间距，继续保持等高与标题基线一致；窄屏下同步降低项目与执行卡片的最小高度。
- 验证：Prettier、相关 ESLint、frontend typecheck、项目详情页面测试、`git diff --check` 与 `openspec validate remediate-issue --strict`。

### 70. 执行上下文只展示当前任务状态

- 对应任务：7.89。
- “执行上下文”标题仅在存在待执行、排队中或执行中任务时展示状态与进度；最近任务已经结束时不再显示“已完成”等终态，避免将历史结果误解为当前执行状态。
- 最近结束任务的类型与消息继续保留在正文的“最近”说明中，不丢失用户判断最近活动所需的信息。
- 验证：Prettier、相关 ESLint、frontend typecheck、项目详情页面测试、`git diff --check` 与 `openspec validate remediate-issue --strict`。

### 71. 顶部上下文关键信息字重收敛

- 对应任务：7.90。
- 项目、当前源码、源/目标环境和当前任务名称的字重由 600 调整为 500，降低三张上下文卡片中多个粗体同时竞争视觉焦点的问题，字号和信息层级保持不变。
- 确认 frontend 已统一从 overview 缓存读取 `runtimeEnvironments`，独立 API 文件只保留 PATCH 更新；按当前范围不修改 backend，GET 兼容路由继续保留。
- 验证：frontend Prettier、相关 ESLint、typecheck、项目详情页面测试、GET 调用源码检索、`git diff --check` 及 `openspec validate remediate-issue --strict`。

### 72. x86 构建接入 latest 与 readiness

- 对应任务：7.91。
- x86 构建打开时并行读取 `readiness?stageId=x86-build` 与 `builds/latest?mode=SOURCE_ONLY`：前者以 `ACTIVE_SOURCE`、`SOURCE_ENVIRONMENT` 是否为 `SATISFIED` 作为唯一构建门禁，并以 `context.sourceRevisionId` 作为创建请求、历史筛选和历史缓存的当前源码事实；overview 仅继续提供源码和环境的展示名称。后者替代 `pageSize=1` 的 List-as-latest 请求并驱动当前结果与运行中轮询，latest 缓存键不再依赖 overview 源码 ID。
- latest 不受 readiness 阻断；当前 Context 没有结果时展示空态，只有旧 Context 结果时明确提示历史结果已过期。构建历史仍在用户进入历史视图后通过分页 List 请求。
- backend 保持不变。
- 验证：frontend Prettier、相关 ESLint、typecheck、x86 构建与 API 测试、`git diff --check` 及 `openspec validate remediate-issue --strict`。

### 73. 前置条件标题与内容间距收紧

- 对应任务：7.92。
- 将嵌入式前置条件 Header 的底部内边距由 14px 收至 8px，条件 item 的顶部内边距由 12px 收至 6px，并同步将最小高度由 64px 收至 58px；消除两层容器纵向留白叠加，同时保留标题和条件值各自的呼吸空间。
- 验证：frontend Prettier、相关 ESLint、前置条件面板与 x86 构建测试、typecheck、`git diff --check` 及 `openspec validate remediate-issue --strict`。

### 74. 知识库扫描接入 readiness

- 对应任务：7.93；后续集中化任务：8.4。
- 知识库 Drawer 打开时并行读取 `readiness?stageId=kb` 和当前扫描事实，以 `ACTIVE_SOURCE=SATISFIED` 作为唯一扫描门禁；删除对 overview `source.activeRevisionId` 的本地判断，readiness 失败进入请求错误态而不是伪装成缺少源码。
- 当前结果手动刷新同步并行刷新 readiness 与扫描数据；源码 Context SSE 增加 `kb` readiness Query Key 失效，确保切换源码后门禁不会沿用旧缓存。
- backend 保持不变，复用已经提供的 `StageReadinessService`。

### 75. 依赖分析接入 latest 与 readiness

- 对应任务：7.94；后续集中化任务：8.3、8.4、8.9。
- 依赖分析 Drawer 打开时并行读取 `readiness?stageId=rv-dependency-analysis` 与 `dependency-analyses/latest`：前者以 `X86_BUILD`、`TARGET_ENVIRONMENT` 是否为 `SATISFIED` 作为唯一执行门禁，并以 `context.sourceRevisionId` 作为创建请求和当前源码历史筛选的事实来源；后者按 `CURRENT/STALE/EMPTY` 展示当前结果，不再用 `pageSize=1` List 充当 latest。
- 删除打开 Drawer 时为判断前置条件而请求 `/builds?pageSize=100` 的前端推算；依赖分析历史仅在进入历史视图后通过分页 List 读取，且不因当前 Context 未就绪而隐藏。`STALE` 明确提示历史结果与当前源码或环境配置不一致。
- backend 保持不变，直接复用现有依赖分析 latest 与 stage readiness 契约。

### 76. 通用阶段阻断态支持条件与操作直接关联

- 对应任务：7.95。
- 为知识库扫描、依赖分析、评估报告等页面共用的 `StageStateNotice` 增加可选 prerequisites 数据模型；每一行直接承载条件名称、当前状态与恢复操作，普通空态、执行态和错误态不传该属性时保持原样。
- 依赖分析同时展示 `X86_BUILD`、`TARGET_ENVIRONMENT` 两行，并按 readiness 的 `status/reasonCode` 显示缺少源码、缺少源环境、构建中、构建失败、缺少目标环境或环境不可用；知识库扫描的 `ACTIVE_SOURCE` 阻断同步使用同一行式结构，验证单条件和多条件都可复用。
- 条件已满足时保留“已准备”事实但不显示操作；未满足条件的按钮贴近对应状态，避免底部主次按钮与原因失去关联。backend 保持不变。

### 78. 知识库扫描接入领域 latest

- 对应任务：7.97；后续集中化任务：8.3。
- 新增 frontend `getProjectKnowledgeBaseScanLatest` API，知识库默认视图直接并行读取 `kb` readiness 与 `kb-scans/latest`，删除 `kb-scans?page=1&pageSize=1` 的 List-as-latest 请求及随后 `GET /kb-scans/{id}` 的重复详情读取。
- latest 的 `CURRENT` 结果直接驱动当前扫描状态与 Finding 列表；`STALE` 不冒充当前源码结果，明确引导重新扫描或查看历史；`EMPTY` 保留首次扫描空态。历史记录继续在用户打开历史视图后使用分页 List，历史详情仍按 ID 读取。
- backend 保持不变，复用已提供的 KB latest 契约。

### 79. 执行上下文活动任务单行化

- 对应任务：7.98。
- 执行上下文的活动任务从“标题状态 + 当前任务标签 + 任务名称 + 消息”四层收敛为两层：任务名称、状态和进度位于同一主行，过程消息位于次行；删除重复的“当前任务”标签。
- 最近终态和完全无任务的展示分支保持不变，不把历史状态误作当前执行状态；增加页面测试确认“知识库扫描、执行中、15%”属于同一主行。
- backend 与数据请求保持不变。

### 80. Drawer 稳定挂载并收敛 latest 刷新来源

- 对应任务：7.99；后续通用约束：8.3。
- `StageDrawer` 只根据 stage ID 选择领域组件，不再因 `stage.status=blocked` 切换到 Default；阶段状态与 readiness 更新时保留同一个 Drawer 实例，避免异步任务启动后出现卸载、关闭动画和重新挂载。阻断事实由各领域 Drawer 的 readiness/状态内容表达。
- 删除 x86 构建和依赖分析 latest 的 1.5 秒常驻轮询。创建成功仍立即失效领域 latest，SSE 在 created/queued/started/terminal 生命周期事件到达时继续失效对应领域 Query Key；SSE 重连沿用 event cursor 续传，用户仍可手动刷新。
- 知识库扫描原本没有 latest 轮询，只保留创建成功刷新和 SSE 生命周期刷新；它同样受益于 Drawer 按 ID 稳定挂载。backend 保持不变。
- 将稳定挂载、创建成功立即刷新、SSE 生命周期失效、游标重连续传、手动刷新以及“连接正常时禁止固定间隔轮询”写入 `project-pipeline-workbench` 规范和设计，后续所有领域 latest Drawer 必须遵循同一刷新所有权。

### 81. x86 构建结果恢复为主视图分页记录

- 对应任务：7.100。
- x86 构建属于需要连续查看多次尝试、日志和取消操作的高频记录型页面，单条 latest 即使改成表格行仍会形成被截断的历史列表；因此主视图直接恢复分页构建记录，移除单条 latest 结果摘要及二级历史导航。状态选择使用 `BaseTable.toolbar.filters`，归入列表筛选区而非区块标题操作。
- `SOURCE_ONLY latest` 保留为构建配置的轻量初始化来源：只在返回 `CURRENT` 且 `result.command` 非空时采用最近命令，否则使用内置默认命令；用户一旦编辑即使用本地值，后续 SSE 刷新不会覆盖未提交输入，关闭 Drawer 后重置初始化状态。
- 分页记录中将 `CURRENT latest.result.id` 对应行标记为“当前”，Tooltip 明确其含义是“当前上下文最近一次构建”，不把该标记混同为运行中状态；`STALE/EMPTY` 不标记任何历史行。
- 列表继续使用 readiness Context 的源码 ID 和源环境 ID 筛选，readiness 仍是唯一执行门禁与创建请求的源码事实来源；overview 不参与门禁判断。
- 创建、取消、手动刷新和 SSE 生命周期事件继续失效 `project-build-validations / SOURCE_ONLY` Query Key，状态更新不依赖固定间隔轮询。
- backend 保持不变。

### 82. 合并领域 SSE 高频非终态刷新

- 对应任务：7.101。
- 定位到创建成功会立即失效一次领域 Query Key，而随后快速到达的 `task.created/task.queued/task.started` 又分别失效同一前缀；x86 的分页列表与 latest 共用该前缀，因此每个事件都会同时产生两次读取。
- 项目级 SSE 现在将非终态领域失效按 Query Key 在 250ms 内合并，并以 `cancelRefetch: false` 避免后续瞬时事件取消、重启正在进行的读取；terminal 事件会清除待执行定时器并立即刷新，保证最终状态及时且准确。
- 创建成功即时刷新、overview 独立批处理、event cursor 去重与重连续传保持不变；该策略同时适用于后续所有领域 Drawer。backend 保持不变。

### 83. 四节点请求与刷新所有权矩阵

- 对应任务：7.102。
- 新增 `request-refresh-matrix.md`，逐项记录环境管理、源码管理、x86 构建和知识库扫描默认读取、readiness/latest 职责、会产生 SSE 的写操作、mutation 成功策略、SSE 刷新路由和当前风险。
- 将写操作划分为同步实体写入、同步 Context 写入、异步任务创建和无 SSE 的同步业务状态编辑，分别指定推荐刷新所有者；明确禁止 mutation 广泛失效、逐事件 SSE 失效和固定轮询三条链路叠加。
- 记录三个后续重点：源码 terminal 与 Context 事件双刷、运行环境 PATCH 与 Context 事件双刷、环境脚本 terminal 未定向刷新执行历史；补充 readiness 依赖图和 List/latest Query Key 拆分条件。
- 在 design 建立矩阵入口，并要求后续 Drawer 请求调整先完成所有权检查。backend 保持不变。

### 84. 按 SSE 事件语义拆分 overview 刷新节奏

- 对应任务：7.103。
- `project.context.changed` 保持 250ms 固定窗口合并；`task.created/queued/started` 改为 5 秒项目级合并；`task.progress` 改为 10 秒节流；`task.succeeded/failed/cancelled/timeout` 四类 terminal 事件立即刷新 overview。
- Context 刷新会覆盖待执行的生命周期和进度刷新，terminal 则清除全部待执行的 overview timer 后立即读取，避免权威数据已经更新后旧 timer 再产生重复请求；页面重新可见仍保留立即刷新。
- 领域 latest/List 的 250ms 非终态合并与 terminal 立即刷新保持不变，backend 保持不变。

### 85. x86 构建创建成功不再抢跑刷新

- 对应任务：7.104；纠正 7.99 至 7.101 中暂时保留的 x86 创建成功即时失效。
- 删除 POST `/builds` 成功回调对 `project-build-validations/project/SOURCE_ONLY` 前缀的失效，mutation 只展示任务已创建提示；`task.created/queued/started` 合并刷新一次运行态，terminal 立即刷新最终态。
- 因 List 与 latest 共用该前缀，正常任务的 latest 从“mutation + 非终态 SSE + terminal”三轮降为最多两轮；极快任务由 terminal 覆盖待执行非终态 timer，只读取一轮。用户手动刷新保持立即校准；取消成功的即时失效随后由 7.105 删除。backend 保持不变。

### 86. 四节点统一单一刷新所有者

- 对应任务：7.105；进一步收敛 7.102 中记录的三项已知双刷与漏刷。
- 环境切换和同步上传源码只将接口响应合并到 overview 提供即时反馈，不再由 mutation 提前失效 Context 下游；Git 同步 source terminal 同样不触碰 Context 下游，统一等待 `project.context.changed` 权威刷新。
- x86 取消成功不再立即失效 List/latest，等待 `task.cancelled` terminal 刷新；知识库扫描原本已遵循创建成功只提示、领域事实由 SSE 刷新的规则，保持不变。
- 环境自定义脚本依据 `resource.mode=CUSTOM_BASH` 和 `resource.id=environmentId` 将 terminal 事件定向路由到对应执行记录，避免错刷环境 List；提交后历史视图的首次挂载负责显示运行态，不再叠加非终态 SSE 读取。环境检查、采集等环境事实任务仍在 terminal 刷新 List/选项。
- backend 保持不变。

### 87. 依赖分析接入请求刷新矩阵

- 对应任务：7.106。
- 删除依赖分析 POST 成功回调对 `project-dependency-analyses` 前缀的即时失效，mutation 只返回最新结果视图并提示任务已创建；运行态与最终态分别由 `dependency_analysis_run` 非终态合并事件和 terminal 事件刷新。
- 自动修复创建同样只提示并关闭弹窗；删除可注入额外刷新的 `onCreated` 回调。`dependency_auto_fix_run` 生命周期不再刷新 dependency latest，也不再在成功时广泛失效全部运行环境下游；默认创建的重分析任务通过自身 `dependency_analysis_run` SSE 更新 latest。
- x86 构建生命周期新增 `rv-dependency-analysis` readiness 精确失效；源码或运行环境 Context 变化也将该 readiness 纳入下游失效集合，确保 `X86_BUILD/TARGET_ENVIRONMENT` 门禁及时校准。
- backend 保持不变。

### 88. 五节点查询作用域与门禁缓存收敛

- 对应任务：7.107。
- 将 `x86-build` readiness 加入源码和运行环境 Context 变更的下游失效集合，避免全局五分钟缓存窗口内继续使用旧源码或旧源环境门禁；x86 latest 请求失败改为明确错误态，不再把请求失败误判成无历史记录并静默采用默认命令。
- 知识库 latest 只在当前结果视图启用、readiness 只在结果或配置视图启用；历史 List 并入 `project-knowledge-base-scans` 父 Query Key，使扫描 SSE 能刷新当前可见历史而不会同时请求不可见 latest。依赖分析 readiness/latest 同样只在默认 current 视图启用，历史和结果详情不再受不可见 current 查询的 loading/error 阻断。
- 源码管理区分初次 loading 与后台 fetching，Context SSE 或手动校准不再卸载 Drawer 内容；共享 `BaseTable` 关闭窗口聚焦和网络重连隐式 refetch，列表事实继续由视图挂载、SSE 精确失效和用户手动刷新推进。
- backend 保持不变。验证覆盖项目 Context SSE、知识库历史、依赖分析视图隔离、x86 latest 失败和 BaseTable 受影响测试。

### 89. 评估报告接入 readiness、latest 与单一刷新链路

- 对应任务：7.108；后续集中化任务：8.3、8.4、8.10。
- 评估报告默认视图并行读取 `readiness?stageId=report` 与 `reports/evaluation/latest`，删除共享 overview 和 `reports/evaluation?page=1&pageSize=1` 的 List-as-latest；创建请求的源码 ID 只取 readiness Context。
- 生成门禁由 `KB_SCAN`、`DEPENDENCY_ANALYSIS`、`INCLUDED_FINDINGS` 的 `key + status` 组合决定，并逐项展示恢复入口；`COMPARABLE_REPORT` 仅服务报告比较，不阻止生成第一份报告。`CURRENT/STALE/EMPTY` 分别表达当前报告、旧 Context 报告和无历史报告。
- POST 创建成功只反馈任务已创建，不主动失效 latest；只有 `evaluation-report + resource.type=report` 生命周期 SSE 刷新报告事实，报告比较和复检事件不误刷 latest；KB/依赖生命周期和源码/环境 Context 变化精确刷新 report readiness。进入报告问题来源详情后停用不可见的 readiness/latest，避免后台 SSE 产生无意义请求。
- 报告纳入/排除属于无 SSE 的同步业务编辑：知识库 Finding 与依赖结果更新本地缓存并校准自身列表后，同时精确失效 report readiness，使 `INCLUDED_FINDINGS` 数量和门禁及时更新。backend 保持不变。

### 90. 评估报告关闭过程不重启 current 查询

- 对应任务：7.109。
- 原实现从报告问题详情关闭 Drawer 时，会先清空 `issueId` 并删除 latest 缓存；父组件的 `visible=false` 尚未提交，导致 readiness/latest observer 在一个中间 render 中从 disabled 变回 enabled，并对已删除的缓存立即发起请求。
- 新实现以本地 `isClosing` 表达关闭意图：收到 `onClose` 后先停用 current 查询，不在 active observer 存在时删除缓存；内部详情与筛选状态仅在 Drawer 关闭动画完成的 `afterOpenChange(false)` 中重置。重新打开时仍按 stale query 的正常挂载规则读取权威数据。

### 91. 领域 Drawer 首次执行状态统一为就绪

- 对应任务：7.110。
- 将“前置条件满足且当前 Context 暂无执行结果”的统一语义从普通 `empty` 调整为 `ready`，明确表达当前阶段已经可以执行，而不只强调缺少数据。
- 知识库扫描在无当前结果和仅有旧 Context 结果时展示 `ACTIVE_SOURCE` 已准备、首次扫描主操作与历史入口；评估报告与依赖分析沿用同一绿色就绪语义和前置条件事实。
- `empty` 继续保留给不涉及执行门禁的普通无数据展示，不再用于上述领域 Drawer 的首次执行状态。
- 验证：知识库与评估报告新增就绪态用例、共享状态组件测试、frontend typecheck、相关 ESLint、Prettier、`git diff --check` 和 `openspec validate remediate-issue --strict` 通过；合并运行页面测试时一个既有“纳入报告”交互用例超时，单独复跑通过。

### 92. 构建验证接入 readiness、latest 与单一刷新链路

- 对应任务：7.111；后续集中化任务：8.3、8.4。
- 构建验证默认视图并行读取展示 Context、`readiness?stageId=build` 与 `builds/latest?mode=VALIDATION`；`ACTIVE_SOURCE/SOURCE_ENVIRONMENT/TARGET_ENVIRONMENT` 的 `key + status` 是唯一门禁，创建请求源码 ID 只取 readiness Context。删除 overview 门禁推导、`buildScope=BOTH&pageSize=100` 的 List-as-latest 和 1.5 秒固定轮询。
- 当前 latest 契约只返回单条构建运行，因此默认页展示一张真实最新运行卡；完整双环境构建记录在进入历史页后按 `buildScope=BOTH` 分页读取。构建命令优先使用 `freshness=CURRENT` 的 latest command，缺少当前记录时才回退内置默认值。
- 创建与取消成功只反馈，不主动失效 latest/List；`build-validation + resource.type=build_run + mode=BOTH` 生命周期事件刷新 `VALIDATION` 父 key，terminal 同时精确刷新自动化测试 readiness。历史和日志视图停用 current 查询；关闭意图先停用 observer，动画结束后再重置内部状态，避免关闭时请求回流。backend 保持不变。

### 93. 构建验证改为与 x86 一致的记录型主视图

- 对应任务：7.112。
- 移除构建验证“当前结果 → 历史记录”二级导航，默认直接展示完整 `BOTH` 分页记录；ID 单元格与 x86 构建统一为纯 ID 加可选“当前”Tag，状态、创建时间、状态筛选、状态 Tag 和单行操作保持一致。构建验证仅额外增加独立环境列显示环境名称与架构，构建目录回归日志详情。
- `VALIDATION latest` 不再单独渲染结果，只在 `freshness=CURRENT` 时以 `result.id` 标记对应记录并初始化构建命令；没有当前结果时不标记历史行。List 与 latest 继续共用 `VALIDATION` 父 Query Key，由同一 SSE 生命周期刷新；进入日志后停用不可见的 readiness/latest/List，backend 保持不变。

### 94. 自动化测试接入 readiness、latest 与单一刷新链路

- 对应任务：7.113；后续契约收敛任务：8.3、8.4。
- 默认视图使用 `readiness?stageId=test` 的 `BUILD_VALIDATION` prerequisite 作为唯一执行门禁，创建请求源码 ID 只取 readiness Context；当前批次改由 `automated-tests/latest` 的 `CURRENT result.testBatchId` 锚定，命令优先初始化为当前 latest command，不再使用测试 List 第一条推算当前事实。
- backend latest 目前只返回批次中的单侧运行，tests List 也没有 batch 过滤，因此当前源码 tests List 暂时只用于补齐 latest 同批另一侧和历史批次；readiness 在已有测试后可能不提供双端 build ID，因此当前源码构建 List 暂时只用于解析 POST 输入。这些兼容读取不参与门禁，也不允许选择其他当前批次。
- 移除 tests/builds 的 1.5 秒固定轮询以及创建、取消 mutation 的查询失效；mutation 只反馈，`automated_test_run` 与 `test_comparison_run` 生命周期 SSE 分别失效测试和比较父 key，terminal 精确刷新归档 readiness。源码或运行环境 Context 变化同时失效 test 与 archive readiness。
- 当前、历史、批次详情和日志分别控制查询作用域；进入历史/详情/日志或开始关闭时停用不可见 readiness/latest，关闭动画结束后才重置内部状态，避免请求回流。backend 保持不变。
- 验证覆盖 API latest 契约、readiness 门禁、latest 命令/当前批次、mutation 无主动失效、历史/日志/关闭态查询隔离以及 SSE 下游 readiness 路由。

### 95. 优化闭环接入 readiness、latest 与上游聚合刷新

- 对应任务：7.114；后续集中化任务：8.3、8.4。
- 默认页由旧 `GET /optimization/overview` 切换为并行读取 `readiness?stageId=optimize` 与 `GET /optimization-cycles/latest`；`ACTIVE_SOURCE` 只判断当前源码前置，当前轮次只接受 `freshness=CURRENT` 的 result。`STALE` 不再冒充当前结论，只提示旧源码轮次可从历史查看；删除未再使用的 frontend overview API 与类型。
- 历史 List 统一使用 `project-optimization-cycles` 父 Query Key，current latest 使用其 `latest` 子 key；上游源码部署、报告生成/源码复检、x86 与双环境构建、自动化测试和结果比较生命周期事件失效父 key，非终态沿用 250ms Query Key 合并、terminal 立即刷新。报告比较不改变轮次摘要，因此不误刷优化聚合。
- 迁移问题纳入/排除是无 SSE 的同步编辑，在来源缓存与 report readiness 校准之外增加一次优化轮次父 key 精确失效，使问题收敛数量及时更新。
- 当前、历史和历史详情按视图启用查询；历史刷新不会请求 readiness/latest，历史详情不提供错误的 current 刷新，关闭意图先停用 current observer，动画结束后再重置视图。backend 保持不变。
- 验证覆盖 latest API 契约、readiness 缺失、CURRENT/STALE 展示、下一步导航、历史与关闭查询隔离、同步纳入状态及上游 SSE 刷新路由。

### 96. 归档接入 readiness、latest 与候选依赖刷新

- 对应任务：7.115，并完成集中化任务 8.3 的最后一个节点。
- 默认视图由旧 `GET /archives/overview + project overview` 切换为并行读取 `readiness?stageId=archive` 与 `GET /archives/latest`；`ARCHIVE_CANDIDATES + SATISFIED` 是创建归档的唯一门禁，源码是否存在来自 readiness/latest Context，归档是否属于当前源码只认 latest freshness，不再在 frontend 比较两个 overview 字段。
- CURRENT 成功归档继续提供主下载操作；STALE 归档明确标记当前源码尚未归档，保留旧归档查看和下载，但当前源码创建操作仍由 readiness 决定；当前源码存在但无候选时引导返回优化闭环，不再发送必然被 backend 拒绝的创建请求。
- 创建 POST 成功只反馈任务已创建，不主动 refetch latest、刷新历史或读取 project overview；`stageId=archive + project_archive` 生命周期事件失效 archives 父 key，运行态合并、terminal 立即刷新。
- 根据 backend 候选登记点补齐 readiness 依赖图：知识库/SBOM、依赖分析、报告/报告比较/源码复检、x86/双环境构建、自动化测试/结果比较只在 `task.succeeded` 后刷新 archive readiness，失败、取消、超时和 progress 不做无意义门禁读取。
- latest 使用 archives 父 key 的 `latest` 子 key，历史 List 使用父 key，详情按归档 ID 独立读取；历史刷新只作用于当前可见 List，历史/详情/关闭态停用 current readiness/latest，关闭动画结束后再重置视图。backend 保持不变。
- 验证覆盖 latest API、readiness 门禁、创建 mutation 无主动失效、CURRENT/STALE/缺候选展示、下载与历史详情、历史/关闭查询隔离以及成功/失败上游 SSE readiness 路由。

### 97. 优化闭环统一前置条件状态展示

- 对应任务：7.116。
- 缺少当前源码时由旧的通用 `Empty + 主按钮` 切换为与知识库扫描、依赖分析和评估报告一致的 `StageStateNotice` 前置条件状态；状态区明确展示“当前源码 / 未导入或未激活”，并在该条件行提供“前往源码管理”恢复入口。
- 门禁和请求链路保持不变，仍只认 `readiness?stageId=optimize` 的 `ACTIVE_SOURCE + SATISFIED`；本次仅统一信息层级与交互表达，backend 保持不变。

### 98. 归档统一前置条件与首次就绪状态展示

- 对应任务：7.117。
- 归档默认页移除自定义交付空态，完整遍历 readiness 返回的 `prerequisites[]` 并映射为 `StageStateNotice` 条件项：`key` 是条件身份、中文标题和恢复入口的唯一来源，`status` 统一映射“已满足/未满足/进行中/失败/已过期/不可用”并决定门禁，`details` 仅补充候选数量，展示层不读取 `reasonCode`。当前 backend 只返回 `ARCHIVE_CANDIDATES`，因此其恢复入口固定为优化闭环。
- 当 latest 是旧源码归档且当前 Context 的门禁未满足时，保留旧归档查看与下载，同时在摘要前嵌入当前前置条件阻断状态，避免 footer 单按钮承担全部语义。readiness/latest、SSE 刷新与创建 mutation 行为均未改变，backend 保持不变。

### 99. Change 最终契约收口

- 以后端现有 overview、readiness、latest、List 和项目 SSE 为最终契约基线，重写 proposal、design 和三组增量 specs，不再把早期动态 Workflow、overview 内 build/source-deployment readiness、复合构建 `resource.step`、批量报告纳入或删除兼容 GET 路由作为本 change 的待交付内容。
- 将 `tasks.md` 从实施流水账收敛为当前可验收结果；本日志继续保留 7.x 期间的临时兼容方案、视觉迭代和后续纠偏，避免通过改写历史掩盖决策过程。
- 校准请求刷新矩阵：overview 不再承担 Workflow 事实，异步任务 mutation 不保留“有理由即时刷新一次”的例外，优化闭环移除独立源码部署事件描述。
- 修复环境列表“设为当前环境”测试因 `userEvent` 与 Ant Design 浮层交互叠加造成的 10 秒超时，改为直接触发确认交互并等待异步回调；同时修复知识库 API 文件格式。
- 最终验证通过：Prettier、ESLint、TypeScript typecheck、31 个相关测试文件共 203 个用例、`openspec validate remediate-issue --strict`。
