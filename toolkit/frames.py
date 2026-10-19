# -*- coding: utf-8 -*-
"""frames：按需抽帧层（L0.5）。

为什么独立成模块（而不塞进 draft.build）：
  - draft.build() 必须保持纯函数（verify 靠反复调用它做回归，不能有写副作用）
  - ffmpeg 是外部二进制，依赖隔离在一个文件里才好做"缺失即降级"
  - 与 draft.derive_steps 严格同源：保证「抽帧的时间点」与「笔记引用的时间点」
    一一对齐（docs/P9-on-demand-frames.md D10）

约定：
  - 帧文件命名：frame_<m>m<SS>s.png（与 vidwise 旧约定一致，让 collect IMG_RE 复用）
  - 全部操作幂等：已存在的帧直接返回，不重复抽
  - 失败仅 WARN，不抛错：单集失败不阻断 19 集 build
"""
import os
import shutil
import subprocess

from . import draft


# ---- 能力检测 ----

def available() -> bool:
    """ffmpeg 是否在 PATH。"""
    return shutil.which("ffmpeg") is not None


# ---- 源视频定位 ----

def resolve_video(mf, ep) -> str | None:
    """定位源 mp4：优先包内 steps_pro/source/<series>/<原名>.mp4，再 manifest 路径。

    返回存在的路径；都不存在返回 None（caller 决定降级）。
    """
    series = ep.get("series", "")
    sv = (ep.get("source_video", "") or "").replace("\\", "/")
    if not sv:
        return None
    base = os.path.basename(sv)

    # 1. 包内副本（最优先：自包含、随包走）
    notes_root = mf["course"].get("notes_subdir", "steps_pro")
    pkg = os.path.join(mf["course"]["out_root"], notes_root, "source",
                       series, base)
    if os.path.isfile(pkg):
        return pkg

    # 2. manifest source_video 绝对路径
    if os.path.isabs(sv) and os.path.isfile(sv):
        return sv

    # 3. 相对 video_root
    vr = mf["course"].get("video_root", "")
    if vr:
        cand = os.path.join(vr, sv) if not os.path.isabs(sv) else sv
        if os.path.isfile(cand):
            return cand

    return None


# ---- 步骤时间点（与 draft 严格同源） ----

def step_times(transcript_path: str, max_steps: int = 80) -> list:
    """从 transcript.json 推出步骤时间点（秒，float），与 draft.build 严格同源。

    实现：直接复用 draft.derive_steps。frames.py 与 draft.py 都只读 transcript
    + 各自纯函数推导；不存任何中间状态；两边永远输出同样的 [t, ...]。
    """
    import json
    if not os.path.isfile(transcript_path):
        return []
    d = json.load(open(transcript_path, encoding="utf-8"))
    segs = d.get("segments") or d.get("chunks") or []
    segs = [s for s in segs if (s.get("text") or "").strip()]
    return [int(s["t"]) for s in draft.derive_steps(segs, max_steps)]


# ---- 单帧抽取 ----

def extract_at(video: str, seconds: int, dst_dir: str) -> str | None:
    """对单个时间点 ffmpeg -ss 精确抽帧。已存在则跳过（幂等）。返回输出路径或 None。"""
    dst = os.path.join(dst_dir, f"frame_{seconds // 60}m{seconds % 60:02d}s.png")
    if os.path.isfile(dst) and os.path.getsize(dst) > 0:
        return dst
    os.makedirs(dst_dir, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(int(seconds)),
         "-i", video, "-frames:v", "1", "-y", dst],
        capture_output=True, text=True, errors="replace",
    )
    if r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 0:
        return dst
    # 失败清理（避免空文件被下次误判"已存在"）
    if os.path.isfile(dst):
        try:
            os.remove(dst)
        except OSError:
            pass
    return None


# ---- 按需编排 ----

def ensure(mf, ep, follow_up: int = 0) -> dict:
    """确保该集 frames/ 含所需帧。幂等。返回统计 dict：

      {"skipped": reason} 跳过；
      或 {"video": path, "times": N, "made": M, "fail": F, "out": frames_dir}
    """
    out_root = mf["course"]["out_root"]
    ep_dir = ep.get("ep_dir", "")
    frames_dir = os.path.join(out_root, ep_dir, "frames")
    transcript = os.path.join(out_root, ep_dir, "transcript.json")

    if not os.path.isfile(transcript):
        return {"skipped": "no_transcript", "out": frames_dir}
    if not available():
        return {"skipped": "no_ffmpeg", "out": frames_dir}

    video = resolve_video(mf, ep)
    if not video:
        return {"skipped": "no_video", "out": frames_dir}

    times = step_times(transcript, mf["draft"].get("max_steps", 80))
    if not times:
        return {"skipped": "no_steps", "out": frames_dir, "video": video}

    os.makedirs(frames_dir, exist_ok=True)
    made = fail = 0
    for t in times:
        for tt in ([t] + ([t + follow_up] if follow_up else [])):
            if extract_at(video, tt, frames_dir):
                made += 1
            else:
                fail += 1
    return {"video": video, "out": frames_dir, "times": len(times),
            "made": made, "fail": fail}
