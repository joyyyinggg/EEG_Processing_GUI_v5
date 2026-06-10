# -*- coding: utf-8 -*-
"""
analysis/source_recon.py
=========================
Epoch 建立、dSPM source reconstruction 與 ROI time course 提取。
"""

import numpy as np
from config import SFREQ, EPOCH_LENGTH, RANDOM_SEED


def build_epochs(raw, epoch_length: int = EPOCH_LENGTH, sfreq: float = SFREQ):
    """
    從 Raw 建立固定長度 Epochs（無 stimulus，連續切割）。

    Returns
    -------
    epo : mne.Epochs
    """
    import mne
    n_samp = raw.n_times
    events = np.array([
        [i, 0, 1]
        for i in range(0, n_samp, int(sfreq * epoch_length))
    ])
    epo = mne.Epochs(
        raw, events, event_id=1,
        tmin=0, tmax=epoch_length - 1.0 / sfreq,
        baseline=None, preload=True,
    )
    epo.drop_bad()
    return epo


def run_source_recon(info, epo, src, bem, subjects_dir):
    """
    使用 dSPM 做 source reconstruction，回傳 stc 列表。

    Parameters
    ----------
    info         : mne.Info
    epo          : mne.Epochs
    src          : source space（來自 shared_res）
    bem          : BEM solution（來自 shared_res）
    subjects_dir : str

    Returns
    -------
    stcs : list[mne.SourceEstimate]
    """
    import mne
    from mne.minimum_norm import make_inverse_operator, apply_inverse_epochs

    fwd  = mne.make_forward_solution(
        info, trans='fsaverage',
        src=src, bem=bem,
        meg=False, eeg=True, mindist=5.0,
    )
    ncov = mne.compute_covariance(epo, method='empirical')
    inv  = make_inverse_operator(info, fwd, ncov, loose=0.2, depth=0.8)
    stcs = apply_inverse_epochs(
        epo, inv,
        lambda2=1.0 / 9.0,
        method='dSPM',
        pick_ori=None,
        return_generator=False,
    )
    return stcs


def extract_roi_tc(stcs, valid_roi_labels, src) -> np.ndarray:
    """
    從 stc 列表提取各 ROI 的平均 time course。

    Returns
    -------
    roi_tc : ndarray, shape (n_epochs, n_rois, n_times)
    """
    import mne
    roi_tc = np.array([
        mne.extract_label_time_course(s, valid_roi_labels, src, mode='mean')
        for s in stcs
    ])
    return roi_tc
