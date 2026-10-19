# P9 方案：按需抽帧（字幕驱动 → 步骤驱动）

> 状态：**方案已定（v2，含架构影响修订），待实施**
> 提出：2026-10-19 · 目标：把「全量抽帧」改为「按步骤按需抽帧」
> 关联：`VIDEONOTES-KIT_ROADMAP.md §12`（P9 行）· 新增 `toolkit/frames.py` · `toolkit/cli.py` · `toolkit/draft.py`（**不改签名**）
>
> **v2 修订（2026-10-19 架构调研后）**：原 v1 设计 `draft.build(video=...)` 被否决——那会让 `draft` 从纯函数变成有副作用（写 `frames/`），破坏 `verify` 的回归假设。改为**新增独立的抽帧层 `toolkit/frames.py`**，`draft` 签名不变。详见 §4.0。

---

## 0. 一页摘要

| 项 | 现状 | 改后 | 收益 |
|---|---|---|---|
| 单集（15 min）抽帧耗时 | 171 s | ~12 s | **14.6× 快** |
| 19 集抽帧总耗时 | 54 min | 3.7 min | **省 50 分钟** |
| 抽帧临时磁盘 | 5.8 GB | 166 MB | **省 5.6 GB** |
| 帧利用率（用到的 / 抽出的） | 185 / ~8,700 ≈ **2.1%** | 250 / 250 = **100%** | 去除 98% 废帧 |
| 改动代码量 | — | ~250 行 + 3 manifest + 5 文档 | 新增 1 层、改 3 处契约 |

**一句话**：现在每集抽 459 张、最终只引用约 10 张。改为「先用字幕算出步骤时间点，再只对这些点精确 seek 抽帧」，抽帧成本降到 1/15，且对齐精度反而提升。

⚠️ **关键纠正 1**：不是「按每条字幕抽一张」——字幕有 5,517 条，`单帧 0.88 s × 5517 ≈ 81 min`，**比现在还慢 1.5 倍**。必须下沉到「按 draft 步骤」（250 个）。
⚠️ **关键纠正 2**：抽帧不能塞进 `draft.build()`——那会让纯函数变成写副作用的函数，`verify` 每次回归都会触发抽帧并改写 `frames/`。必须**独立成层**（§4.0）。

---

## 1. 背景：现状是怎么跑的

```
视频 mp4 ──ffmpeg fps=1/2──→ frames/  459 张/集（每 2 秒一张）
                                   │
transcript.json ──draft.build──→ 找动作句 → 聚合步骤 → nearest_frame(每步 1 张)
                                   │
                            steps_v2.md（250 步 / 19 集）
                                   │
                     curate 人工润色 → steps_pro.md（引用 185 张）
                                   │
              consolidate.collect ─┴→ 只复制被引用的帧到 assets/
```

**关键事实**（读码确认）：

- `toolkit/draft.py` 里帧只出现在 **一处**：`g["frame"] = nearest_frame(frames, g["t"])`，**每个步骤只需 1 张**。
- 步骤划分（`ACTION_RE` 命中 + Jaccard 聚合）**完全是文本算法，不需要任何帧**。
- 全量抽帧的唯一作用：保证 `nearest_frame(t)` 能在 `max_gap=120 s` 内找到帧，且尽量贴近 `t`（2 秒网格 → 误差 ±1 秒）。
- `consolidate.collect()` 只复制 `IMG_RE` 命中的帧 → 459 张里最终只有 ~10 张进 `assets/`。

**结论**：全量抽帧是在为一个「每步只要 1 张、共 10 张」的需求，付出 459 张的成本。

---

## 1.5 架构影响调研（2026-10-19）

> 本节回答：**这个改动是否要同步修改整体架构？**
> 结论：**要——新增一层（L0.5 抽帧层）+ 改 3 处契约**，但不是整体重构。

### 1.5.1 当前分层（实测确认）

```
L0  采集/转写  src/vidwise/           ← ffmpeg + whisper + yt-dlp（上游，不改）
     └→ frames/（全量 459 张）+ transcript.json

L1  字幕      toolkit/sub.py          ← 纯文本，标准库
     └→ transcript.json（B站字幕直通，跳过 L0）

L2  草稿      toolkit/draft.py        ← 纯文本 + **只读** frames/
     └→ steps_v2.md

L3  精校      toolkit/curate.py       ← 纯文本
     └→ _curated/*/steps_pro.md（人工润色）

L4  汇集      toolkit/consolidate.py  ← 文件复制
     └→ steps_pro/{*.md, assets/, source/, play.html, notes.html}

L5  产物      index / play / notes_view / release / verify
```

