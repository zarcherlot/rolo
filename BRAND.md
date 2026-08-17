# rolo 品牌理念 / Brand Story

<p align="center">
  <img src="assets/brand/rolo-logo.svg" width="720" alt="rolo — robot only loop once">
</p>

## 核心理念

机器人调试最怕的不是失败，而是一次无法解释、无法复现的失败。**rolo** 把每次运行约束为一个清晰闭环：给出任务，执行一次，完整观察，留下证据，再决定下一步。

> **只执行一次，完整观察，精确复现。**  
> **Run once. Observe fully. Reproduce exactly.**

这里的 “once” 不代表机器人永远只运行一次，而是强调每一个调试回合都应边界明确、可以审计，并由新证据驱动下一次运行。

## 最终方案：C · Loop Exit

- **全小写 `rolo`**：亲和、轻量，符合开发者工具与开源工程的语气。
- **四个字母彼此独立**：不暗示隐藏耦合或无限连写，对应边界明确、可以单独观察和替换的工程模块。
- **完整的第一个 `o`**：代表执行前已经定义清楚的任务边界。
- **最后一个 `o` 的蓝色出口**：代表一次执行在明确位置结束，并把遥测、画面和结果交给复现与下一次决策。
- **出口不是循环箭头**：rolo 强调一次有终点的闭环，而不是让机器人无限运行。
- **白底与几何线条**：减少噪声，在 README、CLI 文档、GitHub 头像和小尺寸界面中保持清晰。

## 视觉系统

| 角色 | 色值 | 用途 |
| --- | --- | --- |
| Graphite | `#171A22` | 主字标、正文、结构 |
| Loop Blue | `#155EEF` | 唯一出口、交互强调 |
| White | `#FFFFFF` | 标准背景与留白 |
| Slate | `#667085` | 辅助说明文字 |

标准字标下方的全称必须保持为小写：`robot only loop once`。不要改写、缩写或在图形内部添加其他口号。

## 使用规则

- 优先使用 [`rolo-logo.svg`](assets/brand/rolo-logo.svg) 作为 README、网站页头和文档封面。
- 方形头像或 favicon 使用 [`rolo-mark.svg`](assets/brand/rolo-mark.svg)。
- Logo 四周至少保留一个字母 `o` 内径的净空。
- 只使用白色或非常浅的中性背景；当前版本不提供反白稿。
- 四个字母必须保持分离；不要添加连接线、箭头或连写结构。
- 不要关闭、移除或改变最后一个 `o` 的蓝色出口。
- 不要拉伸、旋转、添加渐变、阴影或发光。

## 探索记录

| 方案 | 核心隐喻 | 视觉气质 | 更适合 |
| --- | --- | --- | --- |
| A · One Complete Loop | 从起点到终点的一次执行轨迹 | 直接、有动势、记忆点强 | 产品主品牌、演示与传播 |
| B · State Frames | 输入状态到输出状态的可审计转换 | 工程化、系统化、精确 | SDK、控制面与技术文档 |
| **C · Loop Exit（最终）** | 四个独立字母，最终闭环只打开一次 | 极简、克制、亲和 | rolo 全部正式场景 |

三版并排预览见 [`rolo-logo-comparison.svg`](assets/brand/rolo-logo-comparison.svg)。A、B 仅保留为设计探索记录；README、品牌手册和标准资源均使用最终 C 版。

---

## English summary

The hardest robot failure is not a failure itself, but one that cannot be explained or reproduced. **rolo** frames each run as a bounded loop: define the task, execute once, observe fully, preserve the evidence, and only then choose the next run.

“Once” does not mean a robot can only ever run once. It means every debugging iteration has an explicit boundary, remains auditable, and lets new evidence drive the next action.

The final **Loop Exit** identity uses four independent lowercase letters, reflecting explicit boundaries and replaceable engineering modules. The first `o` is a defined task boundary. The single cobalt exit on the final `o` marks where one execution ends and hands its telemetry, frames, and result to observation and reproduction. It is deliberately not a loop arrow: rolo has a clear endpoint rather than an endless run.
