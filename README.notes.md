# videonotes-kit · 使用手册

> 本文是 `E:/002-Pr/videonotes-kit` 下「视频 + 文档 → 图文笔记」管线的使用手册。
> 上游 vidwise 本体文档见同目录 `README.md`（未改动）。
> 本手册面向：**把本地课程视频 + 配套文档，整理成可独立分发、图片不丢、带总索引的图文笔记包**。

纯本地运行、**无需任何 API key**。

---

## 1. 它能做什么

| 输入 | 处理 | 输出 |
|---|---|---|
| 课程视频（mp4） | vidwise 本地转写 + 全量帧 + draft 聚合 + 人工/可选 LLM 精校 | 每集 `steps_pro.md` 精校笔记 |
| 课程文档（txt/md/xlsx） | 按清单归档改名 | `参考文档/Rxx_类别_主题` |
| 上述两者 | 汇集 + 复制被引帧 + 复制源视频 + 时间轴链接 + 生成总索引 | 自包含 `notes/` 图文笔记包 |

一条命令 `notes build <课程>` 即可复现整套产物。

---

## 2. 目录结构

```
E:/002-Pr/videonotes-kit/                # 工具链根
├── notes.py            # 唯一入口：notes <课程> <子命令>
├── README.md           # 上游 vidwise 文档（未改）
├── README.notes.md     # 本文（项目手册）
├── toolkit/            # 本地管线（零硬编码，全部读 manifest）
│   ├── cli.py          #   CLI 路由 + verify 非破坏回归
│   ├── manifest.py     #   读 projects/<课>/manifest.toml
│   ├── draft.py        #   = v2tutorial：全量帧对齐 + 聚合 + 简繁 → steps_v2.md
│   ├── curate.py       #   Tier1：draft → steps_pro.skeleton.md 骨架 + Tier2 LLM 接口（改由 templates/steps_pro.md 渲染）
│   ├── consolidate.py  #   汇集笔记 + 复制被引帧到 assets/ + 改写图链（自包含）
│   ├── docs.py         #   读 manifest 归档参考文档
│   ├── index.py        #   扫描 notes/ 自动生成 总索引.md（改由 templates/index.md 渲染）
│   ├── templates.py    #   模板渲染层（标准库 string.Template；零第三方依赖）
│   └── release.py      #   release_check 子命令（8 项同步点检查：P* / verify / 总索引 / README / AGENT / manifest / 模板真接 / P5 红线）
├── projects/           # 一门课一个文件夹（数据驱动）
│   └── 沐北AICG/
│       └── manifest.toml   # 课程/集/文档清单 + 索引增强文案 + [llm] 开关
├── templates/          # steps_pro.md / index.md 模板（由 toolkit/templates.py 渲染；详见 templates/README.md）
├── out/<课程>/         # 产物（vidwise 原始产物 + _curated + <notes_subdir>/）
│   ├── <集>.mp4/       #   vidwise 原始产物：transcript.json + frames/ + steps_v2.md
│   ├── _curated/<集>/  #   人工精校金标准 steps_pro.md（curate 生成的骨架为 .skeleton.md）
│   └── <notes_subdir>/ #   最终交付（默认 steps_pro/）：NN_标签_主题.md + 总索引.md
│       ├── assets/<标签>/   # 各集被引帧副本（自包含，可整体移动）
│       └── 参考文档/         # Rxx_类别_主题
└── VIDEONOTES-KIT_ROADMAP.md  # 方案与验收（含 P1→P5 进度 + 6 条验收对照）
```

> 源视频/文档默认在 `D:/002-AIGC/沐北AICG`（项目外），由 `manifest.toml` 记录路径，
> 做到「换课只改 manifest，不放代码里」。

---

## 3. 环境要求

- **Python 3.11+**（用标准库 `tomllib` 读 TOML，无需装 PyYAML）。
- **无第三方依赖**：Tier2 LLM 接口用标准库 `urllib`，不引入 `requests`。
- **无需 API key**：默认 Tier0（draft）+ Tier1（人工精校）。Tier2 本地 LLM 默认关闭。
- vidwise 本地转写依赖本机已缓存的 faster-whisper medium 模型（`HF_HUB_OFFLINE=1` 强制离线）。
- **依赖安装**：`pip install -e .` 仅装工具链必需的 5 个（click / openai-whisper / yt-dlp / numpy / pillow）。`anthropic` / `openai` 已移到 `[project.optional-dependencies].guide` extras；上游 `--guide` 路径要用就 `pip install -e ".[guide]"`。本工具链不需要。

