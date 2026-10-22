## Context

用户最终确认“fact 检测出来，后续分析有依据过滤，否则无法判断”。前一版强制保留候选并展示相关选项的方向已撤回。原 55 条 libarchive 审校中 26 条人工识别的算法/格式候选不等于机器已有排除 proof；不能把人工名称清单作为运行时黑名单。

## Goals / Non-Goals

Goals：保留事实、分类阶段有证据才排除、unknown 如实展示、精确重复覆盖、正确链路标签。
Non-Goals：跨函数值流/用途自动恢复、强制消除 26 条、强制展示候选选项、外部后续机制集成、_rotl alternative/生成测试列表、真实编译/OS/后端改造。

## Decisions

### 1. 保留原始事实和检测入口

Frontend/Normalizer/matcher/FactProofDemand 不变。仅完全相同 fact 中每个架构 identifier 都被确认知识覆盖时省略重复 Observation；原 Evidence/Fact/provenance 仍保留。部分确认、独立 enum、不同 occurrence/configuration 不受影响。

### 2. 分类入口的非破坏性语义门禁

新 SemanticAdmissionIndex 只读 AnalysisSnapshot，单次索引语义关系与完整 proof，不读取源码或恢复第二套图。对候选 Observation 使用 factId、subjectId、configuration 和其原始 matchedEvidenceIds 明确范围。

内部合同：Analysis relation.kind=has_semantic_role，source_id 为该 fact 的 subjectId，target Entity.kind=semantic_role 且 name 为 algorithm、data_format、output_platform 或 execution_architecture；relation metadata 包含 factId、configuration、scope=occurrence、scopeComplete=true。relation Evidence 必须覆盖 matchedEvidenceIds。排除只在 relation.status=complete，且有 source/target 对应、所有关系存在完整的 complete ProofPath 支持时成立。所有关联 proof/role 必须一致；partial、未知角色、scope 未闭合、配置/subject 不符、引用失效或 execution/data 冲突均不能用于排除。

这是内部消费合同，不是本 change 新增的角色识别能力；当前默认图没有产出这些 data-role proofs，因此真实 libarchive 项允许继续 unknown。单元使用合成 AnalysisSnapshot 验证排除/冲突，文档明确限制，后续机制如何产生证明另行设计，不在此实现。

被证明排除的 candidate Observation 与原 facts 均不删除；ClassificationSnapshot 保留 Observation，但不生成迁移 Classification。聚合 INFO Diagnostic 记录 excluded observation/relation/proof refs 和理由，不计入 migration finding/blocking。已有 confirmed_local 不经过候选排除；并存 execution knowledge/proof 不能被数据结论盖掉。

没有排除证明时沿用现有 x86 dependency/reachability 规则；合法未决 enum/identifier 产生 unknown。修正 completeness 只对 enum 生效的缺口，使所有 unknown candidate 在 V2 conclusion/chain 同样 unknown。未知不会单独成为 blocking、portability gap 或 ready。

### 3. 精确重复覆盖

对 architecture_identifier_candidate 的整个触发 identifier 做集合覆盖，不对任意子串做覆盖。同一条件的 __i386__ 被确认不能覆盖 MY_X86_MODE。仅本 NormalizedFact 的 confirmed matches 参与，不合并其他位置/配置，也不删除独立 enum selection。

### 4. 正确投影

建立单次适用 intrinsic/builtin 符号集合，只在相应 symbol/call Evidence 精确匹配时标 intrinsic；不按 call_expression 或 _mm 前缀猜测。CPU API/普通函数不是 intrinsic。主 fact 保持原观察语义，enum/identifier 优先原 matched Evidence，辅助调用不抢占。

相同 kind 的其他 step 不是替代证明，使用中性展示关联；真正 alternative_to 必须有 Analysis relation。无新增核心 kind、必填字段、候选选项 extension 或主结果文件。未知 candidate 的 suggestion 说明当前不能确定执行依赖，可由后续分析补充；数据机器码与执行机器架构不同。

### 5. 验证

新 admission helper、detector 去重 helper/local、classifiers/migration、V2 标签 helper/chain/mapper 分别有隔离 unit mapping，合成 Evidence/Fact/Analysis/Knowledge，fake/mock 源码读取和上下游；逐模块 90% line / 80% branch，不以真实 parser/全扫描代替。

门禁覆盖完整排除、无证明、partial/conflict、跨配置/subject、非法引用、已确认命中不降级、multi-token、SHA/CRC/codec fact 保存、Backend::avx2 未绑定、unknown 完整性和普通/真实 intrinsic 混合。默认/显式 V2、V1、完整 runner 单独验证。

固定 libarchive 810 文件、2 CPU/2 GiB/无额外 swap，两新进程各 300 秒内；逐项审查 55 条来源和新变化。未有排除 proof 的 26 项仍 unknown 是允许结果，不声称用途已自动识别；2 个重叠只有完整覆盖才去重。保留知识哈希、事实/基础图数量与位置；有意输出变化按字段审查。

## Risks / Trade-offs

- [没有 role producer，部分候选不减少] → 明确 unknown，后续机制补齐，不捏造过滤依据。
- [角色证明范围不完整导致误删] → 同 fact/subject/config/原始 Evidence/完整 proof 合同，冲突一律不排除。
- [确认依赖被过滤] → gate 仅处理候选，confirmed 和执行 proof 保持。
- [判 unknown 但展示 complete] → candidate completeness、结论、链与建议联动测试。

## Migration Plan

撤回候选展示偏离，修订规范→实现门禁/去重/投影→独立单元/完整/性能回归。无后端或数据迁移。回滚仅本 change 代码/测试，不恢复 Legacy，不改 compiler facts。

## Open Questions

无当前用户决策阻塞。角色 proof 的自动生成和后续机制接入明确不在本次范围。
