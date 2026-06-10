# -*- coding: utf-8 -*-
"""ecg/worker.py — Async file loading QThread."""
import os
from PyQt5.QtCore import QThread, pyqtSignal
from ecg.signal_processing import load_ecg

class LoadWorker(QThread):
    done  = pyqtSignal(object, object, object, object, str)
    error = pyqtSignal(str, str)
    def __init__(self, fpath: str, trim_s: int = 30):
        super().__init__(); self.fpath = fpath; self.trim_s = trim_s
    def run(self):
        stem = os.path.splitext(os.path.basename(self.fpath))[0]
        try:
            a1, a2, tvec, allch = load_ecg(self.fpath, self.trim_s)
            self.done.emit(a1, a2, tvec, allch, stem)
        except Exception as e:
            self.error.emit(stem, str(e))
