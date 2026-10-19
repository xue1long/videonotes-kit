# -*- coding: utf-8 -*-
"""index：扫描 notes/ 自动生成总索引.md。

全部文案由 manifest 驱动（改 manifest 即改索引，build 可无损复现）：
  - course.learning_path / course.series_note ：「如何使用本教程」段
  - course.glossary                      ：术语对照段（黑话 → 真实含义）
  - episodes[].series / level            ：目录按系列分组 + 难度标注
  - episodes[].purpose / keypoints       ：各集概要（统一体例：1 句话定位 + 要点）
  - course.doc_intro / doc_variant_note  ：文档区引言与同源变体提示
  - docs[].note / docs[].detail          ：文档目录表与文末说明

注意：各集概要**不再**从笔记正文抽取，改由 manifest 的 purpose/keypoints 提供，
避免「索引重复贴全文步骤」的体例不一致。

模板层：本模块只拼装动态块（分组表/各集概要/术语表），模板 templates/index.md
  只放静态骨架（H1/banner/章节标题）。改外观 = 改 templates/index.md；
  改动态行为 = 改本模块。
"""
import os
import re
from . import manifest as M, branding, templates as T


# ---- 文件名/序号 helper ----

def _ext(s: str) -> str:
    i = s.rfind(".")
    return s[i:] if i > 0 else ""


def _name_no_ext(dest: str) -> str:
    return dest[: -len(_ext(dest))] if _ext(dest) else dest


def _n(seq: str) -> str:
    try:
        return str(int(seq))
    except (ValueError, TypeError):
        return seq


def _level(ep: dict) -> str:
    return ep.get("level", "")


def _group_level(vfiles, series: str) -> str:
    levels = {_level(ep) for _, ep, _ in vfiles if ep.get("series", "其他") == series}
    levels.discard("")
    return " / ".join(sorted(levels)) if levels else ""


# ---- 6 个动态块生成器（拼好后整体替换模板中的同名占位符）----

def _block_reading_order(vfiles) -> str:
    lines = []
    for fn, ep, _ in vfiles:
        lv = _level(ep)
        tag = f"（{lv}）" if lv else ""
        lines.append(f"{ep['seq']}. [{ep['topic']}]({fn}){tag}")
    return "\n".join(lines)


def _block_groups(vfiles) -> str:
    """目录按 series 分组：H3 + 4 列表。"""
    # 维持原出现顺序
    groups = []
    for _, ep, _ in vfiles:
        s = ep.get("series", "其他")
        if s not in groups:
            groups.append(s)

    out = []
    for g in groups:
        glv = _group_level(vfiles, g)
        head = f"### {g}系列"
        if glv:
            head += f"（{glv}）"
        out.append(head)
        out.append("")
        out.append("| 集 | 主题 | 步数 | 精校笔记 |")
        out.append("|----|------|------|----------|")
        for fn, ep, sc in vfiles:
            if ep.get("series", "其他") != g:
                continue
            out.append(f"| 第{_n(ep['seq'])}集 | {ep['topic']} | {sc} | [{fn[:-3]}]({fn}) |")
        out.append("")
    return "\n".join(out).rstrip()


def _block_doc_intro(course: dict) -> str:
    return (course.get("doc_intro", "") or "").strip()


def _block_doc_table(mf, dfiles) -> str:
    lines = [
        "| 类别 | 文件 | 说明 |",
        "|------|------|------|",
    ]
    for d in dfiles:
        name = _name_no_ext(d["dest"])
        lines.append("| %s | [%s](%s/%s) | %s |" % (
            d["category"], name, mf["course"]["refdoc_subdir"], d["dest"], d.get("note", "")
        ))
    return "\n".join(lines)


def _block_doc_variant_note(course: dict) -> str:
    return (course.get("doc_variant_note", "") or "").strip()


def _block_ep_summaries(vfiles) -> str:
    out = []
    for fn, ep, sc in vfiles:
        lv = _level(ep)
        title = f"第{_n(ep['seq'])}集 · {ep['topic']}（{sc} 步）"
        if lv:
            title = title[:-1] + f" · {lv}）"
        out.append(f"### {title}")
        out.append("")
        pur = ep.get("purpose", "")
        if pur:
            out.append(pur)
            out.append("")
        kps = ep.get("keypoints") or []
        for k in kps:
            out.append(f"- {k}")
        if kps:
            out.append("")
        out.append(f"> 笔记：[{fn[:-3]}]({fn})")
        out.append("")
    return "\n".join(out).rstrip()


