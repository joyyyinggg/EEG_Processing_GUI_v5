# -*- coding: utf-8 -*-
"""
processing/preprocessor.py
===========================
EEG 前處理核心邏輯（無 GUI 相依）。

流程
----
1. 硬限幅 (Clipping)         ±CLIP_TRUN µV
2. MNE RawArray 建立 & 帶通濾波   0.1–40 Hz → 4–40 Hz
3. 重採樣 + EEG 參考
4. 自動壞通道偵測 (LOF)
5. 球面插值
6. ICA 擬合 & 自動偽跡偵測（EOG / EMG）
7. IC 解釋文字生成（供 ICAReviewDialog tooltip）
"""

import numpy as np
from scipy.signal import welch as sp_welch
from typing import Tuple, List, Dict, Optional

from config import (
    CH_NAMES, SFREQ, RANDOM_SEED,
    CLIP_TRUN, N_ICA_COMP, EOG_THRESHOLD, EMG_THRESHOLD, MAX_AUTO_EXCL,
)


# ─────────────────────────────────────────────────────────────
#  1. 硬限幅（Clipping）
# ─────────────────────────────────────────────────────────────
def apply_clipping(eeg_data: np.ndarray,
                   clip_trun: float = CLIP_TRUN
                   ) -> Tuple[np.ndarray, str]:
    """
    對每個通道執行 ±clip_trun 截斷，回傳處理後矩陣與摘要字串。

    Parameters
    ----------
    eeg_data : ndarray, shape (n_samples, n_channels)
    clip_trun : float, 截斷閾值（單位 V），預設 ±50 µV

    Returns
    -------
    eeg_data  : ndarray  已截斷的資料（原地修改副本）
    summary   : str      每通道截斷樣本數摘要
    """
    eeg_data   = eeg_data.copy()
    clip_counts = []
    for ch_i in range(eeg_data.shape[1]):
        n_hi = int(np.sum(eeg_data[:, ch_i] >  clip_trun))
        n_lo = int(np.sum(eeg_data[:, ch_i] < -clip_trun))
        eeg_data[:, ch_i] = np.clip(eeg_data[:, ch_i], -clip_trun, clip_trun)
        if n_hi + n_lo > 0:
            clip_counts.append(f'{CH_NAMES[ch_i]}:+{n_hi}/-{n_lo}')
    summary = ', '.join(clip_counts) if clip_counts else 'none'
    return eeg_data, summary


# ─────────────────────────────────────────────────────────────
#  2. 建立 MNE Raw & 基礎前處理
# ─────────────────────────────────────────────────────────────
def build_raw(eeg_data: np.ndarray):
    """
    將 ndarray 轉成 MNE RawArray，套用帶通濾波、重採樣、EEG 參考。

    Parameters
    ----------
    eeg_data : ndarray, shape (n_samples, 19)

    Returns
    -------
    raw : mne.io.RawArray
    """
    import mne
    info = mne.create_info(
        ch_names=CH_NAMES, sfreq=SFREQ, ch_types=['eeg'] * 19)
    raw  = mne.io.RawArray(eeg_data.T, info)
    raw.set_montage(
        mne.channels.make_standard_montage('standard_1020'),
        match_alias=False)
    raw.filter(l_freq=4, h_freq=40, verbose=False)
    raw.resample(SFREQ)
    raw, _ = mne.set_eeg_reference(raw, projection=True)
    return raw


# ─────────────────────────────────────────────────────────────
#  3. 自動壞通道偵測
# ─────────────────────────────────────────────────────────────
def detect_bad_channels(raw,
                        n_neighbors: int = 8,
                        threshold: float = 1.5
                        ) -> List[str]:
    """
    使用 MNE LOF 演算法自動偵測壞通道。

    Returns
    -------
    auto_bads : list[str]
    """
    import mne
    auto_bads, _ = mne.preprocessing.find_bad_channels_lof(
        raw, n_neighbors=n_neighbors, threshold=threshold,
        return_scores=True)
    return auto_bads


# ─────────────────────────────────────────────────────────────
#  4. 球面插值
# ─────────────────────────────────────────────────────────────
def interpolate_bad_channels(raw, confirmed_bads: List[str]):
    """
    對確認的壞通道執行球面插值，回傳插值後的 Raw（不改動原始）。

    Returns
    -------
    raw_interpolated : mne.io.RawArray
    """
    raw_working = raw.copy()
    raw_working.info['bads'] = confirmed_bads
    if confirmed_bads:
        raw_working.interpolate_bads(reset_bads=True)
    return raw_working


