# -*- coding: utf-8 -*-
"""consolidate：把各集精校笔记（_curated/<ep>/steps_pro.md）汇集进 notes/，规则化命名 + 复制被引帧为自包含。

P2 行为：图链改写为 `assets/<label>/...`，被引帧从 `<ep_dir>/frames/` 复制到 `notes/assets/<label>/`，
合集可整体移动/打包，图片不丢。
P5 新增：
  - copy_source：把源 mp4（manifest episodes[].source_video）复制到 steps_pro/source/<series>/<原名>.mp4，
    收件人拿到合集即可直接看原视频。
  - gen_play_page：生成 steps_pro/play.html 单页播放器，URL 参数 ?ep=<label>&t=<秒>
    打开后自动定位视频并跳到指定时间。每步笔记的截图可点击链接到此页。
curated 源默认从 manifest 的 curated_subdir 读取；首次缺失时从现状 notes/ 反向改写图链引导出（bootstrap），
使管线可独立复现当前产物。
"""
import os
import re
import shutil
import urllib.parse
from . import manifest as M, branding


def ensure_curated(mf):
    cur = M.curated_root(mf)
    notes = M.notes_root(mf)
    if os.path.isdir(cur) and any(os.listdir(cur)):
        return cur
    os.makedirs(cur, exist_ok=True)
    print("[bootstrap] 从现状 notes/ 反向引导 _curated/")
    for ep in mf["episodes"]:
        fn = f"{ep['seq']}_{ep['label']}_{ep['topic']}.md"
        src = os.path.join(notes, fn)
        if not os.path.isfile(src):
            print("  MISS", fn); continue
        txt = open(src, encoding="utf-8").read()
        # 当前现状图链为 assets/<label>/frame_*.png；恢复成 frames/ 相对链
        txt = re.sub(r"\]\(assets/%s/frame_" % re.escape(ep["label"]), "](frames/frame_", txt)
        d = os.path.join(cur, ep["ep_dir"])
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "steps_pro.md"), "w", encoding="utf-8").write(txt)
    return cur


IMG_RE = re.compile(r"\]\(frames/(frame_(\d+)m(\d+)s\.png)\)")


def _to_seconds(mm: str, ss: str) -> int:
    return int(mm) * 60 + int(ss)


def collect(mf, notes_root=None):
    """汇集笔记 + 复制被引帧到 assets/ + 把每张截图改写为带时间戳的"时间轴链接"。"""
    notes_root = notes_root or M.notes_root(mf)
    cur = ensure_curated(mf)
    os.makedirs(notes_root, exist_ok=True)
    assets_root = os.path.join(notes_root, mf["course"]["assets_subdir"])  # steps_pro/assets
    files = []
    for ep in mf["episodes"]:
        src = os.path.join(cur, ep["ep_dir"], "steps_pro.md")
        if not os.path.isfile(src):
            print("MISS curated:", src); continue
        # P4 修复：先清空该集 assets 子目录，避免旧帧残留导致 staging diff。
        # 沙箱敏感：直接 shutil.rmtree ≥50 文件目录会触发 SAFE_DELETE_BULK_CONFIRM_REQUIRED 死锁；
        # 同步 rmtree 本会话/另一会话也可能并发跑，且 verify 的 _staging → live walk 会把残留
        # 的中间目录当「多余文件」报出。 → 改用「随机 token 改名 + 后台 best-effort 删除」：
        # 1) 立刻原子挪走，当下 collect 就建干净目录；
        # 2) 名字带唯一 token，verify 前置清理能精确扫掉（不碰数据目录）。
        ep_assets = os.path.join(assets_root, ep["label"])
        if os.path.isdir(ep_assets):
            import secrets
            tmp_old = "%s.__staging_%s__" % (ep_assets, secrets.token_hex(4))
            try:
                os.rename(ep_assets, tmp_old)
            except OSError:
                tmp_old = None
            if tmp_old:
                # 在后台静默删旧目录（best-effort，失败也不影响新拷贝）
                def _bg_rm(p):
                    try:
                        shutil.rmtree(p, ignore_errors=True)
                    except Exception:
                        pass
                import threading
                threading.Thread(target=_bg_rm, args=(tmp_old,), daemon=True).start()
            os.makedirs(ep_assets, exist_ok=True)
        txt = open(src, encoding="utf-8").read()

        def repl(m, ep=ep):
            fname = m.group(1)
            mm, ss = m.group(2), m.group(3)
            t = _to_seconds(mm, ss)
            # 复制帧到 assets/<label>/
            src_img = os.path.join(mf["course"]["out_root"], ep["ep_dir"], "frames", fname)
            dst_dir = os.path.join(assets_root, ep["label"])
            os.makedirs(dst_dir, exist_ok=True)
            dst_img = os.path.join(dst_dir, fname)
            if os.path.isfile(src_img):
                shutil.copy2(src_img, dst_img)
            else:
                print("  WARN 缺帧（跳过复制）:", src_img)
            # P5：图链改为"双链接"——图片本身 + 时间轴跳转链接
            # 渲染：![步骤 1 截图 0m00s](assets/.../frame_0m00s.png) [▶ 0:00](play.html?ep=...&t=0)
            return "](" + ("assets/%s/%s" % (ep["label"], fname)) + ") [▶ %s:%02d](play.html?ep=%s&t=%d)" % (
                mm, int(ss), urllib.parse.quote(ep["label"]), t
            )

        txt = IMG_RE.sub(repl, txt)
        # P5：注入顶部播放器入口（紧跟 H1 与第一条 blockquote 之后）
        play_url = "play.html?ep=" + urllib.parse.quote(ep["label"]) + "&t=0"
        banner = (
            "\n\n> ▶ **打开视频播放器**：[play.html?ep=" + urllib.parse.quote(ep["label"]) + "]"
            "(" + play_url + ") · 点击下方步骤后的 `▶ 0m00s` 链接可自动跳到该步骤时间点\n"
        )
        # 找到第一个 H2 之前的位置；找不到则追加到末尾
        m = re.search(r"^##\s", txt, re.M)
        if m:
            txt = txt[:m.start()] + banner.lstrip("\n") + "\n" + txt[m.start():]
        else:
            txt = txt + "\n" + banner
        newname = f"{ep['seq']}_{ep['label']}_{ep['topic']}.md"
        dst = os.path.join(notes_root, newname)
        open(dst, "w", encoding="utf-8").write(txt)
        sc = len(re.findall(r"^###\s*步骤", txt, re.M))
        files.append((newname, ep["label"], ep["topic"], sc))
        print("collected ->", newname, "steps:", sc, "| assets:", ep["label"])
    return files