### 1.5.2 三个关键事实（读码确认）

| # | 事实 | 证据 |
|---|---|---|
| 1 | **`toolkit/` 里 0 处 `ffmpeg` / `subprocess` 调用** | 帧提取 100% 在上游 L0；`toolkit/sub.py:13` 注释「frames/ 仍来自 vidwise --no-transcribe 抽帧」 |
| 2 | **`draft.build()` 是纯函数**（对 frames/ 只 `os.listdir`） | `draft.scan_frames()` 只读；`verify` 正是靠这一点反复调用它做回归 |
| 3 | **`frames/` 有 4 个消费方** | `draft`（读路径）· `curate`（正则取路径）· `consolidate`（复制文件）· `release`（校验图链格式） |

### 1.5.3 P9 会触碰的三条架构契约

| # | 现状契约 | P9 后的变化 | 级别 |
|---|---|---|---|
| **C1** | 抽帧责任在 **L0（vidwise）** | 责任下移到 toolkit | 🔴 架构边界变更 |
| **C2** | `draft.build()` **无副作用** | 若内嵌 ffmpeg → 有副作用（写 frames/） | 🔴 破坏 verify 回归假设 |
| **C3** | toolkit **零外部二进制依赖**（README §3 / AGENT §3） | 需要 **ffmpeg**（可选，缺失时降级） | 🟡 部署前提变化 |

次要契约：
- **`frames/` 语义**：从「全量缓存（可事后换帧）」→「按需产物（只含被引用帧，可从 mp4 重建）」
- **`manifest` 数据契约**：新增 `[draft] frame_mode` / `frame_follow_up`

### 1.5.4 推荐架构：新增 L0.5，`draft` 保持不变

```
L0    采集/转写   vidwise（不动）
L0.5  抽帧       **新增 toolkit/frames.py**   ← ffmpeg 只在这里出现
       frames.ensure(mf, ep, mode="on_demand") → frames/（按需、幂等）
L1    字幕        sub.py（不动）
L2    草稿        draft.py（**签名不变，仍是纯函数**）
L3    精校        curate.py（不动）
L4    汇集        consolidate.py（不动）
L5    产物        index / play / notes_view / release / verify（不动）
```

编排点全部收在 `cli.py`（唯一需要改的控制流）：

```python
# cmd_build / cmd_draft / cmd_verify 三处统一成：
_subtitle_sync(mf, ep)      # 已有
frames.ensure(mf, ep)       # 新增：按需抽帧（幂等，已有则跳过）
draft.build(out, ...)       # 不变，纯函数
```

**为什么这样能同时满足三条契约**：

| 契约 | 解法 |
|---|---|
| C1 职责边界 | ffmpeg 隔离在 `frames.py` 一个文件；draft 不感知视频 |
| C2 draft 纯函数 | 签名不变 → **verify 回归逻辑零改动** |
| C3 外部依赖 | `frames.available()` 检测不到 ffmpeg → WARN + 跳过（老课 frames/ 已存在，不受影响） |
| verify 非破坏 | `frames.ensure` 幂等：首次 build 后 frames/ 已有全部所需帧，verify 时 250 次 `os.path.isfile` ≈ 10 ms |

### 1.5.5 被否决的方案（记录理由，防回退）

| 方案 | 否决理由 |
|---|---|
| `draft.build(video=...)` 内嵌 ffmpeg | draft 变副作用函数；`verify` 每次回归触发抽帧（19×12 s）+ 改写 frames/，违背 verify 非破坏定位 |
| 抽帧直接写 `assets/`（跳过 frames/） | 破坏 collect 的「引用即复制」契约；未引用帧会滞留；verify 的 staging diff 失效 |
| 沿用 vidwise 全量抽帧但降到 `fps=1/30` | 帧数降到 1/4，但仍是"盲抽"，且低密度会让 `nearest_frame` 误差放大 |

---

## 2. 实测基线（2026-10-19）

