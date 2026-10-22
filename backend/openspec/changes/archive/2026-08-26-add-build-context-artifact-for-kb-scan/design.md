## Context

当前构建验证 worker 会在远端源码部署目录中执行用户构建脚本，并在构建 wrapper 中尝试读取 `compile_commands.json`、`CMakeCache.txt` 和 `build.ninja`。其中 `compile_commands.json` 目前只被解析为 `RVPORT_OBSERVATION compileDatabase ...` 日志摘要，并通过 `build_runs.build_facts.logRefs` 间接进入依赖分析。

KB Scanner CLI 已支持 `--compile-commands`，且未显式传参时只会尝试读取后端本机源码工作副本根目录下的 `compile_commands.json`。由于 x86 构建发生在远端环境，远端生成的 compile database 不会自然出现在本机源码工作副本中，导致 KB 扫描无法自动获得真实编译上下文。

## Goals / Non-Goals

**Goals:**
- 在构建验证成功后保存可复用的 `compile_commands.json` 构建上下文制品。
- 让 KB 扫描在同一项目和源码版本下自动使用最新成功 source/x86 构建的 compile database。
- 保持前端 API 简单：前端不需要手动上传或选择 `compile_commands.json`。
- 保存安全摘要、来源引用和降级原因，便于审计和排查。
- 覆盖正常流程、异常流程和 edge case。

**Non-Goals:**
- 不要求所有项目必须先构建成功才能运行 KB 扫描。
- 不把 compile database 拆成逐条编译命令入库。
- 不改变 KB Scanner 的扫描规则、输出 schema 或独立 CLI 定位。
- 不把远端源码目录、服务器本机路径、对象存储 key 暴露给前端。
- 不尝试复用 target/RISC-V 构建产生的 compile database 作为 KB 扫描上下文。

## Decisions

### 1. 保存原始 compile database 为对象存储制品

构建验证成功后，如果远端部署目录中存在 `compile_commands.json`，worker 应将其下载到后端临时目录，执行大小限制、JSON 顶层数组校验和路径脱敏摘要生成，然后保存到 `stored_artifacts`。`artifact_type` 使用稳定值，例如 `COMPILE_COMMANDS_JSON`，`owner_type` 建议使用 `BUILD_VALIDATION`，`owner_id` 指向 `build_runs.id`。

备选方案是只继续保存摘要到 `build_facts`。这个方案无法供 KB Scanner 使用，因为 scanner 需要原始 compile database 中按文件组织的编译命令、include、define 和标准信息。

### 2. 在 `build_runs.build_facts` 中保存安全引用而不是完整内容

`build_facts` 保存如下安全结构：

```json
{
  "compileDatabase": {
    "available": true,
    "storedArtifactId": "...",
    "artifactType": "COMPILE_COMMANDS_JSON",
    "sha256": "...",
    "sizeBytes": 12345,
    "commandCount": 120,
    "source": "REMOTE_BUILD_WORKDIR",
    "environmentId": "...",
    "buildScope": "SOURCE_ONLY"
  }
}
```

`build_facts` 不保存原始 JSON、不保存远端工作目录、不保存对象存储 bucket/key。这样构建详情和 KB 扫描摘要可以复用同一引用，同时避免大字段和路径泄露。

### 3. KB 扫描执行时自动选择最新可用 source/x86 构建上下文

KB_SCAN worker 根据 `projectId + sourceRevisionId` 查询最新成功的 `build_runs`：
- `status = SUCCEEDED`
- `build_scope = SOURCE_ONLY` 优先，其次可接受同源码版本的 `BOTH` 中 source/x86 环境构建
- 环境应匹配项目当前 source 环境或构建事实中的 source/x86 环境
- `build_facts.compileDatabase.available = true`
- `stored_artifacts` 元数据存在且对象可下载

命中后，后端将对象存储内容下载到 KB 输出目录或临时目录，并调用：

```text
python -m kb_scanner scan ... --compile-commands <temp-file>
```

