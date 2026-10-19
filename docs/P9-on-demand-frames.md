# P9 方案：按需抽帧（字幕驱动 → 步骤驱动）

> 状态：**方案已定，待实施**
> 提出：2026-10-19 · 目标：把「全量抽帧」改为「按步骤按需抽帧」
> 关联：`VIDEONOTES-KIT_ROADMAP.md §12`（P9 行）· `toolkit/draft.py` · `toolkit/cli.py`

---

## 0. 一页摘要

| 项 | 现状 | 改后 | 收益 |
|---|---|---|---|
| 单集（15 min）抽帧耗时 | 171 s | ~12 s | **14.6× 快** |
| 19 集抽帧总耗时 | 54 min | 3.7 min | **省 50 分钟** |
| 抽帧临时磁盘 | 5.8 GB | 166 MB | **省 5.6 GB** |
| 帧利用率（用到的 / 抽出的） | 185 / ~8,700 ≈ **2.1%** | 250 / 250 = **100%** | 去除 98% 废帧 |

**一句话**：现在每集抽 459 张、最终只引用约 10 张。改为「先用字幕算出步骤时间点，再只对这些点精确 seek 抽帧」，抽帧成本降到 1/15，且对齐精度反而提升。

⚠️ **关键纠正**：不是「按每条字幕抽一张」——字幕有 5,517 条，`单帧 0.88 s × 5517 ≈ 81 min`，**比现在还慢 1.5 倍**。必须下沉到「按 draft 步骤」（250 个）。

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

### 4.1 总览（三步）

```
① transcript.json → draft 文本算法 → 250 个步骤时间点 t（零帧参与）
② 对每个 t 执行 ffmpeg -ss t -i <mp4> -frames:v 1 frames/frame_XmYYs.png
③ 后续 curate / collect / verify / notes_view 全部不变（契约零改动）
```

### 4.2 接口变更

**`toolkit/draft.py`**

```python
def build(out_dir, max_steps=80, out_name="steps_v2.md", video=None):
    """video: 源 mp4 路径。给定时按需抽帧；None 时保持旧行为（扫描已有 frames/）。"""
```

- 内部新增 `extract_frame_at(video, seconds, dst_dir) -> Path | None`
- 内部新增 `ensure_step_frames(video, steps, frames_dir)`：只对 `steps[i]["t"]` 抽帧
- `scan_frames()` 保留（向后兼容 + verify 回归用）

**`toolkit/cli.py`**

```python
# _draft_all(mf)
video = _resolve_source(mf, ep.get("source_video", ""))   # 复用 consolidate._resolve_source
draft.build(out, max_steps=..., video=video if os.path.isfile(video) else None)
```

- video 不存在（如本机 `video_root` 已失效）→ 传 `None`，静默回退旧行为。**不新增失败模式。**

### 4.3 核心伪代码

```python
def extract_frame_at(video, seconds, dst_dir):
    dst = os.path.join(dst_dir, f"frame_{seconds//60}m{seconds%60:02d}s.png")
    if os.path.isfile(dst) and os.path.getsize(dst) > 0:
        return dst                                    # 幂等：已存在即跳过
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(seconds), "-i", video,
         "-frames:v", "1", "-y", dst],
        capture_output=True, text=True, errors="replace")
    return dst if r.returncode == 0 and os.path.isfile(dst) else None


def ensure_step_frames(video, steps, frames_dir, follow_up=0):
    """只抽步骤时间点。follow_up>0 时额外抽 t+follow_up 作为备选。"""
    os.makedirs(frames_dir, exist_ok=True)
    ok = 0
    for st in steps:
        for t in ([st["t"]] + ([st["t"] + follow_up] if follow_up else [])):
            if extract_frame_at(video, int(t), frames_dir): ok += 1
    return ok
```

### 4.4 不变契约（重要）

| 契约 | 是否变化 | 说明 |
|---|---|---|
| `frames/frame_<m>m<ss>s.png` 命名 | ❌ 不变 | collect 的 `IMG_RE` 正则照常匹配 |
| `steps_v2.md` 结构 | ❌ 不变 | `![步骤 N 截图 XmYYs](frames/…)` 同格式 |
| `curate` 输入/输出 | ❌ 不变 | 只读 `steps_v2.md`，不知道帧怎么来的 |
| `consolidate.collect` | ❌ 不变 | 从 `frames/` 复制被引帧 |
| `verify` staging diff | ❌ 不变 | 仍按目录树逐字节比对 |
| `notes_view` | ❌ 不变 | |
| `release_check` | ⚠️ 加 1 行 | ROADMAP §12 需 P9 状态行（已预置） |

### 4.5 幂等与增量

- 帧文件已存在则跳过 → 重复 build 不重复抽帧。
- 只抽「当前步骤时间点」→ 若 `curate` 后步骤变化，下次 `draft` 会补抽新点，旧点残留但 `collect` 只复制被引用的，不影响产物。

---

## 5. 关键决策与理由（ADR）

