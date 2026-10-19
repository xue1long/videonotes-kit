# docs/ · 方案与设计文档

> 本目录收纳**阶段性方案、设计与技术债文档**。项目级「活文档」仍在根目录，见下方说明。

## 为什么根目录还留着几份文档

`toolkit/release.py` 会按**根路径**硬检查这三个文件的同步性，因此它们不能移走：

| 文档 | 位置 | 被谁检查 |
|---|---|---|
| `AGENT.md` | 根 | `_check_agent_module_map`（§6 模块地图须覆盖所有 `toolkit/*.py`） |
| `README.notes.md` | 根 | `_check_readme_banner`（README.md 头部须指向它） |
| `VIDEONOTES-KIT_ROADMAP.md` | 根 | `_check_roadmap`（§12 须覆盖所有已落地 `P*` 阶段） |

其余根目录文档按惯例保留：`README.md`（上游 vidwise）、`CHANGELOG.md`（变更日志）。

## 文档索引

| 文档 | 状态 | 摘要 |
|---|---|---|
| [P9-on-demand-frames.md](./P9-on-demand-frames.md) | 📋 方案已定，待实施 | **按需抽帧**：全量抽帧每集 171 s / 459 张 / 305 MB，最终只引用约 10 张（利用率 2%）。改为「字幕 → draft 步骤时间点 → 只对这些点 `ffmpeg -ss` 精确抽帧」，单集 12 s（14.6× 快）、19 集省 50 min + 5.6 GB。关键纠正：粒度须为 **draft 步骤（250 个）** 而非字幕条（5,517 条，反而慢 1.5×） |

## 命名与结构约定

- 文件名：`P<序号>-<kebab-case-主题>.md`，例 `P9-on-demand-frames.md`
- 每份方案文档必须含：**摘要表 → 背景/实测 → 方案设计 → 决策(ADR) → 风险 → 验收标准 → 实施步骤 → 回滚**
- 方案落地后：在 `VIDEONOTES-KIT_ROADMAP.md §12` 把对应 `P<n>` 行状态从 📋 改为 ✅，并在此表同步状态
- 实施完成后本文档**保留**（作为设计依据），不删除

## 与根文档的关系

```
根目录/
├── AGENT.md                    # agent 入口（引用 docs/）
├── README.notes.md             # 人类手册（目录树含 docs/）
├── README.md                   # 上游 vidwise
├── CHANGELOG.md                # 变更日志
├── VIDEONOTES-KIT_ROADMAP.md   # 阶段进度（§12 每行指向 docs/ 内对应方案）
└── docs/
    ├── README.md               # 本索引
    └── P9-on-demand-frames.md  # 按需抽帧方案
```

**分工原则**：根目录放「谁是入口、怎么用、改了什么、现在到哪一步」；`docs/` 放「为什么这么设计、怎么实施、风险与验收」。同一特性在两处出现时，根文档写**结论与状态**，`docs/` 写**论证过程**。
