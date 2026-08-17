# Robot Debugging Agent：面向机器人公司的 AI 调试基础设施

## 1. 核心判断

这个方向是成立的。

但 MVP 不应该从“让 Agent 自动修改 ROS 代码”开始，而应该从：

> **自动完成机器人故障的证据采集 + 根因定位**

开始。

机器人调试和普通软件调试最大的区别，不是代码更难，而是故障往往跨越多个层级：

- 硬件
- Linux
- 网络
- DDS
- ROS Graph
- 驱动
- 时间同步
- GPU
- 模型推理
- 上层业务逻辑

现有 coding agent 更擅长的是：

> “代码已经暴露在 repo 里，我来理解和修改。”

但机器人现场最痛苦的问题往往是：

- 雷达为什么突然没数据？
- 是驱动挂了，还是 USB 掉了？
- 是 DDS QoS 不匹配，还是网卡丢包？
- 是 CPU 打满了，还是 subscriber 卡住了？
- 为什么模型延迟从 80ms 变成 400ms？
- 为什么同一份代码仿真正常，上真机就偶发失败？

因此，更适合的产品定位不是：

> Copilot for ROS code

而是：

> **Datadog + strace + ROS diagnostics + senior robotics engineer + coding agent**

机器人出了问题，Agent 自己去调查。

---

# 2. 最适合的 MVP 切入层：ROS Runtime / System Observability

第一版不要直接碰 VLA 模型内部。

也不要一开始进入 firmware、MCU 或底层控制器。

最合适的范围是：

```text
┌──────────────────────────────────────┐
│ VLA / Application                   │
│     暂时只观察，不理解模型内部       │
├──────────────────────────────────────┤
│ ★ ROS Runtime Debug Agent ★         │
│                                      │
│ Nodes / Topics / Services / Actions │
│ DDS / QoS / TF / timestamps         │
│ rosbag / logs / diagnostics         │
├──────────────────────────────────────┤
│ Linux Runtime                        │
│ process / CPU / GPU / RAM / network │
│ USB / PCIe / device / kernel logs   │
├──────────────────────────────────────┤
│ Hardware                             │
│ camera / lidar / robot / GPU        │
└──────────────────────────────────────┘
```

这一层有几个优势：

1. 足够接近真实机器人故障。
2. 不像 firmware 那样高度 hardware-specific。
3. ROS 本身天然是 graph，非常适合 Agent 进行依赖关系推理。
4. 可以直接解决机器人公司大量日常工程痛点。

---

# 3. 一个典型场景：`/lidar/points` 没数据

工程师告诉 Agent：

> `/lidar/points` 没数据了。

普通 coding agent 很难直接解决，因为问题未必出在代码中。

Robot Debugging Agent 可以自动执行 investigation tree：

```text
/lidar/points missing
       │
       ▼
publisher exists?
 ┌─────┴─────┐
 no          yes
 │            │
 ▼            ▼
node alive?   topic hz?
 │            │
 ▼            ▼
process?      0 Hz / low Hz
 │
 ▼
device exists?
 /dev/ttyUSB?
 ethernet?
 USB?
 │
 ▼
kernel logs
dmesg
 │
 ▼
network
ping / packets / NIC drops
 │
 ▼
driver logs
 │
 ▼
parameter/config
 │
 ▼
QoS compatibility
```

最终不要把几千行日志扔给用户，而是输出：

```text
Root cause confidence: 91%

/lidar/points stopped because the lidar driver's
Ethernet receive socket stopped receiving UDP packets.

Evidence:
✓ lidar_node process alive
✓ ROS publisher exists
✓ publisher rate = 0 Hz
✓ NIC eth1 RX packet rate = 0
✓ ping 192.168.1.201 fails
✓ kernel reports link down at 14:32:07

Likely cause:
Physical Ethernet link or lidar power failure.

Suggested next actions:
1. Check lidar power.
2. Check eth1 cable/link.
3. If link returns, restart lidar_node.
```

这实际上就是 senior robotics engineer 的典型排查方式。

---

# 4. MVP 阶段不要让 Agent 自动修机器人

第一版最重要的产品决策之一：

> **先诊断，不自动执行高风险修复。**

机器人和普通 Web 服务不同。

coding agent 改错 React 页面，最坏可能是页面挂掉。

