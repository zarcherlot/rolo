# Capability Provider Host 开发说明

## 定位

`ProviderHost` 是未来 OS/Middleware Provider 的平台无关扩展宿主。它不替换当前
Linux/ROS Adapter，不修改 Registry，也不把 Provider capability 自动加入 Active Tool
Catalog。

宿主当前负责：

- 调用 `probe()` 和 `capabilities()` 完成注册；
- 校验 Provider ID 唯一性、版本、Manifest 声明和 Capability Descriptor；
- 按 Provider ID 列出 Manifest 和生成确定性 Snapshot；
- 卸载 Provider；
- 为 `inspect()` 和 `invoke()` 提供超时、取消和异常隔离；
- 对 Provider evidence 去空、去重、排序、限长，并增加 Provider/阶段标识；
- 校验调用结果的 Provider 版本；
- 校验 `invoke()` 的 route 必须来自已注册 Manifest；
- 对所有 write capability 默认拒绝。

## 注册约束

Provider 只有同时满足以下条件才会进入宿主：

1. `probe()` 返回 `AVAILABLE` 和合法 Manifest；
2. Manifest 自身状态为 `AVAILABLE`；
3. Provider ID 尚未注册；
4. `capabilities()` 返回 `AVAILABLE`；
5. Probe、Manifest、Capability 结果的 Provider 版本一致；
6. Descriptor 的 ID/version 在 Manifest 中声明；
7. Descriptor semantic layer 属于 Manifest 声明范围；
8. 同一 Host 内每个 Capability ID 只有一个活动版本。

注册失败、Capability 缺失、Provider 不可用和未知 Provider kind 都是可观测状态，不会
改变当前产品 release。

## 写能力授权

宿主本身不具有授权能力。`CapabilityDescriptor.access == "write"` 时，调用方必须注入
实现 `CapabilityWriteAuthorizer` 的对象：

```python
class RuntimePolicyBridge:
    def authorize(self, manifest, descriptor, request) -> None:
        # 产品化适配层在这里将 capability 映射到 canonical Operation，
        # 再调用现有 Runtime policy。拒绝时抛出异常。
        ...
```

未注入 authorizer、authorizer 拒绝或授权过程异常时，宿主返回 `UNAVAILABLE`，不会调用
Provider。Provider 返回的 `authorization_ref` 不能替代 Runtime policy 决策。

## 超时与关闭

每次 Provider 调用使用 Host 的统一超时。超时会取消尚未执行的任务并立即返回隔离结果；
已经进入 Provider 的同步调用必须由 Provider 自己响应其平台连接的取消和超时。

`close()` 会停止接受新调用并取消等待队列。产品化 Provider 仍需为底层连接实现可关闭、
可取消的资源生命周期。

## 当前边界

- 不动态加载任意 Python 模块或二进制文件；
- 不实现 Windows、FreeRTOS、CyberRT 等具体 Provider；
- 不把 Provider Manifest 接入当前发布门禁；
- 不允许 Provider 绕过 canonical Operation policy；
- 不承诺强制终止已经进入第三方同步代码的线程。

动态插件加载、进程级故障隔离、签名验证和 Provider 部署属于正式产品化范围。
