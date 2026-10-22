## ADDED Requirements

### Requirement: 知识生产和数据验证必须在独立测试容器中执行
新增 source extractor、curation validator、schema/lint、deterministic renderer、Provider 和 matcher 的正式验证 SHALL 只在 `kb-scanner-test` 镜像环境中执行。宿主机 MUST NOT 安装或执行其 Python、parser 或 toolchain 依赖，生产镜像和根 Compose MUST NOT 因知识采集而修改。

#### Scenario: 验证知识生产模块
- **WHEN** 开发者运行 extractor、curation 或数据质量测试
- **THEN** 测试 SHALL 通过专属 `compose.test.yml` 使用锁定环境和最小只读上游 fixture
- **AND** 任一 unit coverage、schema、provenance、hash 或 determinism gate 失败 SHALL 返回非零状态

#### Scenario: 刷新真实知识数据
- **WHEN** 维护者从固定上游修订刷新 generated 或 curated source
- **THEN** extractor SHALL 在同一测试镜像依赖环境中读取显式提供的只读 source root/archive
- **AND** 它 MUST NOT 依赖宿主机 compiler、assembler、linker 或 Python package

#### Scenario: 运行默认扫描测试
- **WHEN** `kb-scanner-test` 验证提交后的知识和 scanner
- **THEN** 容器 SHALL 保持无业务凭据、与根 Compose 隔离且不执行被扫描项目代码
- **AND** 知识 Provider MUST NOT 因数据刷新能力而获得运行时网络或 subprocess 权限
