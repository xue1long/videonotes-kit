# -*- coding: utf-8 -*-
"""scripts/sync_episode_meta.py — 用精校笔记回填 manifest 的 purpose / keypoints

索引的「各集概要」由 manifest 驱动；新精校的集如果还留着占位文案，索引就会
和笔记内容对不上。本脚本从 `_curated/<集>/steps_pro.md` 里读：
  - H1 标题冒号后的主题 → purpose
  - 「学习目标」前 3 条 → keypoints

用法:
  python scripts/sync_episode_meta.py <课程> 13 14 15 ...   # 指定 seq
  python scripts/sync_episode_meta.py <课程> --all-missing   # 只补 purpose 为占位的
"""
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path("D:/000/vidwise")


def parse_note(md: Path):
    text = md.read_text(encoding="utf-8")
    lines = text.splitlines()
    h1 = next((l for l in lines if l.startswith("# ")), "")
    purpose = h1.split("：", 1)[1].strip() if "：" in h1 else h1.lstrip("# ").strip()
    # 学习目标段
    kps, inside = [], False
    for ln in lines:
        s = ln.strip()
        if re.match(r"^##\s*学习目标", s):
            inside = True
            continue
        if inside and re.match(r"^##\s", s):
            break
        if inside and s.startswith("- "):
            item = re.sub(r"\*\*(.+?)\*\*", r"\1", s[2:]).strip()
            item = item.replace("：", "：", 1)
            if item:
                kps.append(item)
    return purpose, kps[:3]


def main():
    course = sys.argv[1]
    args = sys.argv[2:]
    manifest = ROOT / "projects" / course / "manifest.toml"
    mf = tomllib.load(open(manifest, "rb"))
    cur = Path(mf["course"]["out_root"]) / mf["course"]["curated_subdir"]

    targets = []
    for ep in mf["episodes"]:
        if "--all-missing" in args:
            if ep["seq"] in ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"):
                continue
            targets.append(ep["seq"])
        elif ep["seq"] in args:
            targets.append(ep["seq"])

    text = manifest.read_text(encoding="utf-8")
    blocks = list(re.finditer(r"^\[\[episodes\]\]$", text, re.M))
    changed = 0
    # 从后往前替换，避免 offset 漂移
    for i in range(len(blocks) - 1, -1, -1):
        start = blocks[i].start()
        end = blocks[i + 1].start() if i + 1 < len(blocks) else text.find("# ---- 参考文档", start)
        if end == -1:
            end = len(text)
        block = text[start:end]
        mseq = re.search(r'^seq = "([^"]+)"', block, re.M)
        if not mseq or mseq.group(1) not in targets:
            continue
        seq = mseq.group(1)
        mep = next((e for e in mf["episodes"] if e["seq"] == seq), None)
        md = cur / mep["ep_dir"] / "steps_pro.md"
        if not md.is_file():
            print(f"  SKIP {seq}: 无精校笔记")
            continue
        purpose, kps = parse_note(md)
        new_block = re.sub(r'^purpose = ".*"$',
                           "purpose = " + json.dumps(purpose, ensure_ascii=False),
                           block, count=1, flags=re.M)
        kp_toml = "keypoints = [\n" + "".join(
            "  " + json.dumps(k, ensure_ascii=False) + ",\n" for k in kps) + "]"
        new_block = re.sub(r"^keypoints = \[.*?\]", kp_toml, new_block, count=1, flags=re.M | re.S)
        if new_block != block:
            text = text[:start] + new_block + text[end:]
            changed += 1
            print(f"  OK {seq}: {purpose[:40]} | {len(kps)} 要点")
    manifest.write_text(text, encoding="utf-8")
    print(f"更新 {changed} 集")


if __name__ == "__main__":
    main()
