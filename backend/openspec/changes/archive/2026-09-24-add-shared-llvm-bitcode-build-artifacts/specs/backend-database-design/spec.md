## ADDED Requirements

### Requirement: 数据库必须保存共享 LLVM BC artifact-set 引用
数据库 SHALL 通过 `build_runs.build_facts` 和 `stored_artifacts` 保存共享 LLVM BC 的安全摘要与不可变制品引用，不得将 BC 二进制写入数据库。

#### Scenario: 构建事实保存 BC 摘要
- **WHEN** source/x86 构建的 BC 后处理达到终态
- **THEN** `build_runs.build_facts.bitcode` SHALL 保存状态、可用性、artifact-set ID、计数、toolchain/schema/profile、reason code、warning count、生成时间和 stored artifact ID
- **AND** 摘要 MUST NOT 保存 BC 二进制、完整 manifest、完整编译命令、环境变量值或真实绝对路径

#### Scenario: stored artifacts 保存 manifest 和 bundle
- **WHEN** BC artifact-set 存在可消费制品
- **THEN** `stored_artifacts.owner_type` SHALL 为 `BUILD_VALIDATION`
- **AND** `owner_id` SHALL 为对应 `build_runs.id`
- **AND** artifact type SHALL 能稳定区分 `LLVM_BITCODE_MANIFEST_JSON` 和 `LLVM_BITCODE_BUNDLE_TGZ`
- **AND** 制品元数据 SHALL 保存 SHA-256、大小、content type 和安全摘要

#### Scenario: 同一构建制品类型不得产生不可解释重复
- **WHEN** 系统保存同一 build run 的 BC manifest 或 bundle
- **THEN** 数据库或服务层 SHALL 防止同一 owner 下相同 artifact type 出现多个当前成功制品
- **AND** 重试 SHALL 复用相同 artifact-set identity 或替换未完成临时上传，不得覆盖其他构建的制品

#### Scenario: 对象存储失败只记录 BC 失败
- **WHEN** manifest 或 bundle 写入对象存储失败
- **THEN** `build_facts.bitcode.status` SHALL 为 `FAILED`
- **AND** 不完整 stored artifact 元数据 MUST NOT 被查询为可用
- **AND** `build_runs.status` MUST 保持由真实构建结果决定
