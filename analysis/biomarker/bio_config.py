# -*- coding: utf-8 -*-
"""analysis/biomarker/bio_config.py — All biomarker constants."""

THRESHOLD  = 0.0
ALPHA_FDR  = 0.05
EFFECT_MIN = 0.3
AUC_MIN    = 0.70
MAX_COMBO  = 5
TREND_P_RAW  = 0.10
TREND_EFFECT = 0.20
TREND_AUC    = 0.60
TOP_TREND_N  = 20
PATIENT_MAX_ID       = 25
HIGH_AED_THRESHOLD   = 3
STATE_ORDER  = ['rest1', 'reading', 'rest2']
FREQ_BANDS   = ['Theta', 'Alpha', 'Beta']
COMPARISONS  = {
    'C1_Normal_vs_Epilepsy':  ('Normal','Epilepsy', ['Normal'],['Low-dose','High-dose']),
    'C2_Normal_vs_LowDose':   ('Normal','Low-dose', ['Normal'],['Low-dose']),
    'C3_LowDose_vs_HighDose': ('Low-dose','High-dose',['Low-dose'],['High-dose']),
}
GROUP_COLORS = {'Normal':'#2196F3','Low-dose':'#4CAF50','High-dose':'#F44336'}
REGION_MAP   = {
    'Frontal':  ['ROI4_LH','ROI4_RH','ROI1_LH','ROI1_RH'],
    'Central':  ['ROI2_LH','ROI2_RH'],
    'Parietal': ['ROI6_LH','ROI6_RH','ROI7_LH','ROI7_RH'],
    'Temporal': ['ROI5_LH','ROI5_RH','ROI8_LH','ROI8_RH'],
    'Occipital':['ROI3_LH','ROI3_RH'],
}
REGION_COLORS = {
    'Frontal':'#4C72B0','Central':'#DD8452','Parietal':'#55A868',
    'Temporal':'#C44E52','Occipital':'#8172B2',
}
ROI_KEY_MAP = [
    'ROI1_LH','ROI1_RH','ROI2_LH','ROI2_RH','ROI3_LH','ROI3_RH',
    'ROI4_LH','ROI4_RH','ROI5_LH','ROI5_RH','ROI6_LH','ROI6_RH',
    'ROI7_LH','ROI7_RH','ROI8_LH','ROI8_RH','ROI9_LH','ROI9_RH',
]
ROI_SHORT_LABELS = {k: f"{k.split('_')[0]}\n{k.split('_')[1]}" for k in ROI_KEY_MAP}
ROI_FULL_NAMES = {
    'ROI1_LH':'ACC+Prefrontal (LH)','ROI1_RH':'ACC+Prefrontal (RH)',
    'ROI2_LH':'Motor (LH)',         'ROI2_RH':'Motor (RH)',
    'ROI3_LH':'Visual (LH)',        'ROI3_RH':'Visual (RH)',
    'ROI4_LH':'Orbitofrontal (LH)', 'ROI4_RH':'Orbitofrontal (RH)',
    'ROI5_LH':'Temporal (LH)',      'ROI5_RH':'Temporal (RH)',
    'ROI6_LH':'Sup.Parietal (LH)',  'ROI6_RH':'Sup.Parietal (RH)',
    'ROI7_LH':'Inf.Parietal (LH)',  'ROI7_RH':'Inf.Parietal (RH)',
    'ROI8_LH':'Auditory+Insula (LH)','ROI8_RH':'Auditory+Insula (RH)',
    'ROI9_LH':'Undefined (LH)',     'ROI9_RH':'Undefined (RH)',
}
FALLBACK_COORDS = [
    [-38.,28.,22.],[38.,28.,22.],[-28.,-8.,52.],[28.,-8.,52.],
    [-18.,-82.,14.],[18.,-82.,14.],[-22.,38.,-14.],[22.,38.,-14.],
    [-52.,-28.,-14.],[52.,-28.,-14.],[-24.,-62.,52.],[24.,-62.,52.],
    [-44.,-58.,28.],[44.,-58.,28.],[-50.,-8.,10.],[50.,-8.,10.],
    [-8.,-18.,10.],[8.,-18.,10.],
]
TOPOMAP_CMAP = 'RdYlBu_r'
INTERP_RES   = 250
HEAD_ASPECT  = 1.15
TARGET_R     = 0.90
DPI_OUTPUT   = 150
