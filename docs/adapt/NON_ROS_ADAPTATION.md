<!-- status: archived; authority: reference; owner: docs maintainers; last_reviewed: 2026-09-02; source_of_truth: docs/adapt/AGENT_NATIVE_TOOLS.md -->

# 非 ROS 工程适配设计

Rolo 的产品语义是 Canonical Operation，不是 ROS Topic。ROS 只是运行时 Route Provider
之一。没有 ROS 的 Python/C++ 工程仍可进入 Adapt；缺少 ROS 时，ROS Probe 返回
`UNAVAILABLE`，Application、Linux、Hardware 和启发式 Agent 继续工作。

## 处理链路

```text
源码 manifest 中的 console script
        │  DECLARED_STATIC
        ▼
ApplicationCliRouteProvider
        │
        ├── 源码入口：cli:<canonical-name>
        └── 目标证据：cli:<canonical-name> + cli:<absolute-path>
                           │ OBSERVED_RUNTIME
                           ▼
              Registry + CLI/help 启发式语义推断
                           │
                           ▼
              DISCOVERED_UNVERIFIED Operation
                           │
                           ▼
             Adapter 生成 + 独立 Conformance Gate
                           │
                           ▼
                  VERIFIED Tool Catalog
```

源码侧只读取结构化 manifest，例如 `pyproject.toml [project.scripts]`，不会执行入口。每个
入口形成 `DECLARED_STATIC` 的 `cli` Route；它可以供启发式 Agent 引用，但不能满足
Operation eligibility。

目标侧 collector 只对 enrollment 时显式允许并固定了绝对路径和 SHA-256 的可执行文件运行
有界 `--help`。签名 bundle 验证通过后，控制端从原始 help evidence 重新推导 Route，而不是
信任 collector 自报的映射：

- canonical CLI name 和目标绝对路径；
- executable ID 和 executable SHA-256；
- 从 usage、parameters、subcommands 规范化计算的 interface schema SHA-256；
- target bundle digest 和 observation time。

只有源码声明的 canonical name 与目标机观测 name 精确相交，且 help 成功、Provider ID、
executable hash 和 interface schema 都齐全时，CLI/help 启发式才会运行。推断只读取活动
Operation Registry 的名称、描述、能力要求和风险字段，并结合目标 `--help` 的 usage、参数、
子命令和有界文本；不会加载仓库或厂商专属的 Operation 映射表。

## Gate 边界

CLI name 和 `--help` 只能证明“目标机存在这个自描述入口”，不能证明命令结果正确。推断输出
仍是 `DISCOVERED_UNVERIFIED`；独立 Gate 还必须验证：

1. Candidate Route 与不可变 Linux Probe 中的 target Route 精确一致；
2. Candidate 绑定 exact executable ID，release fingerprint 绑定其 SHA-256；
3. Adapter Bundle 覆盖且只覆盖 eligible Operation；
4. `describe` 返回与 Bundle 完全一致的 Operation 到 entrypoint 映射；
5. write/运动 Operation 继续经过 Runtime policy、外部授权和物理 interlock。

Gate 不通过就不会生成 `VERIFIED` Catalog。`--help` 失败、入口只存在于源码、目标可执行文件
变化、source/target name 不一致时，只保留证据和缺口。

Promotion 只执行 `describe`，不使用 `invoke` 探测 ABI。`invoke` 只允许在 Tool Catalog、策略、
授权、目标指纹和输入 Schema 全部通过后由正式 Runtime 发起。
同一 Operation 若存在多个 gated CLI Route，调用 payload 必须带唯一 route selector；运行时
记录最终选择的 route identity，缺失或歧义时 fail-closed，不按列表顺序猜测。

## Python CLI 运行路径

目标 CLI 的 PATH 只从当前 Bundle Operation 引用的绝对 CLI Route 生成，不继承控制器完整
PATH，也不包含其他已发现但与本次 Bundle 无关的入口。若选中 CLI 位于虚拟环境，Rolo 会把
该虚拟环境加入只读挂载。editable install 的 `.pth` 仅在指向具有 `pyproject.toml`、`setup.py`
或 `setup.cfg` 的有界工程目录时转成显式 `PYTHONPATH`；bubblewrap 不会自行读取 `.pth` 并扩张
宿主挂载范围。

这些 PATH/PYTHONPATH 值进入 Runtime Context、release manifest 和目标指纹。路径缺失、无权
访问或不属于当前 Operation 时不会进入运行环境；严格加载已发布 release 时路径漂移会失败关闭。

## LeRobot 当前边界

LeRobot 使用普通 Python console scripts，因此不需要专用 Provider：

- `lerobot-find-cameras` 可通过 CLI/help 启发式映射到 `app.camera.list`；
- `lerobot-info` 是环境诊断，不等同于 robot status/health，不映射 Operation；
- `lerobot-record`、`lerobot-rollout`、`lerobot-train`、`lerobot-teleoperate` 的生命周期、取消、
  数据和物理风险语义与现有 Operation 不能自动等同，当前只报告为未映射能力；
- 数据集采集和策略推理只有在至少两个独立工程出现相同通用语义缺口、并完成 contract、风险、
  Provider 和验证设计后，才能通过独立 Registry RFC 新增，禁止创建 `lerobot.*` Operation。

## 目标机首次采集

第一次建立本地 collector 时，应同时固定待观察的入口。不要先建立空 allowlist 再直接修改；
已存在 collector 的 allowlist 变化必须走 rotation/re-enrollment。

```bash
uv run robotctl adapt start \
  --robot-id lerobot-host \
  --project-root /path/to/lerobot \
  --allow-executable "$(command -v lerobot-find-cameras)" \
  --allow-executable "$(command -v lerobot-info)" \
  --discover-only
```

先保留 `--discover-only` 检查目标证据。`lerobot-find-cameras --help` 若因依赖、设备权限或入口
初始化失败，会被记录为 help failure，不会降级为可信 Route。确认 Wiki、route evidence、
Operation eligibility 和缺口符合预期后，移除 `--discover-only` 重跑完整 Agent/Gate 链。

远程模式使用同样的两个 `--allow-executable` 初始化目标 collector；控制器无需且不得运行目标
LeRobot 二进制，完整置备方式见 [TARGET_EVIDENCE_DEPLOYMENT.md](../target/TARGET_EVIDENCE_DEPLOYMENT.md)。

## 真机结果回传

保留并回传以下文件，不要回传 collector secret、Codex credential 或 SSH private key：

- `adapt start` 的 Journey JSON 输出；
- 本次新鲜的 target evidence bundle；
- discovery `report.json`、`active_discovery_report.json` 和 `robot_wiki.md`；
- `robotctl adapt operations summary --robot lerobot-host` 输出；
- 如果继续完整链，Adapter run、gate report、handoff 和失败日志。

重点检查 `cli:lerobot-find-cameras` 是否同时具有 static declaration 和 observed target route、
两者 executable/interface identity 是否完整，以及 `app.camera.list` 是 eligible、deferred 还是
因 help/dependency 失败而缺失。
