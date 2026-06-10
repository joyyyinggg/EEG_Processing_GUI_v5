# -*- coding: utf-8 -*-
"""
analysis/mne_resources.py
==========================
MNE fsaverage / BEM / ROI label 資源載入。

函式
----
load_mne_resources() → shared_res dict
    供 MainWindow._init_resources() 呼叫。
    回傳的 dict 直接傳入 ProcessWorker。
"""

import numpy as np
import mne


# ── ROI 定義（9 組 × 2 半球 = 18 ROI）────────────────────────
_ROI_NAME_GROUPS = {
    1: ['anterior cingulate and medial prefrontal cortex',
        'inferior frontal cortex', 'dorsolateral prefrontal cortex'],
    2: ['somatosensory and motor cortex',
        'paracentral lobular and mid cingulate cortex', 'premotor cortex'],
    3: ['dorsal stream visual cortex', 'early visual cortex',
        'mt+ complex and neighboring visual areas', 'primary visual cortex (v1)'],
    4: ['orbital and polar frontal cortex'],
    5: ['lateral temporal cortex', 'medial temporal cortex',
        'ventral stream visual cortex'],
    6: ['superior parietal cortex'],
    7: ['inferior parietal cortex', 'posterior cingulate cortex',
        'temporo-parieto-occipital junction'],
    8: ['auditory association cortex', 'early auditory cortex',
        'insular and frontal opercular cortex', 'posterior opercular cortex'],
    9: ['???'],
}

_CUSTOM_ROI_NAMES = {
    'ROI1_LH': 'ROI1_LH ACC+IFC+DPC (LH)',
    'ROI1_RH': 'ROI1_RH ACC+IFC+DPC (RH)',
    'ROI2_LH': 'ROI2_LH Motor+Premotor (LH)',
    'ROI2_RH': 'ROI2_RH Motor+Premotor (RH)',
    'ROI3_LH': 'ROI3_LH Visual (LH)',
    'ROI3_RH': 'ROI3_RH Visual (RH)',
    'ROI4_LH': 'ROI4_LH OFC (LH)',
    'ROI4_RH': 'ROI4_RH OFC (RH)',
    'ROI5_LH': 'ROI5_LH Temporal (LH)',
    'ROI5_RH': 'ROI5_RH Temporal (RH)',
    'ROI6_LH': 'ROI6_LH Sup.Parietal (LH)',
    'ROI6_RH': 'ROI6_RH Sup.Parietal (RH)',
    'ROI7_LH': 'ROI7_LH Inf.Parietal (LH)',
    'ROI7_RH': 'ROI7_RH Inf.Parietal (RH)',
    'ROI8_LH': 'ROI8_LH Auditory+Insula (LH)',
    'ROI8_RH': 'ROI8_RH Auditory+Insula (RH)',
    'ROI9_LH': 'ROI9_LH ??? (LH)',
    'ROI9_RH': 'ROI9_RH ??? (RH)',
}

_ROI_GROUPS_LR = {
    'ROI1_LH': ['anterior cingulate and medial prefrontal cortex-lh',
                'inferior frontal cortex-lh', 'dorsolateral prefrontal cortex-lh'],
    'ROI1_RH': ['anterior cingulate and medial prefrontal cortex-rh',
                'inferior frontal cortex-rh', 'dorsolateral prefrontal cortex-rh'],
    'ROI2_LH': ['somatosensory and motor cortex-lh',
                'paracentral lobular and mid cingulate cortex-lh', 'premotor cortex-lh'],
    'ROI2_RH': ['somatosensory and motor cortex-rh',
                'paracentral lobular and mid cingulate cortex-rh', 'premotor cortex-rh'],
    'ROI3_LH': ['dorsal stream visual cortex-lh', 'early visual cortex-lh',
                'mt+ complex and neighboring visual areas-lh',
                'primary visual cortex (v1)-lh'],
    'ROI3_RH': ['dorsal stream visual cortex-rh', 'early visual cortex-rh',
                'mt+ complex and neighboring visual areas-rh',
                'primary visual cortex (v1)-rh'],
    'ROI4_LH': ['orbital and polar frontal cortex-lh'],
    'ROI4_RH': ['orbital and polar frontal cortex-rh'],
    'ROI5_LH': ['lateral temporal cortex-lh', 'medial temporal cortex-lh',
                'ventral stream visual cortex-lh'],
    'ROI5_RH': ['lateral temporal cortex-rh', 'medial temporal cortex-rh',
                'ventral stream visual cortex-rh'],
    'ROI6_LH': ['superior parietal cortex-lh'],
    'ROI6_RH': ['superior parietal cortex-rh'],
    'ROI7_LH': ['inferior parietal cortex-lh', 'posterior cingulate cortex-lh',
                'temporo-parieto-occipital junction-lh'],
    'ROI7_RH': ['inferior parietal cortex-rh', 'posterior cingulate cortex-rh',
                'temporo-parieto-occipital junction-rh'],
    'ROI8_LH': ['auditory association cortex-lh', 'early auditory cortex-lh',
                'insular and frontal opercular cortex-lh',
                'posterior opercular cortex-lh'],
    'ROI8_RH': ['auditory association cortex-rh', 'early auditory cortex-rh',
                'insular and frontal opercular cortex-rh',
                'posterior opercular cortex-rh'],
    'ROI9_LH': ['???-lh'],
    'ROI9_RH': ['???-rh'],
}


