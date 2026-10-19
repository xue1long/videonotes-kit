# -*- coding: utf-8 -*-
"""curate：Tier1 精校层 —— 把 draft 半成品（steps_v2.md）转成「待润色骨架」，并预留 Tier2 本地 LLM 接口。

P4 升级：骨架按"教程化"三段式生成（学习目标/前置/术语 → 阶段分组 → 做对了/易错占位），
        把人工量从"从零写"压到"润色+补判定标准"。

设计要点：
  - 非破坏性：骨架写到 `_curated/<ep>/steps_pro.skeleton.md`，绝不覆盖人工已精校的 `steps_pro.md`
    （除非显式 --overwrite，且仅当目标仍是 skeleton 时）。
  - 骨架已包含：规范标题、阶段分组（按 draft 步数自动分 2–3 段）、每步已对齐截图、
    步骤正文（来自 draft，保留原意）、以及 `<!-- TODO 润色 -->` 注释。
  - Tier2 可选本地 LLM 精校：`llm_refine_step` 通过标准库 urllib 调用 OpenAI 兼容接口，
    由 manifest [llm].enabled 控制（默认 false）。禁用或调用失败时回退原文，纯本地链路不受影响。

用法：
  python -m toolkit.curate <out_dir>            # 解析单集 draft，打印步骤摘要
  python notes.py <课程> curate [--overwrite]   # 为清单全部集生成骨架
"""
import os
import re
import json
from . import manifest as M


def parse_draft(path):
    """解析 draft 引擎产物 steps_v2.md，返回步骤列表 [{title, body, frame}]。

    draft 格式：
      ### 步骤 N：<title>
      <正文>。
      ![...](frames/frame_x.png)
      ---
    """
    if not os.path.isfile(path):
        return []
    txt = open(path, encoding="utf-8").read()
    parts = re.split(r"\n###\s*步骤\s*\d+\s*[:：]", txt)
    steps = []
    for b in parts[1:]:
        m = re.match(r"\s*(.*?)\n", b)
        title = m.group(1).strip() if m else ""
        rest = b[m.end():] if m else b
        rest = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", rest)       # 去截图行
        rest = re.sub(r"^-{3,}\s*$\n?", "", rest, flags=re.M)  # 去 --- 分隔
        rest = rest.strip()
        fm = re.search(r"\]\((frames/(frame_[^)\s]+\.png))\)", b)
        steps.append({
            "title": title,
            "body": rest,
            "frame": fm.group(1) if fm else None,
        })
    return steps


# 延迟导入 urllib 到模块末尾集中


def llm_refine_step(title, body, mf):
    """Tier2 可选本地 LLM 精校（默认关）。返回精校后文本；禁用/失败回退原文。

    标准库 urllib 实现，无需额外依赖；只调用 OpenAI 兼容 /chat/completions 接口。
    """
    import urllib.request as _u
    cfg = mf.get("llm", {})
    if not cfg.get("enabled", False):
        return body
    base_url = cfg.get("base_url")
    if not base_url:
        return body
    model = cfg.get("model", "default")
    prompt = (
        "你是视频教程笔记精校助手。下面是一段 AI 视频教程的自动转写草稿，"
        "含有 ASR 错字、口语冗余、未成句。请在不改变原意与步骤顺序的前提下，"
        "修正明显错字、删去无信息量的口语（如「对吧」「然后」「这个」），"
        "把文字整理成通顺、可直接作为教程笔记的一两句话。"
        "只输出整理后的中文，不要解释、不要加序号。\n\n"
        f"步骤标题：{title}\n原始草稿：{body}"
    )
    try:
        data = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "stream": False,
        }).encode("utf-8")
        req = _u.Request(
            base_url.rstrip("/") + "/v1/chat/completions",
            data=data, headers={"Content-Type": "application/json"})
        key = cfg.get("api_key_env")
        if key:
            req.add_header("Authorization", "Bearer " + os.environ.get(key, ""))
        with _u.urlopen(req, timeout=cfg.get("timeout", 60)) as r:
            resp = json.loads(r.read().decode("utf-8"))
        out = resp["choices"][0]["message"]["content"].strip()
        return out or body
    except Exception as e:
        print("  [llm] refine 失败，回退原文:", e)
        return body


