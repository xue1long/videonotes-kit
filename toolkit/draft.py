# -*- coding: utf-8 -*-
"""draft 引擎：vidwise 本地素材 → 人能读的「教程步骤笔记」草稿（无 API key / 无 vision）。

算法源自 vidwise 早期脚本 v2tutorial.py（2026-10 已废弃清理），在 P1 整改时重写为 manifest 驱动、零硬编码的包内模块：
  - 截图对齐用 frames/ 全量帧（每 2s 一张，通常 300+ 张），根治静止段共用一张截图的错位。
  - 相邻同主题步骤按语义相似度（Jaccard>=0.35 或间隔<=15s）聚合，把碎片步压成真步骤。
  - 简繁统一 + 标题清洗。
仍受「无 LLM」限制：标题启发式、口语冗余保留、错字需人工/LLM 精校。成品级精校见 curate 层。

用法：
  python -m toolkit.draft <out_dir> [--max-steps 80] [--out steps_v2.md]
"""
import os
import re
import json
import argparse
from datetime import datetime


def load_transcript(out_dir):
    p = os.path.join(out_dir, "transcript.json")
    d = json.load(open(p, encoding="utf-8"))
    segs = d.get("segments") or d.get("chunks") or []
    return [s for s in segs if (s.get("text") or "").strip()]


def scan_frames(out_dir):
    fd = os.path.join(out_dir, "frames")
    pat = re.compile(r"frame_(\d+)m(\d+)s\.png$")
    out = []
    if not os.path.isdir(fd):
        return out
    for fn in os.listdir(fd):
        m = pat.search(fn)
        if m:
            sec = int(m.group(1)) * 60 + int(m.group(2))
            out.append({"seconds": sec, "path": f"frames/{fn}"})
    out.sort(key=lambda x: x["seconds"])
    return out


def nearest_frame(frames, t, max_gap=120.0):
    if not frames:
        return None
    best = min(frames, key=lambda f: abs(f["seconds"] - t))
    return best if abs(best["seconds"] - t) <= max_gap else None


TRAD2SIMP = {
    "這": "这", "裡": "里", "們": "们", "個": "个", "來": "来", "點": "点", "樣": "样",
    "畫": "画", "會": "会", "後": "后", "時": "时", "麼": "么", "應": "应", "與": "与",
    "並": "并", "傷": "伤", "廢": "废", "據": "据", "別": "别", "處": "处", "產": "产",
    "單": "单", "對": "对", "類": "类", "動": "动", "劇": "剧", "強": "强", "變": "变",
    "擇": "择", "戰": "战", "轉": "转", "場": "场", "結": "结", "錄": "录", "換": "换",
    "庫": "库", "熱": "热", "門": "门", "劍": "剑", "擊": "击", "尋": "寻", "護": "护",
    "統": "统", "說": "说", "話": "话", "語": "语", "細": "细", "給": "给", "鐵": "铁",
    "體": "体", "當": "当", "漸": "渐", "兩": "两", "飛": "飞", "斷": "断", "專": "专",
    "還": "还", "進": "进", "親": "亲", "關": "关", "覺": "觉", "願": "愿", "備": "备",
    "張": "张", "網": "网", "覽": "览", "見": "见", "開": "开", "間": "间", "閃": "闪",
    "顏": "颜", "顧": "顾", "頓": "顿", "題": "题", "風": "风", "雲": "云", "電": "电",
    "頭": "头", "實": "实", "學": "学", "環": "环", "聲": "声", "靜": "静", "馬": "马",
    "鳥": "鸟", "魚": "鱼", "齊": "齐", "龍": "龙", "擴": "扩", "圖": "图", "書": "书",
    "長": "长", "東": "东", "車": "车", "員": "员", "夢": "梦", "歲": "岁", "異": "异",
    "國": "国", "團": "团", "圓": "圆", "園": "园", "醫": "医", "藥": "药", "裝": "装",
    "補": "补", "視": "视", "観": "观", "認": "认", "試": "试", "請": "请", "謝": "谢",
    "證": "证", "誤": "误", "讀": "读", "負": "负", "責": "责", "質": "质", "資": "资",
    "費": "费", "購": "购", "輸": "输", "運": "运", "過": "过", "達": "达", "遠": "远",
    "邊": "边", "務": "务", "歷": "历", "歡": "欢", "氣": "气", "濕": "湿", "溫": "温",
    "階": "阶", "腦": "脑", "際": "际", "組": "组", "狀": "状", "項": "项", "維": "维",
    "終": "终", "習": "习", "創": "创", "導": "导", "驚": "惊", "雜": "杂", "稱": "称",
}
_TRAD_RE = None


def to_simp(s: str) -> str:
    global _TRAD_RE
    if _TRAD_RE is None:
        _TRAD_RE = re.compile("[" + "".join(TRAD2SIMP.keys()) + "]")
    return _TRAD_RE.sub(lambda m: TRAD2SIMP[m.group(0)], s)