测试样本：`out/AI短剧赛道/steps_pro/source/AI漫剧/BV1WraR61EQP.mp4`

| 属性 | 值 |
|---|---|
| 时长 | 15.3 min（917 s） |
| 分辨率 / 帧率 | 1920×1080 / 30 fps |
| 源总帧数 | 27,512 |

| 方案 | 命令要点 | 耗时 | 产出 | 磁盘 |
|---|---|---|---|---|
| **A 现状** | `-vf fps=1/2` | **171.1 s** | 459 张 | **305 MB** |
| **B 按需** | 10 次 `-ss T -i ... -frames:v 1` | **8.8 s** | 10 张 | 7.0 MB |
| C 单次解码 | `-vf select='eq(n,…)+…'` | 94.3 s | 10 张 | — |

### 两个必须记住的结论

1. **B 比 A 快 19.5×、小 44×**。
2. **C 比 B 慢 10.7×** —— `-ss` 放在 `-i` 前是容器级快速 seek（≈0.88 s/张，含进程启动）；`select` 滤镜必须把整条 917 s 视频解码完。**实现必须用循环 seek，禁止用 filter select。**
3. 单帧边际成本 ≈ **0.88 s**（含 ffmpeg 进程启动开销），该数字是后续所有推算的基准。

---

## 3. 粒度分析：为什么「按字幕」不行

19 集统计（`transcript.json` + `steps_v2.md` + 笔记图链）：

| 层级 | 数量 | 与实引用图之比 | 按此粒度抽帧耗时 | 结论 |
|---|---|---|---|---|
| 全量帧（时长/2 s） | ~8,700 | 47 : 1 | 54 min（实测外推） | 现状 |
| **字幕条数** | **5,517** | 29.8 : 1 | **81 min** ❌ | **比现状更慢** |
| 动作句（`ACTION_RE`） | 1,470 | 7.9 : 1 | 21.6 min | 快 2.5× |
| **draft 步骤** | **250** | **1.4 : 1** | **3.7 min** ✅ | 快 14.6× |
| 实际被引用 | 185 | 1 : 1 | — | 理论下界 |

**判据**：抽帧粒度应等于「笔记的最小配图单元」= draft 步骤。字幕是「说了一句」的粒度，比配图需求细 30 倍。

---

## 4. 方案设计

### 4.0 分层与编排（v2 修订的核心）

**不把抽帧塞进 draft，而是独立成模块。** 理由见 §1.5.4/§1.5.5。

```
cli.cmd_build / cmd_draft / cmd_verify
  ├─ _subtitle_sync(mf, ep)       现有：字幕 → transcript.json
  ├─ frames.ensure(mf, ep)        ★新增 L0.5：按需抽帧 → frames/（幂等）
  ├─ draft.build(out, ...)        现有：纯函数，只读 frames/ → steps_v2.md
  └─ consolidate.build_all(mf)    现有：→ 产物
```

**为什么必须在 `draft.build` 之前**：`draft` 需要 `frames/` 已就位（`nearest_frame` 找不到帧该步就没图）。

### 4.1 总览（四步）

```
① transcript.json → draft 文本算法算出 250 个步骤时间点 t（纯文本，零帧）
② frames.ensure() 对每个 t 执行 ffmpeg -ss t -i <mp4> -frames:v 1 frames/frame_XmYYs.png
③ draft.build() 照常扫描 frames/ → steps_v2.md（**签名与逻辑零改动**）
④ curate / collect / index / play / notes_view / verify 全部不变
```

### 4.2 接口设计

**新增 `toolkit/frames.py`（L0.5 抽帧层，~90 行）**