def load_mne_resources(subj_name: str = '') -> dict:
    """
    載入 MNE fsaverage 資源（src / BEM / ROI labels / MNI 座標）。

    Parameters
    ----------
    subj_name : str  輸出資料夾前綴（從 UI 傳入）

    Returns
    -------
    shared_res : dict，直接傳給 ProcessWorker
    """
    mne.set_log_level('WARNING')
    data_path    = mne.datasets.sample.data_path()
    subjects_dir = data_path / 'subjects'
    mne.datasets.fetch_fsaverage(subjects_dir=subjects_dir)

    src   = mne.setup_source_space(
        'fsaverage', spacing='oct4',
        subjects_dir=subjects_dir, add_dist=False)
    model = mne.make_bem_model(
        'fsaverage', ico=4,
        conductivity=(0.3, 0.006, 0.3),
        subjects_dir=subjects_dir)
    bem   = mne.make_bem_solution(model)
    labels_all = mne.read_labels_from_annot(
        'fsaverage', parc='HCPMMP1_combined',
        subjects_dir=subjects_dir)

    # ── 合併 ROI labels ──────────────────────────────────────
    roi_labels_dict = {}
    for roi_idx, name_list in _ROI_NAME_GROUPS.items():
        for hemi in ['lh', 'rh']:
            key    = f'ROI{roi_idx}_{hemi.upper()}'
            merged = None
            for lbl in labels_all:
                if lbl.hemi == hemi and any(
                    n in lbl.name.lower() for n in name_list
                ):
                    merged = lbl if merged is None else merged + lbl
            if merged is not None and len(merged.vertices) > 0:
                roi_labels_dict[key] = merged

    valid_roi_labels = list(roi_labels_dict.values())
    valid_roi_names  = [_CUSTOM_ROI_NAMES[k] for k in roi_labels_dict.keys()]

    # ── MNI 座標 ─────────────────────────────────────────────
    roi_coords_18 = []
    for rn, lkeys in _ROI_GROUPS_LR.items():
        coords = []
        for key in lkeys:
            for lbl in labels_all:
                if key.lower() in lbl.name.lower():
                    hi  = 0 if lbl.hemi == 'lh' else 1
                    c   = lbl.center_of_mass(
                        'fsaverage', subjects_dir=subjects_dir)
                    mni = mne.vertex_to_mni(
                        [c], hemis=hi, subject='fsaverage',
                        subjects_dir=subjects_dir)
                    coords.append(mni[0])
                    break
        roi_coords_18.append(
            np.mean(coords, axis=0) if coords else np.array([np.nan] * 3))
    roi_coords_18 = np.array(roi_coords_18)

    return dict(
        src=src,
        bem=bem,
        labels_all=labels_all,
        valid_roi_labels=valid_roi_labels,
        valid_roi_names=valid_roi_names,
        roi_coords_18=roi_coords_18,
        subjects_dir=subjects_dir,
        subj_name=subj_name,
    )
