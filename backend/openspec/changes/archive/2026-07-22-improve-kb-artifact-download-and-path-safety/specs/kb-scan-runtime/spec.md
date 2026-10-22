## ADDED Requirements

### Requirement: KB 扫描必须使用统一服务器路径安全工具
KB 扫描相关文件访问和路径脱敏 SHALL 使用统一服务器路径安全工具，避免各模块重复实现不一致的 `normalize`、`toRealPath`、边界校验和文本替换逻辑。

#### Scenario: 解析根目录内既有文件
- **WHEN** 后端需要读取 KB artifact、源码文件或其他服务器本地文件
- **THEN** 后端 SHALL 将根目录和候选路径转换为绝对规范路径
- **AND** 后端 SHALL 对既有文件执行真实路径校验
- **AND** 若候选路径不在允许根目录内或通过符号链接逃逸，后端 SHALL 拒绝读取
- **AND** 错误响应 MUST NOT 暴露服务器真实路径

#### Scenario: 解析根目录内相对路径
- **WHEN** 后端根据 scanner 输出、finding `file_path` 或用户输入的相对路径定位文件
- **THEN** 后端 SHALL 将候选路径解析到允许根目录下
- **AND** 后端 MUST 拒绝绝对路径、`..` 路径段、normalize 后越界路径和符号链接逃逸
- **AND** 后端 MUST NOT 允许客户端通过路径参数读取任意服务器文件

#### Scenario: 脱敏根目录内路径文本
- **WHEN** 后端向 API 响应、任务事件、日志摘要、tool run summary 或 finding evidence 写入路径文本
- **THEN** 后端 SHALL 将允许根目录内的服务器绝对路径替换为受控占位符或相对路径
- **AND** 输出 MUST NOT 包含源码工作副本根路径、KB 输出根路径、后端 runtime 根路径或用户 home 下真实路径

#### Scenario: 处理根目录外路径文本
- **WHEN** 待返回文本中包含不属于允许根目录的服务器绝对路径
- **THEN** 后端 SHALL 将其替换为 `<server-path-redacted>` 或返回安全错误
- **AND** 后端 MUST NOT 将根目录外服务器绝对路径原样返回给 API 客户端

### Requirement: KB artifact 下载必须校验输出根目录边界
KB artifact 下载 SHALL 在项目权限校验之后、返回文件之前校验 artifact `content_path` 位于受控 KB 输出根目录内。

#### Scenario: 下载合法 artifact 文件
- **WHEN** 用户下载 KB 扫描 artifact 且 `content_path` 指向 KB 输出根目录内的既有普通文件
- **THEN** 后端 SHALL 返回该文件内容
- **AND** 响应 SHALL 使用由 artifact type 和 scan id 生成的安全文件名
- **AND** 响应 MUST NOT 返回 artifact `content_path`

#### Scenario: artifact content path 越界
- **WHEN** artifact `content_path` 指向 KB 输出根目录之外、包含路径逃逸或通过符号链接逃逸
- **THEN** 后端 SHALL 拒绝下载
- **AND** 后端 SHALL 返回安全错误
- **AND** 后端 MUST NOT 返回真实路径、符号链接目标或文件系统异常细节

#### Scenario: artifact 文件不存在
- **WHEN** artifact metadata 存在但 `content_path` 对应文件不存在或不是普通文件
- **THEN** 后端 SHALL 返回 artifact 文件不存在的安全错误
- **AND** 后端 MUST NOT 暴露服务器真实路径

### Requirement: KB finding 代码上下文必须复用路径安全工具
Finding 代码上下文读取 SHALL 使用统一服务器路径安全工具校验源码工作副本边界。

#### Scenario: 读取源码工作副本内文件
- **WHEN** 用户查询 finding 代码上下文且 finding `file_path` 指向源码工作副本内既有文件
- **THEN** 后端 SHALL 返回固定上下文窗口和高亮行
- **AND** 响应 SHALL 只返回相对文件路径
- **AND** 响应 MUST NOT 返回源码工作副本真实路径

#### Scenario: 代码上下文路径逃逸
- **WHEN** finding `file_path` 是绝对路径、包含 `..`、normalize 后越界或符号链接逃逸
- **THEN** 后端 SHALL 拒绝读取
- **AND** 后端 SHALL 返回安全错误
- **AND** 后端 MUST NOT 返回服务器真实路径或文件系统异常细节

### Requirement: KB scanner 输出路径必须统一脱敏
KB scanner 的 result、evidence、stdout、stderr、scan log、tool run summary 和失败摘要 SHALL 通过统一路径脱敏逻辑处理后才能进入 API 可见数据。

#### Scenario: 脱敏 scanner evidence
- **WHEN** scanner finding evidence 中包含源码根目录、scanner 输出目录或其他服务器绝对路径
- **THEN** 后端 SHALL 在写入 `findings.evidence` 前脱敏路径
- **AND** `findings.evidence` MUST NOT 保存服务器真实路径

#### Scenario: 脱敏 scanner 日志和错误摘要
- **WHEN** scanner stdout、stderr、scan log 或异常消息包含服务器路径
- **THEN** 后端 SHALL 在写入任务日志事件、tool run summary 或任务错误摘要前脱敏路径
- **AND** API 和 SSE MUST NOT 推送服务器真实路径

#### Scenario: 嵌套 JSON 路径脱敏
- **WHEN** scanner 输出中的路径出现在嵌套 JSON object、array 或字符串中
- **THEN** 后端 SHALL 递归脱敏这些路径
- **AND** 后端 MUST NOT 只处理顶层字段
