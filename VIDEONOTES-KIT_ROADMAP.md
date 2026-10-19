# videonotes-kit：基于 vidwise 的「视频 + 文档 → 图文笔记」项目

> 起草时间：2026-10-18 ｜ 范围：`E:/002-Pr/videonotes-kit` 工具链 + `D:/002-AIGC/沐北AICG` 源材料
> 目标：把当前「四个散脚本 + 硬编码路径 + 人工精校」的临时拼装，重构成**单一入口、清单驱动、产物自包含、可换课程复用**的图文笔记生成项目。

---

## 1. 背景与目标

vidwise 本体是「视频 → LLM 可读 Markdown」工具，招牌的 `guide.md`（逐字抄屏）需要 vision 模型或 API key。本机无 key，因此走纯本地 `--no-guide` 路径，自己补了一套图文整合脚本。

现阶段已能跑通：10 集视频 → 转写 + 全量帧 → 自动草稿（`steps_v2.md`）→ 人工手写精校（`steps_pro.md`）→ 集中成合集 + 总索引；外加把课程配套文档（Prompt/Skill/xlsx）整理进同一汇总。

**但这是「能跑」不是「项目」**：脚本各自硬编码路径、彼此割裂、换一门课就要改源码、合集图片靠脆弱的相对链接。本方案把它整改成一个可复用的项目骨架。

**一句话目标**：一条命令 `notes build <课程>` 就能把「视频 + 文档」批量变成一套可独立分发、图片不丢、带总索引的图文笔记包。

---

## 2. 现状盘点（已落地的真实资产）

| 资产 | 位置 | 角色 | 状态 |
|---|---|---|---|
| `src/vidwise/` | `D:/000/vidwise/src` | 上游工具本体（转写 + 像素差关键帧） | 可用，勿改 |
| `run_series.py` | `D:/000/vidwise` | 批量跑 `--no-guide`，断点续跑，跑完调 `v2notes_builder` | 可用，路径硬编码 |
| `v2notes_builder.py` | `D:/000/vidwise` | 出 `notes.md`（**仅用 48 张关键帧**） | 有对齐 bug，建议弃用 |
| `v2step_builder.py` | `D:/000/vidwise` | 初版步骤抽取（同样 48 帧） | 已弃用 |
| `v2tutorial.py` | `D:/000/vidwise` | 改进草稿：全量 372 帧对齐 + 语义聚合 + 简繁统一 → `steps_v2.md` | **保留为 draft 引擎** |
| `consolidate_steps.py` | `D:/000/vidwise` | 搬集笔记 → 合集、改名、改图链、生成索引 | 可用，逻辑写死在脚本里 |
| `consolidate_docs.py` | `D:/000/vidwise` | 复制课程文档 → 合集 `参考文档/`、改名 | 可用，逻辑写死 |
| `out/沐北AICG/<集>/` | `D:/000/vidwise/out` | 每集 vidwise 原始产物 + `steps_v2.md` | 散落 |
| `out/沐北AICG/steps_pro/` | 同上 | 10 篇精校笔记 + `总索引.md` + `参考文档/` | 合集（图链脆弱） |
| 源视频 | `D:/002-AIGC/沐北AICG/<基础\|失焦一\|失焦二>/N.mp4` | 输入 | 项目外 |
| 源文档 | `D:/002-AIGC/沐北AICG/文档/` | 输入 | 项目外 |

---

## 3. 核心痛点（为什么要整改）

