# -*- coding: utf-8 -*-
"""
gui/dialogs_raw.py
==================
原始 EEG 波形檢視視窗 (RawInspectDialog) 與
插值前後對比視窗 (InterpolationCompareDialog)。

兩個 Dialog 均支援：
  - 上一筆 / 下一筆 / 跳過 / 確認 等導航動作
  - 時間滑桿即時重繪
  - 人工壞通道勾選修改
"""

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavToolbar,
)

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QScrollArea, QWidget, QSlider, QSpinBox,
)
from PyQt5.QtGui import QFont

from config import CH_NAMES, SFREQ
from styles import C, BTN_OUTLINE, BTN_SUCCESS, BTN_DANGER, SLIDER_STYLE
from utils.widgets import make_label, make_divider


# ─────────────────────────────────────────────────────────────
#  RawInspectDialog
# ─────────────────────────────────────────────────────────────
class RawInspectDialog(QtWidgets.QDialog):
    """
    顯示全通道 raw EEG，下方滑桿拉時間，右側勾選壞通道。

    Attributes
    ----------
    confirmed_bads : list[str]   使用者確認的壞通道名稱清單
    action         : str         'confirm' | 'prev' | 'next' | 'skip'
    """

    def __init__(self, raw, auto_bads: list, file_stem: str,
                 file_index: int, total_files: int, parent=None):
        super().__init__(parent)
        self.raw            = raw
        self.file_stem      = file_stem
        self.file_index     = file_index
        self.total_files    = total_files
        self.confirmed_bads = list(auto_bads)
        self.action         = 'confirm'
        self.setWindowTitle(
            f'Raw Data Inspection — {file_stem}  [{file_index}/{total_files}]')
        self.setMinimumSize(1250, 800)
        self.setStyleSheet(f'background: {C["bg"]};')
        self._build_ui()
        self._draw()

    # ── UI 建構 ─────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # 標題列
        hdr = QHBoxLayout()
        hdr.addWidget(make_label(
            f'Raw EEG Inspection: {self.file_stem}  '
            f'[{self.file_index}/{self.total_files}]', 13, bold=True))
        hdr.addStretch()
        hdr.addWidget(make_label(
            '紅色 = 自動偵測壞通道，可手動勾選修改', 11, color=C['text_sub']))
        root.addLayout(hdr)
        root.addWidget(make_divider())

        body = QHBoxLayout()

        # ── 左側：波形 ──
        left = QVBoxLayout()

        ctrl = QHBoxLayout()
        ctrl.addWidget(make_label('Window (s):', 11))
        self.t_win = QSpinBox()
        self.t_win.setRange(2, 60); self.t_win.setValue(5)
        self.t_win.setSingleStep(5); self.t_win.setFixedWidth(65)
        self.t_win.valueChanged.connect(self._on_win_changed)
        ctrl.addWidget(self.t_win)

        ctrl.addSpacing(12)
        ctrl.addWidget(make_label('Scale (µV):', 11))
        self.scale = QSpinBox()
        self.scale.setRange(10, 2000); self.scale.setValue(200)
        self.scale.setSingleStep(50); self.scale.setFixedWidth(75)
        self.scale.valueChanged.connect(self._draw)
        ctrl.addWidget(self.scale)

        ctrl.addStretch()
        total_s = int(self.raw.n_times / SFREQ)
        self.time_lbl = make_label('0 s', 11, color=C['accent'])
        ctrl.addWidget(self.time_lbl)
        ctrl.addWidget(make_label(
            f'/ {total_s} s  |  {len(CH_NAMES)} ch', 11, color=C['text_sub']))
        left.addLayout(ctrl)

        self.fig    = Figure(figsize=(10, 7), facecolor='white')
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavToolbar(self.canvas, self)
        self.toolbar.setStyleSheet('background: white;')
        left.addWidget(self.toolbar)
        left.addWidget(self.canvas)

        # 時間滑桿
        slider_row = QHBoxLayout()
        slider_row.addWidget(make_label('Time:', 11))
        self.t_slider = QSlider(Qt.Horizontal)
        self.t_slider.setRange(0, max(0, total_s - self.t_win.value()))
        self.t_slider.setValue(0)
        self.t_slider.setSingleStep(1); self.t_slider.setPageStep(5)
        self.t_slider.setTickInterval(30)
        self.t_slider.setTickPosition(QSlider.TicksBelow)
        self.t_slider.setStyleSheet(SLIDER_STYLE)
        self.t_slider.valueChanged.connect(self._on_slider)
        slider_row.addWidget(self.t_slider)
        slider_row.addWidget(
            make_label(f'{total_s}s', 11, color=C['text_sub']))
        left.addLayout(slider_row)

        body.addLayout(left, stretch=5)

        # ── 右側：通道勾選 ──
        right = QVBoxLayout()
        right.addWidget(make_label('Channel Selection', 13, bold=True))
        right.addWidget(make_label('✓ = interpolate', 11, color=C['text_sub']))
        right.addWidget(make_divider())

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFixedWidth(175)
        scroll.setStyleSheet(
            f'border: 1px solid {C["border"]}; border-radius: 6px;')
        inner = QWidget(); inner.setStyleSheet('background: white;')
        vbox  = QVBoxLayout(inner); vbox.setSpacing(4)

        self.ch_checks = {}
        for ch in CH_NAMES:
            cb = QCheckBox(ch)
            cb.setChecked(ch in self.confirmed_bads)
            cb.setFont(QFont('', 12))
            if ch in self.confirmed_bads:
                cb.setStyleSheet(f'color: {C["danger"]}; font-weight: 600;')
            cb.stateChanged.connect(
                lambda s, c=ch, b=cb: self._on_toggle(c, b))
            vbox.addWidget(cb)
            self.ch_checks[ch] = cb
        vbox.addStretch()
        scroll.setWidget(inner)
        right.addWidget(scroll)

        right.addSpacing(6)
        btn_none = QPushButton('Clear all')
        btn_none.setStyleSheet(BTN_OUTLINE)
        btn_none.clicked.connect(self._clear_all)
        right.addWidget(btn_none)
        right.addStretch()

        self.bad_count_lbl = make_label('', 11)
        self._update_badge()
        right.addWidget(self.bad_count_lbl)

        body.addLayout(right, stretch=1)
        root.addLayout(body)

        # ── 底部按鈕 ──
        root.addWidget(make_divider())
        bot = QHBoxLayout()

        btn_prev = QPushButton('◀ 上一筆')
        btn_prev.setStyleSheet(BTN_OUTLINE)
        btn_prev.setEnabled(self.file_index > 1)
        btn_prev.clicked.connect(self._go_prev)
        bot.addWidget(btn_prev)

        btn_skip = QPushButton('跳過此筆')
        btn_skip.setStyleSheet(BTN_OUTLINE)
        btn_skip.clicked.connect(self._go_skip)
        bot.addWidget(btn_skip)

        bot.addStretch()

        btn_cancel = QPushButton('Cancel')
        btn_cancel.setStyleSheet(BTN_OUTLINE)
        btn_cancel.clicked.connect(self.reject)
        bot.addWidget(btn_cancel)

        btn_next = QPushButton('確認並看下一筆 ▶')
        btn_next.setStyleSheet(BTN_OUTLINE)
        btn_next.setEnabled(self.file_index < self.total_files)
        btn_next.clicked.connect(self._go_next)
        bot.addWidget(btn_next)

        btn_ok = QPushButton('✔ Confirm & Continue')
        btn_ok.setStyleSheet(BTN_SUCCESS)
        btn_ok.clicked.connect(self._go_confirm)
        bot.addWidget(btn_ok)

        root.addLayout(bot)

    # ── 事件 ──────────────────────────────────────────────────
    def _on_slider(self, val):
        self.time_lbl.setText(f'{val} s')
        self._draw()

    def _on_win_changed(self):
        total_s = int(self.raw.n_times / SFREQ)
        self.t_slider.setMaximum(max(0, total_s - self.t_win.value()))
        self._draw()

    def _on_toggle(self, ch: str, cb: QCheckBox):
        if cb.isChecked():
            if ch not in self.confirmed_bads:
                self.confirmed_bads.append(ch)
            cb.setStyleSheet(f'color: {C["danger"]}; font-weight: 600;')
        else:
            self.confirmed_bads = [c for c in self.confirmed_bads if c != ch]
            cb.setStyleSheet('')
        self._update_badge()
        self._draw()

    def _clear_all(self):
        self.confirmed_bads = []
        for cb in self.ch_checks.values():
            cb.blockSignals(True)
            cb.setChecked(False); cb.setStyleSheet('')
            cb.blockSignals(False)
        self._update_badge(); self._draw()

    def _update_badge(self):
        n   = len(self.confirmed_bads)
        pct = n / len(CH_NAMES) * 100
        color = (C['danger']  if pct > 22 else
                 C['warning'] if pct > 10 else C['success'])
        self.bad_count_lbl.setText(
            f'Bad channels: {n}/{len(CH_NAMES)} ({pct:.0f}%)')
        self.bad_count_lbl.setStyleSheet(
            f'color: {color}; font-weight: 600; font-size: 12px;')

    def _draw(self):
        self.fig.clear()
        ax   = self.fig.add_subplot(111)
        t0   = self.t_slider.value()
        win  = self.t_win.value()
        sc   = self.scale.value()
        i0   = int(t0 * SFREQ)
        i1   = min(int((t0 + win) * SFREQ), self.raw.n_times)
        data = self.raw.get_data()[:, i0:i1] * 1e6
        tvec = np.linspace(t0, t0 + win, i1 - i0)
        n_ch = len(CH_NAMES)
        for i, ch in enumerate(CH_NAMES):
            offset = (n_ch - 1 - i) * sc
            color  = C['danger'] if ch in self.confirmed_bads else '#3B82F6'
            lw     = 1.0        if ch in self.confirmed_bads else 0.6
            ax.plot(tvec, data[i] + offset, color=color, linewidth=lw)
            ax.text(t0 - win * 0.01, offset, ch,
                    ha='right', va='center', fontsize=8,
                    color=C['danger'] if ch in self.confirmed_bads else C['text'])
        ax.set_xlim(t0, t0 + win)
        ax.set_xlabel('Time (s)', fontsize=10)
        ax.set_yticks([])
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.set_facecolor('white')
        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ── 動作 ──────────────────────────────────────────────────
    def _go_confirm(self): self.action = 'confirm'; self.accept()
    def _go_next(self):    self.action = 'next';    self.accept()
    def _go_prev(self):    self.action = 'prev';    self.accept()
    def _go_skip(self):    self.action = 'skip';    self.accept()


