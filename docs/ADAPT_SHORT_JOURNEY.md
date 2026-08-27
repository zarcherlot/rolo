# Adapt 短旅程

## 目标

`rolo adapt` 是面向产品用户的正式一站式入口。它将原先需要人工串联的
身份注册、环境检查、工程证据选择、只读发现、Wiki 生成、Adapter Agent、独立门禁和
release 发布编排为一次操作，同时保留原有细粒度命令供 ROLO 开发调试使用。

默认本地模式还会幂等建立 target evidence collector、采集并验证新鲜 v2 签名 bundle，
Discovery 只消费带目标绑定的 Hardware、Linux、Application 和可选 ROS probes。

该入口不会扩大权限：运行时探测仍然只读，URDF 不会自动猜测，Adapter Agent 不拥有
门禁或发布权限，物理执行结果也不在 Adapt 阶段判定。

## 产品用户：一条命令

安装 Rolo 后，以机器人应用用户直接运行。存在 ROS 证据时，Rolo 会在签名证据采集前自动
加载唯一的 ROS 基础环境和 `project-root/install` overlay；非 ROS 工程不要求 ROS setup：

```bash
rolo adapt /path/to/robot-workspace \
  --robot "$ROBOT_ID" \
  --urdf /path/to/robot.urdf
```

`--urdf` 可省略。缺少 URDF 或硬件规格不会阻止发现；未知项会保留在 Wiki 中。

命令默认完成：

1. 首次注册身份，后续运行复用同一身份；
2. 执行 `doctor` 等价的环境检查；
3. 在工程根目录四层以内有界识别 `build`、`install`、`docs` 和 `launch`；
4. 把工程根目录作为源码缺口补充，而不是主要溯源依据；
5. 执行 `runtime-readonly` probe 并生成可编辑 Wiki；
6. 有目标运行时路由时启动 Adapter Agent；
7. 由 ROLO 独立完成 freeze、gate、Tool Catalog、State Graph、handoff 和 release。

成功输出是 `robot-adapt-journey/v2` JSON，其中直接给出 Wiki、discovery artifact、目标证据
模式、collector ID、目标指纹、bundle digest、gate、handoff、release ID、Workbench 地址和
下一步，不要求用户理解内部目录结构。

如果只需要 Wiki 和发现证据：

```bash
rolo adapt /path/to/robot-workspace \
  --robot "$ROBOT_ID" \
  --discover-only
```

如果没有观察到 Topic、Service、Action 或其他目标路由，命令返回结构化 `BLOCKED`，但 Wiki
和 discovery 证据仍然有效。它不会把源码或文档声明升级为真实运行时证据。

控制器与目标机分离时，首次 descriptor、secret 和 SSH host-key pin 仍需独立置备；完成后
使用 `robotctl adapt start --evidence-mode remote`，Journey 会通过固定 collector 采集、验签，
且任何远程失败都不会回退到控制器 host probes。

## ROLO 开发者：保留可拆解路径

源码开发时仍可使用原有命令逐段定位问题：

```bash
uv run robotctl init --robot-id "$ROBOT_ID"
uv run robotctl adapt discover run --robot "$ROBOT_ID" ...
uv run robotctl adapt discover review --robot "$ROBOT_ID"
uv run robotctl adapt operations summary --robot "$ROBOT_ID"
uv run robotctl adapt run --robot "$ROBOT_ID"
```

也可以直接对源码版本运行同一短旅程：

```bash
uv run robotctl adapt start \
  --robot-id "$ROBOT_ID" \
  --project-root /path/to/robot-workspace
```

因此产品入口和工程调试入口共享同一套底层服务、制品和门禁，不维护第二套行为。

## 自动识别与显式输入边界

- 自动识别最多遍历 2,000 个目录、深度不超过四层，每类最多选择 32 个根目录；
- 跳过版本控制目录、虚拟环境、vendor、日志和已有 output/artifacts；
- 多个 URDF 可能表达不同机器人或配置，因此必须由用户用 `--urdf` 明确选择；
- 非典型布局仍可退回 `adapt discover run` 的可重复 `--build-root`、`--install-root`、
  `--doc-root`、`--launch-root` 和 `--source-root`；
- `--active-probe none` 只适合离线开发或负向验证，真机默认保持 `runtime-readonly`。