```python
"""frames：按需抽帧层。唯一允许调用 ffmpeg 的模块。

为什么独立成模块而不是塞进 draft：
  - draft.build() 必须保持纯函数（verify 靠反复调用它做回归，不能有写副作用）
  - ffmpeg 是外部二进制，依赖隔离在一个文件里才好做"缺失即降级"
"""

def available() -> bool:
    """ffmpeg 是否可用（shutil.which）。"""

def resolve_video(mf, ep) -> str | None:
    """定位源 mp4：优先包内 steps_pro/source/<series>/<名>.mp4，再 manifest source_video。"""

def step_times(transcript_path) -> list[int]:
    """复用 draft 的文本算法算出步骤时间点（**不抽帧**）。

    注意：与 draft.build 的步骤推导必须同源，避免"抽帧的点"与"笔记的点"错位。
    实现方式二选一（实施时确定）：
      A) 把 draft 的 raw→groups 推导抽成公开函数 derive_steps(segs) -> list[dict]
      B) frames 只调 draft.derive_step_times() 包装
    """

def ensure(mf, ep, mode="on_demand", follow_up=0) -> dict:
    """确保该集 frames/ 含所需帧。幂等：已存在则跳过。返回统计 dict。"""

def extract_at(video, seconds, dst_dir) -> str | None:
    """单帧精确抽取（-ss 前置，快速 seek）。已存在则直接返回。"""
```

**`toolkit/draft.py`（签名不变，仅可能新增一个纯函数）**

```python
# 现状保持不变
def build(out_dir, max_steps=80, out_name="steps_v2.md"): ...

# 新增（纯函数，无 IO 副作用）：供 frames.step_times 复用步骤推导逻辑
def derive_step_times(segs, max_steps=80) -> list[int]: ...
```

**`toolkit/cli.py`（编排，~15 行）**

```python
def _ensure_frames(mf, ep):
    from . import frames as F
    if mf["draft"].get("frame_mode", "on_demand") == "full":
        return                      # 兼容：全量模式由 L0 负责
    if not F.available():
        print(f"  WARN 无 ffmpeg，跳过按需抽帧：{ep['ep_dir']}")
        return                      # 降级：frames/ 已有则照常工作
    F.ensure(mf, ep, follow_up=mf["draft"].get("frame_follow_up", 0))

# cmd_draft / cmd_build / cmd_verify 里 `_draft_all` 与回归循环均调用
```

**`manifest.toml`（新增 2 个可选字段，有默认值可不填）**

```toml
[draft]
max_steps = 80
frame_mode = "on_demand"   # on_demand（默认）| full（旧全量，由 vidwise 负责）
frame_follow_up = 0        # 0 = 只抽 t；2 = 额外抽 t+2 作为备选
```

### 4.3 核心伪代码

```python
def extract_at(video, seconds, dst_dir):
    dst = os.path.join(dst_dir, f"frame_{seconds//60}m{seconds%60:02d}s.png")
    if os.path.isfile(dst) and os.path.getsize(dst) > 0:
        return dst                                    # 幂等：已存在即跳过
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(seconds), "-i", video,
         "-frames:v", "1", "-y", dst],
        capture_output=True, text=True, errors="replace")
    return dst if r.returncode == 0 and os.path.isfile(dst) else None


def ensure(mf, ep, mode="on_demand", follow_up=0):
    video = resolve_video(mf, ep)
    if not video:
        return {"skipped": "no_video"}
    fdir = os.path.join(mf["course"]["out_root"], ep["ep_dir"], "frames")
    os.makedirs(fdir, exist_ok=True)
    times = step_times(os.path.join(os.path.dirname(fdir), "transcript.json"))
    made = fail = 0
    for t in times:
        for tt in ([t] + ([t + follow_up] if follow_up else [])):
            if extract_at(video, int(tt), fdir):
                made += 1
            else:
                fail += 1
    return {"times": len(times), "ok": made, "fail": fail}
```

### 4.4 契约变化表（v2 修订）

| 契约 | 是否变化 | 说明 |
|---|---|---|
| `draft.build()` 签名/语义 | ❌ **不变** | 仍是纯函数；verify 回归逻辑零改动 |
| `frames/frame_<m>m<ss>s.png` 命名 | ❌ 不变 | collect 的 `IMG_RE` 正则照常匹配 |
| `steps_v2.md` 结构 | ❌ 不变 | `![步骤 N 截图 XmYYs](frames/…)` 同格式 |
| `curate` 输入/输出 | ❌ 不变 | 只读 `steps_v2.md`，不知道帧怎么来的 |
| `consolidate.collect` | ❌ 不变 | 从 `frames/` 复制被引帧 |
| `verify` 比对逻辑 | ❌ 不变 | 但需在回归前调 `frames.ensure`（保证可重放） |
| `notes_view` / `index` / `play` | ❌ 不变 | |
| **`frames/` 语义** | ⚠️ 变 | 全量缓存 → 按需产物（只含被引用帧，可从 mp4 重建） |
| **toolkit 依赖** | ⚠️ 变 | 新增**可选**外部依赖 `ffmpeg`（缺失时 WARN 降级） |
| **manifest 字段** | ⚠️ 变 | 新增 `[draft] frame_mode` / `frame_follow_up`（可选） |
| **`release_check`** | ⚠️ 加 1 项 | 新增「frames/ 帧数 ≫ 步骤数」回归检测 |
| `AGENT.md` / `README.notes.md` | ⚠️ 更新 | 架构图加 L0.5、§6 模块地图加 `frames.py`、环境要求加 ffmpeg（可选） |