1. **四脚本各自硬编码路径**：`SERIES_ROOT`、`OUT_ROOT`、集标签/主题 `meta` 列表全部写死在 `.py` 里。换一门课 = 改源码。
2. **无单一入口**：用户要手动依次跑 `run_series` → `v2tutorial` → `consolidate_steps` → `consolidate_docs`，漏一步就不同步。
3. **金标准 `steps_pro.md` 全靠人工手写**：纯启发式天花板已到（无 vision 模型，不能自动「读屏」总结）。每批新视频都得 AI 逐集读转写+帧重写，不可脚本化复现。
4. **图片链接脆弱**：合集笔记用 `../集目录/frames/` 相对引用，把 `steps_pro/` 单独移出 `沐北AICG/` 就断图。合集不是自包含单元。
5. **两份并行草稿混乱**：`v2notes_builder` 的 `notes.md`（48 帧 bug）与 `v2tutorial` 的 `steps_v2.md` 并存，分不清谁是谁。
6. **文档流程独立于视频流程**：参考文档靠另一个 ad-hoc 脚本，无清单、无版本/去重逻辑。
7. **源材料与产物分家**：视频、文档在 `D:/002-AIGC`，产物在 `E:/002-Pr/videonotes-kit/out`，「这门课有什么」全靠人脑记。

---

## 4. 目标架构

### 4.1 目录树（整改后）

```
D:/000/vidwise/                         # 工具链根（旧位置；当前工程已迁至 E:/002-Pr/videonotes-kit）
├── toolkit/                            # 本地管线代码（统一收口，去硬编码）
│   ├── cli.py          # 唯一入口：notes init/extract/draft/curate/build/docs/index
│   ├── extract.py      # 包装 vidwise --no-guide（复用 run_series 续跑逻辑）
│   ├── draft.py        # = v2tutorial 全量帧对齐 + 聚合 + 简繁（出 steps_v2.md）
│   ├── curate.py       # steps_pro.md 模板 / 可选本地 LLM 精校（默认关）
│   ├── consolidate.py  # 复制被引帧→notes/assets/ + 改名 + 图链改写 + 自包含
│   ├── docs.py         # 读 manifest 的 docs 段，归档参考文档 + 版本/去重标注
│   └── index.py        # 扫描 notes/ 自动生成 总索引.md
├── projects/                           # 一门课一个文件夹（数据驱动）
│   └── 沐北AICG/
│       ├── manifest.yaml       # 课程元数据 + 集清单 + 文档清单 + 命名规则
│       ├── _raw/               # 源视频/文档副本或软链（项目自洽）
│       ├── _work/<集>/         # vidwise 原始产物 + steps_v2.md
│       └── notes/              # 最终交付：NN_标签_主题.md + 总索引.md + assets/ + 参考文档/
├── templates/                         # steps_pro.md / index.md（P6 起由 toolkit/templates.py 渲染）
└── README.md                          # 使用手册
```

### 4.2 流水线（单命令 `notes build` 内部）

```
源材料(视频+文档)
   │
   ├─ extract  →  vidwise --no-guide  →  <集>/transcript.json + frames/(全量)
   │
   ├─ draft    →  draft.py 全量帧对齐+聚合+简繁  →  <集>/steps_v2.md  (半成品草稿)
   │                                         │
   ├─ curate   →  模板 + [人工/可选LLM] 精校   →  <集>/steps_pro.md  (成品，Tier1)
   │                                         │
   ├─ consolidate → 复制被引帧→notes/assets/<集>/ + 改名 NN_标签_主题.md + 改图链
   │                                         │
   └─ docs     →  读 manifest 归档参考文档→ notes/参考文档/Rxx_类别_主题
       index   →  扫描 notes/ 自动生成 总索引.md
                          │
                  交付：notes/ 自包含图文笔记包
```

---

## 5. 整改清单（现状 → 整改后，逐项对照）

