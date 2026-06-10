#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""main_biomarker.py — Biomarker analysis entry point.
Usage: python main_biomarker.py
"""
import sys, warnings; warnings.filterwarnings('ignore')

def _pick_paths():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
    drug_path = filedialog.askopenfilename(
        title='Select drug info Excel (columns: 編號 / 用藥數量)',
        filetypes=[('Excel','*.xlsx')])
    if not drug_path: print('Cancelled.'); root.destroy(); return None, None
    excel_folders = []
    print('Select wPLI Excel folders (cancel when done)')
    while True:
        folder = filedialog.askdirectory(
            title=f'Select folder {len(excel_folders)+1} (cancel = done)')
        if not folder: break
        excel_folders.append(folder); print(f'  + {folder}')
    root.destroy()
    if not excel_folders: print('No folders selected.'); return None, None
    return drug_path, excel_folders

def main():
    print('='*62); print('  Biomarker Analysis  —  EEG Connectivity GUI v11'); print('='*62)
    drug_path, excel_folders = _pick_paths()
    if drug_path is None: return
    from analysis.biomarker.pipeline import run_pipeline
    run_pipeline(drug_path=drug_path, excel_folders=excel_folders, verbose=True)

if __name__ == '__main__':
    main()
