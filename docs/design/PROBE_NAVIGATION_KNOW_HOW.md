<!-- status: active; authority: design; owner: rolo maintainers; last_reviewed: 2026-09-02 -->

# Rolo v2 Probe 与导航 Conformance Know-how

本文固化 Rolo v2 在真实目标机上发现和验证 application Tool 的五条核心经验。
它们适用于 OS/Middleware provider，不把 ROS、Linux 或某个 robot workspace 写成架构前提。

## 1. Probe 自举扫描，不要求用户提供 workspace

Target enrollment 成功后，Rolo 可以自动发现目标机能力。用户不需要预先知道 workspace
位置，也不需要手工编写 shell。

扫描分两层：

1. **有界 inventory**：读取文件名、权限、大小、修改时间、可执行文件元数据和服务清单。
2. **定向读取**：只读取命中的 launch、package、config、service 和已知 middleware 描述文件。

扫描必须有目录范围、文件数、字节数、耗时、敏感路径和输出 digest 限制。静态文件只能
产生 Candidate，不能直接证明 Tool 存在；Candidate 必须经过受控 bring-up 和新鲜
TargetEvidence 才能发布。

## 2. Hands-off 以用户安全声明为前提，但不跳过 Rolo 证据

用户可以一次性声明设备处于安全位置，让低风险 Probe 和 canary 自动执行，减少反复确认。
这项声明只负责环境前提，不替代 Tool 自身的安全边界。

Rolo 仍必须记录并验证：

- 实际命中的 route 和参数；
- action/service 的返回结果；
- cancel 是否生效；
- 实际速度、位移或角位移反馈；
- 超时、停车和最终稳定状态。

用户保证“周围安全”，Rolo 保证“工具行为可审计、可复现、可失败”。

## 3. 导航 discovery 先相对运动，后全局定位

没有 `map → base_footprint` 或等价全局定位证据时，不应直接把导航标记为不可用。
Probe 应按以下顺序尝试：

```text
相对运动接口
  → 底盘控制、cancel、stop
  → 地图、定位、重定位入口
  → 全局导航目标
```

相对运动候选包括“按航向短距离运动”和“小角度旋转”，例如 ROS Nav2 的
`/drive_on_heading`、`/spin`，或其他 OS/Middleware 中的等价接口。

只有发现地图、定位和重定位入口，并完成对应 evidence 后，才把类似
`/navigate_to_pose` 的全局目标接口提升为全局导航 Candidate。

## 4. Level 1：zero-stop 是统一的第一类写入 canary

Level 1 不依赖地图或定位，适用于所有 provider：

```text
重复发布零速度
  → 确认下游 subscriber
  → 观察实际速度
  → 验证位置未变化
  → PASS / FAIL
```

它验证的是最小写入链路和停车闭环，不代表底盘具备移动或导航能力。任何更高等级的
写入测试都必须把 zero-stop 作为收尾步骤。

## 5. Level 2：bounded motion 统一为受限旋转/短动作

Level 2 是跨 provider 的统一 canary，不暴露底层 CLI 差异。每次测试固定：

- 最大角度或距离；
- 最大速度和加速度；
- 最大执行时间；
- 可取消路径；
- zero-stop 收尾；
- 实际位姿变化复核。

在 ROS 上可以映射到 `/spin` 或 `/drive_on_heading`；在其他系统上映射到等价的受限
运动接口。用户的安全位置声明可以让该级别自动运行，但 Rolo 仍必须持续采集反馈，
并在任一 gate 失败时立即取消、停车并报告失败。

## 分级结果与发布边界

```text
Level 0  discovery / observation       不产生运动
Level 1  zero-stop                     自动可执行
Level 2  bounded motion                有安全声明时可自动执行
Level 3  task motion / global nav      需要完整 evidence，不由 discovery 自动执行
```

Candidate、Adapter bundle 和 Conformance 必须分别记录。文件系统发现只能支持 Candidate；
真实运行时 route 支持 Adapter；只有独立 conformance 通过，Tool 才能进入可调用 surface。