机器人控制参数改错，则可能导致机械臂撞击、移动底盘异常运动等问题。

因此自动化能力应该逐级演进：

```text
Level 0
只收集数据

↓

Level 1
自动诊断

↓

Level 2
提出 shell command / code patch
人工批准

↓

Level 3
自动执行低风险操作
例如 restart node

↓

Level 4
simulation 验证 patch

↓

Level 5
真机自动修复
```

创业 MVP 做到 **Level 1～2** 就足够验证价值。

---

# 5. 第一版只解决 10 类高频问题

不要一开始宣传：

> AI automatically debugs robots.

这个范围太宽。

更好的产品承诺是：

> **Automatically diagnose the most common ROS 2 runtime failures.**

第一批可以只解决：

1. Topic 不出流
2. Topic rate 异常
3. Topic latency 过高
4. Node crash / restart
5. QoS mismatch
6. TF tree / timestamp 问题
7. CPU / RAM / GPU resource saturation
8. Network packet loss / bandwidth saturation
9. Device disconnected
10. ROS parameters / launch config 错误

这些问题：

- 高频
- 有明确 evidence
- 有相对客观的 ground truth
- 容易自动化验证

非常适合 Agent。

---

# 6. 为什么不先从代码 Bug 入手？

代码 Bug 已经是 coding agent 最卷的区域之一。

如果产品只是：

```text
ROS error
↓
LLM
↓
read GitHub
↓
modify C++
```

护城河会比较弱。

更有价值的方向是：

```text
Real robot
     │
     ├── ROS graph
     ├── DDS
     ├── logs
     ├── rosbag
     ├── tracing
     ├── Linux
     ├── network
     ├── GPU
     └── hardware state
              │
              ▼
          Agent reasoning
              │
              ▼
         identify culprit
              │
              ▼
           code repo
              │
              ▼
      Claude Code / Codex
```

在这个架构下：

> **coding agent 是 actuator，而不是竞争对手。**

真正的核心能力是理解现实机器人到底发生了什么。

---

# 7. Harness 的三个核心组件

## 7.1 Robot-side Probe

机器人上运行一个轻量 daemon，例如：

```text
robot-agentd
```

部署在：

- IPC
- Jetson
- x86 工控机

它提供结构化工具接口。

例如：

```text
ros.topic.list()
ros.topic.info()
ros.topic.hz()
ros.topic.echo()

ros.node.list()
ros.node.info()

ros.param.get()

ros.tf.tree()

ros.bag.record()

system.processes()
system.cpu()
system.memory()

gpu.status()

network.interfaces()
network.bandwidth()
network.connections()

hardware.usb()
hardware.pci()
hardware.dmesg()

logs.query()
```

Agent 最好不要一开始就拥有 unrestricted shell。

优先采用 structured tools。

例如，不要只返回：

```text
$ ros2 topic hz /camera/image
average rate: ...
```

而是返回：

```json
{
  "topic": "/camera/image",
  "rate_hz": 29.8,
  "expected_hz": 30,
  "jitter_ms": 3.4,
  "dropped": 17
}
```

结构化数据会让 Agent 推理稳定很多。

---

## 7.2 Robot State Graph

这可能是产品长期最核心的技术资产之一。

把机器人实时状态建模为：

```text
Robot
│
├── Host
│   ├── NIC
│   ├── GPU
│   └── USB
│
├── Process
│
├── ROS Node
│   │
│   ├── Publisher
│   └── Subscriber
│
├── Topic
│
├── Sensor
│
└── Actuator
```

同时记录依赖关系：

```text
Lidar
 ↓
eth1
 ↓
UDP socket
 ↓
lidar_driver process
 ↓
lidar_node
 ↓
/lidar/points
 ↓
perception_node
 ↓
pointcloud encoder
 ↓
VLA
```

那么当用户说：

> VLA perception 突然不工作。

Agent 就可以沿 dependency graph 往底层调查，而不是无目标 grep 日志。

这个 Graph 有机会成为真正的 moat。

---

## 7.3 Investigation Agent

Agent 不应该：

> 看到 log → 猜答案。

更合适的是：

```text
Hypothesis
   ↓
select diagnostic
   ↓
collect evidence
   ↓
update probability
   ↓
next test
   ↓
root cause
```

类似医生进行 differential diagnosis。