### 4.5 幂等与增量

- 帧文件已存在则跳过 → 重复 build 不重复抽帧；`verify` 反复跑也不产生新帧。
- 只抽「当前步骤时间点」→ 若 `curate` 后步骤变化，下次 `frames.ensure` 补抽新点；旧点残留但 `collect` 只复制被引用的，不影响产物。
- 换 `frame_follow_up` 后旧帧不删（文件名不同），可手动清理或留着当候选。

### 4.6 保留 `frames/` 的决策

`frames/` **保留**（不做「用完即删」）：

| 保留 | 删除 |
|---|---|
| verify 回归可重放（无需 ffmpeg，10 ms） | 省 166 MB |
| 离线/无 ffmpeg 环境仍可 build | 「按需」更纯粹 |
| 事后换帧无需重抽 | — |

结论：保留。166 MB 相对 1.15 GB 源视频可忽略，而「无 ffmpeg 也能 build」是重要降级能力。

---

## 5. 关键决策与理由（ADR）

| # | 决策 | 理由 |
|---|---|---|
| **D1** | 抽帧粒度 = draft 步骤，不是字幕条 | 字幕 5,517 条 → 81 min，比现状更慢；步骤 250 个 → 3.7 min。见 §3 |
| **D2** | 用循环 `-ss` seek，不用 `-vf select` | 实测 select 需解码全片：94.3 s vs 8.8 s（10.7× 慢） |
| **D3** | 帧仍落 `frames/`，不直接落 `assets/` | 保持 collect 的「引用即复制」契约；verify 的 staging diff 依赖它；直接落 assets 会破坏"未被引用的帧不该存在"的减重逻辑 |
| **D4** | **抽帧独立成 `toolkit/frames.py`，不塞进 `draft.build()`** | draft 必须保持纯函数——`verify` 靠反复调用它做回归，不能有写副作用。见 §1.5.5 |
| **D5** | 默认每步抽 1 张（`t`），不默认抽 `t+2` | 与现状对齐精度持平或更好（现状 ±1 s）；需要时用 `frame_follow_up=2` 一把开。避免默认成本翻倍 |
| **D6** | 抽帧失败不中断，只告警 | 与现有 `WARN 缺帧` 风格一致；单集失败不应炸掉 19 集的 build |
| **D7** | ffmpeg 检测失败 → WARN + 跳过（不抛错） | 现有 3 门课 `frames/` 已存在/可重建，无 ffmpeg 时仍能 build；不应因缺外部二进制让旧流程失败 |
| **D8** | 新增 manifest 字段 `frame_mode` / `frame_follow_up`，**均有默认值** | 老 manifest 不填也不报错；`frame_mode="full"` 可回退旧行为 |
| **D9** | `frames/` 保留不删（见 §4.6） | verify 可重放 + 无 ffmpeg 环境可 build；166 MB 相对 1.15 GB 源视频可忽略 |
| **D10** | 抽帧时间点与笔记步骤必须**同源** | 否则「抽帧的点」与「笔记引用的点」错位，图会配错步骤。实施时把 draft 的步骤推导抽成公开纯函数 `derive_step_times()`，frames 复用 |

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| **字幕时间 ≠ 画面变化时间**（Up 主说完才点击，滞后 0.5–2 s） | 抽到"操作前"的画面 | ① `follow_up=2` 可双候选（500 帧 ≈ 7 min，仍为现状 1/7）；② 与现状同等风险（现状取 t±1 s 网格，无改善也无退化）；③ 人工润色阶段可单点重抽（0.88 s） |
| **`nearest_frame(max_gap=120)` 兜底失效** | 抽帧失败时无邻近帧可退化 | 显式 `WARN` + 回退「该集首帧 0:00」；`steps_v2.md` 里该步照常无图 |
| **素材不可回溯**（不再有全量帧可事后换帧） | 想换帧需重抽 | 单帧 0.88 s，mp4 已在包内 `steps_pro/source/`，无外部依赖风险 |
| **`video` 路径失效**（本机 3 门课 `video_root` 均指向不存在的盘） | 按需抽帧无法启用 | `frames.resolve_video` 优先查包内 `steps_pro/source/<系列>/<名>.mp4`；都找不到则 WARN 跳过（D7） |
| **步骤推导双实现漂移**（frames 与 draft 各算一遍时间点） | 抽帧的点与笔记的点错位 → 图配错步骤 | D10：只保留一份推导逻辑，draft 暴露 `derive_step_times()` 纯函数，frames 调用它；`release_check` 加一致性校验 |
| **verify 回归被抽帧拖慢** | 若 frames/ 被删，verify 每次触发重抽（19×12 s） | `frames.ensure` 幂等 → 首次后仅 250 次 `os.path.isfile` ≈ 10 ms；如需纯只读校验，加 `--no-frames` 开关 |
| **首帧/关键帧 seek 精度** | `-ss` 落在关键帧前导致画面偏差 | 现代 ffmpeg 的 `-ss`（input seeking）默认 accurate_seek，会解码到目标帧；实测抽取结果与 2 s 网格帧视觉一致 |