---

## 4. 快速开始（以现有沐北AICG 为例）

```bash
cd E:/002-Pr/videonotes-kit

# ① 重新生成各集 draft 草稿（确定性，可复现）
python notes.py 沐北AICG draft

# ② 为各集生成「待润色骨架」（仅缺 steps_pro.md 时写 .skeleton.md，不破坏金标准）
python notes.py 沐北AICG curate

# ③ 人工编辑 _curated/<集>/steps_pro.skeleton.md → 另存 steps_pro.md（精校金标准）
#    （沐北AICG 10 集已精校完成，这步可跳过）

# ④ 一键重建自包含图文笔记包（draft + 汇集 + 复制帧 + 文档 + 总索引）
python notes.py 沐北AICG build

# ⑤ 非破坏回归校验：draft 引擎一致 + 笔记逐项一致 + 图片自包含
python notes.py 沐北AICG verify
```

> ⚠️ `build` 依据 `_curated/<集>/steps_pro.md` 重建 `notes/`。现有 10 集金标准已就位，
> `build` 可无损复现；但**不要**手改 `notes/` 里的笔记（那是生成物），改 `_curated/` 里的金标准。

---

## 5. 命令参考

| 子命令 | 作用 | 说明 |
|---|---|---|
| `draft` | 重生成各集 `steps_v2.md` | draft 引擎，确定性，可复现 |
| `curate [--overwrite]` | 生成 `_curated/<集>/steps_pro.skeleton.md` | Tier1 半成品骨架；不覆盖 `steps_pro.md`；`--overwrite` 仅重写骨架 |
| `build` | 跑 `draft` + 汇集 + 文档 + 索引 | 重建自包含 `notes/` 包 |
| `verify` | 非破坏回归 + 图片自包含校验 | draft 重生成比对 + notes 重生成到 `_staging` diff + assets 校验 |
| `docs` | 仅归档参考文档 | 读 manifest docs 段 |
| `index` | 仅重新生成总索引 | 全部文案由 manifest 驱动 |
| `consolidate` | 仅汇集视频笔记 | 不含文档/索引 |
| `release_check` | 8 项同步点自动检查 | P* 阶段覆盖 / verify 产物覆盖 / 总索引 banner / README banner / AGENT 模块地图 / manifest 必填字段 / **模板真接代码** / **P5 教程体红线** |

---

## 6. manifest 字段说明（`projects/<课>/manifest.toml`）

```toml
[course]
name = "沐北AICG"                 # 课程名（用于总索引标题）
video_root = "D:/002-AIGC/..."    # 源视频根（仅记录，vidwise 已跑过）
doc_root   = "D:/002-AIGC/.../文档"  # 源文档根
out_root   = "E:/002-Pr/videonotes-kit/out/沐北AICG"  # 产物根
notes_subdir   = "steps_pro"     # 最终交付子目录名
curated_subdir = "_curated"      # 人工金标准源
refdoc_subdir  = "参考文档"       # 文档归档子目录
assets_subdir  = "assets"        # 自包含帧目录
doc_intro      = "..."           # 总索引·文档区引言（固化文案，免手改）
doc_variant_note = "..."         # 总索引·同源变体提示

[draft]
max_steps = 80                   # draft 单集最大步数

[[episodes]]                     # 每集一条
seq = "01"                       # 两位序号
label = "基础_1"                 # 集标签（同视频文件名主干）
ep_dir = "基础_1.mp4"            # vidwise 输出目录名
topic = "剪映剪辑基础"            # 主题（人工定，或 draft 推断）

[[docs]]                         # 每篇参考文档一条
code = "R01"                     # 序号
category = "编剧"                 # 类别 ∈ 编剧/分镜/资产库/资料库/其他
src = "# 顶级结构化电影编剧执行指令.txt"  # 相对 doc_root
dest = "R01_编剧_顶级结构化电影编剧执行指令.txt"  # 目标文件名
note = "目录表说明"              # 总索引目录表「说明」列
detail = """文末说明逐条正文"""   # 总索引文末说明（缺省回退 note）

[llm]                            # Tier2 可选本地 LLM 精校（默认关）
enabled = false
base_url = "http://127.0.0.1:11434"
model = "qwen2.5:7b"
api_key_env = ""
timeout = 60
```

---

## 7. 新增一门课程（换课不改代码）

