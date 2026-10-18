# -*- coding: utf-8 -*-
"""清单加载：课程/集/文档配置（TOML，Python 3.11 标准库 tomllib，免装 PyYAML）。"""
import tomllib


def load(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


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
