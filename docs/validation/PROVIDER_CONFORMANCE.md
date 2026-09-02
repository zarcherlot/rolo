<!-- status: archived; authority: normative; owner: docs maintainers; last_reviewed: 2026-09-02; source_of_truth: docs/probe/AGENT_NATIVE_TOOLS.md -->

# Provider-neutral Conformance Kit

## 用途

Conformance Kit 用于在开发真实 OS/Middleware Provider 之前验证 Provider 的结构、版本、
Manifest、Capability 和安全边界。它不连接任何指定平台，不修改 Registry、Catalog、
Bundle 或 release。

## 基本用法

```python
from rolo.capabilities import run_provider_conformance

report = run_provider_conformance(provider, timeout_s=5.0)
if not report.conforms:
    for check in report.checks:
        print(check.name, check.status, check.reason)
```

报告使用 `ProviderConformanceReport`，其检查项固定排序、名称唯一，并始终包含：

```text
influences_release = false
```

## 安全检查范围

首版 Runner 执行以下检查：

- 对象满足 `CapabilityProvider` SPI；
- Probe 和 Capability 注册能在统一超时内完成；
- Provider ID、版本、Manifest 和 Descriptor 一致；
- 注册 evidence 已去空、去重、排序和限长；
- 未知 `extensions` 不改变 Core digest；
- 缺失 Capability 返回 `UNAVAILABLE`；
- Host Snapshot 保持 release-neutral；
- 每个 write capability 在没有 Runtime policy authorizer 时 fail closed。

Runner 不会给 write capability 提供 authorizer，因此 Conformance 过程不会真正调用 Provider
的写路径。Runner 也不会主动调用 read invoke；对真实资源的读取验证应由产品化阶段的受控
设备测试负责。

## Fake Provider 模板

`FakeCapabilityProvider` 可用于开发和自动测试：

```python
provider = FakeCapabilityProvider(
    manifest=manifest,
    descriptors=descriptors,
    inspect_values={"os.runtime.status": {"state": "ready"}},
    unavailable_capabilities={"os.service.list"},
    delays_s={"probe": 0.01},
)
```

模板支持：

- Inspect/Invoke 固定结果；
- 明确的 `UNAVAILABLE` Capability；
- Probe、Capabilities、Inspect、Invoke 延时；
- 指定阶段异常；
- 调用计数和请求记录。

Fake Provider 不执行系统命令、SDK 调用或网络访问。

## 抽象验证矩阵

当前自动测试覆盖：

| 场景 | 应支持 | 应保持缺失 |
|---|---|---|
| service-less | runtime、workload | service |
| filesystem-less | runtime、log | filesystem |
| RTOS-like | runtime、workload、resource | process 语义 |
| channel-only | channel list/sample | middleware service |

同时覆盖重复 Provider ID、注册超时、Descriptor 漂移、未知 kind/transport/extensions、空
Provider 和写策略拒绝。

## 当前边界

- 首版只做结构与安全边界验证，不做真实设备 conformance；
- 不动态安装或加载 Provider；
- 不执行具体 Windows、FreeRTOS、CyberRT、Linux 或 ROS 命令；
- 不授予任何写权限；
- 不将通过 Conformance 的 Provider 自动加入生产 Catalog。
