## ADDED Requirements

### Requirement: Associate canonical source entities without inventing target scope

显式 AST-assisted scope SHALL 可选引用 `ProgramEntityIndex` 与 `CanonicalObjectOverlay`，将多个 artifact-local function/object key 关联到已解析 program entity/object；该关联 MUST 保留原 scope 成员和每个 dependency digest。`compile_commands.json` 仍只表示逐 TU 编译记录，不得因实体可解析而自动推导 target/link 图或加入 scope 外 TU。

#### Scenario: Two scoped artifacts bind one external object

- **WHEN** 两个 scope 成员通过唯一 source definition 和兼容 IR binding 指向同一 external object
- **THEN** association 输出一个 canonical object relation，并保留两个原始 artifact-local key

#### Scenario: Repeated evidence names the same artifact-local object

- **WHEN** 多个 source declaration/binding 证据指向完全相同的 `(artifact_key, LLVM object id, kind)`
- **THEN** overlay 在判定定义基数前对 target 去重，但保留所有 binding id/source node；不将重复证据误判为多定义

#### Scenario: The only definition is outside scope

- **WHEN** scoped declaration 的定义只存在于 compilation database 的 scope 外记录
- **THEN** association 保持 unresolved/out-of-scope，不自动扩大 scope

### Requirement: Propagate ambiguous source association conservatively

source entity、definition 或 IR binding 为 ambiguous/conflict 时，scope association SHALL 保存所有候选和 frontier，不得按名称、输入顺序或缓存顺序选择。旧 IR-only association 在未显式请求 AST overlay 时 MUST 保持不变。

#### Scenario: Same-named internal objects appear in multiple modules

- **WHEN** 多个 TU 存在同名 internal-linkage 对象
- **THEN** association 保持各自 TU-local identity，不创建跨模块对象关系
