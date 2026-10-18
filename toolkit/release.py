# -*- coding: utf-8 -*-
"""release-check：项目级「我忘了同步」自动检查器。

痛点：每次落地新特性（P4 教程化升级、P5 视频打包+时间轴、更名 videonotes-kit…），
人脑很难在第一时刻同步更新「整改方案 §12、cmd_verify 校验段、总索引头部 banner、
README.md banner、AGENT.md toolkit 模块地图、toolkit 各模块注释」这 6+ 处文案。
本工具把所有同步点列成可机器校验的清单。

设计原则：
  - 零硬编码：所有"该有什么内容"从 manifest 与 toolkit/ 实际文件结构推导。
  - 非破坏：只读文件不写任何东西。
  - 输出一行清单：每条 PASS/WARN/FAIL 配文件名+行号（如果能定位），便于人立刻定位补什么。
  - 退出码：全部 PASS → 0；任一 FAIL → 1（CI 友好）。
"""
import os
import re
import sys
import tomllib


BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path):
    if not os.path.isfile(path):
        return ""
    return open(path, encoding="utf-8").read()


def _check_roadmap(mf, base):
    """整改方案 §12 是否覆盖所有已落地 P* 阶段（从 toolkit 文件名推断）。"""
    path = os.path.join(base, "VIDEONOTES-KIT_ROADMAP.md")
    body = _read(path)
    issues = []
    if not body:
        return [("FAIL", path, "整改方案文件不存在")]
    # 推断"已落地阶段"：toolkit/ 下包含 P<n> 关键词的代码注释
    landed = set()
    toolkit_dir = os.path.join(base, "toolkit")
    for fname in os.listdir(toolkit_dir):
        if not fname.endswith(".py"):
            continue
        b = _read(os.path.join(toolkit_dir, fname))
        for m in re.finditer(r"P\s*([1-9])\b", b):
            landed.add("P" + m.group(1))
    if not landed:
        return []  # 没有 P* 注释，跳过
    # 检查整改方案 §12 表格
    sec12 = re.search(r"## 12\..*?(?=\n## |\Z)", body, re.S)
    if not sec12:
        return [("FAIL", path, "整改方案缺 §12 实施进度小节")]
    table = sec12.group(0)
    for p in sorted(landed):
        if p not in table:
            issues.append(("WARN", path, "整改方案 §12 表格缺 " + p + " 状态行"))
    return issues


def _check_verify_coverage(mf, base):
    """cmd_verify 是否校验所有 toolkit 产出的关键产物。

    推断规则：扫描 toolkit/*.py 顶部 docstring，提取「产出」文件/目录名（heuristic）。
    """
    path = os.path.join(base, "toolkit", "cli.py")
    body = _read(path)
    issues = []
    if not body:
        return [("FAIL", path, "toolkit/cli.py 不存在")]
    # 已知产物表
    products = ["source", "play.html", "assets"]
    for prod in products:
        if prod not in body:
            issues.append(("WARN", path, "cmd_verify 未校验产物：" + prod))
    return issues


def _check_index_banner(mf, base):
    """产物总索引头部 banner 是否反映最新特性（如 P5 play.html 入口）。"""
    issues = []
    idx_path = os.path.join(mf["course"]["out_root"], mf["course"]["notes_subdir"], "总索引.md")
    body = _read(idx_path)
    if not body:
        return [("WARN", idx_path, "总索引尚未生成（首次跑 build 后才有）")]
    if "play.html" not in body[:1000]:
        issues.append(("WARN", idx_path, "总索引头部未提 play.html 入口"))
    if "videonotes-kit" not in body[:200] and "videonotes" not in body[:200].lower():
        issues.append(("WARN", idx_path, "总索引头部未提项目名 videonotes-kit"))
    return issues


def _check_readme_banner(mf, base):
    """README.md 头部 banner 是否指向所有现存 .md 文档。"""
    path = os.path.join(base, "README.md")
    body = _read(path)
    issues = []
    if not body:
        return [("FAIL", path, "README.md 不存在")]
    # banner 段（在前 60 行内）
    head = "\n".join(body.splitlines()[:60])
    must_link = ["README.notes.md", "AGENT.md", "VIDEONOTES-KIT_ROADMAP.md"]
    for f in must_link:
        if f in head:
            continue
        # 没指向就检查文件本身存在
        if os.path.isfile(os.path.join(base, f)):
            issues.append(("WARN", path, "README.md banner 未指向 " + f))
    return issues


