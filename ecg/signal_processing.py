# -*- coding: utf-8 -*-
"""ecg/signal_processing.py — Pure ECG signal processing (no GUI)."""

import numpy as np
from typing import Tuple, Optional
from ecg.ecg_config import (
    SFREQ, R_MIN_DIST_S, R_HEIGHT_PCTILE, PAN_TOMPKINS_WIN,
    ART_BUFFER_MS, DEFAULT_ART_Z, MAX_ART_RATIO,
    POOR_SCORE_THRESHOLD, HR_HIGH, HR_LOW, HRV_LOW, STATUS_FILL,
)


def load_ecg(fpath: str, trim_s: int = 30):
    try:
        from eeg_decoder import Decoder
        raw_data = Decoder().read_decoded(fpath)
    except Exception:
        raw_data = np.loadtxt(fpath)
    i0 = int(trim_s * SFREQ)
    i1 = raw_data.shape[0] - i0
    data   = raw_data[i0:i1, :]
    n_ch   = data.shape[1]
    ecg_a1 = data[:, 19] if n_ch > 19 else np.zeros(len(data))
    ecg_a2 = data[:, 20] if n_ch > 20 else np.zeros(len(data))
    all_ch = data[:, :min(n_ch, 21)]
    tvec   = np.arange(len(ecg_a1)) / SFREQ
    return ecg_a1, ecg_a2, tvec, all_ch


def bandpass_ecg(signal: np.ndarray, fs: float = SFREQ) -> np.ndarray:
    from scipy.signal import butter, filtfilt
    b, a = butter(4, [0.5/(fs/2), 40.0/(fs/2)], btype='band')
    return filtfilt(b, a, signal)


def detect_rpeaks(ecg: np.ndarray, fs: float = SFREQ) -> np.ndarray:
    from scipy.signal import find_peaks
    diff_sq    = np.diff(ecg, prepend=ecg[0]) ** 2
    win        = int(PAN_TOMPKINS_WIN * fs)
    integrated = np.convolve(diff_sq, np.ones(win)/win, mode='same')
    min_dist   = int(R_MIN_DIST_S * fs)
    height     = np.percentile(integrated, R_HEIGHT_PCTILE)
    peaks, _   = find_peaks(integrated, height=height, distance=min_dist)
    return peaks


def mask_artifacts(ecg: np.ndarray, fs: float = SFREQ,
                   threshold_z: float = DEFAULT_ART_Z):
    from scipy.ndimage import binary_dilation
    from scipy.signal import medfilt
    kernel  = int(fs * 1.0); kernel = kernel + 1 if kernel % 2 == 0 else kernel
    baseline    = medfilt(ecg, kernel_size=kernel)
    ecg_detrend = ecg - baseline
    mad  = np.median(np.abs(ecg_detrend)) + 1e-9
    z    = np.abs(ecg_detrend) / (mad * 1.4826)
    art_mask = z > threshold_z
    struct   = np.ones(int(ART_BUFFER_MS / 1000 * fs), dtype=bool)
    art_mask = binary_dilation(art_mask, structure=struct)
    clean    = ecg.copy(); clean[art_mask] = np.median(ecg)
    return clean, float(art_mask.sum() / len(ecg))


def _score_channel(sig: np.ndarray, fs: float = SFREQ) -> float:
    from scipy.signal import butter, filtfilt, welch
    b, a = butter(2, 0.5/(fs/2), btype='high')
    sig_hp = filtfilt(b, a, sig)
    dc_score = min(abs(np.median(sig)) * 1e6 / 10, 40)
    segs   = np.array_split(sig_hp, 20)
    pps    = np.array([np.ptp(s) for s in segs])
    cv_score = min((np.std(pps)/(np.mean(pps)+1e-9))*30, 40)
    try:
        f, psd = welch(sig_hp, fs=fs, nperseg=min(1024, len(sig_hp)))
        hf_score = min(np.sum(psd[f>40])/(np.sum(psd)+1e-30)*20, 20)
    except Exception:
        hf_score = 0.0
    return float(dc_score + cv_score + hf_score)


def select_best_ecg(a1: np.ndarray, a2: np.ndarray):
    s1, s2 = _score_channel(a1), _score_channel(a2)
    if s1 <= s2:
        best_sig, best_lbl, best_score = a1, 'A1', s1
    else:
        best_sig, best_lbl, best_score = a2, 'A2', s2
    if best_score < POOR_SCORE_THRESHOLD:
        quality = 'good' if best_score < 30 else 'acceptable'
        return best_sig, f'{best_lbl} (score:{best_score:.0f})', quality
    diff_sig   = a1 - a2
    score_diff = _score_channel(diff_sig)
    if score_diff < min(s1, s2) * 0.8:
        return (diff_sig,
                f'A1-A2 diff (A1:{s1:.0f}/A2:{s2:.0f}/diff:{score_diff:.0f})',
                'acceptable')
    return best_sig, f'{best_lbl} (poor, score:{best_score:.0f})', 'poor'


def compute_hr_hrv(peaks: np.ndarray, fs: float = SFREQ):
    if len(peaks) < 3:
        return None, None
    rr_ms  = np.diff(peaks) / fs * 1000
    hr_bpm = round(float(60000 / np.mean(rr_ms)), 1)
    rmssd  = round(float(np.sqrt(np.mean(np.diff(rr_ms)**2))), 1)
    return hr_bpm, rmssd


def classify_status(hr, hrv, quality_ok: bool,
                    hr_high=HR_HIGH, hr_low=HR_LOW, hrv_low=HRV_LOW):
    if not quality_ok or hr is None:
        return 'Poor quality', STATUS_FILL['Poor quality']
    if hr > hr_high or (hrv is not None and hrv < hrv_low):
        return 'Stressed',    STATUS_FILL['Stressed']
    if hr < hr_low:
        return 'Bradycardia', STATUS_FILL['Bradycardia']
    return 'Calm',            STATUS_FILL['Calm']
