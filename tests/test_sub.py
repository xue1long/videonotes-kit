# -*- coding: utf-8 -*-
"""toolkit.sub：SRT 字幕（B 站 AI 字幕）→ transcript.json 桥接的单元 + 集成测试。"""
import json
import os

import pytest

from toolkit import draft, sub

SRT = """1
00:00:01,000 --> 00:00:03,500
大家好，今天我们点击新建项目

2
00:00:04,000 --> 00:00:06,200
然后选择模板，
再确认保存
"""

FRONTMATTER_SRT = """---
title: BV1Test
UP主: 某UP
---

1
00:00:00,000 --> 00:00:02,000
打开剪映，点击开始创作
"""


def test_strip_frontmatter():
    assert sub.strip_frontmatter(FRONTMATTER_SRT).lstrip().startswith("1\n")


def test_strip_frontmatter_stacks_blocks():
    doubled = "---\na: 1\n---\n---\nb: 2\n---\nbody"
    assert sub.strip_frontmatter(doubled) == "body"


def test_strip_frontmatter_absent_is_noop():
    assert sub.strip_frontmatter(SRT) == SRT


def test_parse_srt_basic():
    segs = sub.parse_srt(SRT)
    assert len(segs) == 2
    assert segs[0] == {"start": 1.0, "end": 3.5, "text": "大家好，今天我们点击新建项目"}
    assert segs[1]["start"] == 4.0 and segs[1]["end"] == 6.2


def test_parse_srt_short_ms_crlf_and_no_index():
    # 无序号行 + 毫秒只给 1–2 位 + CRLF
    raw = "00:00:01,5 --> 00:00:02,25\r\n点击确定\r\n\r\n"
    segs = sub.parse_srt(raw)
    assert len(segs) == 1
    assert segs[0]["start"] == 1.5 and segs[0]["end"] == 2.25
    assert segs[0]["text"] == "点击确定"


def test_parse_srt_dot_ms_separator():
    raw = "1\n00:00:01.500 --> 00:00:03.000\n点击保存\n\n"
    segs = sub.parse_srt(raw)
    assert segs[0]["start"] == 1.5 and segs[0]["end"] == 3.0


def test_parse_srt_multiline_join_cjk_and_english():
    raw = "1\n00:00:01,000 --> 00:00:03,000\n打开\n设置面板\n\n"
    assert sub.parse_srt(raw)[0]["text"] == "打开设置面板"

    raw_en = "1\n00:00:01,000 --> 00:00:03,000\nrun the\ncommand\n\n"
    assert sub.parse_srt(raw_en)[0]["text"] == "run the command"


def test_parse_srt_skips_empty_cues():
    raw = "1\n00:00:01,000 --> 00:00:02,000\n\n\n2\n00:00:03,000 --> 00:00:04,000\n有字\n\n"
    segs = sub.parse_srt(raw)
    assert len(segs) == 1 and segs[0]["start"] == 3.0


def test_render_is_deterministic_and_whisper_shaped(tmp_path):
    p = tmp_path / "BV1Test.md"
    p.write_text(FRONTMATTER_SRT, encoding="utf-8")
    a, b = sub.render(str(p)), sub.render(str(p))
    assert a == b  # verify 靠逐字节比对做非破坏校验

    doc = json.loads(a)
    assert doc["language"] == "zh"
    assert [s["start"] for s in doc["segments"]] == [0.0]
    assert doc["segments"][0]["text"] == "打开剪映，点击开始创作"
    assert isinstance(doc["segments"][0]["start"], float)


def test_render_rejects_non_srt(tmp_path):
    p = tmp_path / "bad.md"
    p.write_text("# 只有标题没有时间轴\n", encoding="utf-8")
    with pytest.raises(ValueError, match="未从字幕解析出任何条目"):
        sub.render(str(p))


def test_convert_writes_transcript(tmp_path):
    src, out = tmp_path / "a.md", tmp_path / "ep"
    src.write_text(SRT, encoding="utf-8")
    n = sub.convert(str(src), str(out))
    assert n == 2
    data = json.load(open(os.path.join(str(out), "transcript.json"), encoding="utf-8"))
    assert len(data["segments"]) == 2


def test_draft_consumes_converted_subtitle(tmp_path):
    """端到端：SRT → transcript.json → draft.build 出 steps_v2.md。"""
    ep = tmp_path / "ep1"
    ep.mkdir()
    src = tmp_path / "s.md"
    src.write_text(SRT, encoding="utf-8")
    sub.convert(str(src), str(ep))

    n = draft.build(str(ep))
    md = open(str(ep / "steps_v2.md"), encoding="utf-8").read()
    assert n >= 1
    assert "## 操作步骤" in md
    assert "点击新建项目" in md or "新建项目" in md