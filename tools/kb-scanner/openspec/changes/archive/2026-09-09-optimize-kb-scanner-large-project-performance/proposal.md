## Why

libarchive 全量静态扫描（810 个输入）在独立测试容器的 2 CPU / 2 GiB / 300 秒预算下超时，未能生成报告；连续采样均停在 Normalizer 为每个宏附属 Evidence 重建全局定义集合的位置。需要先消除已经证实的重复遍历，再建立全项目性能验收，避免缩减样例通过却无法处理真实项目。

## What Changes

- 为宏定义引用校验建立单次 normalize 调用内可复用的索引，消除 Evidence 总量与宏附属数量相乘的重复扫描；保留失败诊断、事实身份、排序和 provenance。
- 使用容器内标准库计时、进程资源统计、可选 cProfile/faulthandler 建立阶段级性能证据，区分前端、归一化、关系分析、检测、分类评估和投影耗时。诊断数据只进入测试工件，不改变正式报告。
- 对后续阶段仅优化 profile 证实的重复查找，优先复用现有索引或局部 dict/set；不先行重写整个管线，不改变 parser 技术栈、不引入并行扫描或跨扫描缓存。
- 根据用户确认，源码 proof 改为 fact 驱动的按需生成：复用现有 NormalizedFact、DetectorDefinition、KnowledgeIndex 和 match_fact，将确定命中、candidate 和 hint 的 Evidence 引用作为追溯请求；完整源码、事实与基础关系不删减。反向可达索引收敛起终点，保留原逐目标详细搜索与候选相关 proof。
- 构建/测试分析继续完整运行，其链路预算只计算本阶段新增关系/proof，不再被继承的无关源码 proof 挤占；这是显式的预算隔离修正，不提高原有上限。对可能新增的构建/测试链路单独回归并审校。
- 固定完整 libarchive 源码版本、输入清单和资源预算，增加独立、显式运行的性能验收入口；默认 V2 全量扫描须在 300 秒内正常结束并生成有效的三个 artifact，不能通过少扫文件、移除诊断/证据或增加预算达标。
- 添加合成宏密集输入的复杂度回归、优化前后语义对照及输入乱序/连续扫描隔离测试；每个新增或修改业务模块具有隔离 unit inventory，容器门禁至少 90% line / 80% branch，另跑既有完整回归。
- 保持现有默认 Schema V2、显式 V1 和 `scan-result.json`、`scan-report.html`、`scan.log`；不新增主结果结构，不更改两份 Clang/GCC generated facts、curated 数据或知识加载合同。

## Capabilities

### New Capabilities

- `kb-scanner-large-project-performance`: 定义语义保持的扫描性能优化、阶段级测试观测、复杂度回归及固定真实项目的独立容器验收合同。

### Modified Capabilities

默认报告 schema、知识、候选准入和分类规则不变。内部源码 proof 从全目标预计算改为 fact 驱动，构建/测试预算计数改为本阶段增量；对应新性能规范明确该授权变化和回归边界，归档同步时与现有图/选择规范核对一致性。

## Impact

- 首要业务模块为 `kb_scanner/normalization/cpp.py`；后续仅在 profile 证实必要时修改 graph/detector/projection 的重复查找。每个实际修改模块必须同步登记独立单元测试和逐模块覆盖率门禁。
- 新增测试侧 benchmark runner、源码 provenance/输入 manifest、合成 fixture 和维护文档；优先包装已有 pipeline stage 接口，计时不侵入 core DTO。
- 仅使用独立 `kb-scanner-test` 镜像与只读源码挂载，不在宿主机安装依赖，不改生产镜像、根 Compose、后端或其他任务文件。
- 范围仍为 C/C++ x86→RISC-V 静态分析；不执行目标项目的配置、编译、链接或测试，不分析 OS/内核/驱动迁移，不建模 uname 交叉编译选错分支。