1. 建 `projects/<新课>/manifest.toml`，填 `[course]` + 各 `[[episodes]]` + 各 `[[docs]]`。
2. 把源视频放到对应 `ep_dir`（先用 vidwise 本地 `--no-guide` 跑转写，得到 transcript.json + frames/）。
3. `python notes.py <新课> draft` → 生成 `steps_v2.md`。
4. `python notes.py <新课> curate` → 生成骨架；人工润色成 `steps_pro.md`。
5. `python notes.py <新课> build` → 出自包含图文笔记包（**同时自动生成 `play.html` 播放器 + `notes.html` 三栏笔记浏览器**，无需额外配置）。

**全程不碰 `toolkit/` 任何代码。**

### 7.1 B 站官方 AI 字幕直通（免本地转写）

B 站视频已有官方 AI 字幕时，可跳过数小时的 Whisper 转写，让字幕直接喂 `draft`：

```toml
[[episodes]]
seq = "01"
label = "p1"
ep_dir = "p1.mp4"            # vidwise 产物目录（里面要有 frames/）
topic = "xxx"
subtitle = "字幕/1.md"       # 相对 video_root；绝对路径也行。声明即启用直通。
```

- **`subtitle` 字段声明即开**：`notes draft`/`build` 会先把它转成 `<ep_dir>/transcript.json`（whisper 格式），再照常跑 draft。
- **兼容 SRT（可带 YAML frontmatter）**：bilibili-subtitle-fetch 产出的 `.md` 直接喂。
- **确定性转换**：同字幕 → 逐字节相同 `transcript.json`；`verify` 走非破坏「字幕新鲜度」校验（不同步则报错让你重跑 draft，不改文件）。
- **拿到 `frames/`**：mp4 仍要跑抽帧，但跳过转写：`vidwise <mp4> --no-guide --no-transcribe`（`--no-transcribe` 只抽帧，快）。
- **未声明 `subtitle` 时**：回退原 Whisper 链路（读 `<ep_dir>/transcript.json`），行为不变。

---

## 8. 自动化分层（明确哪层能自动、哪层要人）

- **Tier 0 · 全自动（无 key）**：`draft` → `steps_v2.md`。可读但粗糙（标题启发式、口语冗余、错字未修）。
- **Tier 1 · 人工/AI 精校（当前金标准）**：`curate` 产出 `steps_pro.skeleton.md` 半成品，人润色后存 `steps_pro.md`。本机无 vision 模型，无法自动「读屏」，故这层仍需人。模板 + 骨架把工作量压到「润色级」。
- **Tier 2 · 可选本地 LLM 精校（默认关）**：manifest `[llm].enabled=true` 时，`curate` 对每步正文调本地 LLM 润色；禁用/失败自动回退原文，纯本地链路不受影响。

> 约束：用户明确「不靠 API key」。默认走 Tier 0+1；Tier 2 仅可选扩展，不阻塞整改。

---

## 9. 产物自包含说明

`notes/`（默认 `steps_pro/`）是**自包含单元**：
- 笔记配图已复制到 `notes/assets/<标签>/`，图链为 `assets/...`，**不依赖外部 `frames/` 目录**。
- 可整体移动 / 打包 / 发给他人，图片不丢。
- `总索引.md` 由 manifest 驱动自动生成，含视频笔记表 + 参考文档表 + 各集概要 + 文档说明。

---

## 10. 已知约束 / 遗留

- 本地无 vision 模型 → `steps_pro` 精校仍需人工/AI 手写（Tier 2 可接管）。
- 长视频转写耗时：medium 模型跑 8 小时音视频需数小时，断点续跑已支持。
- `manifest` 的 `topic` 需人工定（或从 draft 推断候选）。
- 旧散脚本 `v2tutorial.py` / `consolidate_steps.py` / `consolidate_docs.py` / `v2notes_builder.py` / `v2step_builder.py` / `run_series.py` 已于 2026-10 清理（被本 toolkit 完全取代）。算法思路保留在 `toolkit/draft.py` 注释中。
- **模板真接代码**：`templates/steps_pro.md` 由 `toolkit/curate.py` 通过 `toolkit/templates.py` 渲染；`templates/index.md` 由 `toolkit/index.py` 同路渲染。改模板外观 = 改 .md，无需碰 toolkit/。详见 `templates/README.md`。

---

## 11. P4 笔记教程化升级

默认的 `steps_pro.md` 笔记模板含五块要素，让笔记从"操作流水账"升级为"可迁移的教程"：

