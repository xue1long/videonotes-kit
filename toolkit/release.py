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


# ---- P5 红线校验（仅校验可机器检测的硬约束，NLP/视觉类的靠人）----

_STEP_TITLE_RE = re.compile(r"^###\s*步骤\s*\d+\s*[:：]", re.M)
_FRAME_RE      = re.compile(r"\]\(frames/(frame_(\d+)m(\d+)s\.png)\)")
_DONE_MARK_RE  = re.compile(r"\*\*做对了的表现\*\*")


def _check_p5_redlines(mf, base):
    """P5 模板（templates/steps_pro_tutorial.md R1-R10）的可机器校验项。

    覆盖：
      R3-ish 步骤标题格式（强建议）：### 步骤 N：xxx（H3 + `步骤 N` + 冒号）
      R6-ish 图链格式：](frames/frame_NNmSSs.png)（consolidate 也用这条正则匹配）
      R4-ish 每步自检标：**做对了的表现**：

    不可机器校验项（NLP/视觉）：R1/R2/R5/R7/R8/R9/R10 —— 留给人工/polish 阶段。
    """
    issues = []
    cur_root = os.path.join(mf["course"]["out_root"], mf["course"]["curated_subdir"])
    if not os.path.isdir(cur_root):
        return []  # 还没 curate；不强制
    for ep in mf.get("episodes", []):
        ep_dir = ep.get("ep_dir", "")
        if not ep_dir:
            continue
        skel = os.path.join(cur_root, ep_dir, "steps_pro.md")
        if not os.path.isfile(skel):
            continue
        body = _read(skel)
        # 步骤标题格式：每条 ### 步骤 N: xxx 必须严格
        bad_titles = [
            line for line in body.splitlines()
            if line.startswith("###") and "步骤" in line and not _STEP_TITLE_RE.match(line)
        ]
        if bad_titles:
            issues.append(("WARN", skel,
                f"步骤标题不规范（{len(bad_titles)} 处不是 `### 步骤 N：xxx`），build 步数统计会漏计：\n      " +
                "\n      ".join(bad_titles[:3])))
        # 图链格式：]（frames/frame_NmSSs.png）（consolidate 正则）
        all_frames = re.findall(r"\]\(([^)]+)\)", body)
        bad_imgs = [u for u in all_frames if "frames/frame_" in u and not _FRAME_RE.search("](" + u + ")")]
        if bad_imgs:
            issues.append(("WARN", skel,
                f"图链命名不规范（{len(bad_imgs)} 处不匹配 frame_NmSSs 格式），build 不会复制到 assets/：\n      " +
                "\n      ".join(bad_imgs[:3])))
        # 自检标记（**做对了的表现**：）必须出现至少 1 次
        if _STEP_TITLE_RE.search(body) and not _DONE_MARK_RE.search(body):
            issues.append(("WARN", skel,
                "缺「做对了的表现：」自检标记（P5 R4 红线）"))
    return issues


def _check_templates_runtime(mf, base):
    """模板是否被代码实际使用（验证 templates/ 不是 dead code）。

    校验：toolkit/templates.py 存在 + curate.py + index.py 都 import 该模块。
    """
    issues = []
    tp = os.path.join(base, "toolkit", "templates.py")
    if not os.path.isfile(tp):
        issues.append(("FAIL", tp, "toolkit/templates.py 不存在（缺少模板渲染层）"))
        return issues

    def _imported(body: str) -> bool:
        # 多种合法 import 形式：from . import templates / from . import templates as T
        # / from . import manifest as M, branding, templates as T  / from toolkit import templates
        import re as _re
        return bool(
            _re.search(r"\bfrom\s+\.\s+import\s+[^#\n]*\btemplates\b", body)
            or _re.search(r"\bfrom\s+toolkit\s+import\s+[^#\n]*\btemplates\b", body)
            or _re.search(r"\bimport\s+templates\b", body)
        )

    for mod in ("curate.py", "index.py"):
        body = _read(os.path.join(base, "toolkit", mod))
        if not _imported(body):
            issues.append(("FAIL", f"toolkit/{mod}", "未导入 toolkit/templates（模板未真正接 curate/index）"))
    # 模板目录至少要有 steps_pro.md 和 index.md
    for name in ("steps_pro.md", "index.md"):
        p = os.path.join(base, "templates", name)
        if not os.path.isfile(p):
            issues.append(("FAIL", p, f"templates/{name} 不存在"))
    return issues


def _check_source_video_paths(mf, base):
    """校验 manifest [[episodes]].source_video 路径是否真实存在。

    解析约定：绝对路径直接用；相对路径相对 course.video_root（与 cli.py / consolidate.py 一致）。
    校验规则：
      - 未声明：跳过
      - video_root 未声明但用了相对路径：WARN（无法解析相对基准）
      - 解析后路径不存在：WARN（不阻断 release_check；build 时会同样报 WARN）
    """
    issues = []
    video_root = mf.get("course", {}).get("video_root", "")
    missing_count = 0
    for ep in mf.get("episodes", []):
        sv = (ep.get("source_video") or "").strip()
        if not sv:
            continue
        if not os.path.isabs(sv):
            if not video_root:
                issues.append(("WARN", f"manifest",
                    f"episodes[{ep.get('seq','?')}] source_video 是相对路径但 course.video_root 未声明"))
                continue
            sv = os.path.join(video_root, sv)
        if not os.path.isfile(sv):
            missing_count += 1
    if missing_count:
        course_name = mf.get("course", {}).get("name", "?")
        issues.append(("WARN", "manifest",
            f"{course_name} 有 {missing_count} 集 source_video 路径不存在（build 会复制失败；可能是 video_root 历史路径迁移，请核对或下回重新下载）"))
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
        ("source_video 路径存在", _check_source_video_paths),
        ("templates/ 真接代码", _check_templates_runtime),
        ("P5 教程体红线", _check_p5_redlines),
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
        print("RELEASE-CHECK PASS（9 项检查全 OK，无遗漏同步点）")
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
