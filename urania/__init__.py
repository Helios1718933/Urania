"""Urania —— 知识点点名册：随机抽取未学习的知识点并安排复习。

核心功能（随机抽取、复习调度、内置 SQLite 数据库）全部由 Python 标准库实现，
前端为遵循 Apple HIG 风格的本地 Web 界面，可选 pywebview 提供原生窗口。
"""
from .config import APP_NAME, APP_VERSION  # noqa: F401

__all__ = ["APP_NAME", "APP_VERSION"]