# ---- P4：阶段分组启发式 ----
def _safe_int(s, fallback: int = 1) -> int:
    """安全 int 转换（seq 如 '01'/'30A'/'加餐_31' 等都安全）。"""
    try:
        return int(s)
    except (ValueError, TypeError):
        return fallback


def _auto_groups(n: int) -> list:
    """按总步数自动划分 2–3 阶段。目标：每阶段 2–4 步。
    总步 ≤4：不分（单阶段）。
    总步 5–8：分 2 段（前置 / 主体）。
    总步 9–14：分 3 段（前置 / 主体 / 收束）。
    总步 ≥15：分 3 段且收束 ≥ 3 步。
    """
    if n <= 4:
        return [("阶段 A · 操作要点", list(range(1, n + 1)))]
    if n <= 8:
        cut = max(2, n // 2)
        return [
            ("阶段 A · 准备与前 1/3 步", list(range(1, cut + 1))),
            ("阶段 B · 主体与收束", list(range(cut + 1, n + 1))),
        ]
    if n <= 14:
        cut1 = max(2, n // 3)
        cut2 = max(cut1 + 2, 2 * n // 3)
        return [
            ("阶段 A · 准备阶段", list(range(1, cut1 + 1))),
            ("阶段 B · 主体执行", list(range(cut1 + 1, cut2 + 1))),
            ("阶段 C · 收束与经验", list(range(cut2 + 1, n + 1))),
        ]
    cut1 = n // 3
    cut2 = 2 * n // 3
    return [
        ("阶段 A · 准备阶段", list(range(1, cut1 + 1))),
        ("阶段 B · 主体执行", list(range(cut1 + 1, cut2 + 1))),
        ("阶段 C · 收束与经验", list(range(cut2 + 1, n + 1))),
    ]


def gen_skeleton(mf, ep, overwrite=False):
    """为单集生成精校骨架 steps_pro.skeleton.md（不破坏现有 steps_pro.md）。

    P4 骨架结构：学习目标 / 前置 / 关键术语 → 阶段分组（2–3 段） → 每步（讲解+截图+做对了占位） → 易错总结占位。
    """
    out = os.path.join(mf["course"]["out_root"], ep["ep_dir"])
    draft_path = os.path.join(out, "steps_v2.md")
    if not os.path.isfile(draft_path):
        print("SKIP curate (无 steps_v2.md，请先 notes draft):", ep["ep_dir"])
        return
    cur_dir = os.path.join(M.curated_root(mf), ep["ep_dir"])
    os.makedirs(cur_dir, exist_ok=True)
    gold = os.path.join(cur_dir, "steps_pro.md")
    skel = os.path.join(cur_dir, "steps_pro.skeleton.md")

    if os.path.isfile(gold) and not overwrite:
        print("SKIP curate (已存在 steps_pro.md，避免覆盖人工精校):",
              ep["ep_dir"], "-> 用 --overwrite 才重写骨架")
        return

    steps = parse_draft(draft_path)
    if not steps:
        print("SKIP curate (draft 无步骤):", ep["ep_dir"])
        return

    llm_cfg = mf.get("llm", {})
    series = ep.get("series", "")
    level = ep.get("level", "")
    purpose = ep.get("purpose", "")
    keypoints = ep.get("keypoints") or []

    # ---- 1) 拼装元信息块（供模板填充）----
    # 学习目标：prefill from manifest.purpose + keypoints[:2]; 缺则给 TODO
    if purpose:
        purpose_lines = [
            "<!-- 以下根据 manifest purpose 自动预填，请润色或保留 -->",
            f"- {purpose}",
        ]
        for kp in keypoints[:2]:
            purpose_lines.append(f"- {kp}")
        purpose_block = "\n".join(purpose_lines)
    else:
        purpose_block = "\n".join([
            "<!-- TODO: 学完本集后你能做到（建议 3 条以内） -->",
            "- 会判断：……",
            "- 会做：……",
            "- 带走一个观：……",
        ])

    # 前置你会什么（manifest 暂无字段）→ TODO 占位
    prereq_block = "\n".join([
        "<!-- TODO: 列已会的能力（降低陌生感；不需要列不会的） -->",
        "- ……",
        "> 不需要：……",
    ])

    # 关键术语（manifest 暂无字段，与总索引 glossary 关联项）→ TODO 占位
    glossary_block = "\n".join([
        "<!-- TODO: 本集黑话 → 真实含义（3–6 条；与总索引术语表呼应） -->",
        "- **xxx**：xxx",
    ])

    # ---- 2) 拼装阶段分组 + 每步详解（替换模板中的 $stages）----
    groups = _auto_groups(len(steps))
    stages_lines = []
    for gname, idxs in groups:
        stages_lines.append(f"## {gname}")
        stages_lines.append("")
        stages_lines.append("<!-- TODO: 这一阶段在解决什么核心问题（1 句话，必须是「问题」而非「动作」） -->")
        stages_lines.append("")
        for i in idxs:
            st = steps[i - 1]
            stages_lines.append(f"### 步骤 {i}：{st['title']}")
            stages_lines.append("")
            stages_lines.append("<!-- TODO 润色：修 ASR 错字、精简口语冗余、把标题改得更像「动作+结果」。"
                                "可选：在 manifest [llm] 设 enabled=true 启用本地 LLM 自动润色。 -->")
            body = st["body"]
            if llm_cfg.get("enabled"):
                body = llm_refine_step(st["title"], body, mf)
            stages_lines.append(body)
            stages_lines.append("")
            stages_lines.append("**做对了的表现**：<!-- TODO: 1 句可观察/可量化的判定（不要写「通顺」「干净」这类无标尺词） -->")
            stages_lines.append("")
            stages_lines.append("> 经验 / 易错：<!-- TODO: 半句话，写最有价值的那一条 -->")
            stages_lines.append("")
            if st["frame"]:
                stages_lines.append(f"![步骤 {i} 截图]({st['frame']})")
                stages_lines.append("")
            stages_lines.append("---")
            stages_lines.append("")
    stages_block = "\n".join(stages_lines)

    # ---- 3) 用模板渲染骨架 ----
    from . import templates as T
    banner_text = (
        f"来源：{mf['course']['name']} {series or ''}第 {_safe_int(ep.get('seq',''), 1)} 集"
        f" ｜ 集目录：{ep['ep_dir']}"
        f" ｜ 转写：vidwise 本地 medium + draft 半成品（Tier0 自动生成，待人工润色 / 可选 Tier2 本地 LLM 精校）"
    )
    skel_text = T.render(
        "steps_pro",
        label=ep["label"],
        topic=ep["topic"],
        banner=banner_text,
        purpose_block=purpose_block,
        prereq_block=prereq_block,
        glossary_block=glossary_block,
        stages=stages_block,
    )

    open(skel, "w", encoding="utf-8").write(skel_text)
    print("curate ->", skel, "steps:", len(steps), "groups:", len(groups))


def refine_all(mf, overwrite=False):
    for ep in mf["episodes"]:
        gen_skeleton(mf, ep, overwrite=overwrite)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python -m toolkit.curate <out_dir | steps_v2.md>")
        raise SystemExit(1)
    p = sys.argv[1]
    if os.path.isdir(p):
        p = os.path.join(p, "steps_v2.md")
    steps = parse_draft(p)
    print(f"解析到 {len(steps)} 个步骤：")
    for i, s in enumerate(steps, 1):
        ts = ""
        if s["frame"]:
            m = re.search(r"frame_(\d+)m(\d+)s", s["frame"])
            if m:
                ts = f" @{int(m.group(1))}m{int(m.group(2)):02d}s"
        print(f"  {i}. {s['title']}{ts}")
