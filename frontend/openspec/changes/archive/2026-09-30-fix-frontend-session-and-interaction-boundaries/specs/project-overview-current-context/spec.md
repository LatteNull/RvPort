## ADDED Requirements

### Requirement: overview 查询订阅所有权统一

同一项目视图树 SHALL 在项目公共边界建立一个 overview 查询订阅，页面与阶段 SHALL 消费该边界提供的类型化数据、查询状态及刷新能力，不复制当前事实或建立兜底重复订阅。当前上下文与 SSE 刷新规则遵循本能力既有要求。

#### Scenario: 页面与多个阶段读取当前上下文

- **WHEN** 项目页、源码、环境及构建上下文需要同一 overview
- **THEN** 它们 SHALL 读取公共查询结果，当前事实更新 SHALL 同步到全部消费方
- **AND** 阶段 SHALL 不各自注册 overview 查询或保存第二套当前事实

#### Scenario: 加载、恢复及阶段关闭

- **WHEN** overview 加载失败、用户重试、mutation 合并缓存或 SSE 使缓存失效
- **THEN** 消费方 SHALL 保留既有加载、错误、恢复与当前事实反馈，刷新所有权 SHALL 明确
- **AND** 关闭或切换阶段 SHALL 不重建项目 SSE 或停止项目级 overview 更新，不增加固定轮询
