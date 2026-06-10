#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
main.py
=======
EEG Preprocessing & Connectivity GUI — 程式進入點。

Usage
-----
    python main.py

Requirements
------------
    見 requirements.txt
"""

import sys
import warnings
warnings.filterwarnings('ignore')

import matplotlib
matplotlib.use('Qt5Agg')

from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
