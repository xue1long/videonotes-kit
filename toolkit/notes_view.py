# -*- coding: utf-8 -*-
"""notes_view：把 steps_pro/ 的 19 篇精校笔记 + 总索引渲染为单页 SPA。

特点：
  - **零 JS fetch / 零 CDN 依赖**：HTML 整页静态生成，双击 file:// 也能用
  - **零第三方依赖**：用标准库 re；markdown 渲染是 ~150 行自写 mini renderer
  - **三栏布局**：左导航（19 集按 series 分组 + 总索引）/ 中正文 / 右时间轴链接按钮列表
  - **预渲染 · 内联 HTML**：笔记内容直接内联在 textarea 里，切换时无 reflow

为什么不用 jinja2 / marked：因为本项目"纯本地、零第三方"。`_safe_html` 用 bleach 无依赖替代
（自写白名单过滤）。
"""
import html as _html
import os
import re
import urllib.parse
from pathlib import Path

from . import manifest as M

# 模块级上下文：build_notes_view 写入，_right_panel_for_article 读取
_SRC_ROOT = [None]   # steps_pro/source（相对 notes_root 的相对串，或 None）
_mf = [None]         # 当前 manifest dict


# ---- 内联资源：markdown → HTML mini renderer ----

_INLINE_LINK_RE  = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)|\[([^\]]*)\]\(([^)]+)\)")
_FENCE_RE        = re.compile(r"^```(\w*)\s*$")
_TABLE_SEP_RE    = re.compile(r"^\s*\|?[\s:|-]+\|?[\s:|-]+\|?\s*$")
_PLAY_LINK_RE    = re.compile(
    r"\[▶\s*(\d+)[:：](\d{2})\]\(play\.html\?ep=([^&]+)&t=\d+\)"
)  # 支持半角/全角冒号（实测 coexist 两种形式）
_RULE_RE         = re.compile(r"^-{3,}\s*$")
_UL_LINE_RE      = re.compile(r"^(\s*)[-*]\s+(.+)$")
_OL_LINE_RE      = re.compile(r"^(\s*)(\d+)\.\s+(.+)$")
_PLAY_LINK_RE    = re.compile(
    r"\[▶\s*(\d+)[:：](\d{2})\]\(play\.html\?ep=([^&]+)&t=\d+\)"
)  # 支持半角/全角冒号（实测 coexist 两种形式）
_RULE_RE         = re.compile(r"^-{3,}\s*$")


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")


def _esc(s: str) -> str:
    return _html.escape(s, quote=False)


def _fmt(s: str) -> str:
    """文字段：escape 后做行内 `code` / **bold**。"""
    s = _esc(s)
    s = _CODE_SPAN_RE.sub(lambda m: "<code>" + m.group(1) + "</code>", s)
    s = _BOLD_RE.sub(lambda m: "<strong>" + m.group(1) + "</strong>", s)
    return s


