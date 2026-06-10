# -*- coding: utf-8 -*-
"""
gui/main_window.py
==================
MainWindow — 應用程式主視窗。

左側欄
------
- Data Settings（資料夾選擇、Subject Name）
- Parameters（Epoch / ICA / EOG / EMG / Bad ch 閾值）
- Heart Rate (ECG) 按鈕
- Load MNE Resources 按鈕
- Run All / Epilepsy / Normal 批次執行按鈕
- Stop 按鈕
- Run Single File 單筆自選執行

右側主區域
----------
- 進度條
- QTabWidget：Files / Processing Log / Help
"""

import os
import sys

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']        = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QFileDialog, QCheckBox,
    QTabWidget, QTextEdit, QScrollArea, QGroupBox,
    QSpinBox, QDoubleSpinBox, QComboBox, QProgressBar,
    QListWidget, QListWidgetItem, QMessageBox, QLineEdit,
    QStatusBar, QSizePolicy, QTextBrowser,
)
from PyQt5.QtGui import QFont

from config import (
    EPOCH_LENGTH, N_ICA_COMP, EOG_THRESHOLD, EMG_THRESHOLD,
    CH_NAMES, SFREQ,
)
from styles import (
    C, BTN_PRIMARY, BTN_SUCCESS, BTN_DANGER, BTN_OUTLINE,
    BTN_EPI, BTN_NOR, BTN_ECG, PANEL_STYLE, tab_style,
)
from utils.widgets import make_label, make_divider, tag_label, make_file_list
from utils.file_utils import scan_folder
from gui.dialogs_raw import RawInspectDialog, InterpolationCompareDialog
from gui.dialogs_ica import ICAReviewDialog
from gui.help_content import HELP_HTML
from processing.worker import ProcessWorker

# ── ECG 選用模組 ────────────────────────────────────────────
try:
    from ecg_viewer_4 import launch_ecg_viewer
    ECG_AVAILABLE = True
