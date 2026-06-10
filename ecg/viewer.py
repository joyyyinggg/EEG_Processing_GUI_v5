# -*- coding: utf-8 -*-
"""ecg/viewer.py — ECGViewer main window (Heart Rate & HRV Analysis v4)."""
import os, re, sys, warnings; warnings.filterwarnings('ignore')
import numpy as np
import matplotlib; matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavToolbar)
from matplotlib.figure import Figure
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QFrame, QSpinBox, QDoubleSpinBox,
    QCheckBox, QSlider, QProgressBar, QGroupBox, QTabWidget,
    QListWidget, QListWidgetItem, QMessageBox, QStatusBar, QLineEdit,
)
from PyQt5.QtGui import QFont, QColor

from ecg.ecg_config import (
    SFREQ, HR_HIGH, HR_LOW, HRV_LOW,
    MAX_ART_RATIO, DEFAULT_ART_Z,
    COLOR_A1, COLOR_A2, COLOR_GRAY,
)
from ecg.signal_processing import (
    select_best_ecg, mask_artifacts, bandpass_ecg,
    detect_rpeaks, compute_hr_hrv, classify_status,
)
from ecg.worker import LoadWorker
from ecg.exporter import export_excel
from styles import C, BTN_PRIMARY, BTN_SUCCESS, BTN_OUTLINE, PANEL_STYLE

def _lbl(text, size=13, bold=False, color=None):
    l = QLabel(text); f = QFont(); f.setPointSize(size)
    if bold: f.setBold(True)
    l.setFont(f)
    if color: l.setStyleSheet(f'color:{color};')
    return l

def _div():
    ln = QFrame(); ln.setFrameShape(QFrame.HLine)
    ln.setStyleSheet(f'color:{C["border"]};'); return ln


