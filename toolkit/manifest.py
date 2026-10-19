# -*- coding: utf-8 -*-
"""清单加载：课程/集/文档配置（TOML，Python 3.11 标准库 tomllib，免装 PyYAML）。"""
import os
import tomllib


def _apply_env_overrides(mf: dict) -> dict:
    """把 course.out_root 的父级前缀换成本机路径（VIDEONOTES_OUT_ROOT）。

    仓库里的 manifest 记的是某台机器的绝对路径（如
    `E:/002-Pr/videonotes-kit/out/风变麦橘AI审美创作课`）。换机器跑时只需：

        set VIDEONOTES_OUT_ROOT=D:/000/vidwise/out      # Windows
        export VIDEONOTES_OUT_ROOT=/data/videonotes/out  # macOS / Linux

    规则：只替换父级前缀，**末级课程目录名保持不变**（这样不用为每门课分别设）。
    若传入的已是完整课程目录（末级同名），则原样使用。manifest 文件本身不改。
    """
    env = os.environ.get("VIDEONOTES_OUT_ROOT", "").strip()
    course = mf.get("course") or {}
    raw = course.get("out_root")
    if not env or not raw:
        return mf
    env = env.replace("\\", "/").rstrip("/")
    raw_n = str(raw).replace("\\", "/").rstrip("/")
    leaf = raw_n.rsplit("/", 1)[-1]
    if env.rsplit("/", 1)[-1] != leaf:
        env = f"{env}/{leaf}"
    course["out_root"] = env
    return mf


def load(path: str) -> dict:
    with open(path, "rb") as f:
        mf = tomllib.load(f)
    return _apply_env_overrides(mf)


def course_out_root(mf: dict) -> str:
    return mf["course"]["out_root"]


def episode_out_dir(mf: dict, ep: dict) -> str:
    return f"{mf['course']['out_root']}/{ep['ep_dir']}"


def notes_root(mf: dict) -> str:
    return f"{mf['course']['out_root']}/{mf['course']['notes_subdir']}"


def curated_root(mf: dict) -> str:
    return f"{mf['course']['out_root']}/{mf['course']['curated_subdir']}"


def refdoc_root(mf: dict) -> str:
    return f"{notes_root(mf)}/{mf['course']['refdoc_subdir']}"