---

## 7. 验收标准（可机检）

| # | 验收项 | 判据 |
|---|---|---|
| V1 | 单集抽帧耗时 | ≤ 20 s（基准 12 s，留 60% 余量） |
| V2 | `frames/` 帧数 | ≈ 该集步骤数（不出现 400+） |
| V3 | 笔记图链完整性 | `assets/` 被引用图 100% 存在（当前 185/185） |
| V4 | `notes verify` | PASS，且回归耗时无显著上升（frames/ 已就位时 < 5 s） |
| V5 | `release_check` | 3 门课 0 FAIL |
| V6 | `notes.html` | 图全部可加载、时间轴标题 183/183 |
| V7 | 抽帧对比抽检 | 随机 20 张，与旧全量帧（或人工判断）视觉一致 |
| V8 | 幂等 | 连跑两次 build，`frames/` 文件数不变 |
| **V9** | **draft 仍是纯函数** | `git diff` 中 `draft.build()` 签名未变；`grep subprocess toolkit/draft.py` = 0 命中 |
| **V10** | **步骤时间点同源** | `frames.step_times()` 与 `draft.derive_step_times()` 对同一 transcript 输出完全一致 |
| **V11** | **无 ffmpeg 降级** | 临时把 ffmpeg 从 PATH 移除 → build 仍成功（WARN 跳过抽帧），现有 notes.html 不受影响 |

---

## 8. 实施步骤（v2）

| 任务 | 文件 | 说明 |
|---|---|---|
| **T1** | `toolkit/draft.py` | 把 raw→groups 的步骤推导抽成公开纯函数 `derive_step_times(segs, max_steps)`；`build()` 改为调用它（**行为不变、签名不变**） |
| **T2** | **新增 `toolkit/frames.py`** | `available()` / `resolve_video()` / `step_times()` / `ensure()` / `extract_at()`，~90 行；唯一 import `subprocess` 的模块 |
| **T3** | `toolkit/cli.py` | 新增 `_ensure_frames(mf, ep)`；在 `_draft_all` 与 `cmd_verify` 的回归循环里、`draft.build()` **之前**调用 |
| **T4** | `projects/*/manifest.toml` | 3 个文件加 `[draft] frame_mode = "on_demand"` / `frame_follow_up = 0`（可选字段，显式写出便于发现） |
| **T5** | `toolkit/release.py` | 新增 `_check_frames_mode`：frames/ 帧数 > 步骤数 × 3 → WARN（回归检测）；同时校验 `frames.py` 是唯一含 `subprocess` 的模块 |
| **T6** | 文档 | `AGENT.md`（§2 架构图加 L0.5、§3 约束加 ffmpeg 可选、§6 加 `frames.py`、§11 记决策）、`README.notes.md`（§3 环境要求、§2 目录树、§7 加课流程）、`CHANGELOG.md` |
| **T7** | 回归 | 3 门课 build + verify + release_check + notes.html 校验 |
| **T8** | 对比抽检 | 20 张新帧 vs 旧帧视觉比对 |

