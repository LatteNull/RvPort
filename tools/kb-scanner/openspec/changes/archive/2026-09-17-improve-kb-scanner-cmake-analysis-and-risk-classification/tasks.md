## 1. 固定基线与解析边界

- [x] 1.1 固定 demo-test1 首次源码版本、原报告摘要、输入清单/哈希与人工审校表；逐项登记原 19 项，不使用不同源码版本的第二次扫描作对照；明确 compdb 原件可获得性及复现限制。
- [x] 1.2 在独立 kb-scanner-test 中评估可复用 CMake parser，验证许可证、版本/ABI、span、错误恢复及资源边界，记录选择；必要时更新容器依赖锁，不安装本机依赖或修改生产镜像。
- [x] 1.3 冻结语义子集/未知污染/预算、风险矩阵和测试 inventory，记录 GCC/Clang 事实 JSON 哈希与现有 V1/V2 合同基线。

## 2. CMake 源码事实与有界求值

- [x] 2.1 接入 CMakeLists.txt/普通 .cmake 源码发现和独立 adapter，保留命令/参数位置、配置、解析完整性，区分机器 JSON 与未引用片段。
- [x] 2.2 为 workspace/adapter 增加隔离单元测试与 inventory，覆盖多行/注释/引号、错误恢复、根外路径、超限及第三方节点不泄漏；单独增加真实 parser 组件测试。
- [x] 2.3 实现受支持变量/列表/布尔及比较条件、本地 include/add_subdirectory 和目录作用域；对 option/cache、未知命令、生成器表达式、循环/超限实施明确未知污染。
- [x] 2.4 为 evaluator/scope/budget 模块增加直接实例化的隔离单元，覆盖目标 CPU、顺序覆盖、未知外部输入、正则子集、根外和循环，不执行 CMake。

## 3. 目标作用与拒绝证明

- [x] 3.1 规范化 CMake target/source/options/definitions 及本地 usage requirements，按 PRIVATE/PUBLIC/INTERFACE、配置和目录建立关系，接入现有 -D/-U 宏桥接。
- [x] 3.2 实现带必需入口/作用范围的 FATAL_ERROR 拒绝 proof、终止状态和 Observation；保留后续事实但禁止伪造后续 selected 或安全 inactive。
- [x] 3.3 隔离 x86 compdb/File API 观察配置和 RISC-V 静态推导，保留冲突/缺失依据，不套用 Make recipe 关联；继续遵守新增图预算。
- [x] 3.4 为 normalizer/analyzer/detector/宏桥接改动补齐隔离单元与 inventory，覆盖两 target 隔离、传播方向、-D0/-U、顺序/源码覆盖、未知配置、可选 fatal、必需 fatal、终止后命令及预算。

## 4. 风险、完整性与项目评估

- [x] 4.1 实现共享风险策略，区分确认局部依赖、未决候选、注释、完整排除及闭合阻断，取消 unknown 默认低风险/完整；保留 RPM 软依赖等专属规则。
- [x] 4.2 修正相关性/完整性处理：精确头文件知识不因 include 内容未知被抹除；只有相关缺口影响对应结论；可处理的高风险局部依赖允许 partial/unknown 且非 blocking。
- [x] 4.3 接入必需 CMake 配置拒绝的分类与 Assessment，限制 proof 范围，不按 high 数量推断阻断或 ready，不全局提升所有 missing-path。
- [x] 4.4 为 classifier/assessment/风险策略新增风险矩阵隔离单元，覆盖互斥优先级、无关 unknown relation、确认头文件、候选宏/枚举、软依赖及拒绝范围，登记全部受影响模块。

## 5. 兼容投影与源码证据链

- [x] 5.1 让 V2 与显式 V1 从同一内部决策适配现有风险字段，修正 status/actionable/blocking/reachability 的组合；不增加核心字段/枚举，不让 V2 依赖 V1。
- [x] 5.2 投影真实 CMake 上游和拒绝链，保留局部断点、命中高亮、每节点上下各 20 行及知识旁支，不恢复 classification/assessment 阶段节点。
- [x] 5.3 补齐相关 reason 的中文 suggestion 和英文 suggestion_en，确保 JSON/HTML/log 支持的风险表达一致，明确高风险非阻断与待补证边界。
- [x] 5.4 为 mapper/chain/suggestion/renderer 等实质修改模块维护隔离单元与 inventory，并增加现有 V1/V2 Schema、引用完整性、确定性、双语和 HTML 转义合同反例。

## 6. 联合回归与质量验收

- [x] 6.1 在独立测试容器扫描固定 demo-test1，逐项人工审校原 Finding 与新增 CMake 拒绝/参数证据的差异；标注无法复现的原输入，不自动重写 oracle。
- [x] 6.2 验证最小正反例：移除前置拒绝后目标闭包、x86 专属优化加真正 generic 路径、孤立片段、未知 option/生成器表达式、其他 target 参数、fatal 后声明；scalar 尾循环不得算完整 fallback。
- [x] 6.3 运行既有 Make/AVX/RPM/Autoconf/enum/候选及适用真实项目回归，记录所有结论变化；验证两份 compiler JSON 哈希、静态无副作用和现有局部图预算不变。
- [x] 6.4 执行并接入可重复的隔离单元覆盖自动门禁：统计所有自有可执行源码（含未加载模块），项目整体与每个受影响模块均达到至少 90% 行/90% 分支；说明第三方/生成文件等排除理由，不能以组件或端到端数字替代。
- [x] 6.5 写入中文能力边界与性能/审校记录，报告实际测试命令、结果、覆盖统计范围/逐模块数字及持久报告路径；失败或历史缺口超范围时保持任务未完成并请求方向。
- [x] 6.6 完成 OpenSpec 严格校验、工作区范围检查与验收汇总；确认未修改后端/前端、生产容器、历史扫描记录和其他任务文件后，再交接 sync/archive 阶段。

## 阶段交接记录

以上“不更新生产”的约束针对实现与独立测试阶段。用户随后于 2026-09-17 另行授权按当前工作区重建后端；镜像依赖补齐、API/worker 更新与冒烟验证记录见 `docs/cmake-risk-implementation-review.md` 的“后续授权更新与归档”。同日经用户授权同步 4 份主规范并归档；未 commit 或 push。
