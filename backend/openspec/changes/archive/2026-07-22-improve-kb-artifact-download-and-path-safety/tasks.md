## 1. 公共路径安全工具

- [x] 1.1 新增 `cn.rvport.backend.common.path.ServerPathGuard` 或等效 util，支持根目录内既有文件、既有目录和相对路径解析
- [x] 1.2 实现真实路径边界校验，覆盖 normalize、toAbsolutePath、toRealPath 和符号链接逃逸
- [x] 1.3 实现路径文本脱敏，支持 Windows 路径、Unix 路径、混合分隔符和嵌套文本
- [x] 1.4 明确并实现文件访问失败和文本脱敏失败的安全错误映射，错误响应不暴露服务器真实路径

## 2. KB artifact 下载 API

- [x] 2.1 新增 `format` 到 `KbScanArtifactType` 的受控映射，支持 `html`、`json` 和 `log`
- [x] 2.2 在 `KbScanRepository` 中新增按 `scanRunId + artifactType` 查询 artifact 下载元数据的方法
- [x] 2.3 在 `KbScanService` 中新增按格式下载 artifact 的服务方法，复用项目访问权限校验
- [x] 2.4 在 `KbScanController` 中新增 `GET /api/kb-scans/{scanId}/artifacts:download?format=...`
- [x] 2.5 保留并加固现有 `GET /api/kb-scans/{scanId}/artifacts/{artifactId}/download`
- [x] 2.6 确保下载响应使用安全文件名和正确 content type，并且不返回 `content_path`

## 3. KB 路径安全接入

- [x] 3.1 artifact 下载时校验 `content_path` 位于受控 KB 输出根目录内
- [x] 3.2 finding 代码上下文读取改为使用统一路径安全工具校验源码工作副本边界
- [x] 3.3 `KbScanRuntimeService` evidence 脱敏改为复用统一路径安全工具
- [x] 3.4 scanner stdout、stderr、scan log、tool run summary 和失败摘要中涉及路径的内容复用统一脱敏逻辑
- [x] 3.5 检查现有 API 响应、任务事件和日志事件，确认不会暴露源码工作副本路径、KB 输出目录或 backend runtime 真实路径

## 4. 单元测试

- [x] 4.1 测试路径安全工具正常解析 root 内文件和目录
- [x] 4.2 测试路径安全工具拒绝 `..`、绝对路径越界、符号链接逃逸和不存在文件
- [x] 4.3 测试路径文本脱敏覆盖 Windows、Unix、混合分隔符、root 内路径和 root 外路径
- [x] 4.4 测试按格式下载 HTML、JSON 和 log artifact 的正常流程
- [x] 4.5 测试不支持的 `format`、缺失 artifact、越权访问和 artifact 文件不存在
- [x] 4.6 测试 artifact `content_path` 越界和符号链接逃逸时拒绝下载且错误不泄露真实路径
- [x] 4.7 测试 finding 代码上下文正常读取、路径逃逸、符号链接逃逸、文件缺失和错误脱敏
- [x] 4.8 测试 scanner evidence、日志摘要和错误摘要中的嵌套路径脱敏

## 5. E2E 和文档

- [x] 5.1 更新 `backend/docs/API_DESIGN.md`，补充 KB artifact 按格式下载接口
- [x] 5.2 更新 `backend/docs/api-e2e-coverage.md`，补充按格式下载和路径安全覆盖点
- [x] 5.3 更新 KB E2E case，真实 KB 扫描后分别下载 HTML 和 JSON artifact
- [x] 5.4 E2E 校验下载响应 content type、文件名和响应体不包含服务器真实路径
- [x] 5.5 E2E 或测试辅助路径覆盖 artifact 文件缺失、格式缺失和越权访问

## 6. 验证

- [x] 6.1 运行 KB 相关 Maven 单元测试
- [x] 6.2 运行完整 Maven 测试
- [x] 6.3 启动后端和基础设施，运行 KB E2E module
- [x] 6.4 运行 `openspec validate improve-kb-artifact-download-and-path-safety`
