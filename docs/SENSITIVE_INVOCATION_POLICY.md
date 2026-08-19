# SENSITIVE operation 调用策略

## 安全边界

Rolo runtime 对 `SENSITIVE` operation 默认拒绝。放行依据是当前进程的操作系统身份与一份
受主机权限保护的 YAML 策略，而不是 CLI 参数、环境布尔值、Agent 自述或 adapter 返回值。
`SECRET` 数据禁止通过通用 operation 暴露。

策略只决定“当前主机身份是否允许调用该数据分类”，不判断 operation 结果是否正确、可靠
或安全；后者属于后续诊断与验证阶段。

## 策略格式

```yaml
schema_version: rolo-invocation-policy/v1
sensitive:
  allowed_users:
    - robot-operator
  allowed_groups:
    - rolo-sensitive-readers
writes:
  allowed_users:
    - robot-operator
  allowed_groups:
    - rolo-operators
  allowed_operations:
    - linux.service.restart
content_resources:
  - operation: linux.file.read
    classification: SENSITIVE
    allowed_roots:
      - /etc/robot
    max_bytes: 1048576
  - operation: linux.service.logs
    classification: SENSITIVE
    allowed_resources:
      - service:robot-controller
    max_bytes: 10485760
```

默认路径由 `ROLO_INVOCATION_POLICY` 指定；默认审计路径由
`ROLO_INVOCATION_AUDIT_LOG` 指定。仓库不附带默认放行策略，部署方必须在目标主机显式创建。

## 文件保护要求

- POSIX：策略所有者必须是 root 或当前进程用户，且 group/other 不得拥有写权限；建议
  `root:rolo`、模式 `0640`，并以受控服务身份运行 Rolo。
- Windows：策略 ACL 不得授予 Everyone、Authenticated Users 或 builtin Users 写入、修改、
  删除、改权限或取得所有权。建议由 Administrators 部署，并只向 Rolo 服务账户授予读取。
- 符号链接、非普通文件、权限检查失败或无法读取都按拒绝处理。

## 写操作授权

所有 `access=write` operation 默认拒绝。R1/R2 写操作必须同时满足当前 OS 用户/组被允许，
并且 operation 精确出现在 `writes.allowed_operations`；不支持通配符，也不能仅按风险等级
整体放行。

R3 不读取静态 write 白名单。`ROLO_R3_AUTHORIZER` 必须指向 root/Administrators/SYSTEM
所有且不可被普通用户修改的可执行授权提供器。Runtime 只向它发送 principal、robot、
operation 和规范化输入 SHA-256，不发送业务 payload；提供器返回的能力必须绑定本次随机
request、robot、operation 和输入摘要，且有效期大于零、不超过五分钟。任何字段不匹配、
超时、拒绝或提供器异常都会闭锁拒绝。

协议的机器可读 Schema 为 `R3AuthorizationRequest.schema.json` 和
`R3AuthorizationCapability.schema.json`。

## 内容资源分类

`file.read`、配置内容和日志 operation 除 SENSITIVE 身份授权外，还必须匹配
`content_resources`。文件路径必须位于显式目录中、是普通文件、路径链不含符号链接，且
请求字节数不超过规则上限；日志使用 discovery/adapter 提供的稳定 `resource_id`，必须
精确匹配 `allowed_resources`。规则只允许声明 `SENSITIVE`，无法确认不含凭据、密钥或认证
材料的资源不得配置，仍按潜在 `SECRET` 拒绝。

正文和 diff 不作为 Tool 返回值内联，只返回受保护 artifact 引用。这样可降低 Agent prompt
污染和无意扩散，但 artifact 存储仍必须执行权限、留存和清理策略。

## 配置变更 artifact

`linux.config.apply` 不接受本地路径或内联正文。调用方必须提供 `artifact://` 引用、当前内容
SHA-256、最大字节数、格式和 discovery/adapter 定义的稳定 `target_resource_id`。Runtime 在
SENSITIVE 与 write 授权通过后解析 artifact，拒绝越界、路径链符号链接、非普通文件、超限
内容或摘要不一致，再将请求交给 gated adapter。Adapter 必须在实际使用前再次确认摘要，且
不得修改原 artifact。

`app.map.import` 复用同一 artifact 边界：只允许 digest-pinned `artifact://` 输入，并在
Runtime 中执行相同的路径、符号链接、大小和 SHA-256 校验。导入只创建非激活地图记录；
激活地图属于独立的 `app.map.load` 写操作和独立审计事件。

Apply 返回的 `rollback://` token 是 adapter 签发并绑定目标及已保存回滚状态的不透明引用；
它不是 bearer authorization capability。`linux.config.rollback` 必须重新通过 OS 身份、精确
operation 白名单、SENSITIVE 策略和审计。Token 无效、过期、已消费或目标不匹配时闭锁拒绝。

## 审计

每次 SENSITIVE、内容资源、write 或 R3 允许/拒绝都会追加一条
`rolo-invocation-audit/v1` JSONL 记录，包含策略域、时间、robot、operation、数据分类、
OS principal、结果和原因；不记录输入或输出 payload。R3 允许记录只附授权 ID。无法写入
审计日志时调用失败关闭。审计文件本身应由部署环境实施留存、轮转和访问控制。

## 覆盖范围

通用 `robotctl tool invoke` 在启动 adapter 前执行该策略；已发布的直接 SENSITIVE CLI
同样必须调用统一授权函数。Adapter Agent 不能通过自定义 entrypoint、修改 Tool Catalog
分类或添加未经签名的 operation 绕过，因为 active release 的 catalog、contract digest 与
adapter package 在运行前仍需一致性校验。
