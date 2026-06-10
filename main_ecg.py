#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""main_ecg.py — ECG Viewer standalone entry point.
Usage: python main_ecg.py [/path/to/folder]
"""
import sys, warnings; warnings.filterwarnings('ignore')
import matplotlib; matplotlib.use('Qt5Agg')
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from ecg.viewer import ECGViewer

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont('Segoe UI' if sys.platform=='win32' else 'Helvetica Neue', 10))
    win = ECGViewer(folder=sys.argv[1] if len(sys.argv)>1 else None)
    win.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
