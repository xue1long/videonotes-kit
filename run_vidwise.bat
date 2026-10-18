@echo off
REM vidwise 本地运行包装（绕过沙箱 venv python + 强制离线加载本地 Whisper 模型）
set HF_HOME=C:\Users\HP\.cache\huggingface
set HF_HUB_OFFLINE=1
set PYTHONPATH=D:\000\video2docs\venv\Lib\site-packages;D:\000\vidwise\src
"C:\Program Files\Python311\python.exe" -m vidwise.cli %*
