# -*- coding: utf-8 -*-
"""
gui/dialogs_ica.py
==================
ICA 結果確認視窗 (ICAReviewDialog)。

分頁說明
--------
- IC Components : Topography（列1）+ 時域（列2）+ 功率頻譜（列3）
                  每個 IC 旁有勾選框可手動修改排除清單。
- Before / After : 3 欄對比（原始 / ICA 後 / 移除成分），
                  支援時間滑桿。

支援上一筆 / 下一筆 / 跳過 / 確認 動作。
"""

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavToolbar,
)
from scipy.signal import welch

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QWidget, QSlider, QSpinBox, QTabWidget, QLabel,
)
from PyQt5.QtGui import QFont

from config import CH_NAMES, SFREQ, N_ICA_COMP, EOG_THRESHOLD, EMG_THRESHOLD
from styles import C, BTN_OUTLINE, BTN_SUCCESS, SLIDER_STYLE
from utils.widgets import make_label, make_divider


class ICAReviewDialog(QtWidgets.QDialog):
    """
    ICA 成分審視與排除確認視窗。

    Attributes
    ----------
    final_exclude : list[int]   使用者確認後的排除成分索引清單
    action        : str         'confirm' | 'prev' | 'next' | 'skip'
    """

    def __init__(self, ica, raw_before, raw_after,
                 eog_idx: list, emg_idx: list,
                 file_stem: str, file_index: int, total_files: int,
                 ic_reasons: dict = None, parent=None):
        super().__init__(parent)
        self.ica           = ica
        self.raw_before    = raw_before
        self.raw_after     = raw_after
        self.eog_idx       = eog_idx
        self.emg_idx       = emg_idx
        self.file_stem     = file_stem
        self.file_index    = file_index
        self.total_files   = total_files
        self.ic_reasons    = ic_reasons or {}
        self.final_exclude = list(ica.exclude)
        self.action        = 'confirm'
        self.setWindowTitle(
            f'ICA Review — {file_stem}  [{file_index}/{total_files}]')
        self.setMinimumSize(1350, 900)
        self.setStyleSheet(f'background: {C["bg"]};')
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        hdr = QHBoxLayout()
        hdr.addWidget(make_label(
            f'ICA Component Review: {self.file_stem}  '
            f'[{self.file_index}/{self.total_files}]', 13, bold=True))
        hdr.addStretch()
        self.excl_badge = make_label('', 12)
        self._update_excl_badge()
        hdr.addWidget(self.excl_badge)
        root.addLayout(hdr)
        root.addWidget(make_divider())

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {C['border']}; border-radius: 6px; }}
            QTabBar::tab {{ padding: 8px 20px; font-size: 13px;
                           background: {C['panel']}; border-radius: 4px 4px 0 0; }}
            QTabBar::tab:selected {{ background: {C['accent']}; color: white; font-weight: 600; }}
        """)
        tabs.addTab(self._build_topo_tab(),    'IC Components')
        tabs.addTab(self._build_compare_tab(), 'Before / After')
        root.addWidget(tabs)

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

        info = make_label(
            'Red = auto-excluded. Toggle checkboxes to modify.',
            11, color=C['text_sub'])
        bot.addWidget(info); bot.addStretch()

        btn_cancel = QPushButton('Cancel')
        btn_cancel.setStyleSheet(BTN_OUTLINE)
        btn_cancel.clicked.connect(self.reject)
        bot.addWidget(btn_cancel)

        btn_next = QPushButton('確認並看下一筆 ▶')
        btn_next.setStyleSheet(BTN_OUTLINE)
        btn_next.setEnabled(self.file_index < self.total_files)
        btn_next.clicked.connect(self._go_next)
        bot.addWidget(btn_next)

        btn_ok = QPushButton('✔ Confirm & Apply ICA')
        btn_ok.setStyleSheet(BTN_SUCCESS)
        btn_ok.clicked.connect(self._go_confirm)
        bot.addWidget(btn_ok)

        root.addLayout(bot)

    # ── IC Components 分頁 ────────────────────────────────────
    def _build_topo_tab(self):
        import mne
        w = QWidget(); w.setStyleSheet('background: white;')
        vbox = QVBoxLayout(w)

        n_ic   = min(N_ICA_COMP, self.ica.n_components_)
        n_rows = 3  # topo / timeseries / spectrum

        fig    = Figure(figsize=(n_ic * 2.2, n_rows * 2.2), facecolor='white')
        canvas = FigureCanvas(fig)
        canvas.setMinimumHeight(520)

        ic_data = self.ica.get_sources(self.raw_before).get_data()

        self.ic_checks = {}
        check_row  = QHBoxLayout()
        check_row.addWidget(make_label('Toggle IC:', 11))

        for ic_i in range(n_ic):
            excl  = ic_i in self.final_exclude
            color = C['danger'] if excl else C['text']
            lbl   = 'EXCL' if excl else 'keep'

            # Topography
            ax_top = fig.add_subplot(n_rows, n_ic, ic_i + 1)
            mne.viz.plot_topomap(
                self.ica.get_components()[:, ic_i],
                self.raw_before.info,
                axes=ax_top, show=False, contours=0, sensors=True)
            ax_top.set_title(
                f'IC{ic_i:02d}\n[{lbl}]', fontsize=7, color=color,
                fontweight='bold' if excl else 'normal')

            # 時域 10 秒
            ax_ts = fig.add_subplot(n_rows, n_ic, n_ic + ic_i + 1)
            ts = ic_data[ic_i, :10 * SFREQ]
            ax_ts.plot(np.arange(len(ts)) / SFREQ, ts,
                       linewidth=0.5, color=C['danger'] if excl else '#3B82F6')
            ax_ts.set_xticks([0, 5, 10])
            ax_ts.set_xticklabels(['0s', '5s', '10s'], fontsize=5)
            ax_ts.set_yticks([])
            ax_ts.spines[['top', 'right', 'left']].set_visible(False)

            # 功率頻譜 0–50 Hz
            ax_sp = fig.add_subplot(n_rows, n_ic, 2 * n_ic + ic_i + 1)
            freqs, psd = welch(ic_data[ic_i], fs=SFREQ,
                               nperseg=min(1024, ic_data.shape[1]))
            f_mask  = freqs <= 50
            psd_db  = 10 * np.log10(psd[f_mask] + 1e-30)
            ax_sp.plot(freqs[f_mask], psd_db,
                       color=C['danger'] if excl else '#3B82F6', linewidth=0.8)
            ax_sp.axvspan(8,  13, alpha=0.12, color='#3B82F6', label='Alpha')
            ax_sp.axvspan(30, 50, alpha=0.12, color='#F97316', label='EMG')
            ax_sp.set_xlim(0, 50)
            ax_sp.set_xlabel('Hz', fontsize=5); ax_sp.set_ylabel('dB', fontsize=5)
            ax_sp.tick_params(labelsize=5)
            ax_sp.spines[['top', 'right']].set_visible(False)
            ax_sp.set_xticks([0, 8, 13, 30, 50])
            ax_sp.set_xticklabels(['0', '8', '13', '30', '50'], fontsize=5)

            # 勾選框
            cb = QCheckBox(f'IC{ic_i:02d}')
            cb.setChecked(excl); cb.setFont(QFont('', 11))
            if ic_i in self.ic_reasons:
                cb.setToolTip(self.ic_reasons[ic_i])
            if excl:
                parts = (['EOG'] if ic_i in self.eog_idx else []) + \
                        (['EMG'] if ic_i in self.emg_idx else [])
                cb.setText(f'IC{ic_i:02d} ({"+".join(parts) or "manual"})')
                cb.setStyleSheet(f'color: {C["danger"]}; font-weight: 600;')
            cb.stateChanged.connect(
                lambda s, i=ic_i, b=cb, at=ax_top, cv=canvas:
                self._toggle_ic(i, b, at, cv))
            check_row.addWidget(cb)
            self.ic_checks[ic_i] = (cb, ax_top, ax_ts)

        check_row.addStretch()

        legend_row = QHBoxLayout()
        for color, label in [('#3B82F6', 'Alpha (8-13 Hz)'),
                              ('#F97316', 'EMG (>30 Hz)')]:
            dot = QLabel('■')
            dot.setStyleSheet(f'color: {color}; font-size: 14px;')
            legend_row.addWidget(dot)
            legend_row.addWidget(make_label(label, 10, color=C['text_sub']))
            legend_row.addSpacing(12)
        legend_row.addStretch()

        fig.tight_layout(pad=0.8)
        vbox.addWidget(canvas)
        vbox.addLayout(legend_row)
        vbox.addLayout(check_row)
        return w

    def _toggle_ic(self, ic_i: int, cb: QCheckBox, ax_top, canvas):
        if cb.isChecked():
            if ic_i not in self.final_exclude:
                self.final_exclude.append(ic_i)
            cb.setStyleSheet(f'color: {C["danger"]}; font-weight: 600;')
            ax_top.set_title(f'IC{ic_i:02d}\n[EXCL]',
                             fontsize=7, color=C['danger'], fontweight='bold')
        else:
            self.final_exclude = [x for x in self.final_exclude if x != ic_i]
            cb.setStyleSheet('')
            ax_top.set_title(f'IC{ic_i:02d}\n[keep]',
                             fontsize=7, color=C['text'], fontweight='normal')
        self.final_exclude.sort()
        self._update_excl_badge()
        canvas.draw_idle()

    def _update_excl_badge(self):
        n        = len(self.final_exclude)
        MAX_EXCL = 5
        if n > MAX_EXCL:
            txt   = f'⚠ WARNING: {n} ICs excluded (max recommended: {MAX_EXCL})'
            color = C['danger']; bg = '#FEE2E2'
        elif n > 3:
            txt   = f'Excluding {n} / {N_ICA_COMP} ICs  (caution: >{n-1})'
            color = C['warning']; bg = '#FEF3C7'
        else:
            txt   = f'Excluding {n} / {N_ICA_COMP} ICs'
            color = C['success']; bg = '#DCFCE7'
        self.excl_badge.setText(txt)
        self.excl_badge.setStyleSheet(
            f'color: {color}; font-weight: 600; font-size: 13px;'
            f'background: {bg}; border-radius: 4px; padding: 3px 8px;')

    # ── Before / After 分頁 ───────────────────────────────────
    def _build_compare_tab(self):
        w = QWidget(); w.setStyleSheet('background: white;')
        vbox = QVBoxLayout(w)

        ctrl = QHBoxLayout()
        ctrl.addWidget(make_label('Scale (µV):', 11))
        self.cmp_scale = QSpinBox()
        self.cmp_scale.setRange(10, 2000); self.cmp_scale.setValue(50)
        self.cmp_scale.setSingleStep(50); self.cmp_scale.setFixedWidth(80)
        self.cmp_scale.valueChanged.connect(self._redraw_compare)
        ctrl.addWidget(self.cmp_scale); ctrl.addStretch()
        self.cmp_time_lbl = make_label('0 s', 11, color=C['accent'])
        ctrl.addWidget(self.cmp_time_lbl)
        vbox.addLayout(ctrl)

        self.fig_cmp    = Figure(figsize=(14, 6), facecolor='white')
        self.canvas_cmp = FigureCanvas(self.fig_cmp)
        vbox.addWidget(NavToolbar(self.canvas_cmp, w))
        vbox.addWidget(self.canvas_cmp)

        slider_row = QHBoxLayout()
        slider_row.addWidget(make_label('Time:', 11))
        total_s = int(self.raw_before.n_times / SFREQ)
        self.cmp_slider = QSlider(Qt.Horizontal)
        self.cmp_slider.setRange(0, max(0, total_s - 30))
        self.cmp_slider.setValue(0); self.cmp_slider.setSingleStep(1)
        self.cmp_slider.setPageStep(10); self.cmp_slider.setTickInterval(30)
        self.cmp_slider.setTickPosition(QSlider.TicksBelow)
        self.cmp_slider.setStyleSheet(SLIDER_STYLE)
        self.cmp_slider.valueChanged.connect(self._on_cmp_slider)
        slider_row.addWidget(self.cmp_slider)
        slider_row.addWidget(make_label(f'{total_s}s', 11, color=C['text_sub']))
        vbox.addLayout(slider_row)

        self._redraw_compare()
        return w

    def _on_cmp_slider(self, val):
        self.cmp_time_lbl.setText(f'{val} s')
        self._redraw_compare()

    def _redraw_compare(self):
        self.fig_cmp.clear()
        t0   = self.cmp_slider.value()
        i0   = int(t0 * SFREQ)
        i1   = min(i0 + 30 * SFREQ, self.raw_before.n_times)
        tvec = np.linspace(t0, t0 + 30, i1 - i0)

        plot_chs = [c for c in ['Fp1', 'Fp2', 'F3', 'T3', 'O1', 'O2']
                    if c in self.raw_before.ch_names]
        ch_idx   = [self.raw_before.ch_names.index(c) for c in plot_chs]

        d_bef = self.raw_before.get_data()[ch_idx, i0:i1] * 1e6
        d_aft = self.raw_after.get_data()[ch_idx, i0:i1]  * 1e6
        d_rem = d_bef - d_aft
        sc    = max(self.cmp_scale.value(), 1)
        offs  = np.arange(len(plot_chs)) * sc

        configs = [
            (d_bef, 'Before ICA',     '#3B82F6'),
            (d_aft, 'After ICA',      '#16A34A'),
            (d_rem, 'Removed (diff)', '#DC2626'),
        ]
        for col, (dat, title, col_) in enumerate(configs):
            ax = self.fig_cmp.add_subplot(1, 3, col + 1)
            for i, (ch, off) in enumerate(zip(plot_chs, offs)):
                ax.plot(tvec, dat[i] + off, color=col_, linewidth=0.6)
                ax.text(t0 - 0.5, off, ch, ha='right', va='center', fontsize=8)
            ax.set_title(title, fontsize=11)
            ax.set_xlabel('Time (s)', fontsize=9)
            ax.set_xlim(t0, t0 + 30); ax.set_yticks([])
            ax.spines[['top', 'right', 'left']].set_visible(False)

        self.fig_cmp.tight_layout()
        self.canvas_cmp.draw_idle()

    # ── 動作 ──────────────────────────────────────────────────
    def _go_confirm(self): self.action = 'confirm'; self.accept()
    def _go_next(self):    self.action = 'next';    self.accept()
    def _go_prev(self):    self.action = 'prev';    self.accept()
    def _go_skip(self):    self.action = 'skip';    self.accept()
