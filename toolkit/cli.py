# -*- coding: utf-8 -*-
"""notes CLI：videonotes-kit 单一入口（改项目名见 toolkit/branding.py）。

子命令：
  draft       重新生成各集 steps_v2.md（draft 引擎，确定性，可复现）
  curate      为各集生成 steps_pro.skeleton.md 半成品骨架（Tier1 精校输入；不覆盖人工金标准）
  build       跑 draft + curate(仅缺失时) + consolidate(含 docs/index) 重建 notes/ 合集（含图片自包含）
  verify      非破坏回归：draft 重生成临时比对 + notes 重生成到 _staging 与现状 diff + 图片自包含校验
  docs        仅归档参考文档
  index       仅重新生成总索引
  consolidate 仅汇集视频笔记
"""
import os
import re
import sys
import argparse
import filecmp
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工具链根（自动推导 = <项目根>）
PROJECTS = os.path.join(BASE, "projects")
sys.path.insert(0, BASE)

from toolkit import manifest as M, draft, consolidate, curate, release, sub


def find_manifest(course):
    p = os.path.join(PROJECTS, course, "manifest.toml")
    if os.path.isfile(p):
        return p
    alt = os.path.join(PROJECTS, course, "manifest.yaml")
    if os.path.isfile(alt):
        return alt
    raise SystemExit(f"[ERR] manifest 未找到: {p}")


# ---- 字幕直通（B 站 AI 字幕 → transcript.json；manifest [[episodes]].subtitle 单一开关源） ----

def _subtitle_src(mf, ep):
    """解析 ep.subtitle：绝对路径直接用；相对路径相对 course.video_root。未声明返回 None。"""
    src = (ep.get("subtitle") or "").strip()
    if not src:
        return None
    if not os.path.isabs(src):
        src = os.path.join(mf["course"].get("video_root", ""), src)
    return src


def _sync_subtitle(mf, ep):
    """声明了 subtitle 就把字幕转成 transcript.json（draft/build 走这里，会写入）。"""
    src = _subtitle_src(mf, ep)
    if not src:
        return
    if not os.path.isfile(src):
        print("  WARN 字幕文件缺失（保留现有 transcript.json）:", src)
        return
    sub.convert(src, os.path.join(mf["course"]["out_root"], ep["ep_dir"]))


def _check_subtitle(mf, ep):
    """verify 专用：校验 transcript.json 是否与字幕一致。**只读，不写**（非破坏约定）。"""
    src = _subtitle_src(mf, ep)
    if not src:
        return True, ""
    if not os.path.isfile(src):
        return False, f"字幕文件缺失: {src}"
    tp = os.path.join(mf["course"]["out_root"], ep["ep_dir"], "transcript.json")
    if not os.path.isfile(tp):
        return False, "字幕已声明但 transcript.json 不存在（跑 notes draft 生成）"
    try:
        want = sub.render(src)
    except ValueError as e:
        return False, str(e)
    with open(tp, encoding="utf-8") as f:
        have = f.read()
    if want != have:
        return False, "transcript.json 与字幕不同步（字幕已更新？跑 notes draft 重建）"
    return True, ""


def _draft_all(mf):
    for ep in mf["episodes"]:
        _sync_subtitle(mf, ep)
        out = os.path.join(mf["course"]["out_root"], ep["ep_dir"])
        if os.path.isfile(os.path.join(out, "transcript.json")):
            draft.build(out, max_steps=mf["draft"].get("max_steps", 80))
        else:
            print("SKIP (无 transcript.json):", ep["ep_dir"])


def cmd_draft(mf, args):
    _draft_all(mf)


def cmd_build(mf, args):
    _draft_all(mf)
    consolidate.build_all(mf)