例如：

```text
Issue:
/camera/color/image_raw rate dropped 30 → 4 Hz

Hypotheses:

H1 camera device issue      25%
H2 network saturation       30%
H3 CPU saturation           15%
H4 subscriber backpressure  15%
H5 DDS QoS issue            15%
```

Agent 检查：

```text
CPU: 32%
Network: 940 Mbps / 1Gbps
packet drops ↑
```

然后更新：

```text
H2 network saturation → 76%
```

继续调查：

```text
top bandwidth topics
```

发现：

```text
/depth/points = 690 Mbps
/camera/raw   = 240 Mbps
```

最终给出：

> Network saturated.

这种调查过程具备更好的可解释性，也更容易获得机器人团队信任。

---

# 8. 时间维度非常关键

机器人 debugging 和普通 SaaS observability 的一个巨大区别是：

> **机器人上的一切都是 timestamped multimodal signals。**

典型信息包括：

- camera
- lidar
- IMU
- ROS message
- logs
- CPU
- GPU
- network
- actuator state
- controller feedback
- VLA inference
- kernel event

因此一个很有价值的工作流是：

用户在某个可视化工具中看到：

> 14:31:22 机器人出现故障。

然后点击：

> Diagnose this incident.

Agent 自动收集：

```text
14:31:10–14:31:30

ROS logs
rosbag
CPU
GPU
DDS
network
TF
processes
kernel logs
```

最终生成 incident report。

产品定位可以是：

```text
Human observability UI
        +
AI observability engineer
```

---

# 9. 一个理想的 MVP UI

用户输入：

```text
Why did robot_07 stop detecting objects?
```

Agent：

```text
Investigating robot_07...

✓ perception node healthy
✓ GPU healthy
✓ model inference running
✗ camera input degraded

/camera/front/image
30 Hz → 1.2 Hz at 15:41:08

Investigating camera pipeline...

✓ camera process alive
✗ USB resets detected

Kernel:
usb 2-1: reset SuperSpeed USB device

Likely root cause
─────────────────
Front camera USB link instability.

Confidence: 94%

Evidence
─────────────────
15:41:07 USB reset
15:41:08 camera fps collapsed
15:41:08 perception detections stopped

Recommended action
─────────────────
Check camera cable / hub.

Software mitigation:
restart camera_node after USB reconnect.
```

对于一个机器人团队，这种产品价值非常容易理解。

---

# 10. 第二阶段再进入 VLA Deployment Observability

当 Runtime Debugging 跑通后，再进入 VLA 层会更自然。

此时产品已经积累：

```text
Observation
+
Robot state
+
Failure
+
Root cause
+
Fix
```

这会形成一个机器人领域很有价值的 debugging dataset。

第二阶段可以做：

## VLA Deployment Observability

例如自动观察：

```text
camera
 ↓ 30 Hz

preprocess
 ↓ 27 Hz
 ↓ 8 ms

GPU H2D
 ↓ 14 ms

VLA inference
 ↓ 130 ms

action decode
 ↓ 3 ms

ROS action publish
 ↓ 6 ms

controller
```

最终 Agent 输出：

```text
End-to-end policy latency: 231 ms

Main bottleneck:
VLA inference        137 ms
Image serialization   46 ms
ROS transport         21 ms
Other                 27 ms
```

这会直接帮助 VLA 团队回答：

> 为什么模型在线下 benchmark 看起来很好，但上真机后性能突然变差？

或者：

> 为什么这个 checkpoint 在 real robot 上的表现比昨天差？

---

# 11. 第三阶段：Robotics SWE Agent

长期可以演化为：

```text
              Robot Engineering Agent

                        │
        ┌───────────────┼────────────────┐
        │               │                │
   Observability     Diagnosis         Coding
        │               │                │
 ROS / DDS          Root cause       Git repo
 Linux              reasoning        patch
 GPU                                   │
 HW                                    ▼
                                 coding agent
                                        │
                                        ▼
                                  simulation
                                        │
                                        ▼
                                   regression
```

用户只需要说：

> Robot #14 navigation randomly freezes.

Agent 自动完成：

1. 查现场状态
2. 找对应 rosbag
3. 找失败时间点
4. 分析 ROS graph
5. 找异常 node
6. 查代码
7. 找相关 commit
8. 生成 patch
9. replay rosbag
10. 运行 regression test

