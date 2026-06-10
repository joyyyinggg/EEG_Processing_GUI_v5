# -*- coding: utf-8 -*-
"""
analysis/connectivity.py
=========================
wPLI 功能連接度計算與 Excel 輸出。

函式
----
compute_wpli      : 計算 Theta / Alpha / Beta 三頻帶 wPLI 矩陣
save_excel        : 將三頻帶矩陣輸出為多工作表 Excel
"""

from typing import Tuple, List
import numpy as np
import pandas as pd

from config import SFREQ, METHOD


def compute_wpli(roi_tc: np.ndarray,
                 sfreq: float = SFREQ
                 ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    對 ROI time courses 計算 wPLI 連接度。

    Parameters
    ----------
    roi_tc : ndarray, shape (n_epochs, n_rois, n_times)
    sfreq  : sampling frequency (Hz)

    Returns
    -------
    ct  : Theta  (4–8  Hz) 對稱矩陣
    ca  : Alpha  (8–12 Hz) 對稱矩陣
    cb_ : Beta   (12–30 Hz) 對稱矩陣
    cm  : 原始 dense 輸出 (n_rois, n_rois, 3)
    """
    import mne_connectivity

    con = mne_connectivity.spectral_connectivity_epochs(
        list(roi_tc),
        method=METHOD,
        mode='multitaper',
        fmin=(4, 8, 12),
        fmax=(8, 12, 30),
        faverage=True,
        sfreq=sfreq,
    )
    cm  = con.get_data(output='dense')

    # 對稱化（上三角 + 下三角）
    ct  = cm[:, :, 0]; ct  = ct  + ct.T
    ca  = cm[:, :, 1]; ca  = ca  + ca.T
    cb_ = cm[:, :, 2]; cb_ = cb_ + cb_.T

    return ct, ca, cb_, cm


def save_excel(path: str,
               ct: np.ndarray,
               ca: np.ndarray,
               cb_: np.ndarray,
               roi_names: List[str]) -> None:
    """
    將三頻帶連接矩陣輸出為多工作表 Excel 檔案。

    Parameters
    ----------
    path      : 輸出路徑（含副檔名 .xlsx）
    ct / ca / cb_ : Theta / Alpha / Beta 矩陣
    roi_names : ROI 名稱清單
    """
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        for mat, sheet in zip(
            [ct, ca, cb_],
            ['Theta (4-8 Hz)', 'Alpha (8-12 Hz)', 'Beta (12-30 Hz)'],
        ):
            pd.DataFrame(mat, index=roi_names, columns=roi_names).to_excel(
                writer, sheet_name=sheet)
