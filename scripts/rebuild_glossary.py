# -*- coding: utf-8 -*-
"""scripts/rebuild_glossary.py — 从 _curated 全量重建 manifest 术语表（去重 + 过滤）

与 extract_glossary.py 的区别：
  - extract_glossary：增量追加（同一术语不同措辞会重复）
  - rebuild_glossary：全量重建（按「规范化术语名」去重，保留首次出现的释义）

用法:
  python scripts/rebuild_glossary.py <课程> [--diff]
"""
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path("D:/000/vidwise")

# 明显不是术语的行（学习目标被误写成「- **标签**：」时兜底）
BAD_PREFIX = ("讲清", "找到", "切出", "换掉", "拼回", "分清", "会用", "避免", "学会", "能", "知道")


def norm(term: str) -> str:
    """术语去重键：去空格、去括号/斜杠/连字符/反引号，小写。"""
    t = term.lower()
    t = re.sub(r"[`'\"《》()（）\[\]【】/／\-—_·、，,。.]", "", t)
    return re.sub(r"\s+", "", t)


def glossary_block(text: str) -> str:
    lines = text.splitlines()
    out, inside = [], False
    for ln in lines:
        s = ln.strip()
        if not inside:
            if re.match(r"^##\s*关键术语", s):
                inside = True
            continue
        if re.match(r"^##\s", s) or s == "---":
            break
        out.append(ln)
    return "\n".join(out)


def main():
    course = sys.argv[1]
    diff_only = "--diff" in sys.argv
    manifest = ROOT / "projects" / course / "manifest.toml"
    mf = tomllib.load(open(manifest, "rb"))
    cur = Path(mf["course"]["out_root"]) / mf["course"]["curated_subdir"]

    pattern = re.compile(r"^\s*-\s*\*\*([^*]+)\*\*[：:]\s*(.+?)\s*$")
    terms, seen, skipped = [], set(), 0
    for ep_dir in sorted(cur.iterdir()):
        md = ep_dir / "steps_pro.md"
        if not md.is_file():
            continue
        for line in glossary_block(md.read_text(encoding="utf-8")).splitlines():
            m = pattern.match(line)
            if not m:
                continue
            term, meaning = m.group(1).strip(), m.group(2).strip()
            if len(term) > 20 or term.startswith(BAD_PREFIX) or not meaning:
                skipped += 1
                continue
            key = norm(term)
            if not key or key in seen:
                skipped += 1
                continue
            seen.add(key)
            terms.append((term, meaning))

    print(f"收录 {len(terms)} 词条（去重/过滤掉 {skipped}）")
    if diff_only:
        for t, mm in terms[:400]:
            print(f"  - {t}: {mm[:30]}")
        return

    text = manifest.read_text(encoding="utf-8")
    start = text.find("# 术语对照")
    if start == -1:
        start = text.find("[[course.glossary]]")
    if start == -1:
        print("未找到 glossary 段")
        return 1
    rest = text[start:]
    m = re.search(r"^\[(?:draft|llm)\]", rest[10:], re.M)
    end = start + 10 + m.start() if m else len(text)

    block = "# 术语对照（由 scripts/rebuild_glossary.py 从 _curated/<集>/steps_pro.md 全量重建）\n"
    for t, mm in terms:
        block += "[[course.glossary]]\n"
        block += f"term = {json.dumps(t, ensure_ascii=False)}\n"
        block += f"meaning = {json.dumps(mm, ensure_ascii=False)}\n"
    manifest.write_text(text[:start] + block + "\n" + text[end:], encoding="utf-8")
    print(f"已写入 {manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
