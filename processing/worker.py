# -*- coding: utf-8 -*-
"""
processing/worker.py
====================
ProcessWorker — 背景處理執行緒（QThread）。

負責協調整個處理流程：
  1. 讀取 EEG 資料（透過 eeg_decoder.Decoder）
  2. 硬限幅 → 前處理 → 壞通道偵測
  3. 發 Signal 等待 UI 確認壞通道
  4. 球面插值 → 插值前後對比確認
  5. ICA 擬合 → 自動偵測 → 發 Signal 等待 UI 確認
  6. Epoch 建立 → Source reconstruction → ROI time courses
  7. wPLI 連接度 → 輸出圖表 & Excel

與 GUI 的溝通機制
-----------------
Worker 端：emit Signal（need_raw_review / need_interp_review / need_ica_review）
MainWindow：在主執行緒中彈出 Dialog，使用者操作後呼叫 set_user_* 方法。
Worker 端：_wait_user() 阻塞等待，收到結果後繼續。
"""

import os
import random
import traceback
import threading

import numpy as np
import pandas as pd

from PyQt5.QtCore import QThread, pyqtSignal, QMutex

from config import (
    CH_NAMES, SFREQ, EPOCH_LENGTH, METHOD, RANDOM_SEED,
    N_ICA_COMP, CLIP_TRUN, MAX_AUTO_EXCL, BAD_CH_LIMIT,
    EOG_THRESHOLD, EMG_THRESHOLD,
)
from processing.preprocessor import (
    apply_clipping, build_raw, detect_bad_channels,
    interpolate_bad_channels, run_ica, detect_artifact_ics,
    build_ic_reasons, cap_auto_exclusion, apply_ic_exclusion,
)
from analysis.connectivity import compute_wpli, save_excel
from analysis.visualization import draw_all_figures
from analysis.source_recon import build_epochs, run_source_recon, extract_roi_tc


