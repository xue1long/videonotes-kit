# P8 · 三栏笔记浏览器 `notes.html` 构建规范与模板化

> 状态：✅ 已落地（P8 功能 2026-10-19 随远端 v0.2 合入；**本文件覆盖的「模板化 + 门禁」于 2026-10-19 补齐**）
> 关联代码：`toolkit/notes_view.py`、`toolkit/templates.py`、`toolkit/release.py::_check_templates_runtime`、`toolkit/cli.py::cmd_verify`
> 关联模板：`templates/notes_view.html` / `notes_view.css` / `notes_view.js`

## 摘要

| 项 | 内容 |
|---|---|
| 产物 | `<notes_root>/notes.html`（单文件，38 集课程实测 769 KB） |
| 解决的问题 | 精校笔记散在 38 个 `.md` 里，收件人得一个个点开；且 `play.html` 是二级页跳转，看一步跳一次 |
| 方案 | 把全部笔记 + 总索引**预渲染内联**成单页三栏 SPA：左导航 / 中正文 / 右「播放器 + 时间轴」 |
| 硬约束 | 零 `fetch`、零 CDN、零第三方依赖；双击 `file://` 必须可用 |
| 本次整改 | ① 骨架/CSS/JS 从 Python 常量外置到 `templates/`；② 「模板真接代码」门禁扩到 `notes_view.py`；③ 补齐本规范文档 |
| 不变量 | 重构前后 `notes.html` **逐字节一致**（md5 `49eaecb875b88617b35798857b94a4ba`） |

## 1. 背景：为什么必须是「预渲染单文件」

浏览器对 `fetch(file://)` 一律拦截（CORS 限制），所以任何「运行时拉 md 再渲染」的方案在双击打开时都必然空白，必须起 HTTP 服务。而本项目的分发场景恰恰是**把 `steps_pro/` 整个目录压缩发出去，对方双击就能看**。

因此选型只有一条路：生成时把全部内容渲染成 HTML 字符串，一次性写进单文件；切换笔记 = 纯 DOM 显隐。代价是文件体积随笔记量线性增长（38 集约 769 KB，可接受）。

时间轴也一样：早期设计是点 `▶ 9:56` 跳 `play.html?ep=…&t=596`（二级页），看三步要跳三次。P8 改为右栏顶部内嵌 `<video src="source/<系列>/<原名>.mp4">`，点时间轴直接 `currentTime = t; play()`，页面不跳。

## 2. 整改前的实测问题

| 问题 | 证据 |
|---|---|
| 外观全硬编码在 Python | `toolkit/notes_view.py` 里 `_CSS` 63 行、`_JS` 90 行，加 `build_notes_view()` 内的 f-string 骨架 |
| 与 P6「模板真接代码」不符 | `grep "templates\|Template\|render(" toolkit/notes_view.py` → 零命中 |
| 逃过门禁 | `release.py::_check_templates_runtime` 只遍历 `("curate.py", "index.py")`，模板目录只要求 `steps_pro.md` + `index.md`；`notes_view` 完全不在检查范围 |
| 无规范文档 | `docs/` 只有 `P9-on-demand-frames.md`；P8 的约束只散落在 `README.notes.md §14`、`ROADMAP` 一行摘要、`CHANGELOG` |
| 改一个背景色要动 Python | 无模板 → 只能改源码字符串，且改完无法从 `templates/` 看出产物外观 |

后果：想把三栏改成两栏、换配色、加个「上一篇/下一篇」按钮，都必须改 `toolkit/`，而 `AGENT.md` 的承诺是「改模板外观 = 改 .md，不碰代码」。

## 3. 方案设计

### 3.1 三文件拆分

| 文件 | 行数 | 渲染方式 | 内容 |
|---|---|---|---|
| `templates/notes_view.html` | 25 | `T.render()`（`string.Template`，7 个占位符） | 文档骨架、顶栏、三栏 grid 容器 |
| `templates/notes_view.css` | 59 | `T.raw()`（原文） | 全部样式：栅格、分割条、正文排版、右栏播放器与按钮 |
| `templates/notes_view.js` | 86 | `T.raw()`（原文） | 导航切换、右栏 seek 播放、分割条拖动 + localStorage |

产物仍是**单文件**：`build_notes_view()` 把 css/js 读成字符串，经 `$css` / `$js` 占位符内联进 `<style>` / `<script>`。

### 3.2 占位符契约

| 占位符 | 来源 | 备注 |
|---|---|---|
| `$title` | `course.name + " · 笔记浏览器"` | 调用方已 `_esc()`，模板不再转义 |
| `$count` | 实际渲染篇数 | 顶栏「N 篇」 |
| `$left` | `_index_panel()` | 总索引入口 + 按 `series` 分组 |
| `$middle` | 各篇 `render_md()` 拼接 | 非当前篇带 `style="display:none"` |
| `$right` | 默认右栏占位 HTML | 切换时由 JS 整体替换 |
| `$css` / `$js` | `T.raw()` | 值不参与二次扫描，内部 `$` 安全 |

### 3.3 `templates.py` 的两处改动