class ECGViewer(QMainWindow):
    def __init__(self, folder=None):
        super().__init__()
        self.setWindowTitle('ECG Viewer v4 — Heart Rate & HRV Analysis')
        self.setMinimumSize(1200, 760)
        self.setStyleSheet(f'background:{C["bg"]};')
        self.folder = folder; self.txt_files = []; self.cur_idx = -1
        self.results = []; self.a1 = self.a2 = self.tvec = self.allch = None
        self.cur_stem = ''; self.quality_ok = True
        self.peaks = np.array([]); self.ecg_used = None
        self.ch_label = 'A1'; self.art_ratio = 0.0
        self._build_ui(); self._build_statusbar()
        if folder: self._load_folder(folder)

    def _build_ui(self):
        cw = QWidget(); self.setCentralWidget(cw)
        root = QHBoxLayout(cw); root.setSpacing(0); root.setContentsMargins(0,0,0,0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_main(), stretch=1)

    def _build_sidebar(self):
        sb = QWidget(); sb.setMinimumWidth(220); sb.setMaximumWidth(370)
        sb.setStyleSheet(f'background:{C["panel"]};border-right:1px solid {C["border"]};')
        vb = QVBoxLayout(sb); vb.setContentsMargins(14,18,14,18); vb.setSpacing(14)
        vb.addWidget(_lbl('ECG Viewer  v4', 16, bold=True, color=C['accent']))
        vb.addWidget(_lbl('Heart Rate & HRV Analysis', 11, color=C['text_sub']))
        vb.addWidget(_div())
        # Folder
        gf = QGroupBox('Data Folder'); gf.setStyleSheet(PANEL_STYLE)
        gfl = QVBoxLayout(gf)
        self.lbl_folder = QLabel('No folder selected')
        self.lbl_folder.setWordWrap(True)
        self.lbl_folder.setStyleSheet(f'color:{C["text_sub"]};font-size:11px;')
        gfl.addWidget(self.lbl_folder)
        btn_b = QPushButton('Browse'); btn_b.setStyleSheet(BTN_OUTLINE)
        btn_b.clicked.connect(self._browse_folder); gfl.addWidget(btn_b)
        vb.addWidget(gf)
        # Params
        gp = QGroupBox('Parameters'); gp.setStyleSheet(PANEL_STYLE)
        gpl = QVBoxLayout(gp); gpl.setSpacing(6)
        def _row(label, widget):
            r = QHBoxLayout(); r.addWidget(_lbl(label, 11)); r.addWidget(widget); gpl.addLayout(r)
        self.trim_spin = QSpinBox(); self.trim_spin.setRange(0,120); self.trim_spin.setValue(30)
        self.trim_spin.setStyleSheet(f'border:1px solid {C["border"]};border-radius:4px;padding:4px;')
        _row('Trim (s):', self.trim_spin)
        self.hr_high_spin = QSpinBox(); self.hr_high_spin.setRange(60,180); self.hr_high_spin.setValue(HR_HIGH)
        self.hr_high_spin.setStyleSheet(f'border:1px solid {C["border"]};border-radius:4px;padding:4px;')
        _row('Stressed HR >:', self.hr_high_spin)
        self.hrv_low_spin = QSpinBox(); self.hrv_low_spin.setRange(5,100); self.hrv_low_spin.setValue(HRV_LOW)
        self.hrv_low_spin.setStyleSheet(f'border:1px solid {C["border"]};border-radius:4px;padding:4px;')
        _row('Stressed HRV <:', self.hrv_low_spin)
        self.art_spin = QDoubleSpinBox(); self.art_spin.setRange(1.0,10.0); self.art_spin.setValue(DEFAULT_ART_Z); self.art_spin.setSingleStep(0.5)
        self.art_spin.setStyleSheet(f'border:1px solid {C["border"]};border-radius:4px;padding:4px;')
        self.art_spin.valueChanged.connect(self._analyze_and_redraw)
        _row('Artifact z:', self.art_spin)
        self.auto_ch_cb = QCheckBox('Auto-select best channel (A1/A2)')
        self.auto_ch_cb.setChecked(True); self.auto_ch_cb.setFont(QFont('',11))
        self.auto_ch_cb.stateChanged.connect(self._analyze_and_redraw)
        gpl.addWidget(self.auto_ch_cb)
        self.show_all_cb = QCheckBox('Show all EEG channels (faded)')
        self.show_all_cb.setChecked(True); self.show_all_cb.setFont(QFont('',11))
        self.show_all_cb.stateChanged.connect(self._redraw); gpl.addWidget(self.show_all_cb)
        vb.addWidget(gp)
        # Current result
        gr = QGroupBox('Current Result'); gr.setStyleSheet(PANEL_STYLE)
        grl = QVBoxLayout(gr); grl.setSpacing(6)
        self.hr_lbl      = _lbl('HR: —', 14, bold=True)
        self.hrv_lbl     = _lbl('HRV (RMSSD): —', 12)
        self.peaks_lbl   = _lbl('Peaks detected: —', 11, color=C['text_sub'])
        self.ch_used_lbl = _lbl('Channel: —', 11, color=C['text_sub'])
        self.art_lbl     = _lbl('Artifact: —', 11, color=C['text_sub'])
        self.status_lbl  = _lbl('Status: —', 13, bold=True)
        for w in [self.hr_lbl,self.hrv_lbl,self.peaks_lbl,
                  self.ch_used_lbl,self.art_lbl,self.status_lbl]: grl.addWidget(w)
        grl.addWidget(_div())
        self.quality_cb = QCheckBox('Mark as Poor Quality')
        self.quality_cb.setFont(QFont('',12))
        self.quality_cb.setStyleSheet(f'color:{C["danger"]};')
        self.quality_cb.stateChanged.connect(self._on_quality_toggle)
        grl.addWidget(self.quality_cb)
        self.note_edit = QLineEdit(); self.note_edit.setPlaceholderText('Optional note...')
        self.note_edit.setStyleSheet(f'border:1px solid {C["border"]};border-radius:4px;padding:5px;font-size:12px;')
        grl.addWidget(self.note_edit)
        vb.addWidget(gr); vb.addStretch()
        self.btn_export = QPushButton('Export Excel'); self.btn_export.setStyleSheet(BTN_SUCCESS)
        self.btn_export.setEnabled(False); self.btn_export.clicked.connect(self._export_excel)
        vb.addWidget(self.btn_export)
        return sb

    def _build_main(self):
        right = QWidget(); right.setStyleSheet(f'background:{C["bg"]};')
        rv = QVBoxLayout(right); rv.setContentsMargins(16,16,16,12); rv.setSpacing(8)
        top = QHBoxLayout()
        self.prog_lbl = _lbl('No files loaded', 13, color=C['text_sub'])
        top.addWidget(self.prog_lbl); top.addStretch()
        self.btn_prev = QPushButton('◀ Prev')
        self.btn_prev.setStyleSheet(f'QPushButton{{background:{C["panel"]};color:{C["text"]};border:1px solid {C["border"]};border-radius:6px;padding:8px 16px;font-size:13px;}}QPushButton:hover{{background:{C["border"]};}}'  )
        self.btn_prev.setEnabled(False); self.btn_prev.clicked.connect(self._go_prev)
        top.addWidget(self.btn_prev)
        self.btn_next = QPushButton('Next ▶'); self.btn_next.setStyleSheet(BTN_PRIMARY)
        self.btn_next.setEnabled(False); self.btn_next.clicked.connect(self._go_next)
        top.addWidget(self.btn_next); rv.addLayout(top)
        self.prog_bar = QProgressBar(); self.prog_bar.setRange(0,100); self.prog_bar.setValue(0)
        self.prog_bar.setFixedHeight(8)
        self.prog_bar.setStyleSheet(f'QProgressBar{{border:none;border-radius:4px;background:{C["border"]};}}QProgressBar::chunk{{background:{C["accent"]};border-radius:4px;}}')
        rv.addWidget(self.prog_bar); rv.addWidget(_div())
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f'QTabWidget::pane{{border:1px solid {C["border"]};border-radius:8px;}}QTabBar::tab{{padding:9px 22px;font-size:14px;background:{C["panel"]};border-radius:4px 4px 0 0;}}QTabBar::tab:selected{{background:{C["accent"]};color:white;font-weight:600;}}')
        self.tabs.addTab(self._build_wave_tab(), 'Waveform')
        self.tabs.addTab(self._build_summary_tab(), 'Summary')
        rv.addWidget(self.tabs)
        return right

    def _build_wave_tab(self):
        w = QWidget(); w.setStyleSheet('background:white;')
        vb = QVBoxLayout(w); vb.setSpacing(4)
        ctrl = QHBoxLayout()
        ctrl.addWidget(_lbl('Scale (µV):', 11))
        self.scale_spin = QSpinBox(); self.scale_spin.setRange(10,5000); self.scale_spin.setValue(500); self.scale_spin.setSingleStep(100)
        self.scale_spin.setStyleSheet(f'border:1px solid {C["border"]};border-radius:4px;padding:4px;')
        self.scale_spin.valueChanged.connect(self._redraw); ctrl.addWidget(self.scale_spin)
        ctrl.addWidget(_lbl('Window (s):', 11))
        self.win_spin = QSpinBox(); self.win_spin.setRange(5,60); self.win_spin.setValue(15); self.win_spin.setSingleStep(5)
        self.win_spin.setStyleSheet(f'border:1px solid {C["border"]};border-radius:4px;padding:4px;')
        self.win_spin.valueChanged.connect(self._redraw); ctrl.addWidget(self.win_spin)
        ctrl.addStretch()
        for color, name in [(COLOR_A1,'A1  '),(COLOR_A2,'A2  ')]:
            dot = QLabel('■'); dot.setStyleSheet(f'color:{color};font-size:16px;')
            ctrl.addWidget(dot); ctrl.addWidget(_lbl(name, 12))
        vb.addLayout(ctrl)
        self.fig = Figure(figsize=(12,6), facecolor='white')
        self.canvas = FigureCanvas(self.fig)
        vb.addWidget(NavToolbar(self.canvas, w)); vb.addWidget(self.canvas)
        sl_row = QHBoxLayout(); sl_row.addWidget(_lbl('Time:', 11))
        self.t_slider = QSlider(Qt.Horizontal); self.t_slider.setRange(0,100); self.t_slider.setValue(0)
        self.t_slider.setStyleSheet(f'QSlider::groove:horizontal{{height:6px;background:{C["border"]};border-radius:3px;}}QSlider::handle:horizontal{{width:16px;height:16px;margin:-5px 0;background:{C["accent"]};border-radius:8px;}}QSlider::sub-page:horizontal{{background:{C["accent_light"]};border-radius:3px;}}')
        self.t_slider.valueChanged.connect(self._on_slider)
        self.t_lbl = _lbl('0 s', 11, color=C['accent'])
        sl_row.addWidget(self.t_slider); sl_row.addWidget(self.t_lbl)
        vb.addLayout(sl_row)
        return w

    def _build_summary_tab(self):
        w = QWidget(); w.setStyleSheet('background:white;')
        vb = QVBoxLayout(w)
        vb.addWidget(_lbl('Processed Files Summary', 13, bold=True)); vb.addWidget(_div())
        self.summary_list = QListWidget()
        self.summary_list.setStyleSheet(f'QListWidget{{border:none;font-size:12px;}}QListWidget::item{{padding:7px 10px;border-bottom:1px solid {C["border"]};}}')
        vb.addWidget(self.summary_list)
        return w

    def _build_statusbar(self):
        sb = QStatusBar(); sb.setStyleSheet(f'background:{C["panel"]};color:{C["text_sub"]};font-size:11px;')
        self.setStatusBar(sb); sb.showMessage('Select a folder to begin.')

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select EEG Folder')
        if folder: self._load_folder(folder)

    def _load_folder(self, folder: str):
        self.folder = folder; self.lbl_folder.setText(folder)
        pat = re.compile(r'subj\d+_\w+', re.IGNORECASE)
        self.txt_files = sorted([
            os.path.join(root, fname)
            for root,_,files in os.walk(folder)
            for fname in files
            if fname.endswith('.txt') and pat.search(fname)
        ])
        self.results = []; self.cur_idx = -1
        n = len(self.txt_files)
        self.prog_lbl.setText(f'{n} files found'); self.prog_bar.setValue(0)
        if n > 0:
            self.btn_next.setEnabled(True)
            self.statusBar().showMessage(f'{n} files loaded from {folder}')
            self._go_next()

    def _go_next(self):
        self._save_current()
        if self.cur_idx + 1 < len(self.txt_files):
            self.cur_idx += 1; self._load_file(self.txt_files[self.cur_idx])
        else:
            QMessageBox.information(self,'Done','All files reviewed! Click Export Excel to save.')
            self.btn_export.setEnabled(True)

    def _go_prev(self):
        self._save_current()
        if self.cur_idx > 0:
            self.cur_idx -= 1; self._load_file(self.txt_files[self.cur_idx])

    def _load_file(self, fpath: str):
        self.statusBar().showMessage(f'Loading {os.path.basename(fpath)}...')
        self.btn_prev.setEnabled(self.cur_idx > 0); self.btn_next.setEnabled(True)
        pct = int((self.cur_idx+1)/len(self.txt_files)*100)
        self.prog_bar.setValue(pct)
        self.prog_lbl.setText(f'{self.cur_idx+1} / {len(self.txt_files)}  —  {os.path.basename(fpath)}')
        self.loader = LoadWorker(fpath, self.trim_spin.value())
        self.loader.done.connect(self._on_loaded); self.loader.error.connect(self._on_load_error)
        self.loader.start()

    def _on_loaded(self, a1, a2, tvec, allch, stem):
        self.a1=a1; self.a2=a2; self.tvec=tvec; self.allch=allch; self.cur_stem=stem
        self.quality_cb.blockSignals(True); self.quality_cb.setChecked(False); self.quality_cb.blockSignals(False)
        self.note_edit.clear(); self.quality_ok = True
        total_s = int(len(tvec)/SFREQ)
        self.t_slider.setRange(0, max(0, total_s - self.win_spin.value())); self.t_slider.setValue(0)
        self._analyze(); self._redraw()
        self.statusBar().showMessage(f'Loaded: {stem}  |  Duration: {total_s}s')

    def _on_load_error(self, stem, err):
        self.statusBar().showMessage(f'Error loading {stem}: {err}')
        QMessageBox.warning(self, 'Load Error', f'{stem}:\n{err}')

    def _analyze(self):
        if self.a1 is None: return
        try:
            z_thresh = self.art_spin.value()
            if self.auto_ch_cb.isChecked() and self.a2 is not None:
                ecg_raw, ch_label, ch_quality = select_best_ecg(self.a1, self.a2)
            else:
                ecg_raw, ch_label, ch_quality = self.a1, 'A1', 'good'
            if ch_quality == 'poor' and not self.quality_cb.isChecked():
                self.quality_ok = False
                self.quality_cb.blockSignals(True); self.quality_cb.setChecked(True); self.quality_cb.blockSignals(False)
                if not self.note_edit.text(): self.note_edit.setText('Auto: both A1/A2 poor quality')
            self.ecg_used = ecg_raw; self.ch_label = ch_label
            ecg_clean, art_ratio = mask_artifacts(ecg_raw, SFREQ, z_thresh)
            self.art_ratio = art_ratio
            ecg_filt = bandpass_ecg(ecg_clean)
            self.peaks = detect_rpeaks(ecg_filt, SFREQ)
            hr, hrv = compute_hr_hrv(self.peaks, SFREQ)
            self.hr_val = hr; self.hrv_val = hrv
            if art_ratio > MAX_ART_RATIO:
                self.quality_ok = False
                self.quality_cb.blockSignals(True); self.quality_cb.setChecked(True); self.quality_cb.blockSignals(False)
            status, _ = classify_status(hr, hrv, self.quality_ok,
                                        self.hr_high_spin.value(), HR_LOW, self.hrv_low_spin.value())
            self.hr_lbl.setText(f'HR: {hr} BPM' if hr else 'HR: N/A')
            self.hrv_lbl.setText(f'HRV (RMSSD): {hrv} ms' if hrv else 'HRV: N/A')
            self.peaks_lbl.setText(f'Peaks detected: {len(self.peaks)}')
            q_colors = {'good':C['success'],'acceptable':C['warning'],'poor':C['danger']}
            self.ch_used_lbl.setText(f'Channel: {ch_label}')
            self.ch_used_lbl.setStyleSheet(f'color:{q_colors.get(ch_quality,C["text_sub"])};font-size:11px;font-weight:600;')
            art_pct = art_ratio*100
            art_color = C['danger'] if art_pct>30 else C['warning'] if art_pct>10 else C['success']
            self.art_lbl.setText(f'Artifact: {art_pct:.1f}% masked')
            self.art_lbl.setStyleSheet(f'color:{art_color};font-size:11px;')
            s_colors = {'Calm':C['success'],'Stressed':C['danger'],'Bradycardia':C['warning'],'Poor quality':C['text_sub']}
            self.status_lbl.setText(f'Status: {status}')
            self.status_lbl.setStyleSheet(f'color:{s_colors.get(status,C["text"])};font-weight:700;font-size:14px;')
        except Exception as e:
            self.hr_lbl.setText(f'HR: Error ({e})')
            self.peaks = np.array([]); self.ecg_used = self.a1; self.ch_label='A1'; self.art_ratio=0.0

    def _redraw(self):
        if self.a1 is None: return
        self.fig.clear()
        t0=self.t_slider.value(); win=self.win_spin.value(); sc=self.scale_spin.value()
        i0=int(t0*SFREQ); i1=min(i0+win*SFREQ, len(self.tvec))
        tvec_seg=self.tvec[i0:i1]
        ax=self.fig.add_subplot(111)
        if self.show_all_cb.isChecked() and self.allch is not None:
            n_eeg=min(19,self.allch.shape[1])
            for ci in range(n_eeg):
                seg=self.allch[i0:i1,ci]*1e6
                ax.plot(tvec_seg,seg-ci*sc*0.3-sc*2.5,color=COLOR_GRAY,linewidth=0.4,alpha=0.25)
        ecg_used=self.ecg_used if self.ecg_used is not None else self.a1
        ax.plot(tvec_seg,ecg_used[i0:i1]*1e6+sc*0.5,color=COLOR_A1,linewidth=1.0,label=self.ch_label,zorder=3)
        ax.plot(tvec_seg,self.a2[i0:i1]*1e6-sc*0.5,color=COLOR_A2,linewidth=1.0,label='A2',zorder=3)
        if len(self.peaks)>0:
            pk_in=self.peaks[(self.peaks>=i0)&(self.peaks<i1)]
            if len(pk_in)>0:
                ax.scatter(self.tvec[pk_in],self.a1[pk_in]*1e6+sc*0.5,
                    color='#F59E0B',s=30,zorder=5,marker='^',label='R-peak')
        ax.set_xlim(t0,t0+win); ax.set_xlabel('Time (s)',fontsize=10); ax.set_ylabel('µV',fontsize=10)
        ax.legend(loc='upper right',fontsize=9)
        ax.set_title(f'{self.cur_stem}  |  Window: {t0}–{t0+win}s',fontsize=11)
        ax.spines[['top','right']].set_visible(False); ax.set_facecolor('white')
        self.fig.tight_layout(); self.canvas.draw_idle()

    def _on_slider(self, val):
        self.t_lbl.setText(f'{val} s'); self._redraw()

    def _analyze_and_redraw(self):
        if self.a1 is not None: self._analyze(); self._redraw()

    def _on_quality_toggle(self, state):
        self.quality_ok = not bool(state); self._analyze()

    def _save_current(self):
        if not self.cur_stem or self.a1 is None: return
        qok = not self.quality_cb.isChecked()
        peaks = detect_rpeaks(bandpass_ecg(self.ecg_used or self.a1), SFREQ)
        hr, hrv = compute_hr_hrv(peaks, SFREQ)
        status, _ = classify_status(hr, hrv, qok,
            self.hr_high_spin.value(), HR_LOW, self.hrv_low_spin.value())
        rec = {
            'Filename': self.cur_stem,
            'HR (BPM)': hr if hr else 'N/A',
            'HRV RMSSD (ms)': hrv if hrv else 'N/A',
            'R-peaks': len(peaks),
            'Status': status if qok else 'Poor quality',
            'Note': self.note_edit.text().strip(),
        }
        for i, r in enumerate(self.results):
            if r['Filename'] == self.cur_stem:
                self.results[i] = rec; self._refresh_summary(); return
        self.results.append(rec); self._refresh_summary()

    def _refresh_summary(self):
        self.summary_list.clear()
        color_map = {'Calm':QColor('#DCFCE7'),'Stressed':QColor('#FECDD3'),
                     'Bradycardia':QColor('#FEF3C7'),'Poor quality':QColor('#FFF3CD')}
        for rec in self.results:
            status = rec['Status']
            item = QListWidgetItem(
                f"{rec['Filename']}   |   HR: {rec['HR (BPM)']} BPM   |   "
                f"HRV: {rec['HRV RMSSD (ms)']} ms   |   Status: {status}"
                + (f"   |   Note: {rec['Note']}" if rec['Note'] else ''))
            item.setBackground(color_map.get(status, QColor('white')))
            item.setFont(QFont('',12)); self.summary_list.addItem(item)
        if self.results: self.btn_export.setEnabled(True)

    def _export_excel(self):
        self._save_current()
        if not self.results:
            QMessageBox.warning(self,'No data','No results to export.'); return
        default_path = os.path.join(self.folder or '','ECG_HeartRate_Results.xlsx')
        path, _ = QFileDialog.getSaveFileName(self,'Save Excel',default_path,'Excel Files (*.xlsx)')
        if not path: return
        export_excel(path, self.results, self.hr_high_spin.value(), self.hrv_low_spin.value())
        QMessageBox.information(self,'Exported',f'Saved to:\n{path}')
        self.statusBar().showMessage(f'Excel exported: {path}')


def launch_ecg_viewer(folder=None) -> ECGViewer:
    win = ECGViewer(folder=folder); win.show(); return win


if __name__ == '__main__':
    app = QApplication(sys.argv); app.setStyle('Fusion')
    win = ECGViewer(folder=sys.argv[1] if len(sys.argv)>1 else None); win.show()
    sys.exit(app.exec_())