ACTION_RE = re.compile(
    r"(点[击]?|单击|双击|按下|选择|选中|勾选|取消勾选|打开|新建|创建|添加|插入|导入|导出|"
    r"拖[动]?|拖到|移动|调整|右键|长按|分离|合并|生成|应用|确认|保存|删除|复制|粘贴|剪切|"
    r"搜索|查找|找|输入|填写|设置|进入|返回|切换|展开|收起|配|改|选|点开|裁剪|对齐|缩放|"
    r"抽[卡]?|审[查]?|拼[接]?|剥离|配音|加[入]?|删[除]?)"
)
CLAUSE_SPLIT = re.compile(r"[,\.，。！？；、\n]+")

FILLER_RE = re.compile(
    r"^(大家[好]?|我们|你|我|咱们|这里|这|就|现在|然后|好|那|这个|那个|其实|如果|比如说|比如|"
    r"这样|直接|可以|需要|的话|啊|吧|呢|嘛|呀|哦|嗯|诶|哎|对|是|把|给|去|再|先|后|也|都|还|它|"
    r"咱们|你看|看到了吗|明白了吗|懂吧|对吧|是不是|其实是|正常来说|一般来说)"
)


def clean_title(clause, limit=20):
    s = to_simp(clause).strip()
    for _ in range(5):
        m = FILLER_RE.match(s)
        if not m:
            break
        s = s[m.end():].strip()
    s = re.sub(r"(对吧|吧|呢|嘛|呀|哦|啊|懂吧|明白了吗|看到了吗|是不是|对不对)$", "", s)
    return s[:limit].strip() or s[:limit]


def fmt_ts(sec):
    m = int(sec) // 60
    s = int(sec) % 60
    return f"{m}m{s:02d}s"


def _norm(s):
    return re.sub(r"\W", "", s or "")


def _jac(a, b):
    A = set(_norm(a)[i:i + 2] for i in range(len(_norm(a)) - 1))
    B = set(_norm(b)[i:i + 2] for i in range(len(_norm(b)) - 1))
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def derive_steps(segs, max_steps=80):
    """从 transcript segments 推导最终步骤（纯函数，无 IO）。

    复用 build() 内部的「动作句 → 分组 → 去重 → 截断」算法。
    公开给 toolkit/frames.py 在按需抽帧时复用，保证「抽帧的时间点」与
    「笔记引用的时间点」同源（见 docs/P9-on-demand-frames.md D10）。

    返回 [dict(t=int_seconds, title=str, body=str, end=int_seconds), ...]
    """
    raw = []
    cur = None
    for seg in segs:
        text = to_simp((seg.get("text") or "").strip())
        if not text:
            continue
        t0 = float(seg["start"])
        clauses = [c.strip() for c in CLAUSE_SPLIT.split(text) if c.strip()]
        for clause in clauses:
            if ACTION_RE.search(clause):
                cur = {"t": t0, "title": clean_title(clause), "body": clause}
                raw.append(cur)
            elif cur is not None:
                cur["body"] += "，" + clause

    groups = []
    for st in raw:
        if groups:
            g = groups[-1]
            gap_t = st["t"] - g["end"]
            sim = _jac(st["body"], g["last_body"])
            if sim >= 0.35 or gap_t <= 15:
                g["end"] = st["t"]
                g["body"] += "；" + st["body"]
                g["last_body"] = st["body"]
                if len(st["title"]) > len(g["title"]) and _jac(st["title"], g["title"]) < 0.6:
                    g["title"] = st["title"]
                continue
        groups.append({"t": st["t"], "end": st["t"], "title": st["title"],
                       "body": st["body"], "last_body": st["body"]})

    out = []
    kept = []
    for g in groups:
        if any(_jac(g["body"], k) > 0.55 for k in kept):
            continue
        out.append({"t": g["t"], "end": g["end"], "title": g["title"], "body": g["body"]})
        kept.append(g["body"])
        if len(out) >= max_steps:
            break
    return out


def build(out_dir, max_steps=80, out_name="steps_v2.md"):
    segs = load_transcript(out_dir)
    frames = scan_frames(out_dir)
    out_steps = derive_steps(segs, max_steps)
    for g in out_steps:
        g["frame"] = nearest_frame(frames, g["t"])

    title = os.path.basename(out_dir)
    L = []
    L.append(f"# 教程步骤笔记 · {title}")
    L.append("")
    L.append(f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M}  ")
    L.append(f"> 管线：vidwise 本地素材 + draft（无 API key） ｜ 全量帧对齐 + 步骤聚合 + 简繁统一")
    L.append(f"> 聚合步骤数：{len(out_steps)}")
    L.append("")
    L.append("## 操作步骤")
    L.append("")
    for i, st in enumerate(out_steps, 1):
        L.append(f"### 步骤 {i}：{st['title']}")
        L.append("")
        L.append(st["body"] + "。")
        L.append("")
        if st["frame"]:
            L.append(f"![步骤 {i} 截图 {fmt_ts(st['frame']['seconds'])}]({st['frame']['path']})")
            L.append("")
        L.append("---")
        L.append("")
    out_md = os.path.join(out_dir, out_name)
    open(out_md, "w", encoding="utf-8").write("\n".join(L))
    print(f"[OK] {out_md}  聚合步数={len(out_steps)}")
    return len(out_steps)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--out", default="steps_v2.md")
    ap.add_argument("--max-steps", type=int, default=80)
    a = ap.parse_args()
    build(a.out_dir, a.max_steps, a.out)
