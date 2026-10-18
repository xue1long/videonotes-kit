# -*- coding: utf-8 -*-
"""notes 入口：python notes.py <course> <cmd>

内部转发到 toolkit.cli.main。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from toolkit.cli import main

if __name__ == "__main__":
    main()