| 区块 | 作用 | 示例 |
|---|---|---|
| **学习目标** | 3 条以内，学完能做到 | "会判断 / 会做 / 带走一个观" |
| **前置你会什么** | 降低陌生感 | "会抽卡、会剪映基础操作" |
| **关键术语** | 黑话→真实含义 | "**抽卡**：AI 批量出图再挑" |
| **阶段分组**（2–3 个 H2） | 把 6–14 步并入 2–3 段，每段一句话"在解决什么问题" | "阶段 A · 想画面 → 解决：废片不是废的，是顺序不对" |
| **每步三件套** | 讲解 + 截图 + 「做对了的表现」+「经验/易错」 | "做对了：原声音轨消失，只有画面无声" |
| **易错总结** | 文末 1 张表 | 错点 / 后果 / 改法 |

**颗粒度建议**：每阶段 2–4 步，总步数 6–8 最佳，10 步为上限（人一次能稳定执行的认知节点 = 3–5，米勒数操作版）。

**已用样本**：`沐北AICG/01_基础_1_剪映剪辑基础.md` 由 11 步 → 7 步 + 3 阶段。

**升级 curate 半成品骨架**：`toolkit/curate.gen_skeleton` 同样按 5 块要素生成占位（学习目标/前置/术语/阶段/做对了/易错），并从 manifest 预填 `purpose`/`keypoints`，让人写骨架时只补"判定标准/易错"。

**升级 consolidate collect**：在写入每集 assets 之前先清空 `assets/<label>/` 目录（修 P2 旧帧残留的潜在 bug）。

---

## 12. P5 视频打包 + 时间轴跳转

收件人拿到合集后，**双击 `play.html` 即可在浏览器内看视频**，点任何笔记里的 `▶ 0:00` 链接即跳到该时间点。

### 产物结构

```
<notes_subdir>/
├── notes.html            # ★ 三栏笔记浏览器（左导航 / 中正文 / 右时间轴；双击即用）
├── play.html             # 单页播放器（HTML5 video + JS 解析 URL 参数）
├── 总索引.md
├── 01_…_剪映剪辑基础.md  # 笔记内截图后追加 [▶ m:ss](play.html?ep=...&t=N)
├── 02_…_…
├── …
├── assets/<集标签>/      # 被引帧（92 张）
├── source/<系列>/        # 源 mp4（10 集共 4.8 GB）
│   ├── 基础/1.mp4
│   ├── 基础/2.mp4
│   └── …
└── 参考文档/              # Rxx 文档
```

### manifest 字段

`[[episodes]]` 每集加 `source_video`（**绝对路径，或相对 `course.video_root` 的相对路径**——两者都支持；推荐相对路径，换机器只改 `video_root`）：

```toml
[[episodes]]
seq = "01"
label = "基础_1"
ep_dir = "基础_1.mp4"
topic = "剪映剪辑基础"
series = "基础"
level = "入门"
source_video = "D:/002-AIGC/沐北AICG/基础/1.mp4"   # 必填
```

### 时间轴链接语法

`toolkit/consolidate.collect` 解析每张截图的 `frame_XmYYs.png`，自动改写为：

```markdown
![步骤 1 截图 0m00s](assets/基础_1/frame_0m00s.png) [▶ 0:00](play.html?ep=%E5%9F%BA%E7%A1%80_1&t=0)
```

点击后跳转到 `play.html?ep=基础_1&t=0`，JS 解析参数、定位视频、设置 `currentTime`。

### play.html 行为

- URL 参数 `?ep=<label>&t=<秒>` 打开自动跳时间
- 顶部视频区 + 元信息（当前集/主题/跳转时间/总时长）
- 下方"所有集"卡片列表，点击切换
- 切换时同步 URL（便于分享"看这段"的链接）

### 收件人使用流程

1. 解压 `steps_pro/` 任意目录
2. 双击 `play.html` → 默认浏览器打开 → 选集 → 播放
3. 在任何笔记里点 `▶ 0:00` 链接 → 自动跳到该步骤

---

## 13. P6 模板真正接入代码

2026-10-19 整改：

