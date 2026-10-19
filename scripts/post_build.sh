#!/usr/bin/env bash
# scripts/post_build.sh - 独立运行清理（不绑定 build 流程）
# 用法：
#   scripts/post_build.sh <course>                # 实际清理
#   scripts/post_build.sh <course> --dry-run      # 只报告不删
#   scripts/post_build.sh <course> --keep-frames  # 保留 frames/（保守）
set -e
if [ -z "$1" ]; then echo "用法: $0 <course> [--dry-run] [--keep-frames]"; exit 1; fi
COURSE="$1"
shift
DRY=""
KEEP=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY="--dry-run" ;;
    --keep-frames) KEEP="--keep-frames" ;;
  esac
done
cd "$(dirname "$0")/.."
PYTHONIOENCODING=utf-8 PYTHONPATH="D:/000/video2docs/venv/Lib/site-packages" \
  "C:/Program Files/Python311/python.exe" -m toolkit.cli "$COURSE" build --auto-clean "$DRY" "$KEEP"