| # | 整改项 | 现状 | 整改后 |
|---|---|---|---|
| 1 | 入口 | 4 个散脚本手动串 | 单一 `notes` CLI（子命令 init/extract/draft/curate/build/docs/index） |
| 2 | 配置 | 路径/集清单硬编码在 `.py` | 每课一份 `manifest.yaml`，代码零硬编码 |
| 3 | 草稿引擎 | `v2notes_builder`(48帧) 与 `v2tutorial`(372帧) 并存 | 统一用 `draft.py`（全量帧），弃用 48 帧逻辑 |
| 4 | 图片自包含 | 合集靠 `../集/frames/` 脆弱链接 | `consolidate` 把被引帧复制到 `notes/assets/<集>/`，合集可整体移动 |
| 5 | 文档流程 | `consolidate_docs.py` 独立、无清单 | `docs` 子命令读 manifest，支持类别/版本/去重标注 |
| 6 | 命名规范 | 仅在两个脚本里约定 | 写进 `manifest` schema + `templates`，集中强制 |
| 7 | 索引生成 | `consolidate_steps.py` 手搓 | `index` 子命令扫描 `notes/` 自动生成，含视频笔记+参考文档两表 |
| 8 | 源材料归位 | 视频/文档在项目外 | `manifest` 记录来源，`_raw/` 存副本/软链，项目自洽 |
| 9 | 精校层 | 从零手写 steps_pro | 提供模板 + draft 半成品（已聚合步骤、已对齐图），手工量降到「润色」 |

---

## 6. 命名与索引规范（固化）

- **视频笔记**：`notes/NN_<集标签>_<主题>.md`
  - `NN` 两位零填序号；`<集标签>` 取自视频文件名主干（如 `基础_1`）；`<主题>` 取自 manifest（或 draft 推断）。
- **参考文档**：`notes/参考文档/Rxx_<类别>_<主题>.<ext>`
  - `<类别>` ∈ `编剧 / 分镜 / 资产库 / 资料库 / 其他`；`Rxx` 两位序号。
- **图片**：`notes/assets/<集标签>/frame_xmxxs.png`（仅复制笔记实际引用的帧，控制体积）。
- **总索引**：`notes/总索引.md`，自动含两张表（视频笔记表 / 参考文档表）+ 各条概要 + 图链校验提示。

---

## 7. 自动化分层（明确「哪层能自动、哪层要人」）

- **Tier 0 · 全自动（无 key）**：`extract` + `draft` → `steps_v2.md`。可读但粗糙（标题启发式、口语冗余、错字未修）。
- **Tier 1 · 人工/AI 精校（当前金标准）**：`curate` 产出 `steps_pro.md`。本机**无 vision 模型**（仅有 faster-whisper 做 ASR），无法自动「读屏」，故这层目前仍需人/AI 手写。模板+draft 半成品把工作量压到润色级。
- **Tier 2 · 可选本地 LLM 精校（未来）**：预留接口，仅当本机接入本地 vision 模型或用户愿配 API key 时启用；默认关闭，不影响纯本地链路。

> 约束说明：用户此前明确「不靠 API key」。本方案默认走 Tier 0+1，Tier 2 仅为可选扩展，不阻塞整改。

---

## 8. 实施分期（建议 3 期，每期可独立验收）

**P1 · 骨架与去硬编码（≈半天）**
- 建 `toolkit/`（cli/draft/consolidate/index）+ `projects/沐北AICG/manifest.yaml` + `templates/`。
- 把 `v2tutorial.py` → `draft.py`、`consolidate_steps.py`+`consolidate_docs.py` → `consolidate.py`+`docs.py`+`index.py`，去掉全部硬编码路径（改读 manifest）。
- 验收：对沐北AICG 重跑 `notes build`，产物与现状 10 集 + 8 文档**逐项一致**。

**P2 · 图片自包含 + 文档入管线（≈半天）**
- `consolidate` 复制被引帧到 `notes/assets/`，消除 `../` 链接；`docs` 读 manifest 的 docs 段；`index` 自动生成双表索引。
- 验收：把 `notes/` 整体复制到别处，图片仍正常显示；总索引无需手改。

**P3 · 精校提效与文档化（≈半天）**
- 出 `steps_pro.md` 模板 + draft 半成品说明；写 `README.md` 使用手册；预留 Tier2 精校接口（默认关）。
- 验收：换一门新课程只需新增 `manifest.yaml` + 放源材料，不改任何代码即可 `notes build` 出同等产物。

---

## 9. 验收标准（整体）

