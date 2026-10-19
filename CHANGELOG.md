# Changelog

> **本文件混合两份历史**：上游 `vidwise` 的 changelog（保留，从 v0.1.0 起）+ 本仓库 `videonotes-kit` 整改日志（2026-10-19 起独立维护）。两套版本号互不相关——上游继续其 `vidwise` SemVer；本仓的 videonotes-kit 整改使用 `[YYYY-MM-DD · <主题>]` 节标题。
>
> 修改指南：上游变更继续放在 `## [Unreleased]` 区；本仓 videonotes-kit 变更另起一节。

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- `--language` option: a language code, or `auto` to detect it (default stays `en`)
- `--word-timestamps` flag: per-word timing in `transcript.json`
- `key_frames.json`: the selected key frames and their times, written on every run, including `--no-guide`

### Fixed

- Declare `numpy` and `pillow`, which key frame selection needs

## [0.1.0] - 2026-02-26

### Added

- Core CLI with `vidwise <source>` command
- Whisper-powered transcription (`.txt`, `.srt`, `.json` outputs)
- Frame extraction every N seconds with timestamp-based naming
- Smart key frame selection via pixel-difference analysis
- URL support via yt-dlp (YouTube, Loom, 1000+ sites)
- AI-powered visual guide generation (Claude and OpenAI providers)
- Claude Code plugin with `/vidwise` slash command
- Parallel frame analysis via Claude Code subagents (no API key needed)

---

# videonotes-kit 整改日志

> 本段为本仓 (videonotes-kit) 整改历史。日期格式 `YYYY-MM-DD`；子节按主题分块。
>
> 关键时间锚：P1=骨架去硬编码；P2=图片自包含；P3=精校提效；P4=教程化；P5=视频+时间轴；P6=模板真接代码；P7=路径迁移。

## [2026-10-19 · 代码-文档同步 + 模板真接代码 (P6) + 路径迁移 (P7)]

### 体检（用户提问"代码和文档是同步的吗"）

发现 10 处不一致 + 1 处事实性问题：

- **3 处严重**：templates/ 三个 .md 是 dead code（无 .py import）；release_check 子命令在 README.notes.md 命令表里缺失；AGENT.md §3.1 整段路径写死老盘符 `D:/000/vidwise`
- **3 处中**：3 个 manifest `out_root` 全部指向历史老盘符；play.html 模板里 `<title>沐北AICG` 是硬编码；`pyproject.toml` 仍声明 anthropic / openai SDK
- **play.html 实际从未生成**（verify 会 FAIL），AGENT 架构图承诺但代码不交付
- **3 个 manifest `source_video` 全部指向不存在的路径**（67 集总受影响）

### P6 — 模板真正接入代码

**痛点**：`templates/steps_pro.md` / `templates/index.md` 在文档里被列为项目骨架，但代码从未读它们——curate / index 全用 Python 字符串直接拼。改产物外观必须改 .py。

#### Added

- 新建 `toolkit/templates.py`（~70 行核心 + doc）：基于 Python 标准库 `string.Template.safe_substitute` 的零依赖模板渲染层，`render(name, **kw)` / `path(name)` 两个公开 API
- 新建 `templates/README.md`：模板契约（占位符清单、3 条红线、最佳实践）
- `toolkit/release.py` 同步点 6 → 9 项：新增 `_check_templates_runtime`（验证 templates.py 真被代码 import）+ `_check_p5_redlines`（验证 R3/R4/R6 字面格式）+ `_check_source_video_paths`（验证 source_video 路径存在）

#### Changed

- `templates/steps_pro.md`：占位符 `{label}` `{topic}` 等改成 `$label` `$topic`（string.Template 约定）；去掉硬编码 "沐北AICG"；增加 `$banner / $purpose_block / $prereq_block / $glossary_block / $stages` 占位符
- `templates/index.md`：从 21 行示意文改写为匹配 index.py 实际产出的 6 段骨架（H1/banner/如何使用/目录/参考文档/各集概要/术语对照/补充说明）
- `toolkit/curate.py`：`_safe_int` helper；`gen_skeleton` 不再 Python 直接拼，改读模板 + for 循环预拼 `$stages` 整段替换；`banner` 拼装为 `f"来源：{course_name} {series}第 N 集 ｜ 集目录：{ep_dir} ｜ 转写：..."`
- `toolkit/index.py`：7 个 `_block_*` 动态块生成器（`_block_reading_order / _block_groups / _block_doc_intro / _block_doc_table / _block_doc_variant_note / _block_ep_summaries / _block_glossary / _block_doc_details`）；`build_index` 渲染模板
- `templates/steps_pro_tutorial.md`（P5 教程体规范）：顶部加 ⚠️ 说明「当前未连接代码，仅作 P5 写作规范参考」
- `AGENT.md §6 模块地图`：增 `toolkit/templates.py` 行；`release.py` 行扩到 8 项；`curate.py` / `index.py` 行注明"改由 templates/*.md 渲染"
- `AGENT.md §3` 约束 1：增加"`[guide]` extras"解释
- `README.notes.md §2` 目录树：tools/ 加 templates.py / release.py；templates/ 注释更新
- `README.notes.md §5` 命令表：补 `release_check` 子命令
- `README.notes.md §10` 已知约束：加"模板真接代码"条目
- `README.notes.md §13` 新增 P6 段
- `VIDEONOTES-KIT_ROADMAP.md §12` 进度表：加 P6 行；§验收 §7 加「模板与代码同步」
- `VIDEONOTES-KIT_ROADMAP.md §4.1` 目录树：templates/ 注释更新

