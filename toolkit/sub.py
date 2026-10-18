# -*- coding: utf-8 -*-
"""字幕直通：SRT 文本（B 站 AI 字幕 .md / 标准 .srt）→ whisper 格式 transcript.json。

为什么存在：
  toolkit/draft.load_transcript() 只认 <out_dir>/transcript.json 的
  {"segments": [{"start": float 秒, "text": str}, ...]} 结构（见 draft.py:20-24），
  而 bilibili-subtitle-fetch 产出的是 SRT 文本（可带 YAML frontmatter，存 .md 后缀）。
  本模块做格式桥接，让 B 站官方 AI 字幕直接替代 Whisper 转写，省掉数小时本地转写批。

设计约束：
  - 纯标准库（项目零第三方依赖约定）
  - **确定性**：同一字幕文件 → 逐字节相同的 JSON，便于 verify 做「字幕新鲜度」非破坏校验
  - 不碰 draft 引擎与帧对齐逻辑：frames/ 仍来自 vidwise --no-transcribe 抽帧

用法：
  python -m toolkit.sub <字幕文件.md|.srt> <out_dir> [--out transcript.json]
"""
import argparse
import json
import os
import re

# HH:MM:SS,mmm --> HH:MM:SS,mmm（毫秒分隔符 , 或 . 均可；毫秒 1–3 位）
_TS_RE = re.compile(
    r"(?P<h1>\d{1,2}):(?P<m1>\d{2}):(?P<s1>\d{2})[,.](?P<ms1>\d{1,3})"
    r"\s*-->\s*"
    r"(?P<h2>\d{1,2}):(?P<m2>\d{2}):(?P<s2>\d{2})[,.](?P<ms2>\d{1,3})"
)

# YAML frontmatter：首行 --- 到下一个 --- 行（可能多块堆叠，循环剥离，幂等）
_FM_RE = re.compile(r"\A[ \t]*---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.S)


def strip_frontmatter(text: str) -> str:
    """剥离文件顶端的 YAML frontmatter（支持多块堆叠；无 frontmatter 原样返回）。"""
    while True:
        m = _FM_RE.match(text)
        if not m:
            return text
        text = text[m.end():]


def _to_sec(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def _join_lines(parts: list) -> str:
    """多行 cue 拼接：英文数字词边界补空格，中文直接相连。"""
    out = parts[0]
    for p in parts[1:]:
        if re.search(r"[A-Za-z0-9]$", out) and re.match(r"[A-Za-z0-9]", p):
            out += " " + p
        else:
            out += p
    return out


def parse_srt(text: str) -> list:
    """解析 SRT 文本 → [{"start": float, "end": float, "text": str}, ...]。

    容错：CRLF、无序号行、毫秒 1 位、多行 cue、块间空行数量不一。
    未识别到任何时间轴 → 返回空列表（由调用方报错）。
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    segs = []
    i = 0
    while i < len(lines):
        m = _TS_RE.search(lines[i])
        if not m:
            i += 1
            continue
        start = _to_sec(m.group("h1"), m.group("m1"), m.group("s1"), m.group("ms1"))
        end = _to_sec(m.group("h2"), m.group("m2"), m.group("s2"), m.group("ms2"))
        i += 1
        buf = []
        while i < len(lines) and lines[i].strip() and not _TS_RE.search(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if not buf:
            continue
        txt = _join_lines(buf)
        if txt:
            segs.append({"start": start, "end": end, "text": txt})
    return segs


def load_segments(src: str) -> list:
    """读字幕文件（utf-8-sig 容 BOM）→ 剥 frontmatter → 解析 SRT。"""
    with open(src, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    return parse_srt(strip_frontmatter(raw))


def render(src: str) -> str:
    """字幕文件 → whisper 格式 transcript.json 文本（确定性，逐字节可复现）。"""
    segs = load_segments(src)
    if not segs:
        raise ValueError(
            f"未从字幕解析出任何条目: {src}\n"
            "  需要 SRT 时间轴（00:00:01,000 --> 00:00:03,000）；可带 YAML frontmatter。"
        )
    doc = {
        "text": "".join(s["text"] for s in segs),
        "language": "zh",
        "segments": [
            {
                "id": i,
                "start": round(s["start"], 3),
                "end": round(s["end"], 3),
                "text": s["text"],
            }
            for i, s in enumerate(segs)
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def convert(src: str, out_dir: str, out_name: str = "transcript.json") -> int:
    """字幕文件 → 写 <out_dir>/<out_name>。返回条目数。"""
    text = render(src)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, out_name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    n = len(json.loads(text)["segments"])
    print(f"  [字幕] {os.path.basename(src)} → {path}（{n} 条）")
    return n


def main():
    ap = argparse.ArgumentParser(prog="toolkit.sub", description="SRT 字幕 → transcript.json")
    ap.add_argument("src", help="字幕文件路径（.md / .srt，可含 YAML frontmatter）")
    ap.add_argument("out_dir", help="vidwise 产物目录（与 frames/ 同级）")
    ap.add_argument("--out", default="transcript.json", help="输出文件名（默认 transcript.json）")
    a = ap.parse_args()
    convert(a.src, a.out_dir, a.out)


if __name__ == "__main__":
    main()