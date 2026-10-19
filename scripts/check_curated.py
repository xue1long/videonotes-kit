# -*- coding: utf-8 -*-
"""scripts/check_curated.py — 精校笔记结构 + 图链体检（只读）

用法:
  python scripts/check_curated.py <课程>            # 全量
  python scripts/check_curated.py <课程> 13 14 15   # 只看指定 seq

检查项:
  1. 结构齐全（学习目标 / 前置 / 关键术语 / 阶段 / 易错总结）
  2. 步骤数 8-15、阶段数 3-4
  3. 每步是否有截图、图链在 frames/ 是否存在
  4. 图链去重（不得多步共用同一张）
  5. 关键术语行是否符合 glossary 提取格式 `- **术语**：释义`
  6. 体积 6-18KB
"""
import os
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path("D:/000/vidwise")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    course = sys.argv[1]
    only = set(sys.argv[2:])
    mf = tomllib.load(open(ROOT / "projects" / course / "manifest.toml", "rb"))
    out_root = Path(mf["course"]["out_root"])
    cur = out_root / mf["course"]["curated_subdir"]

    eps = sorted(mf["episodes"], key=lambda x: (x["seq"].rstrip("ABCDEFG"), x["seq"]))
    print(f"{'seq':<4}{'集':<9}{'步':<4}{'阶段':<5}{'图':<4}{'缺图':<5}{'重图':<5}{'术语':<5}{'KB':<5}状态")
    bad = []
    for e in eps:
        if only and e["seq"] not in only:
            continue
        p = cur / e["ep_dir"] / "steps_pro.md"
        if not p.is_file():
            print(f"{e['seq']:<4}{e['label']:<9}—   未精校")
            continue
        t = p.read_text(encoding="utf-8")
        steps = len(re.findall(r"^### ", t, re.M))
        phases = len(re.findall(r"^## 阶段", t, re.M))
        imgs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", t)
        names = [i.split()[0] for i in imgs]
        miss = 0
        for rel in names:
            cand = out_root / e["ep_dir"] / rel
            if not (cand.is_file() or cand.with_suffix(".jpg").is_file()):
                miss += 1
        dup = len(names) - len(set(names))
        terms = len(re.findall(r"^\s*-\s*\*\*[^*]+\*\*[：:]\s*\S", t, re.M))
        has = all(k in t for k in ("学习目标", "前置", "关键术语", "易错总结"))
        kb = p.stat().st_size / 1024
        prob = []
        if not has:
            prob.append("结构缺项")
        if not (8 <= steps <= 15):
            prob.append(f"步数{steps}越界")
        if not (3 <= phases <= 4):
            prob.append(f"阶段{phases}")
        if miss:
            prob.append(f"缺图{miss}")
        if dup:
            prob.append(f"重复图{dup}")
        if terms < 5:
            prob.append(f"术语{terms}<5")
        if not (6 <= kb <= 18):
            prob.append(f"体积{kb:.1f}KB")
        print(f"{e['seq']:<4}{e['label']:<9}{steps:<4}{phases:<5}{len(imgs):<4}{miss:<5}{dup:<5}{terms:<5}{kb:<5.1f}"
              + ("OK" if not prob else "FAIL " + ",".join(prob)))
        if prob:
            bad.append((e["seq"], prob))
    print()
    if bad:
        print(f"FAIL {len(bad)} 集:", bad)
        return 2
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
