# -*- coding: utf-8 -*-
"""analysis/biomarker/features.py — Self + Cross feature extraction."""
import re, os
import numpy as np
import pandas as pd
from analysis.biomarker.bio_config import ROI_KEY_MAP, REGION_MAP, THRESHOLD, PATIENT_MAX_ID, HIGH_AED_THRESHOLD

def parse_subject_id(filename):
    m = re.search(r'(subj\d+)', filename, re.IGNORECASE)
    return m.group(1).lower() if m else None

def parse_state(filename):
    fn = filename.lower()
    if 'rest2' in fn:   return 'rest2'
    if 'rest1' in fn:   return 'rest1'
    if 'rest' in fn:    return 'rest1'
    if 'reading' in fn: return 'reading'
    return None

def col_to_roi_key(col):
    col = str(col)
    for key in ROI_KEY_MAP:
        b,h = key.split('_')
        if key in col or (b in col and h in col):
            return key
    return None

def _find_sheet_map(sheet_names):
    result = {}
    for sheet in sheet_names:
        sl = sheet.lower()
        if 'theta' in sl and 'Theta' not in result: result['Theta'] = sheet
        elif 'alpha' in sl and 'Alpha' not in result: result['Alpha'] = sheet
        elif 'beta' in sl and 'Beta' not in result:  result['Beta']  = sheet
    return result

def extract_all_features(excel_path, threshold=THRESHOLD):
    try:
        xls = pd.ExcelFile(excel_path, engine='openpyxl')
    except Exception:
        return []
    sheet_map = _find_sheet_map(xls.sheet_names)
    if not sheet_map: return []
    records = []
    for band, sheet in sheet_map.items():
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet, index_col=0, engine='openpyxl')
        except Exception:
            continue
        if df.shape[0] < 2: continue
        matched = []
        for name in df.index:
            k = col_to_roi_key(str(name))
            if k is None:
                k = ROI_KEY_MAP[len(matched)] if len(matched) < len(ROI_KEY_MAP) else 'ROI9_RH'
            matched.append(k)
        matrix = df.values.astype(float)
        np.fill_diagonal(matrix, 0)
        k2i = {k:i for i,k in enumerate(matched)}
        for roi in matched:
            row = k2i[roi]
            val = sum(matrix[row,j] for j in range(len(matched))
                      if j!=row and (threshold==0 or matrix[row,j]>threshold))
            records.append({'feat_type':'self','roi':roi,'band':band,'region':'—',
                'value':float(val),'feat_id':f'self|{roi}|{band}'})
        for region, src_rois in REGION_MAP.items():
            src_idx = [k2i[k] for k in src_rois if k in k2i]
            if not src_idx: continue
            for roi in matched:
                row = k2i[roi]
                val = sum(matrix[row,si] for si in src_idx
                          if si!=row and (threshold==0 or matrix[row,si]>threshold))
                records.append({'feat_type':'cross','roi':roi,'band':band,'region':region,
                    'value':float(val),'feat_id':f'cross|{roi}|{band}|{region}'})
    return records

def load_all_data(excel_files, drug_df, threshold=THRESHOLD):
    def _get_group(subj_id):
        m = re.search(r'\d+', subj_id)
        if not m: return None
        num = int(m.group())
        if num > PATIENT_MAX_ID: return 'Normal'
        row = drug_df[drug_df['編號']==subj_id]
        if row.empty: return None
        n = int(row.iloc[0]['用藥數量'])
        return 'High-dose' if n >= HIGH_AED_THRESHOLD else 'Low-dose'
    all_records = []
    total = len(excel_files)
    print(f"\n[Feature Extraction]  {total} files  threshold={threshold}")
    for i, path in enumerate(excel_files, 1):
        fname = os.path.basename(path)
        print(f"  [{i:>3}/{total}] {fname}", end='\r')
        subj  = parse_subject_id(fname)
        state = parse_state(fname)
        if not subj or not state: continue
        group = _get_group(subj)
        if not group: continue
        feats = extract_all_features(path, threshold)
        for f in feats:
            f.update({'subj':subj,'group':group,'state':state})
        all_records.extend(feats)
    n_subj = len(set(r['subj'] for r in all_records))
    print(f"\n  Done — {n_subj} subjects, {len(all_records):,} records")
    return pd.DataFrame(all_records)