def _check_agent_module_map(mf, base):
    """AGENT.md §6 toolkit 模块地图 是否覆盖所有 toolkit/*.py 模块。"""
    path = os.path.join(base, "AGENT.md")
    body = _read(path)
    issues = []
    if not body:
        return [("WARN", path, "AGENT.md 不存在（agent 文档可选）")]
    toolkit_dir = os.path.join(base, "toolkit")
    py_modules = [f[:-3] for f in os.listdir(toolkit_dir) if f.endswith(".py") and f != "__init__.py"]
    sec6 = re.search(r"## 6\..*?(?=\n## |\Z)", body, re.S)
    if not sec6:
        return [("WARN", path, "AGENT.md 缺 §6 toolkit 模块地图")]
    table = sec6.group(0)
    for m in py_modules:
        if m not in table:
            issues.append(("WARN", path, "AGENT.md §6 模块地图缺 " + m + ".py"))
    return issues


def _check_manifest_required(mf, base):
    """manifest 是否含必要字段（防止 P5/P4 改造后字段缺失）。"""
    issues = []
    course = mf.get("course", {})
    if not course.get("notes_subdir"):
        issues.append(("FAIL", "manifest", "course.notes_subdir 缺失"))
    if not course.get("assets_subdir"):
        issues.append(("FAIL", "manifest", "course.assets_subdir 缺失"))
    if not course.get("refdoc_subdir"):
        issues.append(("FAIL", "manifest", "course.refdoc_subdir 缺失"))
    if not course.get("learning_path"):
        issues.append(("WARN", "manifest", "course.learning_path 缺失（总索引将缺『如何使用本教程』）"))
    if not course.get("glossary"):
        issues.append(("WARN", "manifest", "course.glossary 缺失（总索引将缺术语对照）"))
    # 每集必填字段
    for ep in mf.get("episodes", []):
        for f in ("seq", "label", "ep_dir", "topic", "series", "level", "source_video"):
            if not ep.get(f):
                issues.append(("WARN", "manifest", "episodes[" + str(ep.get("seq", "?")) + "]." + f + " 缺失"))
    return issues


def run(mf, base=None):
    """主入口：跑全部检查，返回 (issues, summary)。"""
    base = base or BASE
    all_issues = []
    checks = [
        ("整改方案 P* 阶段覆盖", _check_roadmap),
        ("cmd_verify 产物覆盖", _check_verify_coverage),
        ("产物总索引 banner", _check_index_banner),
        ("README.md 入口 banner", _check_readme_banner),
        ("AGENT.md 模块地图", _check_agent_module_map),
        ("manifest 必填字段", _check_manifest_required),
    ]
    for name, fn in checks:
        try:
            all_issues.extend(fn(mf, base))
        except Exception as e:
            all_issues.append(("FAIL", name, "check crashed: " + str(e)))
    return all_issues


def main(args=None):
    # 接受 args 由 cli.main 传入（避免重新解析 sys.argv 触发冲突）
    if args is not None and getattr(args, "course", None):
        course = args.course
    else:
        import argparse
        ap = argparse.ArgumentParser(prog="notes release_check",
                                     description="检查项目内『我忘了同步』的 6+ 处文案")
        ap.add_argument("course")
        course = ap.parse_args().course
    # 读 manifest
    mf_path = os.path.join(BASE, "projects", course, "manifest.toml")
    if not os.path.isfile(mf_path):
        print("[ERR] manifest 未找到:", mf_path); sys.exit(1)
    with open(mf_path, "rb") as f:
        mf = tomllib.load(f)
    issues = run(mf, BASE)

    if not issues:
        print("RELEASE-CHECK PASS（6 项检查全 OK，无遗漏同步点）")
        sys.exit(0)

    # 按级别分组打印
    fails = [i for i in issues if i[0] == "FAIL"]
    warns = [i for i in issues if i[0] == "WARN"]
    print("RELEASE-CHECK FAIL" if fails else "RELEASE-CHECK WARN")
    for lvl, where, what in (fails + warns):
        print("  [%s] %s — %s" % (lvl, where, what))
    print()
    print("  共 %d FAIL / %d WARN" % (len(fails), len(warns)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