### P7 — 路径迁移与 pyproject 清理

#### Fixed

- 3 个 manifest `out_root` 从 `D:/000/vidwise/out/<课>` → `E:/002-Pr/videonotes-kit/out/<课>`（项目搬迁，路径修正）
- 3 个 manifest 共 67 处 `source_video` 绝对路径 → 相对路径（与 subtitle 解析约定一致）：

  | 课 | 改前形式（绝对） | 改后形式（相对 `video_root`） | 改动数 |
  |---|---|---|---|
  | 沐北AICG | `D:/002-AIGC/沐北AICG/基础/1.mp4` | `基础/1.mp4` | 10 |
  | AI短剧赛道 | `E:/000/bilibili-subtitle-fetch/out/BV1WraR61EQP.mp4` | `BV1WraR61EQP.mp4` | 19 |
  | 风变麦橘AI审美创作课 | `D:/002-AIGC/002 风变麦橘-AI审美创作课/1xxx.mp4` | `1xxx.mp4`（纯 basename，与物理布局匹配）| 38 |

- `pyproject.toml`：把 `anthropic>=0.40` / `openai>=1.0` 从 `[project.dependencies]` 移到 `[project.optional-dependencies].guide` extras。`pip install -e .` 不再装 LLM SDK；上游 `--guide` 路径需要用 `pip install -e ".[guide]"`
- `toolkit/consolidate.py` `play.html` 模板：硬编码 `<title>沐北AICG · 视频播放器</title>` 与 `<h1>沐北AICG` 改成 `__COURSE_NAME__` 占位符；`gen_play_page(mf, ...)` 传 `mf["course"]["name"]` 动态替换
- `toolkit/consolidate.py copy_source`：加 `_resolve_source(mf, sv)` helper，支持绝对 OR 相对 `video_root` 解析（与 cli.py `_subtitle_src` 一致约定）
- `toolkit/cli.py` 注释：BASE 注释从"硬编码 D:/000" →"自动推导 = `<项目根>`"
- `AGENT.md` 全清 `D:/000/vidwise` 残留路径 5 处 → `E:/002-Pr/videonotes-kit`；§3 §4 §5 §7 §11 §12 全面同步
- `README.notes.md` 同步 §1 §2 §4 §6 路径与 P6 描述
- `VIDEONOTES-KIT_ROADMAP.md` 起草时间盘符 + §3 + §4.1 路径修正

### Added

- 9 项 `release_check` 子命令（整改后状态）：
  1. 整改方案 P* 阶段覆盖
  2. cmd_verify 产物覆盖
  3. 产物总索引 banner
  4. README.md 入口 banner
  5. AGENT.md 模块地图
  6. manifest 必填字段
  7. **source_video 路径存在**（新增）
  8. **templates/ 真接代码**（新增）
  9. **P5 教程体红线**（新增）

### 验收结果

| 检查 | 沐北AICG | AI短剧赛道 | 风变麦橘AI审美创作课 |
|---|---|---|---|
| `notes build` 端到端 | ✅ | ✅ | ✅（37 MISS 集未人工精校，预期） |
| `notes release_check` | ✅ **0 FAIL / 0 WARN** | ✅ 0 FAIL / 2 WARN（业务可选） | ✅ 0 FAIL / 2 WARN |
| play.html 真生成 | — | ✅ 8129 bytes，19 集 label，`<title>` = 课程名 | — |
| 时间轴跳转 | — | ✅ 223 个 `[▶ m:ss]` 链接，0 错误 | — |
| `pip install -e .` dry-run | ✅ 5 包，无 anthropic/openai | — | — |
| `pip install -e ".[guide]"` dry-run | ✅ 含 anthropic/openai | — | — |

### 工程认知

- 项目本机 3 个 manifest 全部 `video_root` 历史路径不存在（项目搬迁时源材料丢失；D:/002-AIGC 整盘不存在）
- 产物里 `out/<课>/steps_pro/source/<系列>/*` 约 1.15 GB 是历史 build 副本，`copy_source` 幂等保护使 build 不会清空
- 任何"重新 build"会保持产物不变（因源不在）；未来把 mp4 放回 `video_root` 下后直接 `notes build` 可恢复完整流程

### 待办（Deferred）

- [ ] 3 个 manifest 的 `video_root` 路径需要用户决策（搬迁到真实存在的目录）
- [ ] `templates/steps_pro_tutorial.md`（P5 体例）当前未接代码，未来加 manifest 字段 `template_version = "p5"` + 重写 curate.py 可启用
- [ ] `pyproject.toml` 注释说"上游兜底"；长期方案是把上游代码移到 `src/vidwise/` 子包 + 本仓库独立最小 `pyproject.toml`

---

## [2026-10-18 · P1-P5 整改落地（上游整改方案）]

> 该段为上游 P1-P5 整改（2026-10-18 落地）。属于本仓 videonotes-kit 的"前置历史"，**不在本 changelog 中展开**，详见 `VIDEONOTES-KIT_ROADMAP.md §12`。

**关键摘要**：

- 单一入口 `notes.py <课> <子命令>`
- 数据驱动：每课一份 `projects/<课>/manifest.toml`
- Tier0 全自动 draft → Tier1 人工精校 steps_pro → consolidate 自包含图文笔记包
- 5 阶段全部 PASS：P1 骨架去硬编码 / P2 图片自包含 / P3 精校提效 / P4 教程化 / P5 视频+时间轴

