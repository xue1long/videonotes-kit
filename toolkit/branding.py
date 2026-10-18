# -*- coding: utf-8 -*-
"""branding：项目级品牌文案单一引用源。

为什么需要：项目名/副标题/管线描述等文案原本散落在 5+ 个 .py / 模板 / 文档里，
每次更名（如 videonotes-kit）都要全工程 grep+Edit 改 5+ 处。

本模块只放字符串常量。所有 .py 模板与文档通过 from toolkit import branding 引用。

修改方式：只改本文件的常量 + 跑 `python notes.py <课> build` 即全工程更新。
"""
# 项目品牌
NAME = "videonotes-kit"            # 短名（包名/CLI 后缀/索引行）
DISPLAY_NAME = "videonotes-kit"    # 显示名（文档标题）
PARENT = "vidwise"                 # 上游父项目

# 一句话定位（README 头部 / 文档开头）
TAGLINE = "「视频 + 文档 → 自包含图文笔记」项目"
ONE_LINER = "本仓库被整改为「视频 + 文档 → 图文笔记」项目（2026-10）"

# 产物内 banner 文案（用户每次打开总索引 / play.html 都看到）
# 模板："| 管线：{NAME}（基于 {PARENT} 本地转写 + 自研 toolkit，**无 API key**）"
INDEX_BANNER = (
    "自动生成 ｜ 管线：" + NAME + "（基于 " + PARENT
    + " 本地转写 + 自研 toolkit，**无 API key**）"
)
INDEX_BANNER_PLAY = (
    "本页面由 " + NAME + "（基于 " + PARENT + "）自动生成（无 API key）"
)

# 工具箱内模板（用户在 _curated/<ep>/ 下打开 .md 顶部看到）
TEMPLATE_BANNER = (
    "steps_pro.md 模板 · " + NAME + " Tier1 精校层  (P4 升级版)"
)
TEMPLATE_INDEX_BANNER = INDEX_BANNER

# 关键术语（行业对话常用）
TERMS = {
    "self_contained": "自包含图文笔记包（图片+视频+播放页都内嵌）",
    "no_api_key": "纯本地、零 API key",
}