| # | 决策 | 理由 |
|---|---|---|
| **D1** | 抽帧粒度 = draft 步骤，不是字幕条 | 字幕 5,517 条 → 81 min，比现状更慢；步骤 250 个 → 3.7 min。见 §3 |
| **D2** | 用循环 `-ss` seek，不用 `-vf select` | 实测 select 需解码全片：94.3 s vs 8.8 s（10.7× 慢） |
| **D3** | 帧仍落 `frames/`，不直接落 `assets/` | 保持 collect 的「引用即复制」契约；verify 的 staging diff 依赖它；直接落 assets 会破坏"未被引用的帧不该存在"的减重逻辑 |
| **D4** | `build(video=None)` 可选参数，缺省回退旧行为 | 本机 `video_root` 已失效（`E:/000/...` 不存在）；硬依赖视频会让现有 3 门课直接失败 |
| **D5** | 默认每步抽 1 张（`t`），不默认抽 `t+2` | 与现状对齐精度持平或更好（现状 ±1 s）；需要时用 `follow_up=2` 一把开。避免默认成本翻倍 |
| **D6** | 抽帧失败不中断，只告警 | 与现有 `WARN 缺帧` 风格一致；单集失败不应炸掉 19 集的 build |

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| **字幕时间 ≠ 画面变化时间**（Up 主说完才点击，滞后 0.5–2 s） | 抽到"操作前"的画面 | ① `follow_up=2` 可双候选（500 帧 ≈ 7 min，仍为现状 1/7）；② 与现状同等风险（现状取 t±1 s 网格，无改善也无退化）；③ 人工润色阶段可单点重抽（0.88 s） |
| **`nearest_frame(max_gap=120)` 兜底失效** | 抽帧失败时无邻近帧可退化 | 显式 `WARN` + 回退「该集首帧 0:00」；`steps_v2.md` 里该步照常无图 |
| **素材不可回溯**（不再有全量帧可事后换帧） | 想换帧需重抽 | 单帧 0.88 s，mp4 已在包内 `steps_pro/source/`，无外部依赖风险 |
| **`video` 路径失效**（本机 3 门课 `video_root` 均指向不存在的盘） | 按需抽帧无法启用 | D4 的 `video=None` 回退；或从包内 `steps_pro/source/<系列>/<名>.mp4` 取源（推荐：`_resolve_source` 优先查包内副本） |
| **`verify` 的 draft 回归失效** | `verify` 会比较 `_steps_v2_verify.md` 与 `steps_v2.md` | 抽帧是**非确定**的（ffmpeg seek 到同一秒结果相同，实际确定）；若出现 diff，把回归改成「只在 video=None 时做全量对比」 |
| **首帧/关键帧 seek 精度** | `-ss` 落在关键帧前导致画面偏差 | 现代 ffmpeg 的 `-ss`（input seeking）默认 accurate_seek，会解码到目标帧；实测抽取结果与 2 s 网格帧视觉一致 |

---

## 7. 验收标准（可机检）

| # | 验收项 | 判据 |
|---|---|---|
| V1 | 单集抽帧耗时 | ≤ 20 s（基准 12 s，留 60% 余量） |
| V2 | `frames/` 帧数 | ≈ 该集步骤数（不出现 400+） |
| V3 | 笔记图链完整性 | `assets/` 被引用图 100% 存在（当前 185/185） |
| V4 | `notes verify` | PASS |
| V5 | `release_check` | 3 门课 0 FAIL |
| V6 | `notes.html` | 图全部可加载、时间轴标题 183/183 |
| V7 | 抽帧对比抽检 | 随机 20 张，与旧全量帧（或人工判断）视觉一致 |
| V8 | 幂等 | 连跑两次 build，`frames/` 文件数不变 |

---

## 8. 实施步骤

| 任务 | 文件 | 说明 |
|---|---|---|
| **T1** | `toolkit/draft.py` | 加 `video` 参数 + `extract_frame_at` + `ensure_step_frames`；`build()` 内 steps 算完后再抽帧（替换 `scan_frames`+`nearest_frame` 路径，保留旧路径 fallback） |
| **T2** | `toolkit/cli.py` | `_draft_all` 解析 video 路径（优先包内 `steps_pro/source/`，再 `_resolve_source`） |
| **T3** | `VIDEONOTES-KIT_ROADMAP.md §12` | P9 状态行改为 ✅（行已预置） |
| **T4** | `AGENT.md` / `README.notes.md` / `CHANGELOG.md` | 模块职责、加课流程（抽帧自动）、变更日志 |
| **T5** | 回归 | 3 门课 build + verify + release_check + notes.html 校验 |
| **T6** | 对比抽检 | 抽 20 张新帧 vs 旧帧人工/视觉比对 |

写作用域：`toolkit/draft.py`、`toolkit/cli.py`、`VIDEONOTES-KIT_ROADMAP.md`、`AGENT.md`、`README.notes.md`、`CHANGELOG.md`。

---

## 9. 回滚方案

- **代码级**：`build(..., video=None)` 即旧行为；`cli.py` 用环境变量 `VN_FULL_FRAMES=1` 强制走全量路径。
- **数据级**：`frames/` 与 `assets/` 均可由 mp4 重建，无不可再生数据。
- **回滚成本**：git revert 单 commit（改动集中在 2 个 .py 文件）。

---

## 10. 影响面清单

| 不改 | 改 |
|---|---|
| `curate.py` / `consolidate.py` / `index.py` / `release.py` / `notes_view.py` / `templates.py` / `templates/*.md` / `manifest.toml` 结构 / `verify` 契约 | `draft.py`（抽帧策略）、`cli.py`（传 video）、4 个文档 |

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