1. `notes build 沐北AICG` 一条命令复现当前全部产物（10 集精校 + 8 文档 + 总索引）。
2. 换新课程：仅新增 `manifest.yaml` + 源材料，**不改代码**。
3. `notes/` 文件夹可整体移动/打包，图片不丢（自包含）。
4. `总索引.md` 自动生成，含视频笔记表 + 参考文档表，链接可点。

---

## 10. 风险与遗留

- **本地无 vision 模型** → `steps_pro` 精校仍需人工/AI 手写；若日后配 key 或本地 vision 模型，Tier 2 可接管。
- **长视频转写耗时**：medium 模型跑 8 小时音视频需数小时，断点续跑已支持，P1 保留。
- **`manifest` 需人工填主题/集标签**：可从文件名推断大部分，主题需人定（或 draft 给候选）。
- **磁盘**：vidwise 默认复制源视频进 `_work/`，全系列约 +8GB；P2 可加「不复制、直接读源」开关。
- **`v2notes_builder.py` / `v2step_builder.py`**：P1 弃用并保留为历史参考，避免与新 `draft.py` 混淆。

---

## 11. 下一步建议

建议从 **P1** 开始落地（骨架 + 去硬编码 + 用现有 10 集做回归验证）。确认后我即按此方案实施，并保留可重跑脚本。是否现在开始 P1？

---

## 12. 实施进度（已落地）

| 阶段 | 状态 | 验收结论 |
|---|---|---|
| **P1** 骨架 + 去硬编码 | ✅ 完成 | `notes build 沐北AICG` 复现 10 集 + 8 文档 + 总索引，逐项一致；verify PASS |
| **P2** 图片自包含 + 文档入管线 | ✅ 完成 | `notes/` 整体可移动不丢图（assets/ 92 帧，脆弱 `../` 链接 0）；总索引由 manifest 驱动免手改 |
| **P3** 精校提效 + 文档化 | ✅ 完成 | 见下 |
| **P4** 笔记教程化升级 | ✅ 完成 | 01_基础_1 由 11 步 → 7 步 + 3 阶段 + 三段式闭环（学习目标/前置/术语 → 阶段分组 → 做对了/易错）；模板 + curate 半成品骨架已升级 |
| **P5** 视频打包 + 时间轴跳转 | ✅ 完成 | 源 mp4 自动复制到 `steps_pro/source/<系列>/`（10 集共 4.8 GB），每步截图后追加 `▶ m:ss` 时间轴链接（10 集共 112 处），`play.html` 单页播放器生成 |
| **P6** 模板真正接入代码 | ✅ 完成 | 新建 `toolkit/templates.py`（标准库 `string.Template`，零第三方依赖）；`curate.py` 骨架与 `index.py` 总索引都改由 `templates/steps_pro.md` / `templates/index.md` 渲染；改产物外观 = 改 .md，无需碰 toolkit。`release_check` 增加 2 项（8 项同步点检查） |
| **P7** 路径迁移 | ✅ 完成 | 3 个 manifest `out_root` 统一到 `E:/002-Pr/videonotes-kit/out/<课>`；67 集 `source_video` 改为相对 `video_root`（换机器只改一行）；`pyproject.toml` 把 anthropic/openai 移入 optional `[guide]`；`play.html` 去硬编码课程名；`cli.py` `BASE` 自动推导 |
| **P8** 三栏笔记浏览器 | ✅ 完成 | 新建 `toolkit/notes_view.py`（零第三方，标准库 mini markdown 渲染器）：三栏 SPA、**分割条可拖动**（localStorage 持久化 + 双击复位）、**右栏顶部内嵌 `<video>` 播放器**（时间轴点击直接 seek 播放，弃二级页）、**时间轴每条带标题**（183/183 全命中）。`build` 必产 `notes.html`，`verify` + `release_check` 已纳入门禁。**后续补齐（同日）**：骨架/CSS/JS 从 Python 常量外置为 `templates/notes_view.{html,css,js}`，`templates.py` 新增 `raw()`（`.css/.js` 内部 `$` 不过 Template）；`_check_templates_runtime` 从 `curate/index` 扩到 `notes_view` + 5 个模板文件；重构前后 `notes.html` md5 逐字节一致。详见 [`docs/P8-notes-html.md`](docs/P8-notes-html.md) |
| **P9** 按需抽帧 | ✅ 完成 | 现状每集全量抽 459 张（171 s / 305 MB），最终只引用约 10 张（利用率 2%）。改为「字幕 → draft 步骤时间点 → 只对这些点 `ffmpeg -ss` 精确抽帧」，单集 12 s（14.6× 快）、19 集省 50 min + 5.6 GB。**两条关键纠正**：① 粒度须为「步骤」（250 个）而非字幕条（5,517 条，反而慢 1.5×）；② 抽帧须**独立成 L0.5 层 `toolkit/frames.py`**，不能塞进 `draft.build()`（会让纯函数变副作用，破坏 verify 回归）。`release_check` 加 1 项（_check_frames_mode）兜底。详见 [`docs/P9-on-demand-frames.md`](docs/P9-on-demand-frames.md) |

