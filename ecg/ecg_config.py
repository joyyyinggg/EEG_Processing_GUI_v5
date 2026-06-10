# -*- coding: utf-8 -*-
"""ecg/ecg_config.py — ECG module constants."""

SFREQ = 1000
CH_NAMES_ALL = [
    'Fp1','Fp2','F7','F3','Fz','F4','F8',
    'T3','C3','Cz','C4','T4','T5','P3','Pz','P4','T6','O1','O2','A1','A2',
]
ECG_CHS = ['A1','A2']
ECG_IDX = [19, 20]

HR_HIGH  = 100
HR_LOW   = 60
HRV_LOW  = 20

POOR_SCORE_THRESHOLD = 55
DEFAULT_ART_Z    = 4.0
ART_BUFFER_MS    = 200
MAX_ART_RATIO    = 0.30
R_MIN_DIST_S     = 0.4
R_HEIGHT_PCTILE  = 75
PAN_TOMPKINS_WIN = 0.15

STATUS_FILL = {
    'Calm':         'DCFCE7',
    'Stressed':     'FECDD3',
    'Bradycardia':  'FEF3C7',
    'Poor quality': 'FFF3CD',
}

COLOR_A1   = '#9123AA'
COLOR_A2   = '#3B82F6'
COLOR_GRAY = '#9CA3AF'
