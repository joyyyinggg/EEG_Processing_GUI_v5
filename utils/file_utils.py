# -*- coding: utf-8 -*-
"""
utils/file_utils.py
===================
檔案掃描與受試者分組工具。

規則
----
- 檔名必須符合 FILE_PATTERN（subj{N}_{session}.txt）
- sub_id 1–25  → 'epilepsy'
- sub_id 26+   → 'normal'
"""

import os
from typing import Optional, Tuple

from config import FILE_PATTERN


def classify_file(stem: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    根據檔名 stem 判斷受試者編號、session 與分組。

    Returns
    -------
    (sub_id, session, group)  或  (None, None, None) 若不符合格式
    """
    m = FILE_PATTERN.search(stem)
    if not m:
        return None, None, None
    sub_id  = int(m.group(1))
    session = m.group(2)
    group   = 'epilepsy' if sub_id <= 25 else 'normal'
    return sub_id, session, group


def scan_folder(folder: str):
    """
    遞迴掃描資料夾，回傳符合格式的 .txt 檔案列表，
    同時依分組分類。

    Returns
    -------
    all_files  : list[str]  — 全部符合格式的絕對路徑
    epi_files  : list[str]  — Epilepsy 組
    nor_files  : list[str]  — Normal 組
    file_meta  : list[dict] — 每筆 {path, stem, sub_id, session, group}
    skipped    : int        — 不符合格式的檔案數
    """
    raw_txts = sorted([
        os.path.join(root, fname)
        for root, _, files in os.walk(folder)
        for fname in files
        if fname.endswith('.txt')
    ])

    all_files, epi_files, nor_files, file_meta = [], [], [], []
    skipped = 0

    for fp in raw_txts:
        stem = os.path.splitext(os.path.basename(fp))[0]
        sub_id, session, group = classify_file(stem)
        if sub_id is None:
            skipped += 1
            continue
        all_files.append(fp)
        meta = dict(path=fp, stem=stem, sub_id=sub_id,
                    session=session, group=group)
        file_meta.append(meta)
        if group == 'epilepsy':
            epi_files.append(fp)
        else:
            nor_files.append(fp)

    return all_files, epi_files, nor_files, file_meta, skipped