# ─────────────────────────────────────────────────────────────
#  5. ICA 擬合 & 自動偽跡偵測
# ─────────────────────────────────────────────────────────────
def run_ica(raw, random_state: int = RANDOM_SEED):
    """
    對已插值的 Raw 執行 Extended Infomax ICA。

    Returns
    -------
    ica          : mne.preprocessing.ICA
    filt_for_ica : mne.io.Raw  1–40 Hz 濾波版本（供 ICA 使用）
    """
    import mne
    filt_for_ica = raw.copy().filter(l_freq=1, h_freq=40, verbose=False)
    ica = mne.preprocessing.ICA(
        n_components=N_ICA_COMP, random_state=random_state,
        method='infomax', fit_params=dict(extended=True))
    ica.fit(filt_for_ica)
    return ica, filt_for_ica


def detect_artifact_ics(ica, filt_raw
                        ) -> Tuple[List[int], List[int]]:
    """
    偵測眼動（EOG）與肌電（EMG）成分。

    Returns
    -------
    eog_idx : list[int]
    emg_idx : list[int]
    """
    eog_idx, _ = ica.find_bads_eog(
        inst=filt_raw, ch_name=['Fp1', 'Fp2'],
        measure='correlation', threshold=EOG_THRESHOLD)
    emg_idx, _ = ica.find_bads_muscle(
        inst=filt_raw, threshold=EMG_THRESHOLD)
    return eog_idx, emg_idx


def apply_ic_exclusion(raw, ica, final_excl: List[int]):
    """
    將 ICA 排除清單套用到原始 Raw，回傳清除後的 Raw。

    Returns
    -------
    raw_clean : mne.io.Raw
    """
    ica.exclude = final_excl
    return ica.apply(raw.copy())


# ─────────────────────────────────────────────────────────────
#  6. IC 解釋文字（Tooltip）
# ─────────────────────────────────────────────────────────────
def explain_ic(ic_i: int, tag: str,
               ic_src: np.ndarray, ic_comps: np.ndarray) -> str:
    """
    為自動標記的 IC 產生人類可讀的解釋文字。

    Parameters
    ----------
    ic_i    : IC 索引
    tag     : 'EOG' 或 'EMG'
    ic_src  : shape (n_components, n_times)
    ic_comps: shape (n_channels, n_components)
    """
    ts     = ic_src[ic_i]
    pp     = float(np.ptp(ts))
    sd     = float(np.std(ts))
    freqs, psd = sp_welch(ts, fs=SFREQ, nperseg=min(1024, len(ts)))
    total_p  = float(np.sum(psd)) + 1e-30
    hf_pct   = float(np.sum(psd[freqs > 30])) / total_p * 100
    alpha_p  = float(np.sum(psd[(freqs >= 8) & (freqs <= 13)])) / total_p * 100
    lf_p     = float(np.sum(psd[freqs < 2])) / total_p * 100
    comp     = ic_comps[:, ic_i]
    front_idx = [CH_NAMES.index(c) for c in ['Fp1', 'Fp2'] if c in CH_NAMES]
    front_w   = float(np.mean(np.abs(comp[front_idx]))) if front_idx else 0.0

    lines = [f'[IC{ic_i:02d}] Auto-flagged as {tag}']
    if tag == 'EOG':
        lines += [
            f'  • Frontal weight avg: {front_w:.3f}  (high = eye artifact)',
            f'  • Low-freq power (<2Hz): {lf_p:.1f}%  (blink/saccade drift)',
            f'  • Peak-to-peak amplitude: {pp*1e6:.1f} µV',
            f'  • Criterion: Fp1/Fp2 correlation ≥ {EOG_THRESHOLD}',
        ]
    else:
        lines += [
            f'  • High-freq power (>30Hz): {hf_pct:.1f}%  (muscle noise)',
            f'  • Std dev: {sd*1e6:.2f} µV',
            f'  • Alpha power (8-13Hz): {alpha_p:.1f}%',
            f'  • Criterion: EMG z-score ≥ {EMG_THRESHOLD}',
        ]
    return '\n'.join(lines)


def build_ic_reasons(ica, filt_raw,
                     eog_idx: List[int], emg_idx: List[int]) -> Dict[int, str]:
    """
    為所有自動標記的 IC 建立解釋字典。

    Returns
    -------
    ic_reasons : dict {ic_index: explanation_str}
    """
    ic_src   = ica.get_sources(filt_raw).get_data()
    ic_comps = ica.get_components()
    reasons  = {}
    for i in eog_idx:
        reasons[i] = explain_ic(i, 'EOG', ic_src, ic_comps)
    for i in emg_idx:
        if i not in reasons:
            reasons[i] = explain_ic(i, 'EMG', ic_src, ic_comps)
    return reasons


def cap_auto_exclusion(ica, eog_idx: List[int], emg_idx: List[int],
                       max_excl: int = MAX_AUTO_EXCL) -> List[int]:
    """
    依 EOG 優先合併排除清單，並限制最多 max_excl 個。

    Returns
    -------
    final_auto : list[int]
    """
    combined = list(dict.fromkeys(eog_idx + emg_idx))
    if len(combined) > max_excl:
        combined = combined[:max_excl]
    ica.exclude = combined
    return combined
