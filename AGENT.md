# AGENT.md · 面向 AI Agent 的项目操作手册

> 你是被叫来继续开发这个项目的 AI Agent。本文件给出 **30 秒理解 + 关键约束 + 可执行命令**。
> 上游文档：`README.md`（vidwise 原始）。人类使用手册：`README.notes.md`。方案与验收：`VIDEONOTES-KIT_ROADMAP.md`。

---

## 1. 这是什么

`E:/002-Pr/videonotes-kit` 是被整改过的「**视频 + 文档 → 自包含图文笔记包**」项目。
- 入口：`python notes.py <课程> <子命令>`
- 一条命令 `build` 即把课程视频 + 文档批量产出可独立分发的笔记包
- **纯本地、零 API key**（默认不依赖任何 vision/LLM）
- 已落地 P1→P6 全部整改（骨架去硬编码 / 图片自包含 / 教程化 / 视频打包+时间轴 / **模板真接代码**）

## 2. 30 秒架构

```
<课程>视频 ─┐
            ├─→ notes build <课程> ─→ steps_pro/  ←── 自包含交付物
<课程>文档 ─┘                            ├─ NN_标签_主题.md     (10 集精校笔记)
                                         ├─ assets/<集>/        (被引帧)
                                         ├─ source/<系列>/      (源 mp4)
                                         ├─ play.html           (单页播放器)
                                         ├─ notes.html          (三栏笔记浏览器 ★ 首推入口)
                                         ├─ 参考文档/           (Rxx 文档)
                                         └─ 总索引.md
```

**数据驱动** = 一切由 `projects/<课程>/manifest.toml` 决定。换课只改这一文件，**不改任何 toolkit 代码**。

## 3. 关键约束（务必先读）

| # | 约束 | 后果 |
|---|---|---|
| 1 | **纯本地、零 API key** | 不要主动加任何需要 KEY 的依赖；不要调用外部 LLM/vision。`pyproject.toml` 已把 `anthropic` / `openai` 移到 `[guide]` extras，本工具链 `pip install -e .` 不会装；要用上游 `--guide` 路径请 `pip install -e ".[guide]"` |
| 2 | **Tier1 精校需要人工** | 本机无 vision 模型，`steps_pro.md`（金标准）仍需人手写。Tier2 LLM 精校默认关（`[llm].enabled=false`） |
| 3 | **图链用 `frames/` 在 _curated 源里** | 由 `consolidate.collect` 自动改写为 `assets/<集>/...` 并复制帧。**不要**在 _curated 源里直接写 `assets/...` |
| 4 | **assets 清空必须用临时改名 + 后台 rmtree** | 直接 `shutil.rmtree(ep_assets)` 对 ≥50 文件目录会触发沙箱 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 死锁（已踩过坑） |
| 5 | **总索引完全 manifest 驱动** | 改 `manifest.toml` 的 `course.learning_path` / `course.series_note` / `course.glossary` / `episodes[].purpose` / `episodes[].keypoints` / `docs[].note` / `docs[].detail` 即可改总索引文案，**不要手改 `总索引.md`** |
| 6 | **不要在 tools 下写硬编码路径** | 全部读 manifest。历史硬编码版本已清掉（`v2tutorial.py` 等 6 个） |

### 3.1 沙箱行为约定（写给 agent，防踩坑）

**危险操作清单**（必须用安全替代方案）：

| 操作 | 风险 | 替代方案 |
|---|---|---|
| `shutil.rmtree(目录)`（≥50 文件） | 触发 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 死锁 | 临时改名 + 后台线程 rmtree + 重建，参考 `toolkit/consolidate.collect` 实现 |
| `rm -f` / `rm -rf` 大文件/用户目录 | 触发 `safe-delete` 批量保护 | 单文件用 `os.remove()`；用户目录永不删 |
| `cat / head / tail` 大文件 | 输出可能 mojibake（GBK 误读 UTF-16/UTF-8） | 用 Read 工具读，或 `iconv -f UTF-16LE -t UTF-8` |
| 在 `E:/002-Pr/videonotes-kit` 顶层放临时文件 | 污染工程目录 | 放 `%TEMP%` / `tempfile.gettempdir()` |

**输出编码**（所有跑 Python 的命令加这两个）：

```bash
PYTHONIOENCODING=utf-8 PYTHONUTF8=1
```

