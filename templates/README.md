# templates/ · 模板约定

> 本目录的文件**不是只读文档**——它们由 `toolkit/templates.py:render(name, **kw)` / `raw(name)` 配合
> `toolkit/curate.py` / `toolkit/index.py` / `toolkit/notes_view.py` 渲染，生成
> `_curated/<ep>/steps_pro.skeleton.md`、`<notes_root>/总索引.md` 与 `<notes_root>/notes.html`。
>
> 改动本目录内的文件 = 改产物外观，无需碰 toolkit/。

---

## 1. 文件清单与生产者

| 模板 | 生产者 | 渲染产物 | 走哪个函数 |
|---|---|---|---|
| `steps_pro.md` | `toolkit/curate.py:gen_skeleton` | `_curated/<ep>/steps_pro.skeleton.md` | `render()` |
| `index.md` | `toolkit/index.py:build_index` | `<notes_root>/总索引.md` | `render()` |
| `notes_view.html` | `toolkit/notes_view.py:build_notes_view` | `<notes_root>/notes.html` 骨架 | `render()` |
| `notes_view.css` | 同上 | 内联进 `notes.html` 的 `<style>` | `raw()` |
| `notes_view.js` | 同上 | 内联进 `notes.html` 的 `<script>` | `raw()` |
| `steps_pro_tutorial.md` | **当前未连接**（P5 教程体规范，留作历史参考与未来切档）| —（见文件顶部注释） | — |

> `raw()` 与 `render()` 的区别：`raw()` 只读原文、**不做占位符替换**。`.css` / `.js`
> 内部有 `$`（CSS 变量、JS 模板字符串）必须走 `raw()`，否则会被当成占位符吞掉。

---

## 2. 占位符语法（Python 标准库 `string.Template`）

- 形如 `$varname` —— 渲染时被替换
- 未提供值时（`safe_substitute`）保留字面 `$varname` 不报错，方便排查
- `$$` 转义为字面 `$`（不推荐使用）

**红线**：
- ❌ 不要在模板里用反引号包裹 `$varname`（`string.Template` 不识别反引号，会原样替换）
- ❌ 不要把 `$varname` 写成 `$集标签`（中英混，约定全英文）
- ❌ 不要在模板顶部写"占位符约定文档"——`$` 会被替换，造成内容污染

---

## 3. 占位符清单

### `steps_pro.md`

| 名称 | 来源 | 必填 | 用途 |
|---|---|---|---|
| `$label` | `manifest.episodes[].label` | ✓ | 集标签，H1 |
| `$topic` | `manifest.episodes[].topic` | ✓ | 主题，H1 |
| `$banner` | `curate.py` 拼装的完整 banner（含来源/课程/目录/转写） | ✓ | H1 下首行 blockquote |
| `$purpose_block` | 拼装：`purpose` + `keypoints[:2]` | ✓ | 学习目标预填 |
| `$prereq_block` | TODO 占位（manifest 暂无字段） | ✓ | 前置你会什么 |
| `$glossary_block` | TODO 占位（manifest 暂无字段） | ✓ | 关键术语 |
| `$stages` | `curate.py` for 循环拼装的阶段分组 | ✓ | 主体动态部分 |

### `index.md`

| 名称 | 来源 |
|---|---|
| `$course_name` | `manifest.course.name` |
| `$banner` | `toolkit/branding.py:INDEX_BANNER` |
| `$learning_path` | `manifest.course.learning_path` |
| `$series_note` | `manifest.course.series_note` |
| `$reading_order` | `index.py` 按 seq 拼好的列表 |
| `$groups` | `index.py` 按 series 分组的 H3 + 表 |
| `$doc_intro` | `manifest.course.doc_intro` |
| `$doc_table` | `index.py` 拼的文档目录表 |
| `$doc_variant_note` | `manifest.course.doc_variant_note` |
| `$ep_summaries` | `index.py` 各集概要（H3 + purpose + keypoints） |
| `$glossary` | `index.py` 术语对照表 |
| `$doc_details` | `index.py` 按类别分组的补充文档说明 |

### `notes_view.html`

| 名称 | 来源 | 用途 |
|---|---|---|
| `$title` | `manifest.course.name` + ` · 笔记浏览器` | `<title>` 与顶栏 `<h1>` |
| `$count` | 实际渲染的笔记篇数 | 顶栏右侧「N 篇」 |
| `$left` | `notes_view._index_panel()` | 左栏导航（总索引 + 按 series 分组） |
| `$middle` | 各篇 `render_md()` 结果拼接 | 中栏全部 `<article>`（非当前篇 `display:none`） |
| `$right` | 默认右栏占位 | 右栏初始内容，切换笔记时由 JS 替换 |
| `$css` | `raw("notes_view.css")` | 内联 `<style>` |
| `$js` | `raw("notes_view.js")` | 内联 `<script>` |

> ⚠️ `notes_view.html` 里不能出现除上述 7 个以外的裸 `$`；确需字面 `$` 请写 `$$`。
> 三栏结构的类名（`main.three` / `aside.left` / `section.middle` / `aside.right` / `.splitter`）
> 与 `notes_view.js` 强耦合，改结构必须同步改 JS 的选择器。

---

## 4. 改模板的最佳实践

- **改外观**：改 .md，**不动** toolkit/
- **加段落**：在 .md 里加 H2 + 内容，新占位符用 `⟨name⟩`（不参与渲染）
- **加新占位符**：先在 .py 端拼字符串再传给 `render(name, new_field=...)`；模板里写 `$new_field`
- **改控制流（if/for）**：模板里只放 `$block` 占位，控制流在 .py 端用 for 循环预先拼好

---

## 5. 改 .md 不破产物的 3 条红线

1. **不要改占位符名称**：`$label` 不能改成 `$集标签`（约定全英文）
2. **不要在模板里加反引号 + `$` 的组合**：` `$label` ` 会被原样替换
3. **不要把 `## H2` 改成 `# H1`**：被渲染产物的 Markdown 结构是固定的
4. **不要给 `.css` / `.js` 加占位符**：它们由 `raw()` 读取，占位符不会被替换，会原样留在产物里