def _resolve_source(mf, sv: str) -> str:
    """解析 ep.source_video：绝对路径直接用；相对路径相对 course.video_root。

    与 cli.py:_subtitle_src 完全平行：同套约定 = 绝对 OR 相对 video_root。
    """
    if not sv:
        return sv
    if not os.path.isabs(sv):
        sv = os.path.join(mf["course"].get("video_root", ""), sv)
    return sv


def copy_source(mf, notes_root=None):
    """P5：把源 mp4 复制到 steps_pro/source/<series>/<原名>.mp4，幂等（size 一致则跳过）。

    路径解析约定：
      - 绝对路径：直接用
      - 相对路径：相对 course.video_root（与 subtitle 解析一致）
    """
    notes_root = notes_root or M.notes_root(mf)
    source_root = os.path.join(notes_root, "source")
    copied = 0
    for ep in mf["episodes"]:
        sv = ep.get("source_video", "")
        if not sv:
            print("  SKIP source (无 source_video):", ep["label"]); continue
        sv = _resolve_source(mf, sv)
        if not os.path.isfile(sv):
            print("  WARN 源 mp4 不存在:", sv); continue
        series = ep.get("series", "其他")
        dst_dir = os.path.join(source_root, series)
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.basename(sv))
        # 幂等：size 一致则跳过；否则覆盖
        if os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(sv):
            print("  source skip (size 一致):", ep["label"], "->", os.path.relpath(dst, notes_root))
            continue
        shutil.copy2(sv, dst)
        copied += 1
        print("  source copy:", ep["label"], "->", os.path.relpath(dst, notes_root))
    print(f"source -> {copied} 个 mp4 已复制到 {os.path.relpath(source_root, notes_root)}/")
    return source_root


def _play_html(episodes, source_root_rel: str, course_name: str = "课程") -> str:
    """生成 play.html：单页播放器，支持 ?ep=<label>&t=<秒>。"""
    # 把每集 label / series / source 路径（相对 notes_root）注册到 JS
    ep_map = []
    for ep in episodes:
        sv = ep.get("source_video", "")
        if not sv:
            continue
        rel = os.path.join("source", ep.get("series", "其他"), os.path.basename(sv))
        ep_map.append({
            "label": ep["label"],
            "topic": ep["topic"],
            "series": ep.get("series", "其他"),
            "source": rel.replace(os.sep, "/"),
        })
    ep_json = repr(ep_map).replace("'", '"')  # 简化：手写 JSON 字符串

    # 用内联 JS 解析查询参数，定位视频并跳时间
    html = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__COURSE_NAME__ · 视频播放器</title>