**跑 Python 的最短路径**（沙箱禁用 venv python）：

```bash
# 跑模块
PYTHONIOENCODING=utf-8 "C:/Program Files/Python311/python.exe" -m toolkit.X

# 跑内部命令（cd 到工程根）
cd E:/002-Pr/videonotes-kit
PYTHONIOENCODING=utf-8 "C:/Program Files/Python311/python.exe" notes.py 沐北AICG build

# 调试时单行内联
PYTHONIOENCODING=utf-8 "C:/Program Files/Python311/python.exe" -c "import sys; sys.path.insert(0, r'E:/002-Pr/videonotes-kit'); from toolkit.X import Y; print(Y(...))"
```

**长任务**：用 Bash 的 `run_in_background: true`（不要前台等），完成后会自动通知。

**管道陷阱**：

- PowerShell `Out-File -Encoding utf8` 与 `Get-Content` 在 Windows 上对 UTF-16LE Python 输出乱码
- `*>` 与 `2>&1` 在 PowerShell 与 Git Bash 行为不同
- **最佳实践**：让 Python 直接写文件到 `%TEMP%/<name>.txt`，再 Read 读

## 4. 关键命令（Cheat Sheet）

```bash
# 跑通（最重要）
python notes.py 沐北AICG build           # 一条命令复现 10 笔记 + 8 文档 + 92 帧 + 10 源 mp4 + play.html + 总索引
python notes.py 沐北AICG verify          # 非破坏回归：draft 引擎 + notes/_staging 逐项 diff + 图片/视频自包含校验

# 单独跑某段（调试用）
python notes.py 沐北AICG draft           # 只重跑 draft 引擎 → steps_v2.md（不破坏金标准）
python notes.py 沐北AICG curate [--overwrite]   # 生成 _curated/<集>/steps_pro.skeleton.md 骨架（不覆盖金标准）
python notes.py 沐北AICG consolidate     # 只汇集视频笔记
python notes.py 沐北AICG docs            # 只归档参考文档
python notes.py 沐北AICG index           # 只重生成总索引

# B 站课素材采集（字幕直通，免本地转写）
python -m yt_dlp "<BV链接>"              # 下 mp4（yt-dlp 不在 PATH，用模块形式）
vidwise <mp4> --no-guide --no-transcribe # 只抽 frames/，跳过 Whisper（用官方 AI 字幕时）
python -m toolkit.sub <字幕.md> <ep_out_dir>   # 单独转字幕 → transcript.json（draft/build 自动跑，手动调试用）

# 沙箱环境跑 Python（venv 在本沙箱不可用，必须用系统 Python + PYTHONPATH）
PYTHONIOENCODING=utf-8 "C:/Program Files/Python311/python.exe" <脚本>

# 直接调模块
python -m toolkit.curate "E:/002-Pr/videonotes-kit/out/沐北AICG/基础_1.mp4"   # 解析单集 draft 打印步骤摘要
```

## 5. manifest 字段速查（`projects/<课>/manifest.toml`）