GLOSSARY_INLINE_MAX = 80   # 术语 ≤ 80 条直接内联；超过则另存 术语总表.md，索引只留入口


def _block_glossary(course: dict) -> str:
    gl = course.get("glossary") or []
    if not gl:
        return ""
    if len(gl) > GLOSSARY_INLINE_MAX:
        return (f"共 **{len(gl)}** 条，完整表格见 **[术语总表.md](术语总表.md)**；"
                "每集自己的关键术语见各篇笔记的「关键术语」段。")
    lines = [
        "| 黑话 | 含义 |",
        "|------|------|",
    ]
    for g in gl:
        lines.append(f"| {g.get('term', '')} | {g.get('meaning', '')} |")
    return "\n".join(lines)


def write_glossary_table(course: dict, notes_root: str):
    """术语超过内联阈值时，把全表另存 术语总表.md（中文优先排序），索引只留入口。

    返回写出的路径；未超阈值或没有术语则返回 None。
    """
    gl = course.get("glossary") or []
    if len(gl) <= GLOSSARY_INLINE_MAX:
        return None
    top = sorted(gl, key=lambda g: (not (g.get("term") or "")[:1].isascii(),
                                    (g.get("term") or "").lower()))
    rows = [
        "# 术语总表",
        "",
        f"> 共 {len(gl)} 条，由 manifest `course.glossary` 生成（源：各集精校笔记「关键术语」段）",
        "",
        "| 术语 | 含义 |",
        "|------|------|",
    ]
    for g in top:
        rows.append(f"| {g.get('term', '')} | {g.get('meaning', '')} |")
    rows.append("")
    p = os.path.join(notes_root, "术语总表.md")
    open(p, "w", encoding="utf-8").write("\n".join(rows))
    return p


def _block_doc_details(mf, dfiles) -> str:
    out = []
    cats = []
    for d in dfiles:
        if d["category"] not in cats:
            cats.append(d["category"])
    for cat in cats:
        out.append(f"### {cat}类")
        out.append("")
        for d in dfiles:
            if d["category"] != cat:
                continue
            name = _name_no_ext(d["dest"])
            detail = d.get("detail", d.get("note", ""))
            out.append(f"- **{d['code']} {name}**：{detail}")
        out.append("")
    return "\n".join(out).rstrip()


# ---- 主入口 ----

def build_index(mf, notes_root=None):
    notes_root = notes_root or M.notes_root(mf)
    ref = os.path.join(notes_root, mf["course"]["refdoc_subdir"])

    vfiles = []
    for ep in mf["episodes"]:
        fn = f"{ep['seq']}_{ep['label']}_{ep['topic']}.md"
        p = os.path.join(notes_root, fn)
        if not os.path.isfile(p):
            continue
        txt = open(p, encoding="utf-8").read()
        sc = len(re.findall(r"^###\s*步骤", txt, re.M))
        vfiles.append((fn, ep, sc))

    dfiles = [d for d in mf["docs"] if os.path.isfile(os.path.join(ref, d["dest"]))]

    # 模板渲染
    out = T.render(
        "index",
        course_name=mf["course"]["name"],
        banner=branding.INDEX_BANNER,
        learning_path=(mf["course"].get("learning_path", "") or "").rstrip(),
        series_note=(mf["course"].get("series_note", "") or "").rstrip(),
        reading_order=_block_reading_order(vfiles),
        groups=_block_groups(vfiles),
        doc_intro=_block_doc_intro(mf["course"]),
        doc_table=_block_doc_table(mf, dfiles),
        doc_variant_note=_block_doc_variant_note(mf["course"]),
        ep_summaries=_block_ep_summaries(vfiles),
        glossary=_block_glossary(mf["course"]),
        doc_details=_block_doc_details(mf, dfiles),
    )

    idx = os.path.join(notes_root, "总索引.md")
    open(idx, "w", encoding="utf-8").write(out)
    print("index ->", idx)
    gt = write_glossary_table(mf["course"], notes_root)
    if gt:
        print("glossary ->", gt)
