## Context

demo-test1 运行 d1130a1e-0d38-4d07-b83e-26181a89313f 保存了两条 Finding，原始 detail 中 primaryLocation 与 occurrence.location 均为空。后端按该字段入库，并非前端遗漏。当前 facts._point 要求 file、line、col 齐全；Clang 的合法子表达式经常只包含 offset、col。在 worker 中通过真实 Clang 已复现这种输入返回空位置。

当前 map_ast 的项目归属布尔值不足以恢复具体文件；rules._aggregate_findings 选择的 primary 与排序后的关联位置也可能不一致，需要用测试验证并纠正。最近 AST-only 变更解决了扫描前置条件，但未解决坐标恢复。

## Goals / Non-Goals

**Goals:**
- 在来源可证实时恢复真实项目相对路径、行列及内部起止范围。
- 保留直接证据对应的全部位置，遵守既有结果预算和 v2 协议。
- 验证 JSON、数据库、列表/详情和 HTML 的一致性。

**Non-Goals:**
- 不改变规则选择、BC readiness 或内存序工具；风险判定仅追加修复用户授权的指针比较误报。
- 不从报错文本猜路径，不使用函数声明行替代运算表达式行。
- 不自动回填旧报告，不修改前端，不扩大现有 API/schema。

## Decisions

### 1. 扫描器内集中恢复源码位置

在 facts 层建立任务内的位置解析上下文，以真实翻译单元、编译工作目录、AST 显式文件标记及遍历上下文确定当前文件。显式位置优先；文件字段省略时，仅在文件归属可证明的情况下继承。实现需覆盖兄弟节点切换和 include 进入/退出，不能简单把所有缺 file 节点归入主文件。

文件边界校验后，按源文件原始字节缓存换行索引，从 Clang 字节 offset 恢复缺失行列，避免 UTF-8 多字节、CRLF 和制表符引起字符索引偏移。明确行列为 1-based，偏移为 byte offset；只对有效文件及范围内偏移恢复。缓存遵守既有扫描预算，不为每个 AST 节点重复读文件。

loc 缺失或空对象时尝试 range.begin；起止位置分别解析，不直接复制父节点行列。跨文件范围不拼成伪造的连续代码区间。#line 的逻辑文件名与物理源码位置必须区分，无法可靠映射时保留未知。

不采用后端读取源码猜测坐标：扫描器掌握完整 AST 上下文，后端仅凭 finding 摘要无法恢复真实表达式。

### 2. 宏和头文件保留各自来源

分别解析 spellingLoc 和 expansionLoc。沿用 v2 现有主位置选择语义；项目内调用位置与必要来源证据保持区分，系统头文件不得因字段省略而冒充项目文件。项目头文件应允许成为真实项目位置；若与现有归属过滤存在冲突，在工具规范中同步澄清，仍排除外部头文件独立 Finding。

路径读取继续使用项目边界检查，禁止越界和通过符号链接读取未授权文件。缺源文件、非法 offset、无法确定文件等情况保留空位置，使用现有 diagnostics 表达双语稳定原因，不把定位失败当作无风险。

### 3. 聚合以可用主位置为基准去重

依据实际直接证据生成位置集合，以相对路径和行列稳定排序；选择可用主位置，再将其余位置列为 related occurrences。不能先取任意 finding 为 primary，再独立丢弃排序集合的第一项。多个不同位置不能因其他语义相同而丢失，主位置不能重复出现。超预算沿用显式截断/partial 约束，不能声称完整。

v2 对外 location 目前是点位置，不增加未经设计的范围字段；内部 source_range 必须恢复正确。后端 start/end 若来自点位置可以相同，不伪装成扫描器提供了完整表达式区间。

### 4. 通过现有后端链路验证

保留 v2 和现有 DTO。验证 parseFindings、入库字段及 detail、API、HTML 与工具输出一致；仅发现实际映射缺口时修改后端实现。未知位置继续允许为空。历史记录和报告不可变，部署后重新创建扫描，不直接更新旧数据库记录。

### 5. 测试与文档

