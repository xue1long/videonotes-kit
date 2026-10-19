#!/usr/bin/env bash
# scripts/curate_one.sh — 单集精校 4 步走（手动写笔记后一键 build+verify）
# 用法: bash scripts/curate_one.sh <课程> <seq>
#   例: bash scripts/curate_one.sh 风变麦橘AI审美创作课 13
# 流程:
#   1. 检查 _curated/<ep>/steps_pro.md 是否存在
#   2. 增量更新 manifest.glossary（自动从 _curated 提取）
#   3. build（包含 collect + index + play.html + source/ 复制）
#   4. verify（非破坏 diff）
set -e

COURSE="$1"
SEQ="$2"

if [ -z "$COURSE" ] || [ -z "$SEQ" ]; then
    echo "用法: bash scripts/curate_one.sh <课程> <seq>"
    echo "  例: bash scripts/curate_one.sh 风变麦橘AI审美创作课 13"
    exit 1
fi

# 1) 检查金标准
PROJ="D:/000/vidwise/projects/$COURSE"
read -r EP_DIR OUT_ROOT CUR_SUB <<< $(python -c "
import tomllib
with open(r'$PROJ/manifest.toml','rb') as f:
    mf = tomllib.load(f)
c = mf['course']
ep = next((e for e in mf['episodes'] if e['seq']=='$SEQ'), None)
print((ep['ep_dir'] if ep else ''), c['out_root'], c['curated_subdir'])
")
if [ -z "$EP_DIR" ]; then
    echo "[ERR] 找不到 seq=$SEQ 的 ep_dir"
    exit 1
fi

GOLD="$OUT_ROOT/$CUR_SUB/$EP_DIR/steps_pro.md"
if [ ! -f "$GOLD" ]; then
    echo "[ERR] 金标准文件不存在: $GOLD"
    echo "      请先手工写 $GOLD"
    exit 1
fi
echo "[1/4] ✓ 金标准存在: $GOLD"

# 2) 全量重建 glossary（去重）
echo "[2/4] 更新 glossary..."
PYTHONIOENCODING=utf-8 "C:/Program Files/Python311/python.exe" \
    D:/000/vidwise/scripts/rebuild_glossary.py "$COURSE"

# 3) build
echo "[3/4] build..."
cd D:/000/vidwise
PYTHONIOENCODING=utf-8 PYTHONPATH="D:/000/video2docs/venv/Lib/site-packages" \
    "C:/Program Files/Python311/python.exe" notes.py "$COURSE" build 2>&1 | tail -5

# 4) verify
echo "[4/4] verify..."
PYTHONIOENCODING=utf-8 PYTHONPATH="D:/000/video2docs/venv/Lib/site-packages" \
    "C:/Program Files/Python311/python.exe" notes.py "$COURSE" verify 2>&1 | tail -10
