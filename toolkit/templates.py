# -*- coding: utf-8 -*-
"""templates：模板渲染层（零第三方依赖，仅用标准库 string.Template）。

为什么需要：项目文档（AGENT.md / README.notes.md / VIDEONOTES-KIT_ROADMAP.md）
承诺 templates/* 是项目骨架的一部分，但历史实现是 toolkit/*.py 用 Python 字符串
直接拼接（curate.py:165-246, index.py:62-163），模板与代码完全脱节 → 模板失效。

本模块把 templates/*.md 真正接到代码上：
  - 占位符形如 $varname，避免与 Markdown 表格中的 {} / { 出现歧义
  - safe_substitute 对未提供的占位符保留为 $xxx 不报错，方便「可选」填充
  - 控制流（if/for）由外部 Python for 循环处理，模板只放静态骨架
  - 整段动态内容（如分阶段步骤、表格行）由外部拼好后整体替换模板里的 $block

约定（双端需一致）：
  1) 模板中所有需要被填充的占位符用 $name 形式（string.Template 语法）
  2) 反引号包裹的 `` `$xxx` `` 不要出现在模板里——Python 的 string.Template
     不会区分反引号里的 $，会把里面的 $xxx 也当占位符替换
  3) 控制流（if/for/loop）由 Python 处理；模板里只放 $block 占位 + 文字说明
  4) 模板顶部可用 HTML 注释 <!-- ... --> 写渲染约定文档

修改方式（最重要）：
  - 改模板外观 / 加新段落：只改 templates/*.md + 跑 build，toolkit/*.py 不动
  - 改动态逻辑（如何填每行）：改 toolkit/*.py
"""
from pathlib import Path
from string import Template


# 模板目录：项目根 / templates/
_DIR = Path(__file__).parent.parent / "templates"


class TemplateError(Exception):
    """模板渲染错误（如模板不存在 / 占位符语法错误）。"""


def render(name: str, **kw) -> str:
    """读 templates/<name>.md，用 kw 填占位符；未填占位符保留为 $xxx。

    Args:
        name: 模板文件名（不含 .md 后缀），如 "steps_pro" / "index"
        **kw: 占位符名 → 值。值可以是 str / int / list，由 string.Template
              内部调用 str()；因此预先在调用方拼好字符串最稳。

    Returns:
        渲染后的 Markdown 文本。
    """
    path = _resolve(name)
    if not path.is_file():
        raise TemplateError(f"模板文件不存在: {path}")
    src = path.read_text(encoding="utf-8")
    return Template(src).safe_substitute(**kw)


def path(name: str) -> Path:
    """拿到模板原始 Path（如需整段替换、不经 string.Template 时使用）。"""
    p = _resolve(name)
    if not p.is_file():
        raise TemplateError(f"模板文件不存在: {p}")
    return p


def _resolve(name: str) -> Path:
    """统一解析：允许 'steps_pro' / 'steps_pro.md' 两种传入。"""
    if not name.endswith(".md"):
        name = name + ".md"
    return _DIR / name