**写作用域**：`toolkit/draft.py`、`toolkit/frames.py`（新增）、`toolkit/cli.py`、`toolkit/release.py`、`projects/*/manifest.toml`、`AGENT.md`、`README.notes.md`、`CHANGELOG.md`、`VIDEONOTES-KIT_ROADMAP.md`。

**预估代码量**：新增 ~90 行（frames.py）+ 改 ~60 行（cli/draft/release）+ 3 manifest + 5 文档 ≈ **250 行级**（v1 估的「40 行」偏乐观，已修正）。

---

## 9. 回滚方案

- **代码级**：`manifest [draft] frame_mode = "full"` 即回到旧行为（frames 由 L0/vidwise 提供）；或在 `cli` 层用环境变量 `VN_FULL_FRAMES=1` 强制跳过 `frames.ensure`。
- **数据级**：`frames/` 与 `assets/` 均可由 mp4 重建，无不可再生数据。
- **回滚成本**：git revert 单 commit（改动集中在 3 个 .py + 1 新增文件）。

---

## 10. 影响面清单（v2）

| 不改 | 改 |
|---|---|
| `draft.py` 的 `build()` 签名与语义 / `curate.py` / `consolidate.py` / `index.py` / `notes_view.py` / `templates.py` / `templates/*.md` / `verify` 比对逻辑 / `sub.py` | **新增 `frames.py`（L0.5）** / `draft.py`（抽出纯函数） / `cli.py`（编排） / `release.py`（新检查） / 3 个 manifest / 5 份文档 |

### 架构层变化一览

| 层 | 变化 |
|---|---|
| L0 vidwise | 不再承担抽帧职责（可选保留用于 `frame_mode="full"`） |
| **L0.5 frames（新增）** | 按需抽帧，唯一的 ffmpeg 调用点 |
| L1 sub | 不变 |
| L2 draft | 签名不变，内部抽出 `derive_step_times()` |
| L3 curate | 不变 |
| L4 consolidate | 不变 |
| L5 产物 | 不变（`release_check` 多一项检查） |

---

## 附录 A：复现实验命令

```powershell
# A 全量
ffmpeg -v error -i <video> -vf fps=1/2 <tmp>/f_%04d.png -y

# B 按需（推荐路径）
ffmpeg -v error -ss 596 -i <video> -frames:v 1 frame_9m56s.png -y

# C 单次解码 select（**不推荐**，实测慢 10×）
ffmpeg -v error -i <video> -vf "select='eq(n\,14900)+eq(n\,30000)'" -vsync 0 m_%02d.png -y
```

## 附录 B：当前数据状态（2026-10-19）

- `out/AI短剧赛道/steps_pro/assets/` 有 **183 张**帧（曾因 `collect()` 清空重建被删，已从包内 19 个 mp4 按笔记引用时间点重新提取恢复，0 失败）。
- `out/<课>/p*/frames/` 当前**不存在**（历史全量帧已不在本机）→ 正是本方案 P9 要解决的场景：**有 mp4 就能按需重建帧，不需要预存全量帧**。
- 19 个 mp4 均在 `out/AI短剧赛道/steps_pro/source/<系列>/`，共 1.15 GB。

## 附录 C：修订记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 2026-10-19 | 初稿：粒度分析 + 实测基线 + `draft.build(video=...)` 接口设计 |
| **v2** | 2026-10-19 | 架构调研后修订：<br>① **否决** v1 的 `draft.build(video=...)`——改为新增 L0.5 `toolkit/frames.py`（D4）；<br>② 新增 §1.5 架构影响调研（三条契约 C1/C2/C3 + 被否决方案）；<br>③ 新增 D7–D10（ffmpeg 降级 / manifest 字段 / frames 保留 / 步骤推导同源）；<br>④ 实施步骤从 6 项扩到 8 项，代码量估算 40 行 → **250 行级**；<br>⑤ 验收新增 V9–V11（draft 纯函数 / 时间点同源 / 无 ffmpeg 降级） |