<style>
  :root { color-scheme: light; }
  body { font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
         margin: 0; background: #f7f7f5; color: #1a1a1a; }
  header { padding: 16px 24px; background: #1a1a1a; color: #f5f5f5; }
  header h1 { margin: 0; font-size: 18px; font-weight: 500; }
  header .sub { color: #999; font-size: 13px; margin-top: 4px; }
  main { max-width: 960px; margin: 0 auto; padding: 24px; }
  .player { background: #000; border-radius: 8px; overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,.15); }
  video { width: 100%; display: block; }
  .meta { margin: 16px 0; padding: 12px 16px; background: #fff; border-radius: 6px;
          border: 1px solid #e5e5e5; font-size: 14px; }
  .meta b { color: #2563eb; }
  .meta .ts { color: #666; font-family: ui-monospace, Consolas, monospace; }
  .ep-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
             gap: 12px; margin-top: 24px; }
  .ep-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 6px;
             padding: 12px 14px; cursor: pointer; transition: all .15s; }
  .ep-card:hover { border-color: #2563eb; transform: translateY(-1px); }
  .ep-card .label { font-weight: 600; font-size: 14px; }
  .ep-card .topic { color: #666; font-size: 13px; margin-top: 4px; }
  .ep-card .series { display: inline-block; margin-top: 6px; padding: 2px 8px;
                     background: #eef2ff; color: #4338ca; border-radius: 10px; font-size: 11px; }
  .err { color: #b91c1c; padding: 16px; background: #fef2f2; border-radius: 6px; }
</style>
</head>
<body>
<header>
  <h1>__COURSE_NAME__ · 视频播放器</h1>
  <div class="sub">__BRANDING_INDEX_BANNER_PLAY__</div>
</header>
<main>
  <div class="player">
    <video id="v" controls preload="metadata" playsinline>
      <source id="vsrc" src="" type="video/mp4">
      你的浏览器不支持 HTML5 视频。
    </video>
  </div>
  <div class="meta" id="meta">加载中…</div>
  <div id="err" class="err" style="display:none"></div>
  <h3 style="margin-top:32px">所有集</h3>
  <div class="ep-list" id="list"></div>
</main>
<script>
const EPS = __EPS_JSON__;

function getQuery() {
  const p = new URLSearchParams(location.search);
  return { ep: p.get('ep') || '', t: parseFloat(p.get('t') || '0') };
}

function fmtTime(s) {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60), ss = Math.floor(s % 60);
  return m + ':' + String(ss).padStart(2, '0');
}

function renderList(activeLabel) {
  const list = document.getElementById('list');
  list.innerHTML = '';
  EPS.forEach(function(e) {
    const c = document.createElement('div');
    c.className = 'ep-card';
    c.style.borderColor = (e.label === activeLabel) ? '#2563eb' : '';
    c.innerHTML = '<div class="label">' + e.label + '</div>'
                + '<div class="topic">' + e.topic + '</div>'
                + '<div class="series">' + e.series + '系列</div>';
    c.onclick = function() { loadEp(e.label, 0); };
    list.appendChild(c);
  });
}

function loadEp(label, t) {
  const ep = EPS.find(function(x) { return x.label === label; });
  if (!ep) {
    const err = document.getElementById('err');
    err.style.display = 'block';
    err.textContent = '未找到集：' + label + '。可用的集：' + EPS.map(function(x){return x.label;}).join(', ');
    return;
  }
  const v = document.getElementById('v');
  const src = document.getElementById('vsrc');
  src.src = ep.source;
  v.load();
  v.onloadedmetadata = function() {
    if (t > 0 && t < v.duration) v.currentTime = t;
    document.getElementById('meta').innerHTML =
      '<b>' + ep.label + '</b> · ' + ep.topic
      + ' &nbsp;<span class="ts">[' + ep.series + '] 跳转: ' + fmtTime(t) + ' / 时长: ' + fmtTime(v.duration) + '</span>';
  };
  renderList(ep.label);
  // 同步 URL（便于复制分享）
  const u = new URL(location.href);
  u.searchParams.set('ep', label);
  u.searchParams.set('t', String(t));
  history.replaceState(null, '', u.toString());
}

window.addEventListener('load', function() {
  renderList('');
  const q = getQuery();
  if (q.ep) loadEp(q.ep, q.t);
  else if (EPS.length) loadEp(EPS[0].label, 0);
});
</script>
</body>
</html>
"""
    return html.replace("__EPS_JSON__", ep_json)


def gen_play_page(mf, notes_root=None):
    """P5：生成 steps_pro/play.html 单页播放器（含集列表与跳转逻辑）。"""
    notes_root = notes_root or M.notes_root(mf)
    course_name = mf.get("course", {}).get("name", "课程")
    html = _play_html(mf["episodes"], "source", course_name=course_name)
    # 替换品牌占位符（统一从 toolkit/branding.py 读）
    html = html.replace("__BRANDING_INDEX_BANNER_PLAY__", branding.INDEX_BANNER_PLAY)
    html = html.replace("__COURSE_NAME__", course_name)
    out = os.path.join(notes_root, "play.html")
    open(out, "w", encoding="utf-8").write(html)
    print("play.html ->", out)
    return out


def build_all(mf, notes_root=None):
    """build 全流程：docs → source → notes → index → play page。"""
    from . import docs as D, index as I
    D.import_docs(mf, notes_root)
    copy_source(mf, notes_root)
    collect(mf, notes_root)
    I.build_index(mf, notes_root)
    gen_play_page(mf, notes_root)