def render_inline(text: str) -> str:
    """渲染行内元素：图片 ![a](b) / 链接 [t](u) / ▶ 时间轴按钮 / `code` / 转义。

    关键：raw markdown text 输入，**不预 escape**——escape 在每个文字段单独做，
    标签段保留 raw。⚠️ 上游调用方不能预先 _esc。
    """
    out = []
    i = 0
    while i < len(text):
        # 找最近的 [▶ ...](play.html...)
        m = _PLAY_LINK_RE.search(text, i)
        # 普通 inline: ![alt](url) 或 [txt](url)
        m_alt = _INLINE_LINK_RE.search(text, i)
        if not m and not m_alt:
            out.append(_fmt(text[i:]))
            break
        # 取最近的（按 start 升序，相同则 PLAY 优先）——后续逻辑按 PLAY 优先
        candidates = []
        if m_alt:
            candidates.append(("link", m_alt))
        if m:
            candidates.append(("play", m))
        # 按 start 排序；如果同位置 PLAY 优先
        candidates.sort(key=lambda x: (x[1].start(), 0 if x[0] == "play" else 1))
        kind, first = candidates[0]
        if first.start() > i:
            out.append(_fmt(text[i:first.start()]))
        if kind == "play":
            mm, ss = first.group(1), first.group(2)
            ep_enc = first.group(3)  # URL-encoded label（已经是 encoded）
            ep_label = _html.unescape(ep_enc)
            secs = int(mm) * 60 + int(ss)
            out.append(
                f'<a class="play-link" href="play.html?ep={_esc(ep_enc)}&t={secs}" '
                f'target="_blank" data-ep="{_esc(ep_label)}" data-time="{mm}:{ss}">▶ {mm}:{ss}</a>'
            )
            i = first.end()
        else:
            # _INLINE_LINK_RE：图片 or 普通链接
            if first.group(1) is not None:
                alt, url = first.group(1), first.group(2)
                out.append(f'<img src="{_esc(url)}" alt="{_esc(alt)}" loading="lazy">')
            else:
                txt, url = first.group(3), first.group(4)
                target = ' target="_blank"' if (
                    url.startswith(("http://", "https://")) or url.startswith("play.html")
                ) else ''
                out.append(f'<a href="{_esc(url)}"{target}>{_fmt(txt)}</a>')
            i = first.end()
    return "".join(out)