### P3 交付清单

1. **`toolkit/curate.py`（Tier1 半成品骨架 + Tier2 接口）**
   - `parse_draft()` 解析 `steps_v2.md` → 步骤列表（标题/正文/图链）。
   - `gen_skeleton()` 生成 `_curated/<集>/steps_pro.skeleton.md`：规范标题 + 每步已对齐截图 + 正文（来自 draft）+ `<!-- TODO 润色 -->` 注释。**非破坏**：已存在 `steps_pro.md` 时跳过，不覆盖人工金标准（`--overwrite` 仅重写骨架）。
   - `llm_refine_step()` 预留 Tier2 本地 LLM 精校：标准库 `urllib` 调 OpenAI 兼容接口，由 `manifest [llm].enabled` 控制（默认 false）；禁用/失败自动回退原文，纯本地链路不受影响。
2. **CLI 加 `curate` 子命令 + `--overwrite`**（在 `toolkit/cli.py`）。
3. **`manifest.toml` 加 `[llm]` 段**（默认 `enabled=false`，含 base_url/model/timeout）。
4. **`templates/steps_pro.md`** 重写为规范模板 + draft 半成品说明（四步流程注释）。
5. **`README.notes.md`** 项目使用手册（目录/环境/命令/manifest 字段/换课流程/三层自动化/自包含/约束）。
   - 注：上游 `README.md`（vidwise 本体）**保留未改**，项目手册另存 `README.notes.md` 以免覆盖上游文档。
6. **验收标准达成**：换一门新课只需新增 `manifest.toml` + 放源材料，**不改任何代码**即可 `notes build` 出同等产物（已用现有 10 集回归验证 P1/P2 不被破坏）。

### 整体整改验收（对照方案 §9）

| # | 验收项 | 结果 |
|---|---|---|
| 1 | `notes build` 一条命令复现全部产物 | ✅ 10 集精校 + 8 文档 + 总索引 + source 视频 + play.html |
| 2 | 换新课程仅改 manifest，不改代码 | ✅ 数据驱动，新增 `projects/<课>/manifest.toml` 即可 |
| 3 | `notes/` 可整体移动/打包，图片不丢 | ✅ assets/ 自包含，脆弱链接 0；source/ 含源 mp4，播放页自洽 |
| 4 | 总索引自动生成，含双表、链接可点 | ✅ 由 manifest 驱动，免手改 |
| 5 | 教程可读性 | ✅ P4 升级后笔记含学习目标/前置/阶段分组/做对了/易错总结 |
| 6 | 步骤可跳到视频对应时间 | ✅ P5 时间轴链接 `[▶ m:ss](play.html?ep=...&t=N)`，双击 play.html 唤起浏览器内嵌播放器 |
| 7 | 模板与代码同步 | ✅ P6 新建 `toolkit/templates.py`（标准库 `string.Template`），curate 骨架 / index 总索引都改由 templates/*.md 渲染；改产物外观 = 改 .md，无需碰 toolkit |