```toml
[course]
name                = "课名"                  # 用于标题
video_root          = "E:/.../<课>"          # 源视频根目录（同时作为字幕相对基准）
doc_root            = "E:/.../<课>/文档"     # 源文档根目录
out_root            = "E:/002-Pr/videonotes-kit/out/<课>"  # 产物根目录
notes_subdir        = "steps_pro"            # 合集目录名（默认 steps_pro/）
curated_subdir      = "_curated"             # 精校源目录
refdoc_subdir       = "参考文档"             # 文档归档子目录
assets_subdir       = "assets"               # 帧副本目录
doc_intro           = "..."                  # 文档表引言（manifest 驱动总索引）
doc_variant_note    = "..."                  # 同源变体提示
learning_path       = "..."                  # 总索引「如何使用本教程」段
series_note         = "..."                  # 总索引「系列说明」段
[[course.glossary]]                          # 黑话→真实含义（术语表）
term = "抽卡"; meaning = "用 AI 批量出图再挑"

[draft]
max_steps = 80                               # 单集最大步数

[[episodes]]
seq            = "01"                       # 序号（决定命名/排序）
label          = "基础_1"                   # 集标签（用于 assets/ 与 step 锚点）
ep_dir         = "基础_1.mp4"               # vidwise 输出目录名
topic          = "剪映剪辑基础"              # 主题（用于笔记标题/索引）
series         = "基础"                     # 系列名（用于目录分组/源视频目录）
level          = "入门"                     # 难度（入门/进阶）
purpose        = "一句话定位"                # 索引「各集概要」第 1 行
keypoints      = ["要点1", "要点2"]          # 索引「各集概要」bullet
source_video   = "D:/.../<课>/基础/1.mp4"   # 源 mp4 精确路径（P5 必填）
subtitle       = "字幕/1.md"                # 可选：相对 video_root 的 SRT/.md（含 frontmatter 也行）。
                                            # 声明即启用 B 站官方 AI 字幕直通，免本地 Whisper 转写；
                                            # draft/build 会自动转成 transcript.json；verify 做只读新鲜度校验。

[[docs]]
code     = "R01"
category = "编剧"                           # 用于目录分组
src      = "顶级结构化电影编剧执行指令.txt"  # 源文件名（相对 doc_root）
dest     = "R01_编剧_顶级结构化电影编剧执行指令.txt"  # 目标文件名
note     = "..."                            # 目录表「说明」列
detail   = "..."                            # 文末「补充参考文档说明」正文

[llm]
enabled  = false                            # Tier2 LLM 精校开关（默认关）
base_url = "http://127.0.0.1:11434"         # Ollama 兼容接口
model    = "qwen2.5:7b"
timeout  = 60
```

## 6. toolkit 模块地图

| 文件 | 职责 | 关键函数 |
|---|---|---|
| `toolkit/manifest.py` | 读 TOML，提供 `notes_root` / `curated_root` / `refdoc_root` 路径助手 | `load(path)` |
| `toolkit/draft.py` | Tier0 自动：全量帧对齐 + 语义聚合 + 简繁 → `steps_v2.md` | `build(out_dir, max_steps, out_name)` |
| `toolkit/sub.py` | SRT（B 站官方 AI 字幕，可带 YAML frontmatter）→ `transcript.json`（whisper 结构）；确定性输出供 verify 校验 | `render(src)` / `convert(src, out_dir)` |
| `toolkit/curate.py` | Tier1 骨架生成（改由 `templates/steps_pro.md` 渲染，动态步骤 for 循环预拼进 `$stages`） + Tier2 LLM 接口 | `parse_draft(path)` / `gen_skeleton(mf, ep, overwrite)` / `llm_refine_step()` |
| `toolkit/consolidate.py` | 汇集笔记 + 复制被引帧到 assets/ + 复制源 mp4 + 改写图链 | `collect()` / `copy_source()` / `gen_play_page()` / `build_all()` |
| `toolkit/docs.py` | 读 manifest 归档参考文档 | `import_docs(mf)` |
| `toolkit/index.py` | 扫描 notes/ 自动生成总索引（改由 `templates/index.md` 渲染，6 个动态块预拼后整段替换） | `build_index(mf)` |
| `toolkit/branding.py` | **项目级品牌文单一引用源**（NAME/TAGLINE/INDEX_BANNER 等）。下次更名只改本文件 + build 即可全工程更新 | 常量 |
| `toolkit/release.py` | release_check 子命令：检查项目内 9 处"我忘了同步"点（整改方案 P* / verify 产物覆盖 / 总索引 banner / README banner / AGENT 模块地图 / manifest 必填字段 / **source_video 路径存在** / **templates 真接代码** / **P5 教程体红线**） | `run(mf, base)` / `main(args)` |
| `toolkit/templates.py` | **模板渲染层**（零第三方依赖，仅 `string.Template`）。`curate` + `index` 都通过它读 `templates/*.md`；改模板外观 = 改 .md，无需碰代码 | `render(name, **kw)` / `path(name)` |
| `toolkit/notes_view.py` | **三栏笔记浏览器**（左导航 / 中正文 / 右时间轴）。把全部笔记 + 总索引预渲染内联成单个 `notes.html`，零 fetch / 零 CDN，双击 `file://` 可用；`build` 末尾自动调用 | `build_notes_view(mf)` / `render_md(text)` / `extract_play_links(text, label)` |
| `toolkit/cli.py` | 入口路由 + verify 非破坏回归 + P5 校验 | `cmd_draft/cmd_build/cmd_verify/cmd_curate/...` |

