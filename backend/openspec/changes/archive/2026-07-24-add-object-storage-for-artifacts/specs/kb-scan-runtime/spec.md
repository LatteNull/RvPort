## ADDED Requirements

### Requirement: KB 扫描 artifact 必须支持对象存储
KB 扫描运行时 SHALL 支持将新生成的扫描输出制品保存到对象存储，并 SHALL 保持现有 KB 业务下载接口语义。

#### Scenario: 保存 KB 输出到对象存储
- **WHEN** KB Scanner 生成 `scan-result.json`、`scan-report.html` 或 `scan.log`
- **THEN** 后端 SHALL 能将文件内容上传到对象存储
- **AND** 后端 SHALL 保存输出制品元数据
- **AND** 元数据 SHALL 关联 `project_id`、`task_id` 和 `scan_run_id`

#### Scenario: 下载对象存储中的 KB artifact
- **WHEN** 用户通过 KB artifact 下载接口下载已保存到对象存储的 artifact
- **THEN** 后端 SHALL 校验 artifact 属于该 scan run
- **AND** 后端 SHALL 校验用户对 scan 所属项目有访问权限
- **AND** 后端 SHALL 从对象存储读取内容并返回安全文件名

#### Scenario: 兼容历史本地 KB artifact
- **WHEN** KB artifact 只有历史 `content_path` 且没有对象存储元数据
- **THEN** 后端 MAY 继续按受控本地路径规则读取历史文件
- **AND** 后端 MUST 继续校验 KB 输出根目录边界