未命中或下载失败时，KB 扫描降级为当前源码上下文扫描，记录 warning，但不失败。

### 4. 来源摘要写入 KB scan summary

`kb_scan_runs.summary` 增加 `compileCommands` 摘要：

```json
{
  "compileCommands": {
    "mode": "USED",
    "source": "LATEST_SOURCE_BUILD",
    "buildRunId": "...",
    "storedArtifactId": "...",
    "sha256": "...",
    "commandCount": 120
  }
}
```

如果未使用：

```json
{
  "compileCommands": {
    "mode": "NOT_AVAILABLE",
    "reason": "NO_SUCCESSFUL_SOURCE_BUILD"
  }
}
```

如果下载或格式校验失败：

```json
{
  "compileCommands": {
    "mode": "FALLBACK",
    "reason": "ARTIFACT_DOWNLOAD_FAILED"
  }
}
```

### 5. 构建上下文 artifact 不作为通用前端资源暴露

前端只通过构建详情和 KB scan summary 查看是否使用了 compile database。原始 `compile_commands.json` 不需要提供通用下载接口。后续若需要审计下载，应通过构建业务接口新增受控下载，而不是开放通用 artifact API。

### 6. 测试策略

单元测试覆盖：
- 构建成功且存在 compile database 时保存 artifact 和 build facts。
- 文件不存在、JSON 非数组、过大、对象存储失败时的降级或失败边界。
- KB 扫描命中最新构建上下文时传入 `--compile-commands`。
- KB 扫描无上下文、artifact 不存在或下载失败时降级。

E2E 覆盖：
- 创建源码、部署 source/x86、运行 source-only 构建生成 `compile_commands.json`。
- 运行 KB_SCAN，不传 compile database 参数。
- 校验 KB scan summary 显示 `compileCommands.mode=USED`，scanner 输出诊断包含已使用 compile database。
- 校验清理测试项目、任务、构建、KB scan、findings、stored artifacts 和对象存储内容。

## Risks / Trade-offs

- [Risk] 远端下载 `compile_commands.json` 可能很大。  
  Mitigation: 设置最大大小限制，超限时记录 warning 并降级，不阻断构建成功。

- [Risk] compile database 中可能包含远端绝对路径。  
  Mitigation: 原始文件只作为后端内部 scanner 输入保存；API summary 只返回 sha256、大小和计数。scanner 输出、日志和 findings 继续走路径脱敏。

- [Risk] 对象存储保存失败会影响构建结果判断。  
  Mitigation: 构建命令退出码仍决定构建成功；compile database 保存失败只写 warning 和 `available=false`，不把成功构建改成失败。

- [Risk] 使用过期构建上下文导致 KB 扫描和当前源码不一致。  
  Mitigation: 查询必须绑定同一 `source_revision_id`，并优先使用最新成功 source/x86 构建；源码更新会产生新的 source revision，旧上下文不会被新扫描自动复用。

- [Risk] KB 扫描临时文件清理不彻底。  
  Mitigation: 将下载文件放在该 scan run 输出目录或受控临时目录，并在任务结束后删除临时输入；artifact 原件仍在对象存储中。

## Migration Plan

1. Liquibase 增加 `stored_artifacts.owner_type` 枚举值 `BUILD_VALIDATION`，并增加必要索引或约束。
2. 如需更高效查询，可给 `build_runs(project_id, source_revision_id, build_scope, status, finished_at desc)` 增加索引。
3. 重新生成 jOOQ 代码。
4. 实现构建上下文保存和 KB 扫描自动解析。
5. 补充单元测试和 E2E。

回滚时可停止新代码写入 `BUILD_VALIDATION` artifact；已保存的 stored artifact 元数据不会影响旧逻辑。KB 扫描在找不到可用上下文时会按原行为降级。

## Open Questions

- 是否需要提供构建上下文 artifact 的受控下载 API供管理员审计？当前建议不做，先只返回摘要。
- compile database 最大大小默认值建议为 50 MiB 还是沿用 KB scanner max output 限制？实现时需要在配置中明确。