- **痛点**：`templates/steps_pro.md` 与 `templates/index.md` 在文档（AGENT.md / README.notes.md / VIDEONOTES-KIT_ROADMAP.md）里被列为项目骨架，但代码从未读它们——curate / index 全用 Python 字符串直接拼。改产物外观必须改 .py。
- **改造**：新建 `toolkit/templates.py`（标准库 `string.Template`，零第三方依赖），把 curate 骨架与 index 总索引改为「读 templates/*.md + safe_substitute 填占位符」。控制流（if/for）仍由 Python for 循环预拼成块整体替换。
- **效果**：改产物外观 = 改 templates/*.md，无需碰 toolkit/。
- **配套**：`toolkit/release.py` 增加 2 项检查（`_check_templates_runtime` + `_check_p5_redlines`），同步点从 6 → 8（另加 `_check_source_video_paths` 后共 9 项）。模板契约详见 `templates/README.md`。
- **约束**：
  - 占位符 `$name`（全英文），禁止反引号包裹 `$xxx`（会被替换）
  - `templates/steps_pro_tutorial.md`（P5 体例）当前**未连接代码**，留作历史参考与未来切档
  - `release_check` 警告 ≠ 阻塞，但模板层 FAIL 必须修

> 注意：`source/` 是**冗余副本**（4.8 GB）。如需减重，删除 `source/` 后 `play.html` 仍会工作但视频无法播放——笔记可读、跳转链接仍可点（浏览器会报"无法加载视频"）。

---

## 14. 三栏笔记浏览器 `notes.html`

`build` 末尾自动生成 `<notes_subdir>/notes.html`——**双击即可在浏览器里读全部笔记**，不需要起 HTTP 服务。

### 三栏布局

| 栏 | 内容 |
|---|---|
| **左** | 总索引入口 + 各集按 `series` 分组；当前集高亮 |
| **中** | 渲染后的笔记正文：标题 / 表格 / 代码块 / 引用 / 嵌套列表 / 截图；`**粗体**` 与 `` `行内代码` `` 正常显示 |
| **右** | **顶部内嵌 `<video>` 播放器** + **时间轴按钮列表**（每条带标题）：点击 → 播放器直接 seek 到该秒播放，不跳二级页 |

### 交互特性

- **分割条可拖动**：左右两条 `grid` 分割条支持鼠标拖拽调宽（左 150–460px / 右 200–560px），宽度写 `localStorage` 持久化，**双击分割条恢复默认**（240 / 280）。
- **右栏内嵌播放器**：`src="source/<系列>/<原名>.mp4"`（包内自包含副本，相对路径 `file://` 可用）；点时间轴 `▶ 9:56` 按钮 → `video.currentTime = 596; play()`，当前条目高亮 `.playing`；首次点击若元数据未加载则等 `loadedmetadata` 再 seek。
- **时间轴标题**：从笔记图链 `![步骤 N 截图 XmYYs · 描述](…)` 的 `·` 后半段描述提取，按时间戳匹配（取首次出现）；无描述显示灰色 `—`。
- 正文内 `▶ m:ss` 跳 `play.html` 的链接**按原设计保留**（只有右栏改为内嵌播放）。

### 实现要点（`toolkit/notes_view.py`）

- **预渲染 + 内联**：全部笔记 + 总索引的 HTML 在生成时一次内联进单文件（约 450–500 KB）。切换笔记是纯 DOM 显隐，**零网络请求**——所以 `file://` 双击可用（浏览器对 `fetch(file://)` 会拦截，这是选预渲染的原因）。
- **零第三方依赖**：markdown 渲染是自写 mini renderer（标准库 `re`）：标题 / 段落 / 有序列 / 无序列（含 2 空格缩进嵌套）/ 表格（跳过 `---` 分隔行）/ 代码块 / 引用块 / 分割线 / 图片 / 链接 / 行内粗体与代码。
- **时间轴链接识别**：`[▶ m:ss](play.html?ep=…&t=N)` 兼容半角/全角冒号，渲染为 `.play-link` 按钮，同时在右栏聚合。
- **图片**：`assets/<集标签>/frame_x.png` 相对路径引用，与笔记同目录，随包移动不丢。

### 流程固化（三门课通用）

| 环节 | 行为 |
|---|---|
| `notes build` | `consolidate.build_all()` 末尾调用 `notes_view.build_notes_view()`，**必然**产出 `notes.html`（与 `play.html` 同级） |
| `notes verify` | 校验 notes.html 存在 + 含全部集 label + 无 `fetch(`（防破坏 file:// 可用性） |
| `notes release_check` | 产物清单含 `notes.html`，缺失报 WARN |
| 新增课程 | **无需额外配置**，`build` 自动带出该课的 notes.html |

### 用法

```bash
python notes.py <课程> build     # 生成 notes.html（含在内）
# 然后直接双击 out/<课程>/<notes_subdir>/notes.html
```

> 已知限制：只有 `steps_pro/` 内已存在的笔记会被收录（依赖 build 先跑 `collect`）；某集缺金标准时该集在左侧不可见——与「10 集金标准」一致。