1. **`_resolve()` 修后缀判断**：原实现 `if not name.endswith(".md"): name += ".md"`，传 `notes_view.html` 会被拼成 `notes_view.html.md`。改为 `if not Path(name).suffix` 才补 `.md`。
2. **新增 `raw(name)`**：只读原文不做替换。CSS 里的 `--w-left`、JS 里的 `${...}` 模板字符串都是合法内容，过一遍 `Template` 会被当占位符吃掉。

### 3.4 门禁升级

`release.py::_check_templates_runtime` 从「curate + index」扩到「curate + index + **notes_view**」，模板清单从 2 个 `.md` 扩到 5 个文件（含 `notes_view.html/css/js`）。这样「模板被删/被绕过」会直接 FAIL，而不是静默退化。

## 4. 决策（ADR）

| # | 决策 | 理由 | 放弃的方案 |
|---|---|---|---|
| ADR-1 | 拆 3 个文件（html + css + js） | CSS/JS 内含 `$`，塞进同一个 `.html` 模板会让「哪些 `$` 要替换」变成隐式规则；分文件后只有骨架过 `Template`，规则单一 | 单文件 `notes_view.html`（风险高） |
| ADR-2 | 产物仍内联成单文件，不外链 `.css`/`.js` | `file://` 双击可用是硬约束；且单文件便于分发。外链还会让 `verify` 的产物清单和 `_staging` diff 逻辑各多两个文件 | 产物外链三件套 |
| ADR-3 | 继续用 `string.Template`，不引 jinja2 | 「零第三方依赖」是项目级承诺（`AGENT.md §3` 约束 1） | jinja2 / handlebars |
| ADR-4 | 门禁扩现有检查，不另立新检查 | `_check_templates_runtime` 语义就是「模板是否真被用」，扩清单是最小改动 | 新增 `_check_notes_view_templates` |
| ADR-5 | 重构必须**逐字节不变** | 有 769 KB 真实产物可比对，字节一致等价于「零回归」，比人工目测可靠 | 只跑 `verify`（它会连内容一起重算，掩盖不了但定位慢） |

## 5. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 改模板类名导致 JS 失联 | 切换笔记无反应、分割条失效 | `templates/README.md` 明写「`main.three`/`aside.*`/`.splitter` 与 JS 强耦合」；改结构须同步改选择器 |
| 骨架新增裸 `$` | 占位符未被替换，产物里留字面 `$xxx` | 模板红线第 4 条；`safe_substitute` 不报错，需靠人查 |
| `raw()` 误用于 `.md` 模板 | 占位符不生效，产物是原始模板 | 文档区分 `render()` / `raw()` 用途；`.md` 全部走 `render()` |
| 体积继续增长 | 笔记破百集时单文件过大，浏览器打开变慢 | 单文件 769 KB / 38 集，线性外推 100 集约 2 MB，仍在可接受区；超阈值再考虑按 series 拆页 |

## 6. 验收标准

| # | 标准 | 验证命令 |
|---|---|---|
| A1 | 重构前后 `notes.html` 逐字节一致 | `md5sum` 对比（实测两侧均 `49eaecb8…`） |
| A2 | 无残留硬编码样式/脚本 | `grep -n "_CSS\|_JS" toolkit/notes_view.py` 为空 |
| A3 | 模板门禁生效 | `release_check` 中 `_check_templates_runtime` 无 FAIL |
| A4 | 产物门禁仍通过 | `notes.html` 存在 + 含全部集 label + 不含 `fetch(` |
| A5 | 改模板即可改外观 | 改 `notes_view.css` 的 `body` 背景色 → 重 build → 产物变色，Python 未改动 |

## 7. 实施步骤（已完成）

1. 拆出 `templates/notes_view.html`（骨架 + 7 占位符）、`.css`、`.js`
2. `toolkit/templates.py`：修 `_resolve()` 后缀判断；新增 `raw()`
3. `toolkit/notes_view.py`：删 `_CSS`/`_JS`，`import templates as T`，`build_notes_view()` 改 `T.render(...)` + `T.raw(...)`
4. 重建 `notes.html`，与重构前 `md5sum` 比对（一致）
5. `toolkit/release.py`：`_check_templates_runtime` 扩到 `notes_view.py` + 5 个模板文件
6. 文档：`templates/README.md` 生产者表与占位符清单、本文件、`docs/README.md` 索引

## 8. 回滚

- 代码级：`git revert <commit>` 即可，模板文件与 Python 改动在同一个 commit 内
- 若只想临时绕过门禁：**不要**删模板文件（会 FAIL），应修 `_check_templates_runtime` 的清单——但那等于回退整改，需在 commit message 说明
- 产物无回滚需要：`notes.html` 是派生文件，`notes build` 可随时重建，且本次重构字节不变

## 9. 与 P5/P6/P9 的边界

| 阶段 | 边界 |
|---|---|
| P5（教程体红线） | 约束的是 `_curated/<ep>/steps_pro.md` 的**写作内容**；P8 只消费已渲染的 md，不校验红线 |
| P6（模板真接代码） | P8 是其**遗漏项**：P6 只接了 `curate` 与 `index`，`notes_view` 当时仍是硬编码；本次补齐 |
| P9（按需抽帧） | 决定 `frames/` 里有哪些帧；P8 通过 md 里的 `assets/<集>/frame_NmSSs.png` 与 `· 描述` 反推时间轴标题，不直接读帧目录 |
