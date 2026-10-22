## ADDED Requirements

### Requirement: 构建验证必须保存 compile database 构建上下文
构建验证 worker SHALL 在成功构建后保存可复用的 `compile_commands.json` 构建上下文制品，并 SHALL 将安全摘要写入构建事实。

#### Scenario: 成功保存 compile database artifact
- **WHEN** `BUILD_VALIDATION` worker 在远端源码部署目录完成构建且退出码为 `0`
- **AND** 远端工作目录存在合法 `compile_commands.json`
- **THEN** worker SHALL 将该文件下载到后端受控临时位置
- **AND** worker SHALL 校验 JSON 顶层为数组
- **AND** worker SHALL 将文件保存为对象存储制品
- **AND** worker SHALL 在 `build_runs.build_facts.compileDatabase` 中写入 `available=true`、stored artifact ID、sha256、size bytes、command count、source environment ID 和 build run ID

#### Scenario: compile database 不存在时构建仍成功
- **WHEN** 构建命令退出码为 `0`
- **AND** 远端工作目录不存在 `compile_commands.json`
- **THEN** worker SHALL 将构建运行标记为 `SUCCEEDED`
- **AND** worker SHALL 在 `build_runs.build_facts.compileDatabase` 中写入 `available=false`
- **AND** worker MUST NOT 因缺少 compile database 将成功构建改为失败

#### Scenario: compile database 无效时降级
- **WHEN** 构建命令退出码为 `0`
- **AND** 远端 `compile_commands.json` 下载失败、超过大小限制或 JSON 格式非法
- **THEN** worker SHALL 将构建运行标记为 `SUCCEEDED`
- **AND** worker SHALL 记录 warning 和安全失败原因
- **AND** `build_runs.build_facts.compileDatabase.available` SHALL 为 `false`

#### Scenario: 构建详情只返回安全摘要
- **WHEN** 用户查询包含 compile database 的构建详情
- **THEN** 响应 SHALL 返回 compile database 是否可用、artifact ID、sha256、size bytes、command count 和来源构建摘要
- **AND** 响应 MUST NOT 返回完整 `compile_commands.json`、远端工作目录、服务器本机路径、bucket 或 object key
