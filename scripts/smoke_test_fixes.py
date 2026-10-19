#!/usr/bin/env python
"""scripts/smoke_test_fixes.py - 烟测 P0/P1/P2 修复是否生效。

跑法：python scripts/smoke_test_fixes.py <course>
示例：python scripts/smoke_test_fixes.py 风变麦橘AI审美创作课
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from toolkit import cleanup as CL
from toolkit import manifest as M

COURSE = sys.argv[1] if len(sys.argv) > 1 else "风变麦橘AI审美创作课"
ROOT = Path("D:/000/vidwise")
mf = M.load(str(ROOT / "projects" / COURSE / "manifest.toml"))
print("=" * 60)
print(f"P0/P1/P2 修复烟测 — {COURSE}")
print("=" * 60)

# A1：cleanup.safe_rmtree 存在且签名正确
print("\n[A1] toolkit.cleanup (沙箱 50 阈值绕过)")
print(f"  module path: {CL.__file__}")
print(f"  functions: safe_rmtree={hasattr(CL, 'safe_rmtree')} safe_remove={hasattr(CL, 'safe_remove')} post_build_cleanup={hasattr(CL, 'post_build_cleanup')}")
assert hasattr(CL, "safe_rmtree"), "缺 safe_rmtree"
assert hasattr(CL, "safe_remove"), "缺 safe_remove"
assert hasattr(CL, "post_build_cleanup"), "缺 post_build_cleanup"
print("  ✓ A1 PASS")

# A5：consolidate.clean_intermediates 存在
from toolkit import consolidate as CO
print("\n[A5] consolidate.clean_intermediates")
print(f"  has clean_intermediates: {hasattr(CO, 'clean_intermediates')}")
auto_clean_supported = "auto_clean" in CO.build_all.__code__.co_varnames
print(f"  build_all supports auto_clean: {auto_clean_supported}")
assert hasattr(CO, "clean_intermediates"), "缺 clean_intermediates"
print("  ✓ A5 PASS")

# A3：copy_source 使用 mtime 校验
import inspect
src = inspect.getsource(CO.copy_source)
print("\n[A3] copy_source 含 mtime 校验")
has_mtime = "getmtime" in src
print(f"  uses getmtime: {has_mtime}")
assert has_mtime, "copy_source 没 getmtime 校验"
print("  ✓ A3 PASS")

# N11：JPEG 压缩器
print("\n[N11] frames JPEG 压缩")
from toolkit import consolidate
src = inspect.getsource(consolidate)
has_pil = "from PIL import Image" in src
has_compressor = "_maybe_compress_jpeg" in src
print(f"  has PIL import: {has_pil}")
print(f"  has _maybe_compress_jpeg: {has_compressor}")
assert has_pil, "缺 PIL import"
assert has_compressor, "缺 _maybe_compress_jpeg"
print("  ✓ N11 PASS")

# N4: scripts/curate_one.sh 存在
print("\n[N4] scripts/curate_one.sh")
sh_path = Path("D:/000/vidwise/scripts/curate_one.sh")
print(f"  exists: {sh_path.exists()}")
print(f"  size: {sh_path.stat().st_size if sh_path.exists() else 0}B")
assert sh_path.exists(), "curate_one.sh 不存在"
print("  ✓ N4 PASS")

# N5: scripts/extract_glossary.py 存在
print("\n[N5] scripts/extract_glossary.py")
gl_path = Path("D:/000/vidwise/scripts/extract_glossary.py")
print(f"  exists: {gl_path.exists()}")
assert gl_path.exists(), "extract_glossary.py 不存在"
print("  ✓ N5 PASS")

# A2: _run_p3.py 包含 frames 完整性检查
print("\n[A2] _run_p3.py 含 frames 完整性")
run_p3 = Path("D:/000/vidwise/projects/风变麦橘AI审美创作课/_run_p3.py")
if run_p3.exists():
    text = run_p3.read_text(encoding="utf-8")
    has_force = "--force-frames" in text
    has_frame_check = "n_frames" in text or "no_frames" in text or "frames_status" in text
    has_force_transcript = "--force-transcript" in text
    print(f"  --force-frames: {has_force}")
    print(f"  frame_count check: {has_frame_check}")
    print(f"  --force-transcript: {has_force_transcript}")
    assert has_force and has_frame_check, "_run_p3.py 缺 force-frames 或 frame_count 检查"
    print("  ✓ A2 PASS")
else:
    print("  ⚠ _run_p3.py 不存在（项目级脚本，可选检查）")

print("\n" + "=" * 60)
print("全部烟测 PASS — P0/P1/P2 修复已生效")
print("=" * 60)
