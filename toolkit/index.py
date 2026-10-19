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
避免「索引重复贴全文步骤」的体例不一致（09/10 不再特殊）。
"""
import os
import re
from . import manifest as M, branding


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

    L = []
    L.append(f"# {mf['course']['name']} 图文笔记 · 总索引\n")
    L.append("> " + branding.INDEX_BANNER)
    L.append("> 本文件夹为**自包含图文笔记包**：笔记配图已内嵌于 `assets/<集标签>/`，源视频已复制于 `source/<系列>/`，步骤时间轴链接跳转到 `play.html`。整体可移动 / 打包分发，图片与视频都不丢。\n")
    L.append("> 🎬 **快速开始**：双击打开 [play.html](play.html) 即可在浏览器内看视频、跳转到任意步骤时间。\n")

    # ---- 如何使用本教程 ----
    L.append("## 如何使用本教程\n")
    if mf["course"].get("learning_path"):
        L.append(mf["course"]["learning_path"] + "\n")
    if mf["course"].get("series_note"):
        L.append("### 系列说明\n")
        L.append(mf["course"]["series_note"] + "\n")
    if vfiles:
        L.append("### 推荐阅读顺序\n")
        for fn, ep, sc in vfiles:
            lv = _level(ep)
            tag = f"（{lv}）" if lv else ""
            L.append(f"{ep['seq']}. [{ep['topic']}]({fn}){tag}")
        L.append("")

    # ---- 目录（按系列分组） ----
    L.append("## 目录（按系列分组）\n")
    groups = []
    for _, ep, _ in vfiles:
        s = ep.get("series", "其他")
        if s not in groups:
            groups.append(s)
    for g in groups:
        glv = _group_level(vfiles, g)
        head = f"### {g}系列"
        if glv:
            head += f"（{glv}）"
        L.append(head + "\n")
        L.append("| 集 | 主题 | 步数 | 精校笔记 |")
        L.append("|----|------|------|----------|")
        for fn, ep, sc in vfiles:
            if ep.get("series", "其他") != g:
                continue
            L.append(f"| 第{_n(ep['seq'])}集 | {ep['topic']} | {sc} | [{fn[:-3]}]({fn}) |")
        L.append("")

    # ---- 补充参考文档（目录表） ----
    L.append("## 补充参考文档（课程 Prompt / SKILL / 资料库）\n")
    if mf["course"].get("doc_intro"):
        L.append(mf["course"]["doc_intro"] + "\n")
    L.append("| 类别 | 文件 | 说明 |")
    L.append("|------|------|------|")
    for d in dfiles:
        name = _name_no_ext(d["dest"])
        L.append("| %s | [%s](%s/%s) | %s |" % (
            d["category"], name, mf["course"]["refdoc_subdir"], d["dest"], d.get("note", "")))
    L.append("")
    if mf["course"].get("doc_variant_note"):
        L.append("> " + mf["course"]["doc_variant_note"] + "\n")

    # ---- 各集概要（manifest 驱动，统一体例：1 句话定位 + 要点） ----
    L.append("## 各集概要\n")
    for fn, ep, sc in vfiles:
        lv = _level(ep)
        title = f"第{_n(ep['seq'])}集 · {ep['topic']}（{sc} 步）"
        if lv:
            title = title[:-1] + f" · {lv}）"
        L.append(f"### {title}\n")
        pur = ep.get("purpose", "")
        if pur:
            L.append(pur + "\n")
        kps = ep.get("keypoints") or []
        if kps:
            for k in kps:
                L.append(f"- {k}")
            L.append("")
        L.append(f"> 笔记：[{fn[:-3]}]({fn})\n")

    # ---- 术语对照（黑话 → 真实含义）：全文另存 术语总表.md，索引只做入口 ----
    gl = mf["course"].get("glossary") or []
    if gl:
        L.append("## 术语对照（黑话 → 真实含义）\n")
        L.append(f"共 **{len(gl)}** 条，完整表格见 **[术语总表.md](术语总表.md)**；"
                 "每集自己的关键术语见各篇笔记的「关键术语」段。\n")
        top = sorted(gl, key=lambda g: (not g.get("term", "")[:1].isascii(),
                                        g.get("term", "").lower()))
        rows = ["# 术语总表\n", f"> 共 {len(gl)} 条，由 manifest `course.glossary` 生成（源：各集精校笔记「关键术语」段）\n",
                "| 术语 | 含义 |", "|------|------|"]
        for g in top:
            rows.append(f"| {g.get('term', '')} | {g.get('meaning', '')} |")
        rows.append("")
        gp = os.path.join(notes_root, "术语总表.md")
        open(gp, "w", encoding="utf-8").write("\n".join(rows))
        print("glossary ->", gp)

    # ---- 补充参考文档说明（按类别分组） ----
    L.append("## 补充参考文档说明\n")
    cats = []
    for d in dfiles:
        if d["category"] not in cats:
            cats.append(d["category"])
    for cat in cats:
        L.append(f"### {cat}类\n")
        for d in dfiles:
            if d["category"] != cat:
                continue
            name = _name_no_ext(d["dest"])
            detail = d.get("detail", d.get("note", ""))
            L.append(f"- **{d['code']} {name}**：{detail}\n")
        L.append("")

    idx = os.path.join(notes_root, "总索引.md")
    open(idx, "w", encoding="utf-8").write("\n".join(L))
    print("index ->", idx)
