# -*- coding: utf-8 -*-
"""analysis/biomarker/coords.py — ROI coordinate loader & 2D projection."""
import os, numpy as np
from analysis.biomarker.bio_config import ROI_KEY_MAP, FALLBACK_COORDS, HEAD_ASPECT, TARGET_R

def load_roi_coords(npy_hint=None):
    candidates = []
    if npy_hint: candidates.append(npy_hint)
    for base in [
        os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..'),
        os.getcwd(),
    ]:
        candidates.append(os.path.join(base,'roi_coords_18.npy'))
    for path in candidates:
        if path and os.path.isfile(path):
            arr = np.load(path)
            if arr.shape == (18,3):
                print(f"  ROI coords loaded: {path}")
                return {k: arr[i] for i,k in enumerate(ROI_KEY_MAP)}
    print("  roi_coords_18.npy not found — using fallback.")
    arr = np.array(FALLBACK_COORDS)
    return {k: arr[i] for i,k in enumerate(ROI_KEY_MAP)}

def build_norm_coords(roi_mni):
    xy  = np.array([[v[0],v[1]] for v in roi_mni.values()])
    r   = np.sqrt(xy[:,0]**2 + (xy[:,1]/HEAD_ASPECT)**2)
    sc  = TARGET_R / r.max()
    return {k:(float(xy[i,0]*sc),float(xy[i,1]*sc))
            for i,k in enumerate(roi_mni.keys())}