def render_md(md_text: str) -> str:
    """mini markdown → HTML。无第三方依赖；不支持复杂 GFM 扩展。"""
    lines = md_text.split("\n")
    out = []
    in_code = False
    code_lang = ""
    code_buf = []
    in_table = False
    table_buf = []  # rows of cells

    def flush_table():
        if not table_buf:
            return
        rows = table_buf[:]
        # 检测 separator 行（--- | ---）并跳过
        has_sep = any(_TABLE_SEP_RE.match(r) for r in rows)
        if has_sep:
            rows = [r for r in rows if not _TABLE_SEP_RE.match(r)]
        # 第一行作 header
        header_cells = [c.strip() for c in rows[0].split("|") if c.strip() != ""] if rows else []
        body_rows = rows[1:] if header_cells else rows
        out.append('<table>')
        if header_cells:
            out.append("<thead><tr>" + "".join(f"<th>{render_inline(c)}</th>" for c in header_cells) + "</tr></thead>")
        out.append("<tbody>")
        for r in body_rows:
            cells = [c.strip() for c in r.split("|") if c.strip() != ""]
            if not cells:
                continue
            out.append("<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in cells) + "</tr>")
        out.append("</tbody></table>")
        table_buf.clear()

    def _render_list_block(items, idx, depth):
        """递归渲染列表块。items: [(depth, kind, text)]；返回 (html, next_idx)。"""
        kind = items[idx][1]
        parts = [f"<{kind}>"]
        while idx < len(items) and items[idx][0] == depth:
            _d, _k, txt = items[idx]
            idx += 1
            sub = ""
            if idx < len(items) and items[idx][0] > depth:
                sub, idx = _render_list_block(items, idx, items[idx][0])
                while idx < len(items) and items[idx][0] > depth:
                    more, idx = _render_list_block(items, idx, items[idx][0])
                    sub += more
            parts.append(f"<li>{render_inline(txt)}{sub}</li>")
        parts.append(f"</{kind}>")
        return "".join(parts), idx

    def _collect_list(start_i):
        """从 start_i 起收集连续列表行 → (html, next_i)。支持 2 空格缩进嵌套。"""
        items = []
        i2 = start_i
        while i2 < len(lines):
            ln = lines[i2]
            m_ul2 = _UL_LINE_RE.match(ln)
            m_ol2 = _OL_LINE_RE.match(ln)
            if m_ul2:
                indent = m_ul2.group(1)
                depth = 0 if not indent else max(1, len(indent) // 2)
                items.append((depth, "ul", m_ul2.group(2).strip()))
            elif m_ol2:
                indent = m_ol2.group(1)
                depth = 0 if not indent else max(1, len(indent) // 2)
                items.append((depth, "ol", m_ol2.group(3).strip()))
            else:
                break
            i2 += 1
        if not items:
            return "", start_i
        base = min(d for d, _k, _t in items)
        html, _idx = _render_list_block(items, 0, base)
        return html, i2

    def close_list():
        """列表已按块渲染，无需收尾（保留空函数以兼容旧调用点）。"""
        return

    i = 0
    while i < len(lines):
        line = lines[i]
        # 代码块
        m_fence = _FENCE_RE.match(line)
        if m_fence:
            close_list()
            if in_code:
                out.append(f'<pre><code class="lang-{_esc(code_lang)}">{_esc("".join(code_buf))}</code></pre>')
                code_buf = []
                in_code = False
                code_lang = ""
            else:
                flush_table()
                in_code = True
                code_lang = m_fence.group(1) or ""
            i += 1
            continue
        if in_code:
            code_buf.append(line + "\n")
            i += 1
            continue
        # 分割线
        if _RULE_RE.match(line):
            flush_table()
            close_list()
            out.append("<hr>")
            i += 1
            continue
        # 标题
        m_h = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m_h:
            flush_table()
            close_list()
            lvl = len(m_h.group(1))
            out.append(f"<h{lvl}>{render_inline(m_h.group(2).strip())}</h{lvl}>")
            i += 1
            continue
        # 引用块（合并连续行）
        if line.startswith(">"):
            flush_table()
            close_list()
            blockquote = []
            while i < len(lines) and lines[i].startswith(">"):
                blockquote.append(lines[i].lstrip(">").strip())
                i += 1
            inner = "<br>".join(render_inline(b) for b in blockquote)
            out.append(f"<blockquote>{inner}</blockquote>")
            continue
        # 表格
        if "|" in line:
            close_list()
            table_buf.append(line)
            i += 1
            # peek next line: still in table?
            if i >= len(lines) or "|" not in lines[i]:
                flush_table()
            continue
        else:
            flush_table()
        # 列表（支持嵌套：按块收集后递归渲染）
        if _UL_LINE_RE.match(line) or _OL_LINE_RE.match(line):
            flush_table()
            html, ni = _collect_list(i)
            out.append(html)
            i = ni
            continue
        # 空行
        if not line.strip():
            close_list()
            i += 1
            continue
        # 默认段落：收集连续非空、非特殊行
        close_list()
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not (
            lines[i].startswith("#") or lines[i].startswith(">") or lines[i].startswith(("-", "*"))
            or "|" in lines[i] or _FENCE_RE.match(lines[i]) or _RULE_RE.match(lines[i])
        ):
            para.append(lines[i])
            i += 1
        out.append(f"<p>{render_inline(' '.join(para))}</p>")

    close_list()
    flush_table()
    if in_code and code_buf:
        out.append(f'<pre><code class="lang-{_esc(code_lang)}">{_esc("".join(code_buf))}</code></pre>')
    return "\n".join(out)


# ---- 提取时间轴跳转链接 ----

def extract_play_links(md_text: str, label: str) -> list:
    """返回 [(mm, ss, seconds, ep_label)] 列表，按文件中出现顺序。"""
    out = []
    seen = set()
    for m in _PLAY_LINK_RE.finditer(md_text):
        mm, ss = m.group(1), m.group(2)
        key = (mm, ss)
        if key in seen:
            continue
        seen.add(key)
        out.append((mm, ss, int(mm) * 60 + int(ss), _html.unescape(m.group(3))))
    return out


def extract_play_links_inline(md_text: str) -> int:
    """调试辅助：数文件中 [▶ m:ss](play.html...) 链接数（无论全角半角）。"""
    return len(_PLAY_LINK_RE.findall(md_text))


# ---- HTML 包装 ----

_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
       background: #f7f7f5; color: #1a1a1a; height: 100vh; overflow: hidden; }
header.topbar { display: flex; align-items: center; padding: 10px 20px; background: #1a1a1a; color: #f5f5f5;
                border-bottom: 1px solid #333; }
header.topbar h1 { margin: 0; font-size: 16px; font-weight: 500; }
header.topbar .sub { margin-left: auto; color: #999; font-size: 12px; }
main.three { display: grid; grid-template-columns: var(--w-left, 240px) 4px 1fr 4px var(--w-right, 280px);
             height: calc(100vh - 42px); }
aside.left { background: #fafaf7; border-right: 1px solid #e5e5e5; overflow-y: auto; }
aside.right { background: #fafaf7; border-left: 1px solid #e5e5e5; overflow-y: auto; padding: 12px 16px; }
section.middle { overflow-y: auto; padding: 24px 36px; background: #fff; }
/* 可拖分割条 */
.splitter { background: #e5e5e5; cursor: col-resize; position: relative; transition: background .15s; }
.splitter:hover, .splitter.dragging { background: #4338ca; }
.splitter::before { content: ""; position: absolute; inset: 0 -3px; } /* 加宽命中区 */
nav ul { list-style: none; margin: 0; padding: 0; }
nav .group { padding: 6px 16px 4px; font-size: 11px; text-transform: uppercase;
             color: #888; letter-spacing: 0.5px; font-weight: 600; margin-top: 8px; }
nav li a { display: block; padding: 6px 16px 6px 24px; color: #333; text-decoration: none;
          font-size: 14px; border-left: 3px solid transparent; }
nav li a:hover { background: #efefef; }
nav li a.active { background: #eef2ff; border-left-color: #4338ca; color: #1e1b4b; font-weight: 500; }
article > h1 { font-size: 24px; margin-top: 0; }
article > h2 { font-size: 19px; border-bottom: 1px solid #e5e5e5; padding-bottom: 6px; margin-top: 28px; }
article > h3 { font-size: 16px; margin-top: 24px; }
article p { line-height: 1.7; font-size: 15px; }
article ul, article ol { padding-left: 24px; line-height: 1.7; }
article li { margin: 4px 0; }
article blockquote { border-left: 3px solid #cbd5e1; padding: 6px 14px; margin: 12px 0;
                     color: #475569; background: #f1f5f9; border-radius: 0 4px 4px 0; }
article table { border-collapse: collapse; margin: 12px 0; font-size: 14px; }
article th, article td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }
article th { background: #f5f5f5; }
article pre { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 4px;
              overflow-x: auto; font-size: 13px; line-height: 1.5; }
article code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 13px;
               font-family: ui-monospace, Consolas, monospace; }
article pre code { background: transparent; color: inherit; padding: 0; }
article img { max-width: 100%; border-radius: 4px; margin: 12px 0; border: 1px solid #e5e5e5; }
article hr { border: none; border-top: 1px dashed #ddd; margin: 28px 0; }
aside.right h3 { font-size: 13px; text-transform: uppercase; color: #666; margin: 14px 0 10px; font-weight: 600; }
aside.right .empty { color: #999; font-size: 13px; padding: 12px 0; }
aside.right video.player { width: 100%; border-radius: 6px; background: #000; display: block;
                            aspect-ratio: 16/9; }
aside.right button.step { display: block; width: 100%; text-align: left; padding: 8px 10px;
                          margin-bottom: 6px; background: #fff; border: 1px solid #e5e5e5;
                          border-radius: 4px; font: inherit; font-size: 13px; cursor: pointer;
                          transition: all .15s; }
aside.right button.step:hover { border-color: #2563eb; background: #f0f6ff; transform: translateY(-1px); }
aside.right button.step.playing { border-color: #2563eb; background: #eef2ff; }
aside.right button.step .time { font-weight: 600; color: #2563eb; font-family: ui-monospace, Consolas, monospace; }
aside.right button.step .topic { color: #555; margin-top: 2px; font-size: 12px; display: block;
                                 line-height: 1.45; }
aside.right button.step .topic.muted { color: #bbb; }
header.course-banner { padding: 12px 36px 0; background: #fff; }
header.course-banner h2 { margin: 0; font-size: 18px; }
header.course-banner .meta { color: #888; font-size: 12px; margin-top: 4px; }
"""


def _index_panel(mf, vfiles) -> str:
    """左导航 HTML。"""
    # 按 series 分组
    by_series = {}
    for fn, ep, _ in vfiles:
        s = ep.get("series", "其他")
        by_series.setdefault(s, []).append((fn, ep))
    parts = ['<nav><ul>']
    parts.append('<li><a href="#_总索引.md" data-target="总索引.md" class="active">📋 总索引</a></li>')
    # 系列分组
    for series in by_series:
        parts.append(f'<li class="group">{_esc(series)}</li>')
        for fn, ep in by_series[series]:
            parts.append(
                f'<li><a href="#{_esc(fn)}" data-target="{_esc(fn)}">'
                f'{_esc(ep.get("topic", fn))}</a></li>'
            )
    parts.append("</ul></nav>")
    return "\n".join(parts)


def _extract_titles(md_text: str) -> dict:
    """从图链 alt 提取时间点 → 标题（取首次出现）。

    形如 ![步骤 1 截图 9m56s · 项目目录里剧本与脚本是两个文件](assets/.../frame_9m56s.png)
    → {596: "项目目录里剧本与脚本是两个文件"}
    alt 中无 `·` 分隔时，整个 alt 作标题；`步骤 N 截图` 前缀被剥掉。
    ⚠️ 时间戳必须是 `XmYYs`（两位秒、后跟 s），不能让 digits 捕获组误捕 `步骤 1` 的编号。
    """
    titles = {}
    for m in re.finditer(r"!\[([^\]]*)\]\(assets/[^)]+\)", md_text):
        alt = m.group(1)
        tm = re.search(r"(\d+)m(\d{2})s", alt)  # 锚定 XmYYs，避免被前缀数字干扰
        if not tm:
            continue
        secs = int(tm.group(1)) * 60 + int(tm.group(2))
        if secs in titles:
            continue
        desc = alt
        if "·" in alt:
            desc = alt.split("·", 1)[1]
        desc = re.sub(r"^步骤\s*\d+\s*截图\s*", "", desc).strip(" ·")
        if desc:
            titles[secs] = desc
    return titles


def _right_panel_for_article(md_text: str, ep_label: str, ep: dict | None = None) -> str:
    """右栏：顶部播放器（有源 mp4 时）+ 时间轴跳转列表（点击=在播放器内播放，不跳页）。"""
    links = extract_play_links(md_text, ep_label)
    titles = _extract_titles(md_text)
    parts = []
    # ---- 播放器 ----
    src = ""
    if ep and ep.get("source_video") and _SRC_ROOT[0]:
        base = os.path.basename(ep["source_video"].replace("\\", "/"))
        cand = os.path.join(_SRC_ROOT[0], ep.get("series", ""), base)
        if os.path.isfile(cand):
            src = "source/%s/%s" % (ep.get("series", ""), urllib.parse.quote(base))
    if src:
        parts.append(
            f'<video class="player" controls preload="metadata" src="{_esc(src)}"></video>'
        )
    else:
        parts.append('<div class="empty">未找到本集源视频</div>')
    # ---- 时间轴列表 ----
    if not links:
        parts.append('<div class="empty">本集没有时间轴链接</div>')
        return "".join(parts)
    parts.append('<h3>⏱ 点击在上方播放</h3>')
    for mm, ss, secs, ep_enc in links:
        title = titles.get(secs, "")
        topic_html = (f'<span class="topic">{_esc(title)}</span>' if title
                      else '<span class="topic muted">—</span>')
        parts.append(
            f'<button type="button" class="step" data-t="{secs}">'
            f'<span class="time">▶ {mm}:{ss}</span>'
            f'{topic_html}'
            f'</button>'
        )
    return "".join(parts)


# ---- JS：导航联动 + 右栏随之变化 ----

_JS = """
const LEFT_LINKS = document.querySelectorAll('aside.left a[data-target]');
const ARTICLES = document.querySelectorAll('article.pane');
const RIGHT_CONTENT = document.querySelector('aside.right .content');
const ALL_RIGHT_PANES = {};
const PLAYER_KEY = 'vn_left', PLAYERR_KEY = 'vn_right';
const main = document.querySelector('main.three');

document.querySelectorAll('article.pane').forEach(a => {
  ALL_RIGHT_PANES[a.id] = a.querySelector('.right-pane-content')?.innerHTML || '';
});

// ---- 笔记切换 ----
LEFT_LINKS.forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const t = a.dataset.target;
    LEFT_LINKS.forEach(x => x.classList.toggle('active', x === a));
    ARTICLES.forEach(art => { art.style.display = (art.id === 'file_' + t) ? '' : 'none'; });
    RIGHT_CONTENT.innerHTML = ALL_RIGHT_PANES['file_' + t] || '<div class="empty">本集没有时间轴链接</div>';
    bindRightPane();
    document.querySelector('section.middle').scrollTop = 0;
  });
});

// ---- 右栏：时间轴点击 → 播放器 seek + 播放（不跳页）----
function bindRightPane() {
  const v = RIGHT_CONTENT.querySelector('video.player');
  if (!v) return;
  RIGHT_CONTENT.querySelectorAll('button.step').forEach(btn => {
    btn.addEventListener('click', () => {
      const t = parseFloat(btn.dataset.t);
      if (v.readyState >= 1) {          // 元数据已加载
        v.currentTime = t;
        v.play();
      } else {                          // 首次点击，等 loadedmetadata 再 seek
        v.addEventListener('loadedmetadata', () => { v.currentTime = t; v.play(); }, { once: true });
      }
      RIGHT_CONTENT.querySelectorAll('button.step').forEach(x => x.classList.remove('playing'));
      btn.classList.add('playing');
    });
  });
}

// ---- 分割条拖动（三栏宽度可调 + localStorage 持久化）----
function setW(side, px) {
  if (side === 'l') main.style.setProperty('--w-left', px + 'px');
  else main.style.setProperty('--w-right', px + 'px');
}
function loadW() {
  const l = localStorage.getItem(PLAYER_KEY), r = localStorage.getItem(PLAYERR_KEY);
  if (l) setW('l', l);
  if (r) setW('r', r);
}
document.querySelectorAll('.splitter').forEach(sp => {
  sp.addEventListener('mousedown', e => {
    e.preventDefault();
    sp.classList.add('dragging');
    const side = sp.dataset.side;
    const mainR = main.getBoundingClientRect();
    const move = ev => {
      let px;
      if (side === 'l') { px = ev.clientX - mainR.left; px = Math.max(150, Math.min(px, 460)); }
      else              { px = mainR.right - ev.clientX; px = Math.max(200, Math.min(px, 560)); }
      setW(side, px);
    };
    const up = () => {
      sp.classList.remove('dragging');
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      const cur = side === 'l'
        ? getComputedStyle(main).getPropertyValue('--w-left')
        : getComputedStyle(main).getPropertyValue('--w-right');
      localStorage.setItem(side === 'l' ? PLAYER_KEY : PLAYERR_KEY, parseInt(cur) || '');
    };
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  });
  // 双击重置默认
  sp.addEventListener('dblclick', () => {
    const side = sp.dataset.side;
    if (side === 'l') { setW('l', 240); localStorage.removeItem(PLAYER_KEY); }
    else              { setW('r', 280); localStorage.removeItem(PLAYERR_KEY); }
  });
});
loadW();
bindRightPane();
"""


def build_notes_view(mf, notes_root=None):
    """主入口：构建 + 写 notes.html（单页 SPA）。"""
    notes_root = notes_root or M.notes_root(mf)
    notes_root_p = Path(notes_root)
    # 播放器源路径上下文（_right_panel_for_article 读）
    _mf[0] = mf
    _SRC_ROOT[0] = str(notes_root_p / "source")

    # 收集 notes
    vfiles = []
    for ep in mf["episodes"]:
        fn = f"{ep['seq']}_{ep['label']}_{ep['topic']}.md"
        p = notes_root_p / fn
        if not p.is_file():
            continue
        vfiles.append((fn, ep, 0))

    # 渲染左/中：所有 article 内联渲染，每个 article 同时内嵌其右栏 HTML（hidden div 存）
    left_html = _index_panel(mf, vfiles)
    parts = []
    idx_path = notes_root_p / "总索引.md"
    if idx_path.is_file():
        idx_md = idx_path.read_text(encoding="utf-8")
        # 总索引通常没有 play.html 时间轴链接，extract 后一般是空
        parts.append(
            f'<article id="file_总索引.md" class="pane">'
            f'<header class="course-banner">'
            f'<h2>📋 {_esc(mf["course"]["name"])} · 总索引</h2>'
            f'<div class="meta">本页 + {len(vfiles)} 篇精校笔记 + play.html 单页播放器</div></header>'
            f'{render_md(idx_md)}'
            f'<div class="right-pane-content" style="display:none">'
            f'{_right_panel_for_article(idx_md, "")}</div>'
            f'</article>'
        )
    for fn, ep, _ in vfiles:
        p = notes_root_p / fn
        if not p.is_file():
            continue
        md = p.read_text(encoding="utf-8")
        right_inner = _right_panel_for_article(md, ep.get("label", ""), ep)
        parts.append(
            f'<article id="file_{_esc(fn)}" class="pane" style="display:none">'
            f'<header class="course-banner">'
            f'<h2>第{_esc(ep.get("seq", "?"))}集 · {_esc(ep.get("topic", fn))}</h2>'
            f'<div class="meta">{_esc(ep.get("series", ""))} · {_esc(ep.get("level", ""))}</div></header>'
            f'{render_md(md)}'
            f'<div class="right-pane-content" style="display:none">{right_inner}</div>'
            f'</article>'
        )
    middle_html = "\n".join(parts)

    # 右栏：默认显示总索引的右栏内容；之后 JS 切换
    default_right = (
        '<div class="content">'
        + '<div class="empty">选中左侧的笔记查看时间轴跳转列表</div>'
        '</div>'
    )

    title = f"{mf['course']['name']} · 笔记浏览器"
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<header class="topbar">
  <h1>📚 {_esc(title)}</h1>
  <div class="sub">{len(vfiles)} 篇 · 双击 file:// 即可在浏览器中查看</div>
</header>
<main class="three">
  <aside class="left">{left_html}</aside>
  <div class="splitter" data-side="l" title="拖动调整左栏宽度 · 双击复位"></div>
  <section class="middle">{middle_html}</section>
  <div class="splitter" data-side="r" title="拖动调整右栏宽度 · 双击复位"></div>
  <aside class="right">{default_right}</aside>
</main>
<script>{_JS}</script>
</body>
</html>
"""
    out = notes_root_p / "notes.html"
    out.write_text(html, encoding="utf-8")
    print(f"notes.html -> {out}")
    return out


def main():
    """CLI 入口：python -m toolkit.notes_view <manifest_path>"""
    import sys, argparse
    ap = argparse.ArgumentParser(prog="toolkit.notes_view",
        description="把 steps_pro/ 的笔记 + 总索引渲染为单页 HTML 浏览器")
    ap.add_argument("manifest", help="manifest.toml 路径")
    a = ap.parse_args()
    mf = M.load(a.manifest)
    build_notes_view(mf)


if __name__ == "__main__":
    main()
