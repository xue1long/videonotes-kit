# -*- coding: utf-8 -*-
"""scripts/extract_glossary.py — 从 _curated/<集>/steps_pro.md 提取 "**术语**: meaning" 段
自动追加到 manifest.toml 的 [[course.glossary]] 段，避免手动 Edit。

用法:
  python scripts/extract_glossary.py <课程>            # 默认 append 模式
  python scripts/extract_glossary.py <课程> --diff   # 只打印新增项，不改文件
  python scripts/extract_glossary.py <课程> --reset  # 清空 glossary 后重写
"""
import os
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path("D:/000/vidwise")
PROJECT = ROOT / "projects" / sys.argv[1]
MANIFEST = PROJECT / "manifest.toml"


def load_manifest():
    with open(MANIFEST, "rb") as f:
        return tomllib.load(f)


def _glossary_block(md_text: str) -> str:
    """只取 `## 关键术语` 段（到下一个 ## 标题或 --- 为止）。

    历史坑：早期用全文扫描，会把步骤里 `- **自动化**：...` 这类加粗小标题
    误当术语写进 manifest.glossary。
    """
    lines = md_text.splitlines()
    out = []
    inside = False
    for ln in lines:
        s = ln.strip()
        if not inside:
            if re.match(r"^##\s*关键术语", s):
                inside = True
            continue
        if re.match(r"^##\s", s):
            break
        if s == "---":
            break
        out.append(ln)
    return "\n".join(out)


def extract_terms_from_curated(curated_dir: Path) -> list:
    """扫 _curated/<集>/steps_pro.md 抽 "**术语**: meaning" 行。

    返回 [(term, meaning), ...] 按首次出现顺序。
    """
    seen = set()
    out = []
    if not curated_dir.exists():
        return out
    pattern = re.compile(r"^\s*-\s*\*\*([^*]+)\*\*[：:]\s*(.+?)\s*$")
    for ep_dir in sorted(curated_dir.iterdir()):
        md = ep_dir / "steps_pro.md"
        if not md.exists():
            continue
        for line in _glossary_block(md.read_text(encoding="utf-8")).splitlines():
            m = pattern.match(line)
            if m:
                term = m.group(1).strip()
                meaning = m.group(2).strip()
                key = (term, meaning)
                if key not in seen:
                    seen.add(key)
                    out.append((term, meaning))
    return out


def main():
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    diff_only = "--diff" in args
    reset = "--reset" in args

    mf = load_manifest()
    existing = mf.get("course", {}).get("glossary", [])
    existing_pairs = {(g["term"], g["meaning"]) for g in existing}

    # 金标准目录在 out_root/<curated_subdir>（不是 projects/<课程>/_curated）
    curated_dir = Path(mf["course"]["out_root"]) / mf["course"]["curated_subdir"]
    extracted = extract_terms_from_curated(curated_dir)
    new_pairs = [(t, m) for t, m in extracted if (t, m) not in existing_pairs]

    print(f"已存在: {len(existing_pairs)} 词条")
    print(f"扫到 _curated 中: {len(extracted)} 词条")
    print(f"新增: {len(new_pairs)} 词条")
    for t, m in new_pairs:
        print(f"  + **{t}**: {m}")

    if diff_only:
        return

    if not new_pairs and not reset:
        print("无需写入。")
        return

    # 重写 glossary 段
    text = MANIFEST.read_text(encoding="utf-8")
    # 找 glossary 段的开始与结束
    start = text.find("# 术语对照")
    if start == -1:
        start = text.find("[[course.glossary]]")
    if start == -1:
        print("未找到 glossary 段，请先在 manifest 加 [[course.glossary]] 占位。")
        return
    # 找下一个非 glossary 的 section
    rest = text[start:]
    end_match = re.search(r"^\[(?:draft|llm)\]", rest[10:], re.M)
    if end_match:
        end = start + 10 + end_match.start()
    else:
        end = len(text)

    all_pairs = list(existing_pairs) if not reset else []
    all_pairs.extend(new_pairs)

    new_block = "# 术语对照（自动从 _curated/<集>/steps_pro.md 提取，每次跑追加）\n"
    for t, m in all_pairs:
        new_block += f"[[course.glossary]]\nterm = \"{t}\"\nmeaning = \"{m}\"\n"

    text = text[:start] + new_block + "\n" + text[end:]
    MANIFEST.write_text(text, encoding="utf-8")
    print(f"已写入 manifest: +{len(new_pairs)} 词条")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main()
