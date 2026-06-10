# -*- coding: utf-8 -*-
"""
styles.py
=========
GUI 顏色系統與所有 Qt StyleSheet 字串。
所有視窗元件統一從此處 import，避免散落在各模組中。
"""

# ─── 顏色系統 ──────────────────────────────────────────────────
C = {
    'bg':           '#FFFFFF',
    'panel':        '#F7F8FA',
    'border':       '#E2E6EA',
    'accent':       '#2563EB',
    'accent_dark':  '#1D4ED8',
    'accent_light': '#DBEAFE',
    'success':      '#16A34A',
    'success_bg':   '#DCFCE7',
    'warning':      '#D97706',
    'warning_bg':   '#FEF3C7',
    'danger':       '#DC2626',
    'danger_bg':    '#FEE2E2',
    'text':         '#111827',
    'text_sub':     '#6B7280',
    'text_light':   '#9CA3AF',
    'tag_epi':      '#FEE2E2',
    'tag_epi_txt':  '#991B1B',
    'tag_nor':      '#DCFCE7',
    'tag_nor_txt':  '#166534',
}

# ─── 按鈕 StyleSheet ──────────────────────────────────────────
BTN_PRIMARY = f"""
    QPushButton {{
        background: {C['accent']}; color: white;
        border: none; border-radius: 6px;
        padding: 8px 18px; font-size: 13px; font-weight: 600;
    }}
    QPushButton:hover {{ background: {C['accent_dark']}; }}
    QPushButton:disabled {{ background: {C['border']}; color: {C['text_light']}; }}
"""

BTN_SUCCESS = f"""
    QPushButton {{
        background: {C['success']}; color: white;
        border: none; border-radius: 6px;
        padding: 8px 18px; font-size: 13px; font-weight: 600;
    }}
    QPushButton:hover {{ background: #15803D; }}
    QPushButton:disabled {{ background: {C['border']}; color: {C['text_light']}; }}
"""

BTN_DANGER = f"""
    QPushButton {{
        background: {C['danger']}; color: white;
        border: none; border-radius: 6px;
        padding: 8px 18px; font-size: 13px; font-weight: 600;
    }}
    QPushButton:hover {{ background: #B91C1C; }}
    QPushButton:disabled {{ background: {C['border']}; color: {C['text_light']}; }}
"""

BTN_OUTLINE = f"""
    QPushButton {{
        background: white; color: {C['accent']};
        border: 1.5px solid {C['accent']}; border-radius: 6px;
        padding: 7px 16px; font-size: 13px;
    }}
    QPushButton:hover {{ background: {C['accent_light']}; }}
    QPushButton:disabled {{ border-color: {C['border']}; color: {C['text_light']}; }}
"""

BTN_EPI = f"""
    QPushButton {{
        background: {C['danger']}; color: white;
        border: none; border-radius: 6px;
        padding: 8px 18px; font-size: 13px; font-weight: 600;
    }}
    QPushButton:hover {{ background: #B91C1C; }}
    QPushButton:disabled {{ background: {C['border']}; color: {C['text_light']}; }}
"""

BTN_NOR = f"""
    QPushButton {{
        background: {C['success']}; color: white;
        border: none; border-radius: 6px;
        padding: 8px 18px; font-size: 13px; font-weight: 600;
    }}
    QPushButton:hover {{ background: #15803D; }}
    QPushButton:disabled {{ background: {C['border']}; color: {C['text_light']}; }}
"""

BTN_ECG = f"""
    QPushButton {{
        background: #EF4444; color: white;
        border: none; border-radius: 6px;
        padding: 9px 16px; font-size: 14px; font-weight: 600;
    }}
    QPushButton:hover {{ background: #B91C1C; }}
    QPushButton:disabled {{ background: {C['border']}; color: {C['text_sub']}; }}
"""

# ─── GroupBox StyleSheet ───────────────────────────────────────
PANEL_STYLE = f"""
    QGroupBox {{
        background: {C['panel']}; border: 1px solid {C['border']};
        border-radius: 8px; margin-top: 10px; padding: 10px;
        font-size: 13px; font-weight: 600; color: {C['text']};
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
"""

# ─── Slider StyleSheet（共用）─────────────────────────────────
SLIDER_STYLE = f"""
    QSlider::groove:horizontal {{
        height: 6px; background: {C['border']}; border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        width: 16px; height: 16px; margin: -5px 0;
        background: {C['accent']}; border-radius: 8px;
    }}
    QSlider::sub-page:horizontal {{
        background: {C['accent_light']}; border-radius: 3px;
    }}
"""

# ─── QListWidget StyleSheet ────────────────────────────────────
LIST_STYLE = f"""
    QListWidget {{ border: 1px solid {C['border']}; font-size: 12px; border-radius: 6px; }}
    QListWidget::item {{ padding: 5px 8px; border-bottom: 1px solid {C['border']}; }}
    QListWidget::item:hover {{ background: {C['accent_light']}; }}
    QListWidget::item:selected {{ background: {C['accent']}; color: white; }}
"""

# ─── QTabWidget StyleSheet ────────────────────────────────────
def tab_style(selected_color: str = None) -> str:
    sc = selected_color or C['accent']
    return f"""
        QTabWidget::pane {{ border: 1px solid {C['border']}; border-radius: 8px; }}
        QTabBar::tab {{
            padding: 9px 22px; font-size: 13px;
            background: {C['panel']}; border-radius: 4px 4px 0 0;
        }}
        QTabBar::tab:selected {{ background: {sc}; color: white; font-weight: 600; }}
    """