# ─────────────────────────────────────────────────────────────
#  InterpolationCompareDialog
# ─────────────────────────────────────────────────────────────
class InterpolationCompareDialog(QtWidgets.QDialog):
    """
    插值完成後顯示兩欄對比圖（插值前 vs 插值後），
    提供「重新插值」按鈕。

    Attributes
    ----------
    action : str   'ok' | 're_interp'
    """

    def __init__(self, raw_before_interp, raw_after_interp,
                 confirmed_bads: list, file_stem: str,
                 file_index: int, total_files: int, parent=None):
        super().__init__(parent)
        self.raw_before  = raw_before_interp
        self.raw_after   = raw_after_interp
        self.bads        = confirmed_bads
        self.file_stem   = file_stem
        self.file_index  = file_index
        self.total_files = total_files
        self.action      = 'ok'
        self.setWindowTitle(
            f'Interpolation Check — {file_stem}  [{file_index}/{total_files}]')
        self.setMinimumSize(1200, 760)
        self.setStyleSheet(f'background: {C["bg"]};')
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.addWidget(make_label(
            f'Interpolation Before / After — {self.file_stem}  '
            f'[{self.file_index}/{self.total_files}]', 13, bold=True))
        hdr.addStretch()
        n_bad       = len(self.bads)
        badge_color = (C['danger']  if n_bad > 3 else
                       C['warning'] if n_bad > 1 else C['success'])
        badge = make_label(
            f'Interpolated: {n_bad} channels: '
            f'{", ".join(self.bads) if self.bads else "None"}',
            11, color=badge_color)
        badge.setStyleSheet(f'color: {badge_color}; font-weight: 600;')
        hdr.addWidget(badge)
        root.addLayout(hdr)
        root.addWidget(make_divider())

        ctrl = QHBoxLayout()
        ctrl.addWidget(make_label('Scale (µV):', 11))
        self.scale = QSpinBox()
        self.scale.setRange(10, 2000); self.scale.setValue(50)
        self.scale.setSingleStep(50); self.scale.setFixedWidth(80)
        self.scale.valueChanged.connect(self._draw)
        ctrl.addWidget(self.scale)
        ctrl.addStretch()
        total_s = int(self.raw_before.n_times / SFREQ)
        self.time_lbl = make_label('0 s', 11, color=C['accent'])
        ctrl.addWidget(self.time_lbl)
        ctrl.addWidget(make_label(f'/ {total_s} s', 11, color=C['text_sub']))
        root.addLayout(ctrl)

        self.fig    = Figure(figsize=(14, 7), facecolor='white')
        self.canvas = FigureCanvas(self.fig)
        root.addWidget(NavToolbar(self.canvas, self))
        root.addWidget(self.canvas)

        slider_row = QHBoxLayout()
        slider_row.addWidget(make_label('Time:', 11))
        self.t_slider = QSlider(Qt.Horizontal)
        self.t_slider.setRange(0, max(0, total_s - 30))
        self.t_slider.setValue(0); self.t_slider.setSingleStep(1)
        self.t_slider.setPageStep(5); self.t_slider.setTickInterval(30)
        self.t_slider.setTickPosition(QSlider.TicksBelow)
        self.t_slider.setStyleSheet(SLIDER_STYLE)
        self.t_slider.valueChanged.connect(self._on_slider)
        slider_row.addWidget(self.t_slider)
        slider_row.addWidget(make_label(f'{total_s}s', 11, color=C['text_sub']))
        root.addLayout(slider_row)
        root.addWidget(make_divider())

        bot = QHBoxLayout()
        btn_reinterp = QPushButton('Re-interpolate（重新插值）')
        btn_reinterp.setStyleSheet(BTN_DANGER)
        btn_reinterp.clicked.connect(self._go_reinterp)
        bot.addWidget(btn_reinterp)
        bot.addStretch()
        hint = make_label(
            'Check green channels (interpolated). If unsatisfactory → Re-interpolate.',
            11, color=C['text_sub'])
        bot.addWidget(hint)
        bot.addStretch()
        btn_ok = QPushButton('OK — Proceed to ICA')
        btn_ok.setStyleSheet(BTN_SUCCESS)
        btn_ok.clicked.connect(self._go_ok)
        bot.addWidget(btn_ok)
        root.addLayout(bot)

        self._draw()

    def _on_slider(self, val):
        self.time_lbl.setText(f'{val} s')
        self._draw()

    def _draw(self):
        self.fig.clear()
        t0   = self.t_slider.value()
        sc   = self.scale.value()
        i0   = int(t0 * SFREQ)
        i1   = min(i0 + 30 * SFREQ, self.raw_before.n_times)
        tvec = np.linspace(t0, t0 + 30, i1 - i0)

        d_bef = self.raw_before.get_data()[:, i0:i1] * 1e6
        d_aft = self.raw_after.get_data()[:, i0:i1]  * 1e6
        n_ch  = len(CH_NAMES)

        for col, (dat, title, dflt) in enumerate([
            (d_bef, 'Before Interpolation', '#3B82F6'),
            (d_aft, 'After Interpolation',  '#3B82F6'),
        ]):
            ax = self.fig.add_subplot(1, 2, col + 1)
            for i, ch in enumerate(CH_NAMES):
                off    = (n_ch - 1 - i) * sc
                is_bad = ch in self.bads
                color  = (C['danger']   if col == 0 and is_bad else
                          '#16A34A'     if col == 1 and is_bad else dflt)
                lw     = 1.0 if is_bad else 0.5
                ax.plot(tvec, dat[i] + off, color=color, linewidth=lw)
                ax.text(t0 - 0.3, off, ch, ha='right', va='center',
                        fontsize=7,
                        color=(C['danger'] if col == 0 and is_bad else
                               '#16A34A'   if col == 1 and is_bad else C['text']))
            ax.set_title(title, fontsize=12, color=C['text'])
            ax.set_xlabel('Time (s)', fontsize=9)
            ax.set_xlim(t0, t0 + 30)
            ax.set_yticks([])
            ax.spines[['top', 'right', 'left']].set_visible(False)

        if self.bads:
            self.fig.text(
                0.5, 0.01,
                f'Red (before) = bad | Green (after) = interpolated: '
                f'{", ".join(self.bads)}',
                ha='center', fontsize=9, color=C['text_sub'])
        self.fig.tight_layout(rect=[0, 0.04, 1, 1])
        self.canvas.draw_idle()

    def _go_ok(self):       self.action = 'ok';        self.accept()
    def _go_reinterp(self): self.action = 're_interp'; self.accept()
