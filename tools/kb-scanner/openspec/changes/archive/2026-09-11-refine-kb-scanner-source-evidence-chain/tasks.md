## 1. 冻结基线与测试边界

> 2026-09-11：用户已通过“可以补齐”授权 KB Scanner 内必要的历史隔离单测补齐；基线见 [quality-baseline.md](quality-baseline.md)。整体及受影响模块仍执行 90% 行/分支门槛，不涉及其他工具目录，不降低统计范围。

- [x] 1.1 在独立 kb-scanner-test 容器记录当前 V2 阶段节点、按类型拼链和前后 2 行行为；冻结同一输入的 facts、conclusion/summary、compiler JSON 哈希及性能/报告体积基线。
- [x] 1.2 创建人工最小 Makefile → 参数实际使用 → target/source → 条件宏 → 多级包装宏 → intrinsic 跨文件 fixture，逐节点/边定义 oracle；加入未使用变量、其他目标、缺失输入、同名歧义、-D0/-U/覆盖反例，不用 scanner 输出自动生成真值。
- [x] 1.3 按 design 为所有新增/实质修改模块登记 isolated unit inventory、fake/mock 边界和独立门禁入口，冻结项目整体及每个受影响模块 90% line / 90% branch 与既有图预算，包含未加载源码并明确排除项；历史大规模缺口须报告并请求扩大范围；记录可重复性能验收阈值和命令，不安装本机依赖。

## 2. Makefile 宏参数与作用域桥接

- [x] 2.1 在受限 Make frontend 提取 -D/-U token、已知变量赋值/追加及 recipe 静态引用，保留原始参数行列和顺序；新增 fake 输入单测覆盖组合/分离参数和不支持构造。
- [x] 2.2 在 normalizer 保留参数定义/取消、target/source/configuration 和变量来源引用，不合并不同状态 occurrence；配套隔离单测校验位置和引用闭合。
- [x] 2.3 实现有界 build macro binding resolver 及 build_selection 接线，分别证明参数实际使用、源码成员和条件绑定；配套未使用变量、其他 target、未知 recipe 的隔离单测。
- [x] 2.4 接入 #ifdef/#ifndef、defined、已知整数 #if/受限比较的宏值/存在性、-U 与源内覆盖语义，保留嵌套 guard 和 include 可见性；为所有修改 resolver/源图模块补隔离单测，未支持表达式保持 unknown。
- [x] 2.5 在独立容器运行本阶段逐模块门禁及真实语法组件测试，证明最小正例确实闭合，反例无伪启用关系且不执行 Make/编译器。

## 3. 需求驱动的真实上游查询

- [x] 3.1 为 Entity/Evidence 和入/出边建立可复用索引，按 matched Evidence、occurrence/configuration 查询上游及必要终端展开；补 fake DAG 单测，不恢复全 root×terminal 或逐 Finding 全图扫描。
- [x] 3.2 补齐普通宏、嵌套 guard、include 与 build 关系的精确端点映射和连续结构节点折叠，明确 guarded_by 方向投影及完整 provenance；单测覆盖无位置实体和无法映射端点。
- [x] 3.3 保留多层同 kind、候选分支和各 occurrence 状态，实现确定性主路径选择及循环/歧义/缺失/预算断点；补乱序输入、冲突配置、孤立同类节点和低预算单测。
- [x] 3.4 在独立容器运行 query/index/关系模块隔离覆盖和合成大图检查，确认无关图增长不改变相关查询语义、计数真实且原图预算未放宽。

## 4. V2 代码主链与结论分离

- [x] 4.1 修改 mapper/chain builder 显式传递命中锚点，移除 kind 代表节点、无依据相邻/contains 连线；主路径必须包含锚点且实际连通，为两模块补独立 fake snapshot 单测。
- [x] 4.2 不再生成 classification/assessment 节点及 classified_as/impacts_assessment 边，impactStepIds 输出 []；内部 Classifier/Assessor 和 conclusion/summary 保留，增加同一 snapshots 投影前后结论不变的单元断言。
- [x] 4.3 将 knowledge_match 保留为实际命中关联的旁支而非 primaryPath 节点，保留 entry/source digest；补普通调用不抢占 intrinsic、缺少知识来源和多命中隔离单测。
- [x] 4.4 为单节点/局部链、unknown candidate、RPM 和 enum 统一生成真实证据断点，更新 projector 接线与被修改模块的隔离测试；不得把 classification 名称伪装为代码断点。
- [x] 4.5 在独立容器执行 chain/mapper/projector 单元门禁，字段级确认新结果无分析阶段节点、有实际连线、非等价候选不被拼为 complete。

## 5. 上下各 20 行与上下文缓存

- [x] 5.1 将统一 source projector 默认窗口调整为前后各 20 行、256 行/65536 字符硬预算，命中优先并均衡保留邻近上下文；补 41 行、多行命中、文件首尾的 fake reader 单测。
- [x] 5.2 修正多行/超长单行/字符预算截断处理，保留原始 span、合法高亮和显式 partial/unavailable；补命中不可被普通上下文挤掉、Unicode/CRLF、读取/解码失败与根外路径单测。
- [x] 5.3 实现扫描内按文件读取/拆行及 span/window 缓存，fact/occurrence/step 共享规则，核查 Diagnostic 影响；补每文件一次读取/拆行、缓存隔离及不跨扫描复用单测。
- [x] 5.4 在独立容器运行 context 及所有受影响模块的覆盖门禁，断言输出不超硬预算、正常窗口不缩水、不产生越界 highlights。

## 6. 机器合同与兼容迁移

- [x] 6.1 原子更新 V2 model、JSON Schema、reference rules、vocabulary：空 impact、扩大 context、真实主路径端点与状态验证；为 model/validator 增加隔离正反例。
- [x] 6.2 更新 complete/partial/ambiguous/inactive/unknown、AVX/enum/RPM 代表性示例与迁移清单；验证有效历史 V2 可读取、新 producer 禁止旧阶段节点，无效历史引用仍失败。
- [x] 6.3 验证默认 V2、显式 V1、三个 artifact、无 V1→V2 补链和原子发布；核查 scanner renderer 对空 impact/新上下文的处理与 HTML 转义，如修改业务模块则补其隔离单测。
- [x] 6.4 在独立容器运行契约与本 change 组件测试，逐字段检查最小完整链、每个节点位置/上下文/高亮、primaryPath/edge/break/knowledge 引用，不能只校验数量。

## 7. 回归、性能与交付

- [x] 7.1 在独立容器运行全部受影响 unit gates 与完整回归，覆盖 AVX、RPM、enum、候选语义和既有可用 libarchive 基线；区分纯投影变化与新增证据引起的结论修正，逐项审校差异账本。
- [x] 7.2 按固定输入/配置/容器比较索引查询与上下文投影耗时、访问/缓存计数、RSS 和报告字节；达到首阶段冻结阈值，输出增长须归因，不能降低正常 20 行窗口或扩大图预算规避。
- [x] 7.3 验证 compiler JSON 原哈希、静态无执行/无根外读取/无输入修改和 V1 合同；确认所有实质修改模块已映射且满足逐模块覆盖率。
- [x] 7.4 更新 schema-v2-design、支持矩阵、开发计划和源码链审校记录，明确 V2 消费语义兼容边界、Make 子集、未知项及性能结果。
- [x] 7.5 严格验证 OpenSpec 与文件范围，完成任务后向用户提供下一阶段 /opsx:sync 与 /opsx:archive 命令；不自动同步归档、commit/push、修改其他任务目录或更新生产容器。
