# -*- coding: utf-8 -*-
"""docs：按 manifest 的 docs 段，把课程配套文档（txt/md/xlsx）归档进 notes/参考文档/，规则化命名。"""
import os
import shutil
from . import manifest as M


def import_docs(mf, notes_root=None):
    notes_root = notes_root or M.notes_root(mf)
    doc_root = mf["course"]["doc_root"]
    ref = M.refdoc_root(mf) if notes_root is None else os.path.join(notes_root, mf["course"]["refdoc_subdir"])
    os.makedirs(ref, exist_ok=True)
    for d in mf["docs"]:
        s = os.path.join(doc_root, d["src"])
        t = os.path.join(ref, d["dest"])
        if not os.path.isfile(s):
            print("MISS doc:", s); continue
        shutil.copy2(s, t)
        print("doc ->", d["dest"])
    return len(mf["docs"])