def cmd_verify(mf, args):
    print("=== DRAFT 回归（比较引擎实质产物：## 操作步骤 之后内容，忽略头部元数据） ===")
    draft_ok = True
    sub_ok = True
    for ep in mf["episodes"]:
        out = os.path.join(mf["course"]["out_root"], ep["ep_dir"])
        cur = os.path.join(out, "steps_v2.md")

        # 字幕新鲜度（只读校验，不写入）
        ok_sub, msg_sub = _check_subtitle(mf, ep)
        if not ok_sub:
            sub_ok = False
            print(f"  SUBTITLE {ep['ep_dir']}: {msg_sub}")

        if not os.path.isfile(cur):
            print("  skip（无 steps_v2.md）:", ep["ep_dir"]); continue
        draft.build(out, max_steps=mf["draft"].get("max_steps", 80), out_name="_steps_v2_verify.md")
        tmp = os.path.join(out, "_steps_v2_verify.md")

        def _body(p):
            ls = open(p, encoding="utf-8").read().splitlines()
            try:
                i = ls.index("## 操作步骤")
            except ValueError:
                i = 0
            return ls[i:]

        a, b = _body(cur), _body(tmp)
        same = (a == b)
        print(f"  {ep['ep_dir']}: 步骤正文 {'MATCH' if same else 'DIFF'}")
        if not same:
            draft_ok = False
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    print("     L%d:" % i, repr(x), "|", repr(y))
                    if i > 4:
                        break
        os.remove(tmp)

    print("=== NOTES 回归（重生成到 _staging 与现状逐字节 diff，含总索引与 assets） ===")
    # 扫掉历史 collect 遗留的 <label>.__staging_*__ 碎片目录（后台删除未完成/被并发打断的产物），
    # 否则 walk(live, staging) 会把它们当「多余文件」误判 staging 缺失。只删 .*__staging_*__ 样式，
    # 正常数据目录不受影响。
    live_assets = os.path.join(M.notes_root(mf), mf["course"]["assets_subdir"])
    if os.path.isdir(live_assets):
        for name in os.listdir(live_assets):
            if ".__staging" in name:
                shutil.rmtree(os.path.join(live_assets, name), ignore_errors=True)
    staging = os.path.join(mf["course"]["out_root"], "_staging")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    consolidate.ensure_curated(mf)
    consolidate.build_all(mf, notes_root=staging)
    live = M.notes_root(mf)

    issues = []

    def walk(a, b, tag):
        for root, _, fs in os.walk(a):
            for f in fs:
                pa = os.path.join(root, f)
                pb = pa.replace(a, b, 1)
                if not os.path.isfile(pb):
                    issues.append((tag + ":missing_in_staging", pa))
                elif not filecmp.cmp(pa, pb, shallow=False):
                    issues.append((tag + ":diff", pa))
        for root, _, fs in os.walk(b):
            for f in fs:
                pb = os.path.join(root, f)
                pa = pb.replace(b, a, 1)
                if not os.path.isfile(pa):
                    issues.append((tag + ":missing_in_live", pb))

    walk(live, staging, "notes")
    if issues:
        for k, p in issues:
            print("  ", k, p)
    else:
        print("  notes/ == _staging : 全部逐项一致（含 10 笔记 + 8 文档 + assets/ 帧 + 总索引）")
    shutil.rmtree(staging, ignore_errors=True)

    print("=== ASSET 自包含校验（图片链接是否都落在 assets/ 内且文件存在；不应残留 ../ 脆弱链接） ===")
    asset_total = 0
    asset_missing = 0
    fragile = 0
    for root, _, fs in os.walk(live):
        for f in fs:
            if not f.endswith(".md") or f == "总索引.md":
                continue
            p = os.path.join(root, f)
            body = open(p, encoding="utf-8").read()
            for link in re.findall(r"\]\((assets/[^)]+)\)", body):
                asset_total += 1
                if not os.path.isfile(os.path.join(live, link)):
                    asset_missing += 1
                    print("  MISSING IMG:", f, "->", link)
            for bad in re.findall(r"\]\((\.\./[^)]+)\)", body):
                fragile += 1
                print("  FRAGILE LINK:", f, "->", bad)
    print(f"  图片引用 {asset_total} 处，缺失 {asset_missing}，脆弱 ../ 链接 {fragile}")

    # ---- P5 校验：source mp4 完整 + play.html 存在 ----
    print("=== P5 校验（source 视频完整 + play.html 存在） ===")
    source_root = os.path.join(live, "source")
    source_ok = True
    source_count = 0
    source_empty = []
    if not os.path.isdir(source_root):
        source_ok = False
        print("  MISSING source/ 目录")
    else:
        for ep in mf["episodes"]:
            sv = ep.get("source_video", "")
            if not sv:
                continue
            ep_src = os.path.join(source_root, ep.get("series", "其他"), os.path.basename(sv))
            if not os.path.isfile(ep_src):
                source_ok = False
                print("  SOURCE MISSING:", ep["label"], "->", os.path.relpath(ep_src, live))
            elif os.path.getsize(ep_src) == 0:
                source_ok = False
                source_empty.append(ep["label"])
                print("  SOURCE EMPTY:", ep["label"])
            else:
                source_count += 1
    print(f"  源 mp4 已就位 {source_count} / {len(mf['episodes'])}")

    play_path = os.path.join(live, "play.html")
    play_ok = os.path.isfile(play_path) and os.path.getsize(play_path) > 0
    if not play_ok:
        source_ok = False
        print("  MISSING play.html")
    else:
        # 检查 play.html 含全部 10 集 label
        body = open(play_path, encoding="utf-8").read()
        missing_eps = [ep["label"] for ep in mf["episodes"] if ep["label"] not in body]
        if missing_eps:
            source_ok = False
            print("  play.html 缺集 label:", missing_eps)
        else:
            print(f"  play.html 存在，含 {len(mf['episodes'])} 集 label")

    # ---- P8 校验：notes.html 三栏笔记浏览器存在 + 含全部集 label + 无外部 CDN ----
    view_path = os.path.join(live, "notes.html")
    view_ok = os.path.isfile(view_path) and os.path.getsize(view_path) > 0
    if not view_ok:
        source_ok = False
        print("  MISSING notes.html（跑 notes build 生成）")
    else:
        body = open(view_path, encoding="utf-8").read()
        missing_eps = [ep["label"] for ep in mf["episodes"] if ep["label"] not in body]
        if missing_eps:
            source_ok = False
            print("  notes.html 缺集 label:", missing_eps)
        elif "fetch(" in body:
            source_ok = False
            print("  notes.html 含 fetch( —— 会破坏 file:// 双击可用性")
        else:
            print(f"  notes.html 存在（{os.path.getsize(view_path)//1024} KB），含 {len(mf['episodes'])} 集 label")

    ok = draft_ok and sub_ok and not issues and asset_missing == 0 and fragile == 0 and source_ok
    print("VERIFY", "PASS" if ok else "FAIL（详见上方）")


def main():
    ap = argparse.ArgumentParser(prog="notes")
    ap.add_argument("course")
    ap.add_argument("cmd", choices=["draft", "build", "verify", "docs", "index", "consolidate", "curate", "release_check"])
    ap.add_argument("--overwrite", action="store_true", help="curate：强制重写已存在的骨架（不破坏 steps_pro.md 金标准，仅重写 .skeleton）")
    args = ap.parse_args()
    mf = M.load(find_manifest(args.course))
    dispatch = {
        "draft": cmd_draft,
        "build": cmd_build,
        "verify": cmd_verify,
        "docs": lambda m, a: __import__("toolkit.docs", fromlist=["import_docs"]).import_docs(m),
        "index": lambda m, a: __import__("toolkit.index", fromlist=["build_index"]).build_index(m),
        "consolidate": lambda m, a: consolidate.build_all(m),
        "curate": lambda m, a: curate.refine_all(m, a.overwrite),
        "release_check": lambda m, a: release.main(a),
    }
    dispatch[args.cmd](mf, args)


if __name__ == "__main__":
    main()