独立单测覆盖正常、异常和边界，不连接数据库、SSH、对象存储或其他外部服务；mock 连接返回值。真实 Clang 生成 AST 的验证归入集成测试，真实项目 API 验证归入 E2E，均不能替代单测。Linux Docker 中执行现有覆盖率命令，工具整体及受影响模块行/分支均达到 90%；后端发生实现变更时执行对应整体及模块门禁。纳入未加载自有源码，记录测试、fixture、第三方及生成文件的排除理由。

同步工具的 compilation-context-ingestion、相关结果聚合规范及设计文档，不把工具规范误同步到 backend 的独立能力目录。

## Risks / Trade-offs

- 文件上下文继承错误会产生看似准确的错误位置 → 使用真实 Clang 主文件/项目头文件/系统头文件/宏混合 fixture 验证，不确定时保留未知。
- 位置参与事实 ID 与语义摘要 → 新扫描 ID 可能变化，依照现有重跑替换策略处理，不承诺旧 ID 稳定。
- 字节索引增加内存 → 任务内按需缓存并遵守已有资源预算。
- 旧项目源码或构建制品已清理 → 明确记录 E2E 阻塞，不编造历史位置；使用保留源码的真实用例补充验证。

## Migration Plan

先完成工具与后端测试，再重建包含新版扫描器的 worker。通过新扫描验证 demo-test1 和保留的回归项目，保留 JSON/HTML 与 API 对照结果。无数据库迁移，必要时回滚镜像；已经生成的新旧扫描结果均保持可审计。

## Open Questions

无阻塞性产品问题。用户已在 apply 中授权 tools/floating-point-precision-scanner；不涉及其他工具。

## 追加：后端源码上下文

直接扩展现有浮点/内存序 Finding 详情响应，增加 `codeContext` 和 `codeContextUnavailableReason`，一次请求获取详情和代码；撤销独立 `/code-context` API。列表不读取源码，避免分页列表逐条加载大量上下文。共用后端读取逻辑，不改工具 schema，也不修改前端。

首先校验项目访问权，再约束 Finding 的 projectId/analyzerType，从 Finding 绑定的 sourceRevisionId 查找工作副本；不能回退到当前源码版本。读取既有主位置，前后各 20 行，文件不足则截断；返回 findingId/runId/sourceRevisionId/filePath、contextBefore/contextAfter、实际 startLine/endLine、highlightStartLine/highlightEndLine 及 lines（lineNumber/text/highlighted）。关联 occurrences 的多文件展开不在本次接口范围内。

复用 ServerPathGuard 拒绝绝对路径、目录穿越和越界符号链接。UTF-8 严格解码，以最多 8 MiB+1 的有界读取拒绝超过 8 MiB 文件。无位置、旧文件已清理、非法范围、编码错误时，详情仍返回原始 Finding，`codeContext=null`，`codeContextUnavailableReason` 提供稳定原因码；权限和 Finding 归属错误仍拒绝整个请求。不伪造文本、不泄漏绝对路径。原始 detail 与不可变扫描结果不变。

测试覆盖正常读取、多行高亮、历史版本、文件头尾、空文件、缺失/越界位置、路径攻击、无权限/跨项目/跨类型、非法编码和体积限制。Docker 运行后端全量独立测试和 JaCoCo 整体/包级 90% 门禁；真实 API 验证已保存的 demo-test1 Finding，不要求重新扫描。

## 实施补充

- SourceLocations 在已加载 AST 的位置字典上原位补齐，按 Clang 序列化顺序继承文件名，避免复制大型 AST。物理坐标以源文件字节索引恢复，索引读取与存储共同受 16 MiB 的翻译单元内预算约束。
- source-facts 缓存键加入位置解析版本，避免重跑命中修复前的空位置缓存。
- 真实 AST+BC 回归发现坐标恢复后同一行乘法/加法被原有按行匹配判为歧义。对具有明确源码 opcode 的 arithmetic 事实要求与 LLVM 运算符一致，未明确 opcode 的旧证据仍沿用原有匹配；不改变风险规则。
- 用户追加授权修复空指针误报。comparison 事实使用隐式转换后的直接操作数类型，优先 desugaredQualType 展开 typedef，再判断完整浮点标量类型；不能使用包含 float/double 的子串匹配。指针比较被排除，解引用、数组元素和引用值的真实浮点比较保留。声明/ABI 类型识别不作无关调整，缓存版本升至 3。
