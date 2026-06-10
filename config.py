# -*- coding: utf-8 -*-
"""
config.py
=========
全域常數與設定。所有模組皆從此處 import，
修改時只需改這一份檔案即可。
"""

import re
import os
import random
import numpy as np

# ─── 隨機種子 ──────────────────────────────────────────────────
RANDOM_SEED    = 42

# ─── EEG 基本參數 ──────────────────────────────────────────────
SFREQ          = 1000          # Hz
EPOCH_LENGTH   = 10            # seconds per epoch
METHOD         = 'wpli'        # 連接度方法

# ─── 前處理參數 ────────────────────────────────────────────────
CLIP_TRUN      = 5e-5          # [v11] 硬限幅閾值 ±50 µV（單位 V）
N_ICA_COMP     = 15            # ICA 成分數
EOG_THRESHOLD  = 0.5           # 眼動 IC 偵測相關係數閾值
EMG_THRESHOLD  = 0.7           # 肌電 IC 偵測 z-score 閾值
DIFF_THRESHOLD = 0.05          # 差分通道偵測閾值（備用）
MAX_AUTO_EXCL  = 5             # [v10] 自動排除 IC 上限（EOG 優先）
BAD_CH_LIMIT   = 22            # 壞通道百分比上限，超過則跳過此筆

# ─── 通道名稱（19 通道，標準 10-20）──────────────────────────
CH_NAMES = [
    'Fp1', 'Fp2',
    'F7',  'F3',  'Fz',  'F4',  'F8',
    'T3',  'C3',  'Cz',  'C4',  'T4',
    'T5',  'P3',  'Pz',  'P4',  'T6',
    'O1',  'O2',
]

# ─── ROI 短名稱（18 個 ROI，雙側）───────────────────────────
ROI_SHORT_NAMES = [
    'ACC-L',    'ACC-R',
    'Motor-L',  'Motor-R',
    'Visual-L', 'Visual-R',
    'OFC-L',    'OFC-R',
    'Temp-L',   'Temp-R',
    'SupPar-L', 'SupPar-R',
    'InfPar-L', 'InfPar-R',
    'Aud-L',    'Aud-R',
    'ROI9-L',   'ROI9-R',
]

# ─── 檔案命名規則 ──────────────────────────────────────────────
# 格式：subj{數字}_{session名稱}.txt，例如 subj01_rest1.txt
# sub01-25 → epilepsy；sub26+ → normal
FILE_PATTERN = re.compile(r'subj(\d+)_(\w+)', re.IGNORECASE)

# ─── 環境變數（可重現性）──────────────────────────────────────
os.environ['PYTHONHASHSEED']          = str(RANDOM_SEED)
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)