这时产品才真正变成：

> **Robotics SWE Agent**

而不是简单的 ROS chatbot。

---

# 12. 三个应该避免的坑

## 12.1 不要做 ChatGPT + ROS Documentation

单纯：

- 解释 ROS error
- 搜 ROS 文档
- 回答 ROS API
- 帮忙写 ROS node

非常容易被通用 coding agent 吞掉。

真正应该做的是机器人运行环境里的 active diagnosis。

---

## 12.2 不要从 Visualization 做起

Visualization 已经有成熟工具。

更值得做的是 visualization 之后的：

> **reasoning layer**

即：

```text
大量 telemetry
↓
自动调查
↓
root cause
↓
actionable recommendation
```

---

## 12.3 不要一开始支持所有机器人

第一版应该极度限定环境。

例如：

```text
Ubuntu 22 / 24
ROS 2 Humble / Jazzy
x86 / NVIDIA Jetson
Ethernet / USB sensors
```

硬件可以先支持少数典型设备：

```text
RealSense
Ouster / Hesai
工业相机
常见 USB Camera
常见 Ethernet Lidar
```

这样更容易把诊断准确率做起来。

---

# 13. 一个非常具体的 MVP 定义

产品承诺可以是：

> **Give me SSH access to your ROS 2 robot, and I can diagnose the most common runtime failures.**

而不是：

> AI for robotics development.

架构：

```text
             Engineer
                 │
        "why is lidar down?"
                 │
                 ▼
        ┌────────────────┐
        │ Debugging Agent │
        └────────┬───────┘
                 │
        Investigation Engine
                 │
     ┌───────────┼────────────┐
     │           │            │
 ROS tools    Linux tools   HW tools
     │           │            │
     └───────────┼────────────┘
                 │
           robot-agentd
                 │
              Robot
```

GitHub / GitLab / Coding Agent 可以作为后续 optional actuator。

---

# 14. 如何在产品写完前验证商业需求

可以找 10 家：

- 10～100 人规模
- 已经有真实机器人
- AI / model team 很强
- platform / infra team 很薄
- 正在做 VLA / embodied AI / manipulation / AMR / humanoid 等方向

不要问：

> 你们会不会买 AI Debugging Agent？

而是问：

> **过去两周，你们最浪费工程师时间的 5 次机器人故障是什么？**

记录：

```text
问题
排查耗时
参与人数
用了什么工具
最终 root cause
是否可自动检测
```

如果大量出现：

```text
topic 没数据       2h
DDS 问题            4h
GPU OOM             3h
TF 错误             6h
USB 摄像头掉线       2h
网络带宽打满         1 day
```

说明这个方向存在非常强的需求信号。

---

# 15. 最终创业 Thesis

可以把整个方向压缩成一句话：

> **Coding agents 解决“代码为什么不对”；Robot Debugging Agent 解决“真实机器人为什么不工作”。**

后一个问题更复杂，因为真实机器人存在：

- 软件
- 网络
- 硬件
- 时序
- GPU
- 传感器
- middleware
- physical world

之间的大量耦合。

但也正因为复杂，才更容易形成技术壁垒。

---

# 16. 推荐的产品演进路径

```text
Phase 1
ROS 2 Runtime Incident Investigator
│
├── topic
├── node
├── QoS
├── TF
├── device
├── CPU / GPU
├── network
└── logs
        │
        ▼
Phase 2
Robot Observability Agent
        │
        ▼
Phase 3
VLA Deployment Debugger
        │
        ▼
Phase 4
Code / Config Patch Agent
        │
        ▼
Phase 5
Simulation Validation
        │
        ▼
Phase 6
Robotics SWE Agent
```

---

# 17. MVP 最值得做的版本

如果只能选择一个版本，我会选择：

> **ROS 2 Runtime Incident Investigator**

第一版暂时不自动写代码。

重点把下面的问题做到非常准：

- topic 不出流
- topic rate 异常
- latency
- network
- device
- node crash
- QoS
- TF
- resource saturation
- launch / config

一旦这一层跑通，再接：

- 代码仓库
- rosbag replay
- simulation
- coding agent
- VLA runtime observability

就有机会一步步演化成真正的：

> **Robot Engineering Agent**
