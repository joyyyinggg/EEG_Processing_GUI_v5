# -*- coding: utf-8 -*-
"""
utils/widgets.py
================
共用 Qt 小元件工廠函式。
所有 Dialog / MainWindow 統一呼叫，避免重複的樣式設定。
"""

from PyQt5.QtWidgets import QLabel, QFrame, QListWidget
from PyQt5.QtGui import QFont

from styles import C, LIST_STYLE


def make_label(text: str, size: int = 13, bold: bool = False,
               color: str = None) -> QLabel:
    """建立一個字型 / 顏色可設定的 QLabel。"""
    lbl  = QLabel(text)
    font = QFont()
    font.setPointSize(size)
    if bold:
        font.setBold(True)
    lbl.setFont(font)
    if color:
        lbl.setStyleSheet(f'color: {color};')
    return lbl


def make_divider() -> QFrame:
    """建立一條水平分隔線。"""
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f'color: {C["border"]};')
    return line


def tag_label(text: str, bg: str, fg: str) -> QLabel:
    """建立圓角 tag 標籤（Epilepsy / Normal / session 等小標記）。"""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f'background: {bg}; color: {fg}; border-radius: 4px;'
        f'padding: 2px 7px; font-size: 11px; font-weight: 600;'
    )
    lbl.setFixedHeight(22)
    return lbl


def make_file_list() -> QListWidget:
    """建立統一樣式的 QListWidget（用於 Files 分頁）。"""
    lst = QListWidget()
    lst.setStyleSheet(LIST_STYLE)
    return lst