class ProcessWorker(QThread):
    """
    Signals
    -------
    log               (str)
    progress          (int current, int total)
    status            (str)
    need_raw_review   (raw, auto_bads, file_stem, file_idx, total)
    need_interp_review(raw_before, raw_after, bads, file_stem, fi, total)
    need_ica_review   (ica, raw_before, raw_after,
                       eog_idx, emg_idx, file_stem, fi, total, ic_reasons)
    done              ()
    error             (str)
    """

    log                = pyqtSignal(str)
    progress           = pyqtSignal(int, int)
    status             = pyqtSignal(str)
    need_raw_review    = pyqtSignal(object, list, str, int, int)
    need_interp_review = pyqtSignal(object, object, list, str, int, int)
    need_ica_review    = pyqtSignal(object, object, object,
                                    list, list, str, int, int, object)
    done               = pyqtSignal()
    error              = pyqtSignal(str)

    def __init__(self, txt_files: list, out_folder: str, shared_res: dict):
        super().__init__()
        self.txt_files        = txt_files
        self.out_folder       = out_folder
        self.shared_res       = shared_res
        self._mutex           = QMutex()
        self._user_bads            = None
        self._user_excl            = None
        self._user_action          = None
        self._user_interp_action   = None
        self._waiting              = threading.Event()
        self.all_bad_channels      = []
        self.all_ica_log           = []

    # ── 使用者回應介面（由主執行緒呼叫）────────────────────────
    def set_user_bads(self, bads: list, action: str = 'confirm'):
        self._user_bads   = bads
        self._user_action = action
        self._waiting.set()

    def set_user_excl(self, excl: list, action: str = 'confirm'):
        self._user_excl   = excl
        self._user_action = action
        self._waiting.set()

    def set_user_interp_action(self, action: str):
        self._user_interp_action = action
        self._waiting.set()

    def _wait_user(self):
        self._waiting.clear()
        self._waiting.wait()

    # ── 主流程 ────────────────────────────────────────────────
    def run(self):
        try:
            import mne
            from eeg_decoder import Decoder
            from sklearn.preprocessing import MinMaxScaler
            from nilearn import plotting as nlplot
            from mne_connectivity.viz import plot_connectivity_circle

            mne.set_log_level('WARNING')
            np.random.seed(RANDOM_SEED)
            random.seed(RANDOM_SEED)

            src              = self.shared_res['src']
            bem              = self.shared_res['bem']
            valid_roi_labels = self.shared_res['valid_roi_labels']
            valid_roi_names  = self.shared_res['valid_roi_names']
            roi_coords_18    = self.shared_res['roi_coords_18']
            subj_name        = self.shared_res['subj_name']
            decoder          = Decoder()
            total            = len(self.txt_files)

            file_idx = 0
            while file_idx < total:
                fpath     = self.txt_files[file_idx]
                file_stem = os.path.splitext(os.path.basename(fpath))[0]

                self.progress.emit(file_idx + 1, total)
                self.status.emit(f'Processing {file_stem}  ({file_idx+1}/{total})')
                self.log.emit(
                    f'\n{"="*60}\n[{file_idx+1}/{total}] {file_stem}\n{"="*60}')

                try:
                    np.random.seed(RANDOM_SEED + file_idx)
                    base_dir = os.path.dirname(fpath)
                    output_dir = os.path.join(
                        base_dir, f'{subj_name}_con_figures_{EPOCH_LENGTH}s', file_stem)
                    output_dir_matrix = os.path.join(
                        base_dir, f'{subj_name}_matrix_{EPOCH_LENGTH}s')
                    cache_dir = os.path.join(
                        base_dir, f'{subj_name}_roi_tc_cache')
                    for d in [output_dir, output_dir_matrix, cache_dir]:
                        os.makedirs(d, exist_ok=True)

                    cache_tc    = os.path.join(cache_dir, f'{file_stem}_roi_tc.npy')
                    cache_names = os.path.join(cache_dir, f'{file_stem}_roi_names.npy')

                    # ── Cache 命中 ──────────────────────────────
                    if os.path.exists(cache_tc) and os.path.exists(cache_names):
                        self.log.emit('  [CACHE] roi_tc cache found, skipping preprocessing.')
                        roi_tc         = np.load(cache_tc)
                        used_roi_names = np.load(cache_names, allow_pickle=True).tolist()
                        self.log.emit(f'  roi_tc.shape = {roi_tc.shape}')
                        file_idx += 1
                    else:
                        # ── 讀取資料 ──────────────────────────────
                        self.log.emit('  Reading EEG data...')
                        eeg_data = decoder.read_decoded(fpath)
                        eeg_data = eeg_data[30000:-30000, :19]
                        self.log.emit(f'  Shape after trim: {eeg_data.shape}')

                        # ── [v11] 硬限幅 ──────────────────────────
                        eeg_data, clip_summary = apply_clipping(eeg_data, CLIP_TRUN)
                        self.log.emit(
                            f'  [CLIP] ±{CLIP_TRUN*1e6:.0f}µV  clipped: {clip_summary}')

                        # ── 前處理 ────────────────────────────────
                        raw = build_raw(eeg_data)

                        # ── 壞通道偵測 ────────────────────────────
                        self.log.emit('  Detecting bad channels (LOF)...')
                        auto_bads = detect_bad_channels(raw)
                        self.log.emit(f'  Auto-detected: {auto_bads}')

                        # ── [USER] 壞通道確認 ─────────────────────
                        self.log.emit('  >> Waiting: bad channel confirmation...')
                        self._user_bads = None; self._user_action = None
                        self.need_raw_review.emit(
                            raw.copy(), auto_bads, file_stem, file_idx + 1, total)
                        self._wait_user()
                        action         = self._user_action
                        confirmed_bads = self._user_bads

                        if action == 'prev':
                            file_idx = max(0, file_idx - 1)
                            self.log.emit('  >> User navigated BACK.'); continue
                        if action in ('next', 'skip'):
                            file_idx += 1
                            self.log.emit(f'  >> User {action.upper()}.'); continue

                        self.log.emit(f'  Confirmed bad channels: {confirmed_bads}')

                        # [v11] 記錄 auto/manual 選擇模式
                        auto_set     = set(auto_bads)
                        user_set     = set(confirmed_bads)
                        added_manual = sorted(user_set - auto_set)
                        removed_auto = sorted(auto_set - user_set)
                        bad_select_mode = ('auto'
                                           if not added_manual and not removed_auto
                                           else 'manual')
                        self.log.emit(
                            f'  [BAD CH] mode={bad_select_mode}  '
                            f'added={added_manual}  removed={removed_auto}')

                        pct = len(confirmed_bads) / len(CH_NAMES) * 100
                        if pct > BAD_CH_LIMIT:
                            self.log.emit(
                                f'  [SKIP] Bad ch {len(confirmed_bads)}/{len(CH_NAMES)}'
                                f' = {pct:.0f}% > {BAD_CH_LIMIT}%')
                            self.all_bad_channels.append({
                                '檔案名稱': file_stem,
                                '壞通道': ', '.join(confirmed_bads),
                                '壞通道數量': len(confirmed_bads), '狀態': 'SKIP'})
                            file_idx += 1; continue

                        # ── [v9] 插值 + 對比迴圈 ─────────────────
                        re_interp = True
                        while re_interp:
                            raw_before_interp = raw.copy()
                            raw_working       = interpolate_bad_channels(
                                raw, confirmed_bads)
                            if confirmed_bads:
                                self.log.emit(f'  Interpolated: {confirmed_bads}')
                            else:
                                self.log.emit('  No channels to interpolate.')

                            self.log.emit('  >> Waiting: interpolation check...')
                            self._user_interp_action = None
                            self.need_interp_review.emit(
                                raw_before_interp, raw_working.copy(),
                                confirmed_bads, file_stem, file_idx + 1, total)
                            self._wait_user()

                            if self._user_interp_action == 're_interp':
                                self.log.emit('  >> User requested re-interpolation.')
                                self._user_bads = None; self._user_action = None
                                self.need_raw_review.emit(
                                    raw_before_interp.copy(),
                                    confirmed_bads, file_stem, file_idx + 1, total)
                                self._wait_user()
                                act2 = self._user_action
                                if act2 in ('prev', 'next', 'skip'):
                                    file_idx = (max(0, file_idx - 1)
                                                if act2 == 'prev' else file_idx + 1)
                                    re_interp = False; break
                                confirmed_bads = self._user_bads
                            else:
                                re_interp = False
                                raw = raw_working

                        if self._user_action in ('prev', 'next', 'skip'):
                            continue

                        # ── 儲存插值記錄 ──────────────────────────
                        interp_rec_dir = os.path.join(
                            base_dir, f'{subj_name}_interp_records', file_stem)
                        os.makedirs(interp_rec_dir, exist_ok=True)
                        _save_interp_figure(
                            raw_before_interp, raw, confirmed_bads,
                            file_stem, interp_rec_dir)
                        pd.DataFrame([{
                            '檔案名稱':   file_stem,
                            '插值通道':   ', '.join(confirmed_bads) or '無',
                            '插值通道數': len(confirmed_bads),
                            '通道比例%':  round(pct, 1),
                            '自動偵測':   ', '.join(auto_bads) or '無',
                            '人工新增':   ', '.join(added_manual) or '無',
                            '人工移除':   ', '.join(removed_auto) or '無',
                            '選擇方式':   bad_select_mode,
                            '狀態':       'OK',
                        }]).to_excel(
                            os.path.join(interp_rec_dir, 'interp_log.xlsx'),
                            index=False, engine='openpyxl')
                        self.all_bad_channels.append({
                            '檔案名稱': file_stem,
                            '壞通道': ', '.join(confirmed_bads) or '無',
                            '壞通道數量': len(confirmed_bads), '狀態': 'OK'})

                        # ── ICA ──────────────────────────────────
                        self.log.emit('  Running ICA...')
                        ica, filt_raw = run_ica(raw)
                        eog_idx, emg_idx = detect_artifact_ics(ica, filt_raw)
                        ic_reasons = build_ic_reasons(
                            ica, filt_raw, eog_idx, emg_idx)
                        for r in ic_reasons.values():
                            self.log.emit(r)

                        auto_excl = cap_auto_exclusion(ica, eog_idx, emg_idx)
                        self.log.emit(
                            f'  Auto-exclude — EOG:{eog_idx}  EMG:{emg_idx}  '
                            f'Applied:{auto_excl}')

                        raw_before_ica = raw.copy()
                        raw_after_ica  = apply_ic_exclusion(raw, ica, auto_excl)

                        # ── [USER] ICA 確認 ───────────────────────
                        self.log.emit('  >> Waiting: ICA review...')
                        self._user_excl = None; self._user_action = None
                        self.need_ica_review.emit(
                            ica, raw_before_ica, raw_after_ica,
                            eog_idx, emg_idx, file_stem,
                            file_idx + 1, total, ic_reasons)
                        self._wait_user()
                        action     = self._user_action
                        final_excl = self._user_excl

                        if action == 'prev':
                            file_idx = max(0, file_idx - 1)
                            self.log.emit('  >> BACK.'); continue
                        if action in ('next', 'skip'):
                            file_idx += 1
                            self.log.emit(f'  >> {action.upper()}.'); continue

                        # [v11] ICA 選擇模式
                        auto_set_ica  = set(auto_excl)
                        final_set_ica = set(final_excl)
                        ica_added     = sorted(final_set_ica - auto_set_ica)
                        ica_removed   = sorted(auto_set_ica - final_set_ica)
                        ica_select_mode = ('auto'
                                           if not ica_added and not ica_removed
                                           else 'manual')
                        self.log.emit(
                            f'  [ICA] mode={ica_select_mode}  '
                            f'added={ica_added}  restored={ica_removed}')

                        raw = apply_ic_exclusion(raw_before_ica, ica, final_excl)
                        self.all_ica_log.append({
                            '檔案名稱':    file_stem,
                            '排除IC總數':  len(final_excl),
                            '眼動IC':      str(eog_idx),
                            '肌電IC':      str(emg_idx),
                            '排除IC索引':  str(final_excl),
                            '人工新增排除': str(ica_added),
                            '人工恢復IC':   str(ica_removed),
                            '選擇方式':     ica_select_mode,
                        })

                        # ── 儲存 ICA 記錄 ─────────────────────────
                        ica_rec_dir = os.path.join(
                            base_dir, f'{subj_name}_ica_records', file_stem)
                        os.makedirs(ica_rec_dir, exist_ok=True)
                        _save_ica_figures(
                            raw_before_ica, raw, ica,
                            eog_idx, emg_idx, file_stem, ica_rec_dir)
                        pd.DataFrame([{
                            '檔案名稱':    file_stem,
                            '排除IC總數':  len(final_excl),
                            '眼動IC':      str(eog_idx),
                            '肌電IC':      str(emg_idx),
                            '手動調整IC':  str([i for i in final_excl
                                              if i not in eog_idx and i not in emg_idx]),
                            '人工新增排除': str(ica_added),
                            '人工恢復IC':   str(ica_removed),
                            '選擇方式':     ica_select_mode,
                            '排除IC索引':  str(final_excl),
                        }]).to_excel(
                            os.path.join(ica_rec_dir, 'ica_log.xlsx'),
                            index=False, engine='openpyxl')

                        # ── Epochs & Source recon ─────────────────
                        self.log.emit('  Building epochs...')
                        epo = build_epochs(raw, EPOCH_LENGTH, SFREQ)
                        self.log.emit(f'  Valid epochs: {len(epo)}')

                        self.log.emit('  Source reconstruction (dSPM)...')
                        stcs = run_source_recon(
                            raw.info, epo, src, bem,
                            self.shared_res['subjects_dir'])

                        roi_tc = extract_roi_tc(stcs, valid_roi_labels, src)
                        used_roi_names = valid_roi_names
                        self.log.emit(f'  roi_tc.shape = {roi_tc.shape}')

                        np.save(cache_tc,    roi_tc)
                        np.save(cache_names, np.array(used_roi_names, dtype=object))
                        self.log.emit('  Cache saved.')
                        file_idx += 1

                    # ── Connectivity & Output ──────────────────
                    self.log.emit('  Computing wPLI connectivity...')
                    ct, ca, cb_, cm = compute_wpli(roi_tc, SFREQ)

                    if np.count_nonzero(ct) == 0 or np.isnan(ct).any():
                        self.log.emit('  [WARN] Connectivity matrix abnormal, skip.')
                        continue

                    for xp in [
                        os.path.join(output_dir,
                            f'{subj_name}_{EPOCH_LENGTH}s_{file_stem}.xlsx'),
                        os.path.join(output_dir_matrix,
                            f'{subj_name}_{EPOCH_LENGTH}s_{file_stem}.xlsx'),
                    ]:
                        save_excel(xp, ct, ca, cb_, used_roi_names)
                    self.log.emit('  Excel saved.')

                    draw_all_figures(
                        ct, ca, cb_, cm, used_roi_names,
                        roi_coords_18, output_dir,
                        subj_name, EPOCH_LENGTH, METHOD, file_stem,
                        base_dir, nlplot, plot_connectivity_circle,
                        MinMaxScaler)
                    self.log.emit(f'  Figures saved.')
                    self.log.emit(f'  Done: {file_stem}')

                except Exception as e:
                    self.log.emit(
                        f'  [ERROR] {file_stem}: {e}\n{traceback.format_exc()}')
                    file_idx += 1

            # ── 統計彙整 Excel ────────────────────────────────
            out_stat = os.path.join(
                self.out_folder,
                f'{self.shared_res["subj_name"]}_con_figures_{EPOCH_LENGTH}s')
            os.makedirs(out_stat, exist_ok=True)
            if self.all_bad_channels:
                pd.DataFrame(self.all_bad_channels).to_excel(
                    os.path.join(out_stat, '所有檔案_壞通道統計.xlsx'),
                    index=False, engine='openpyxl')
            if self.all_ica_log:
                pd.DataFrame(self.all_ica_log).to_excel(
                    os.path.join(out_stat, '所有檔案_ICA排除統計.xlsx'),
                    index=False, engine='openpyxl')

            self.done.emit()

        except Exception as e:
            self.error.emit(f'{e}\n{traceback.format_exc()}')


# ─────────────────────────────────────────────────────────────
#  Helper: 儲存圖檔（呼叫 visualization 模組）
# ─────────────────────────────────────────────────────────────
def _save_interp_figure(raw_before, raw_after, bads, file_stem, out_dir):
    from analysis.visualization import save_interp_figure
    save_interp_figure(raw_before, raw_after, bads, file_stem, out_dir)


def _save_ica_figures(raw_before, raw_after, ica,
                      eog_idx, emg_idx, file_stem, output_dir):
    from analysis.visualization import save_ica_figures
    save_ica_figures(
        raw_before, raw_after, ica,
        eog_idx, emg_idx, file_stem, output_dir)