except ImportError:
    ECG_AVAILABLE = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('EEG Preprocessing & Connectivity Analysis  v11')
        self.setMinimumSize(1150, 820)
        self.setStyleSheet(f'background: {C["bg"]};')

        self.txt_files_all = []
        self.txt_files_epi = []
        self.txt_files_nor = []
        self.out_folder    = ''
        self.shared_res    = None
        self.worker        = None
        self._res_ready    = False

        self._build_ui()
        self._status_bar()

    # ════════════════════════════════════════════════════════
    #  UI 建構
    # ════════════════════════════════════════════════════════
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_main_area(), stretch=1)

    # ── 左側欄 ───────────────────────────────────────────────
    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(272)
        sidebar.setStyleSheet(
            f'background: {C["panel"]}; '
            f'border-right: 1px solid {C["border"]};')
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(14); layout.setContentsMargins(14, 18, 14, 18)

        layout.addWidget(make_label('EEG Analysis v11', 16, bold=True, color=C['accent']))
        layout.addWidget(make_label(
            'Preprocessing & Connectivity', 10, color=C['text_sub']))
        layout.addWidget(make_divider())

        layout.addWidget(self._build_folder_group())
        layout.addWidget(self._build_param_group())
        layout.addStretch()

        # ECG 按鈕
        self.btn_ecg = QPushButton('Heart Rate (ECG)')
        self.btn_ecg.setStyleSheet(BTN_ECG)
        self.btn_ecg.setToolTip(
            'Open ECG Viewer\n'
            'Reads A1/A2 channels from EEG txt files\n'
            'Detects R-peaks, calculates HR/HRV, exports Excel')
        self.btn_ecg.clicked.connect(self._open_ecg_viewer)
        if not ECG_AVAILABLE:
            self.btn_ecg.setEnabled(False)
            self.btn_ecg.setToolTip('ecg_viewer_4.py not found in same folder')
        layout.addWidget(self.btn_ecg)
        layout.addSpacing(4)

        # Load MNE Resources
        self.btn_init = QPushButton('Load MNE Resources')
        self.btn_init.setStyleSheet(BTN_OUTLINE)
        self.btn_init.clicked.connect(self._init_resources)
        layout.addWidget(self.btn_init)
        self.init_status = make_label('Not loaded', 11, color=C['text_sub'])
        layout.addWidget(self.init_status)
        layout.addSpacing(8)

        # Run 按鈕群
        self.btn_run_all = QPushButton('▶ Run All Files')
        self.btn_run_all.setStyleSheet(BTN_PRIMARY)
        self.btn_run_all.setEnabled(False)
        self.btn_run_all.clicked.connect(lambda: self._run('all'))
        layout.addWidget(self.btn_run_all)

        sub = QHBoxLayout()
        self.btn_run_epi = QPushButton('Epilepsy')
        self.btn_run_epi.setStyleSheet(BTN_EPI)
        self.btn_run_epi.setEnabled(False)
        self.btn_run_epi.clicked.connect(lambda: self._run('epilepsy'))
        sub.addWidget(self.btn_run_epi)

        self.btn_run_nor = QPushButton('Normal')
        self.btn_run_nor.setStyleSheet(BTN_NOR)
        self.btn_run_nor.setEnabled(False)
        self.btn_run_nor.clicked.connect(lambda: self._run('normal'))
        sub.addWidget(self.btn_run_nor)
        layout.addLayout(sub)

        self.btn_stop = QPushButton('■ Stop')
        self.btn_stop.setStyleSheet(BTN_DANGER)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        layout.addWidget(self.btn_stop)

        # 單筆自選
        layout.addSpacing(4)
        layout.addWidget(make_divider())
        layout.addWidget(make_label('Run Single File', 11, bold=True,
                                    color=C['text_sub']))
        self.single_combo = QComboBox()
        self.single_combo.setStyleSheet(
            f'border: 1px solid {C["border"]}; border-radius: 5px; '
            f'padding: 4px; font-size: 11px; background: white;')
        self.single_combo.setPlaceholderText('— select file —')
        self.single_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.single_combo)

        self.btn_run_single = QPushButton('▶ Run This File')
        self.btn_run_single.setStyleSheet(BTN_OUTLINE)
        self.btn_run_single.setEnabled(False)
        self.btn_run_single.clicked.connect(self._run_single)
        layout.addWidget(self.btn_run_single)

        return sidebar

    def _build_folder_group(self) -> QGroupBox:
        grp = QGroupBox('Data Settings'); grp.setStyleSheet(PANEL_STYLE)
        gf  = QVBoxLayout(grp)
        gf.addWidget(make_label('EEG Folder', 11, bold=True))
        self.lbl_folder = QLabel('No folder selected')
        self.lbl_folder.setWordWrap(True)
        self.lbl_folder.setStyleSheet(f'color: {C["text_sub"]}; font-size: 11px;')
        gf.addWidget(self.lbl_folder)
        btn_sel = QPushButton('Browse Folder')
        btn_sel.setStyleSheet(BTN_OUTLINE)
        btn_sel.clicked.connect(self._select_folder)
        gf.addWidget(btn_sel)
        gf.addSpacing(6)
        gf.addWidget(make_label('Subject Name (prefix)', 11, bold=True))
        self.subj_edit = QLineEdit('0420v11_Epilepsy_infomax')
        self.subj_edit.setStyleSheet(
            f'border: 1px solid {C["border"]}; border-radius: 5px; '
            f'padding: 5px; font-size: 12px;')
        gf.addWidget(self.subj_edit)
        return grp

    def _build_param_group(self) -> QGroupBox:
        grp = QGroupBox('Parameters'); grp.setStyleSheet(PANEL_STYLE)
        gp  = QGridLayout(grp); gp.setVerticalSpacing(6)

        for r, (lbl_txt, attr, lo, hi, val) in enumerate([
            ('Epoch length (s)', 'epoch_spin', 1, 60, EPOCH_LENGTH),
            ('ICA components',   'ica_spin',   1, 19, N_ICA_COMP),
        ]):
            gp.addWidget(make_label(lbl_txt, 11), r, 0)
            spin = QSpinBox(); spin.setRange(lo, hi); spin.setValue(val)
            spin.setStyleSheet(
                f'border: 1px solid {C["border"]}; border-radius: 4px; padding: 3px;')
            setattr(self, attr, spin); gp.addWidget(spin, r, 1)

        gp.addWidget(make_label('EOG threshold', 11), 2, 0)
        self.eog_spin = QDoubleSpinBox()
        self.eog_spin.setRange(0.1, 1.0); self.eog_spin.setValue(EOG_THRESHOLD)
        self.eog_spin.setSingleStep(0.05)
        self.eog_spin.setStyleSheet(
            f'border: 1px solid {C["border"]}; border-radius: 4px; padding: 3px;')
        gp.addWidget(self.eog_spin, 2, 1)

        gp.addWidget(make_label('EMG threshold', 11), 3, 0)
        self.emg_spin = QDoubleSpinBox()
        self.emg_spin.setRange(0.1, 3.0); self.emg_spin.setValue(EMG_THRESHOLD)
        self.emg_spin.setSingleStep(0.1)
        self.emg_spin.setStyleSheet(
            f'border: 1px solid {C["border"]}; border-radius: 4px; padding: 3px;')
        gp.addWidget(self.emg_spin, 3, 1)

        gp.addWidget(make_label('Bad ch limit (%)', 11), 4, 0)
        self.bad_lim = QSpinBox(); self.bad_lim.setRange(5, 50); self.bad_lim.setValue(22)
        self.bad_lim.setStyleSheet(
            f'border: 1px solid {C["border"]}; border-radius: 4px; padding: 3px;')
        gp.addWidget(self.bad_lim, 4, 1)
        return grp

    # ── 右側主區域 ────────────────────────────────────────────
    def _build_main_area(self) -> QWidget:
        right = QWidget(); right.setStyleSheet(f'background: {C["bg"]};')
        rv = QVBoxLayout(right)
        rv.setSpacing(10); rv.setContentsMargins(18, 18, 18, 14)

        prog_row = QHBoxLayout()
        self.prog_lbl = make_label('Ready', 12, color=C['text_sub'])
        prog_row.addWidget(self.prog_lbl); prog_row.addStretch()
        self.file_count_lbl = make_label('0 files loaded', 12, color=C['text_sub'])
        prog_row.addWidget(self.file_count_lbl)
        rv.addLayout(prog_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ border: none; border-radius: 5px;
                           background: {C["border"]}; height: 10px; text-align: center; }}
            QProgressBar::chunk {{ background: {C["accent"]}; border-radius: 5px; }}
        """)
        self.progress_bar.setFixedHeight(10)
        rv.addWidget(self.progress_bar)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(tab_style())
        self.tabs.addTab(self._build_file_tab(),  'Files')
        self.tabs.addTab(self._build_log_tab(),   'Processing Log')
        self.tabs.addTab(self._build_help_tab(),  'Help / 說明')
        rv.addWidget(self.tabs)
        return right

    # ── Files 分頁 ────────────────────────────────────────────
    def _build_file_tab(self) -> QWidget:
        w = QWidget(); w.setStyleSheet('background: white;')
        vbox = QVBoxLayout(w); vbox.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.addWidget(make_label('Loaded EEG Files', 13, bold=True))
        hdr.addStretch()
        hdr.addWidget(make_label(
            'Only subj{N}_{session}.txt  |  subj01-25 = Epilepsy  |  subj26+ = Normal',
            11, color=C['text_sub']))
        vbox.addLayout(hdr)
        vbox.addWidget(make_divider())

        badge_row = QHBoxLayout()
        self.badge_epi = tag_label('Epilepsy: 0', C['tag_epi'], C['tag_epi_txt'])
        self.badge_nor = tag_label('Normal: 0',   C['tag_nor'], C['tag_nor_txt'])
        self.badge_all = tag_label('Total: 0',    C['accent_light'], C['accent'])
        badge_row.addWidget(self.badge_epi)
        badge_row.addWidget(self.badge_nor)
        badge_row.addWidget(self.badge_all)
        badge_row.addStretch()
        vbox.addLayout(badge_row)

        sub_tabs = QTabWidget()
        sub_tabs.setStyleSheet(tab_style())

        for attr, label, color in [
            ('epi_list', 'Epilepsy  (subj01 – subj25)', C['danger']),
            ('nor_list', 'Normal  (subj26+)',            C['success']),
            ('all_list', 'All loaded files',             None),
        ]:
            sw = QWidget(); sw.setStyleSheet('background: white;')
            sv = QVBoxLayout(sw); sv.setSpacing(4)
            sv.addWidget(make_label(label, 12, bold=True, color=color))
            lst = make_file_list()
            setattr(self, attr, lst)
            sv.addWidget(lst)
            sub_tabs.addTab(sw, label.split('  ')[0])

        vbox.addWidget(sub_tabs)
        return w

    def _add_file_item(self, lst: QListWidget,
                       stem: str, sub_id: int, session: str, group: str):
        item = QListWidgetItem()
        row  = QWidget(); row.setStyleSheet('background: transparent;')
        hl   = QHBoxLayout(row)
        hl.setContentsMargins(4, 2, 4, 2); hl.setSpacing(6)

        num_lbl = make_label(f'#{sub_id:02d}', 11, color=C['text_light'])
        num_lbl.setFixedWidth(30)
        hl.addWidget(num_lbl)
        hl.addWidget(make_label(stem, 12))
        hl.addStretch()

        if group == 'epilepsy':
            hl.addWidget(tag_label('Epilepsy', C['tag_epi'], C['tag_epi_txt']))
        else:
            hl.addWidget(tag_label('Normal', C['tag_nor'], C['tag_nor_txt']))
        if session:
            hl.addWidget(tag_label(session, C['accent_light'], C['accent']))

        item.setSizeHint(row.sizeHint())
        lst.addItem(item); lst.setItemWidget(item, row)

    # ── Log 分頁 ──────────────────────────────────────────────
    def _build_log_tab(self) -> QWidget:
        w = QWidget(); w.setStyleSheet('background: white;')
        vbox = QVBoxLayout(w)
        hdr  = QHBoxLayout()
        hdr.addWidget(make_label('Processing Log', 13, bold=True))
        hdr.addStretch()
        btn_clear = QPushButton('Clear')
        btn_clear.setStyleSheet(BTN_OUTLINE); btn_clear.setFixedWidth(70)
        btn_clear.clicked.connect(lambda: self.log_text.clear())
        hdr.addWidget(btn_clear)
        vbox.addLayout(hdr)
        vbox.addWidget(make_divider())
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            f'font-family: Consolas, monospace; font-size: 12px; '
            f'background: {C["panel"]}; border: none; padding: 8px;')
        vbox.addWidget(self.log_text)
        return w

    # ── Help 分頁 ─────────────────────────────────────────────
    def _build_help_tab(self) -> QWidget:
        w = QWidget(); w.setStyleSheet('background: white;')
        vbox = QVBoxLayout(w)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(HELP_HTML)
        tb.setStyleSheet('border: none; background: white;')
        vbox.addWidget(tb)
        return w

    def _status_bar(self):
        sb = QStatusBar()
        sb.setStyleSheet(
            f'background: {C["panel"]}; color: {C["text_sub"]}; font-size: 11px;')
        self.setStatusBar(sb)
        sb.showMessage('選擇資料夾後，載入 MNE Resources 即可開始。')

    # ════════════════════════════════════════════════════════
    #  資料夾選擇
    # ════════════════════════════════════════════════════════
    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select EEG Folder')
        if not folder:
            return
        self.out_folder = folder
        self.lbl_folder.setText(folder)

        all_files, epi_files, nor_files, file_meta, skipped = \
            scan_folder(folder)

        self.txt_files_all = all_files
        self.txt_files_epi = epi_files
        self.txt_files_nor = nor_files

        for lst in [self.epi_list, self.nor_list, self.all_list]:
            lst.clear()

        for meta in file_meta:
            if meta['group'] == 'epilepsy':
                self._add_file_item(
                    self.epi_list, meta['stem'],
                    meta['sub_id'], meta['session'], meta['group'])
            else:
                self._add_file_item(
                    self.nor_list, meta['stem'],
                    meta['sub_id'], meta['session'], meta['group'])
            self._add_file_item(
                self.all_list, meta['stem'],
                meta['sub_id'], meta['session'], meta['group'])

        n_all = len(all_files); n_epi = len(epi_files); n_nor = len(nor_files)
        self.badge_epi.setText(f'Epilepsy: {n_epi}')
        self.badge_nor.setText(f'Normal: {n_nor}')
        self.badge_all.setText(f'Total: {n_all}')
        self.file_count_lbl.setText(
            f'{n_all} files loaded  (skipped {skipped} non-matching)')
        self.statusBar().showMessage(
            f'{n_all} matching files  (Epilepsy={n_epi}, Normal={n_nor})'
            f'  |  skipped={skipped}')

        self.single_combo.clear()
        for fp in all_files:
            stem = os.path.splitext(os.path.basename(fp))[0]
            self.single_combo.addItem(stem, userData=fp)
        self.btn_run_single.setEnabled(bool(all_files) and self._res_ready)

        if self._res_ready:
            self._update_run_buttons()

    def _update_run_buttons(self):
        self.btn_run_all.setEnabled(bool(self.txt_files_all))
        self.btn_run_epi.setEnabled(bool(self.txt_files_epi))
        self.btn_run_nor.setEnabled(bool(self.txt_files_nor))

    # ════════════════════════════════════════════════════════
    #  MNE 資源初始化
    # ════════════════════════════════════════════════════════
    def _init_resources(self):
        self.btn_init.setEnabled(False)
        self.init_status.setText('Loading... (1–3 min)')
        self.init_status.setStyleSheet(f'color: {C["warning"]}; font-size: 11px;')
        QApplication.processEvents()
        try:
            from analysis.mne_resources import load_mne_resources
            self.shared_res = load_mne_resources(self.subj_edit.text())
            self._res_ready = True
            self.init_status.setText('✔ Resources loaded')
            self.init_status.setStyleSheet(
                f'color: {C["success"]}; font-size: 11px; font-weight: 600;')
            self._update_run_buttons()
            self.btn_run_single.setEnabled(self.single_combo.count() > 0)
            self.statusBar().showMessage('MNE resources ready.')
        except Exception as e:
            self.init_status.setText('Load failed')
            self.init_status.setStyleSheet(
                f'color: {C["danger"]}; font-size: 11px;')
            QMessageBox.critical(self, 'Error',
                                 f'Failed to load MNE resources:\n{e}')
            self.btn_init.setEnabled(True)

    # ════════════════════════════════════════════════════════
    #  執行
    # ════════════════════════════════════════════════════════
    def _run(self, mode: str = 'all'):
        if not self._res_ready:
            QMessageBox.warning(self, 'Not ready',
                                'Please load MNE resources first.')
            return
        file_map = {
            'all':      self.txt_files_all,
            'epilepsy': self.txt_files_epi,
            'normal':   self.txt_files_nor,
        }
        files = file_map.get(mode, [])
        if not files:
            QMessageBox.warning(self, 'No files',
                                f'No {mode} files loaded.')
            return
        self.shared_res['subj_name'] = self.subj_edit.text()
        self._start_worker(files, mode)

    def _run_single(self):
        idx = self.single_combo.currentIndex()
        if idx < 0:
            return
        fp   = self.single_combo.itemData(idx)
        stem = self.single_combo.currentText()
        if not fp or not os.path.exists(fp):
            QMessageBox.warning(self, 'File not found', f'Cannot find:\n{fp}')
            return
        if not self._res_ready:
            QMessageBox.warning(self, 'Not ready',
                                'Please load MNE resources first.')
            return
        self.shared_res['subj_name'] = self.subj_edit.text()
        self.log_text.append(f'[Run Single] {stem}\n')
        self._start_worker([fp], 'single')

    def _start_worker(self, files: list, mode: str):
        for btn in [self.btn_run_all, self.btn_run_epi, self.btn_run_nor,
                    self.btn_run_single]:
            btn.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.log_text.append(f'[Run] Mode: {mode}  |  {len(files)} files\n')

        self.worker = ProcessWorker(files, self.out_folder, self.shared_res)
        self.worker.log.connect(self._on_log)
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(lambda s: self.statusBar().showMessage(s))
        self.worker.need_raw_review.connect(self._show_raw_review)
        self.worker.need_interp_review.connect(self._show_interp_review)
        self.worker.need_ica_review.connect(self._show_ica_review)
        self.worker.done.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _stop(self):
        if self.worker:
            self.worker.terminate(); self.worker.wait()
        self._update_run_buttons()
        self.btn_stop.setEnabled(False)
        self.prog_lbl.setText('Stopped')
        self.statusBar().showMessage('Processing stopped by user.')

    # ════════════════════════════════════════════════════════
    #  使用者互動 callbacks（主執行緒）
    # ════════════════════════════════════════════════════════
    @QtCore.pyqtSlot(object, list, str, int, int)
    def _show_raw_review(self, raw, auto_bads, file_stem, file_idx, total):
        dlg = RawInspectDialog(raw, auto_bads, file_stem, file_idx, total, self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.worker.set_user_bads(dlg.confirmed_bads, dlg.action)
        else:
            self.worker.set_user_bads(auto_bads, 'confirm')

    @QtCore.pyqtSlot(object, object, list, str, int, int)
    def _show_interp_review(self, raw_before, raw_after,
                            bads, file_stem, fi, total):
        dlg = InterpolationCompareDialog(
            raw_before, raw_after, bads, file_stem, fi, total, self)
        dlg.exec_()
        self.worker.set_user_interp_action(dlg.action)

    @QtCore.pyqtSlot(object, object, object, list, list, str, int, int, object)
    def _show_ica_review(self, ica, raw_before, raw_after,
                         eog_idx, emg_idx, file_stem, file_idx, total,
                         ic_reasons):
        dlg = ICAReviewDialog(
            ica, raw_before, raw_after, eog_idx, emg_idx,
            file_stem, file_idx, total,
            ic_reasons=ic_reasons, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.worker.set_user_excl(dlg.final_exclude, dlg.action)
        else:
            self.worker.set_user_excl(list(ica.exclude), 'confirm')

    # ── Worker callbacks ──────────────────────────────────────
    def _on_log(self, msg: str):
        self.log_text.append(msg)
        QTimer.singleShot(0, lambda: self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()))

    def _on_progress(self, cur: int, total: int):
        pct = int(cur / total * 100)
        self.progress_bar.setValue(pct)
        self.prog_lbl.setText(f'File {cur} / {total}')

    def _on_done(self):
        self._update_run_buttons()
        self.btn_stop.setEnabled(False)
        self.btn_run_single.setEnabled(self.single_combo.count() > 0)
        self.progress_bar.setValue(100)
        self.prog_lbl.setText('✔ All done')
        self.statusBar().showMessage('All files processed successfully.')
        QMessageBox.information(self, 'Done',
            'All files processed!\nOutputs saved to the selected folder.')

    def _on_error(self, msg: str):
        self._update_run_buttons()
        self.btn_stop.setEnabled(False)
        self.btn_run_single.setEnabled(self.single_combo.count() > 0)
        self.log_text.append(f'[FATAL ERROR]\n{msg}')
        QMessageBox.critical(self, 'Fatal Error', msg[:500])

    # ── ECG ───────────────────────────────────────────────────
    def _open_ecg_viewer(self):
        folder = self.out_folder or None
        if not folder:
            folder = QFileDialog.getExistingDirectory(
                self, 'Select EEG folder for ECG analysis')
        if folder:
            self._ecg_win = launch_ecg_viewer(folder=folder)
        else:
            QMessageBox.information(self, 'ECG Viewer',
                                    'Please select a folder first.')