## 7. 加新课程的标准流程

1. 创建 `projects/<新课>/manifest.toml`，填 `course` / `episodes` / `docs` 字段
2. 把源视频/文档放到 `manifest` 指定的路径（不需要复制到 out，由管线按需读）
3. 跑 `python notes.py <新课> verify` 验证配置
4. 跑 `python notes.py <新课> build` 产物
5. **不要**在 out 内手改任何文件——下次 build 会覆盖

## 8. 改 notes_pro.md 金标准的标准流程

1. 读 `_curated/<集>/steps_pro.md`（手工精校源）
2. 编辑它（按 `templates/steps_pro.md` P4 教程化模板：学习目标/前置/术语/阶段/做对了/易错）
3. 跑 `python notes.py <课> build`（consolidate 自动改写图链到 assets/、注入时间轴链接、加播放器入口）
4. 跑 `python notes.py <课> verify`（应仍 PASS）

> ⚠️ **不要在 `out/.../steps_pro/` 内手改任何 .md**——下次 build 会从 `_curated/` 覆盖。

## 9. 调试故障排查

| 现象 | 可能原因 | 排查 |
|---|---|---|
| `ModuleNotFoundError: No module named 'toolkit'` | 没在 `E:/002-Pr/videonotes-kit` 目录跑 | `cd` 后再跑；或显式 `PYTHONPATH=E:/002-Pr/videonotes-kit` |
| `manifest 未找到` | `projects/<课>/manifest.toml` 不存在 | `ls projects/` 看现有课程名 |
| `curated MISS` | `_curated/<集>/` 没有 `steps_pro.md` | 跑 `notes build`（会 bootstrap 从现状引导）或手写 |
| `WARN 缺帧` | 源视频没有对应时刻的 2s 全量帧 | 重新跑 vidwise 抽帧（`vidwise --no-guide`） |
| `SOURCE MISSING` | manifest `source_video` 路径错 | 核对 `[[episodes]].source_video` 是否指到真实 mp4 |
| verify FAIL | 见具体行：diff 哪个文件 / 哪张图缺 / 哪个源视频缺 | 修对应根因后重跑 build+verify |
| `shutil.rmtree` 卡住 | ≥50 文件目录触发沙箱保护 | 用 `tmp_dir = ep_assets + ".__staging__"; os.rename(); threading.Thread(rmtree).start()` 模式（见 `consolidate.collect` 注释） |

## 10. 不该做的事

- ❌ 不要往 `toolkit/` 加第三方依赖（requests / openai / anthropic 等）——纯标准库
- ❌ 不要把源视频复制到 out/.../steps_pro/ 之外（已在 source/ 4.8 GB，别再加）
- ❌ 不要在 `out/.../steps_pro/*.md` 手改（build 会覆盖）
- ❌ 不要在总索引.md 手动改文案（改 manifest）
- ❌ 不要给 `topics` 拼字符串拼接——manifest 字段会被 toml 原样读，特殊字符用 `"""..."""` 包
- ❌ 不要在 `verify` 里加覆盖式检查（它的职责是**只校验不修改**）

## 11. 历史决策（为什么要这样）

- **目录名 `steps_pro/` 而非方案里的 `notes/`** — 用户决定沿用旧名以不破坏现有成品（cosmetic 改名不值得折腾）
- **manifest 用 TOML 而非 YAML** — Python 3.11 标准库 `tomllib` 免装 PyYAML，零依赖
- **旧散脚本已清** — 2026-10 清理 6 个（v2tutorial.py / v2step_builder.py / v2notes_builder.py / consolidate_steps.py / consolidate_docs.py / run_series.py），算法思路保留在 `toolkit/draft.py` 注释中
- **双 README** — `README.md`（上游未改）+ `README.notes.md`（项目手册） + `AGENT.md`（本文件）
- **Tier2 默认关** — 本机无对话生成模型，开了也用不到；纯本地链路不依赖
- **模板用标准库 `string.Template`，不引入 jinja2** — `toolkit/templates.py` 仅 ~50 行；保留"零第三方依赖"承诺；占位符 `$name` 约定，详见 `templates/README.md`

## 12. 紧急联络

如需找历史决策依据：见 `VIDEONOTES-KIT_ROADMAP.md §11 实施进度`（P1→P6 同步盘点 + 沙箱坑的所有决策）。
