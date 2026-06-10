# -*- coding: utf-8 -*-
"""
analysis/visualization.py
==========================
所有圖表輸出函式（與 GUI 解耦，純 matplotlib / nilearn）。

輸出清單
--------
- heatmap_3band.png       三頻帶 ROI 熱圖
- circle_*.png            每頻帶圓形連接圖
- connectome_*.png        3D nilearn connectome
- view_connectome_*.png   2D 俯視連接圖
- mean_connectivity_wpli.txt  均值摘要
- interp_compare.png      插值前後對比圖（儲存至 interp_records）
- ICA_check/ICA_before_after.png      ICA 前後對比
- ICA_check/ICA_components_topo.png   IC topography
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from config import CH_NAMES, SFREQ, ROI_SHORT_NAMES
from styles import C


# ─────────────────────────────────────────────────────────────
#  主要連接度圖表
# ─────────────────────────────────────────────────────────────
def draw_all_figures(ct, ca, cb_, cm, roi_names, roi_coords,
                     output_dir, subj_name, epoch_len, method,
                     file_stem, base_dir,
                     nlplot, plot_connectivity_circle, MinMaxScaler):
    """
    繪製並儲存所有連接度相關圖表。
    參數與原版 _draw_all_figures 完全一致，方便直接替換。
    """
    n     = len(roi_names)
    short = (ROI_SHORT_NAMES[:n] if n <= len(ROI_SHORT_NAMES)
             else ROI_SHORT_NAMES + [f'ROI{i}'
                                     for i in range(len(ROI_SHORT_NAMES) + 1, n + 1)])

    # ── Heatmap ──────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(22, 7))
    for ax, mat, title in zip(
        axes, [ct, ca, cb_],
        ['Theta (4-8 Hz)', 'Alpha (8-12 Hz)', 'Beta (12-30 Hz)'],
    ):
        d = mat.copy().astype(float)
        np.fill_diagonal(d, np.nan)
        im = ax.imshow(d, cmap='RdBu_r', vmin=0, vmax=1, aspect='auto')
        ax.set_title(title, fontsize=13, pad=8)
        ax.set_xticks(range(n))
        ax.set_xticklabels(short, rotation=90, fontsize=7)
        ax.set_yticks(range(n))
        ax.set_yticklabels(short, fontsize=7)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.suptitle('ROI Connectivity Matrix — wPLI', fontsize=15, y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'heatmap_3band.png'),
                dpi=300, bbox_inches='tight')
    plt.close(fig)

    # ── Circle ───────────────────────────────────────────────
    for fi, (mat, fl) in enumerate(zip(
        [ct, ca, cb_],
        ['Theta (4-8 Hz)', 'Alpha (8-12 Hz)', 'Beta (12-30 Hz)'],
    )):
        fig2, _ = plot_connectivity_circle(
            cm[:, :, fi], roi_names,
            title=f'Brain Connectivity - {fl}',
            colormap='rainbow', facecolor='white', textcolor='black',
            vmin=0, vmax=1, n_lines=80, fontsize_names=8, show=False,
        )
        fname = (f"circle_{fl.replace(' ', '_').replace('(', '')"
                 f".replace(')', '').replace('-', '_')}.png")
        fig2.savefig(os.path.join(output_dir, fname), dpi=300)
        plt.close(fig2)

    # ── 3D Connectome + 2D Graph ─────────────────────────────
    if roi_coords is not None and len(roi_coords) == n:
        for mat, fn, fl in zip(
            [ct, ca, cb_], ['theta', 'alpha', 'beta'],
            ['Theta', 'Alpha', 'Beta'],
        ):
            ns    = np.sum(mat, axis=0) + np.sum(mat, axis=1)
            nsize = MinMaxScaler((10, 300)).fit_transform(
                ns.reshape(-1, 1)).flatten()
            norm_s = (ns - ns.min()) / (ns.max() - ns.min() + 1e-9)

            # 3D nilearn connectome
            fig3      = plt.figure(figsize=(20, 13))
            mat_thresh = mat.copy()
            mat_thresh[mat_thresh < 0.3] = 0
            disp = nlplot.plot_connectome(
                adjacency_matrix=mat_thresh,
                node_coords=roi_coords,
                node_color='red', node_size=nsize,
                display_mode='lzr', black_bg=False, figure=fig3,
                edge_kwargs={'linewidth': 2.5, 'alpha': 0.8},
            )
            disp.title(f'{fl} Band Connectivity', size=35)
            plt.savefig(
                os.path.join(output_dir, f'connectome_{fn}.png'),
                dpi=300, bbox_inches='tight')
            plt.close(fig3)

            # 2D 俯視圖
            x, y = roi_coords[:, 0], roi_coords[:, 1]
            fig4, ax4 = plt.subplots(figsize=(10, 10))
            for i in range(n):
                for j in range(i + 1, n):
                    if mat[i, j] > 0:
                        ax4.plot([x[i], x[j]], [y[i], y[j]],
                                 color='blue', linewidth=mat[i, j] * 3)
            ax4.scatter(x, y, s=nsize, c=norm_s, cmap='Reds')
            ax4.axis('off')
            plt.title(f'2D Network Graph - {fl}', fontsize=25)
            plt.tight_layout()
            plt.savefig(
                os.path.join(output_dir, f'view_connectome_{fn}.png'),
                dpi=300, bbox_inches='tight')
            plt.close(fig4)

    # ── Mean connectivity txt ─────────────────────────────────
    mean_dir  = os.path.join(base_dir, f'{subj_name}_con_figures_{epoch_len}s')
    os.makedirs(mean_dir, exist_ok=True)
    mean_path = os.path.join(mean_dir, f'mean_connectivity_{method}.txt')
    for fi, fl in enumerate(
        ['Theta (4-8 Hz)', 'Alpha (8-12 Hz)', 'Beta (12-30 Hz)']
    ):
        m  = cm[:, :, fi]
        mv = float(np.mean(m[m != 0]))
        with open(mean_path, 'a', encoding='utf-8') as f:
            f.write(f'{file_stem} - {fl} mean: {mv:.3f}\n')


# ─────────────────────────────────────────────────────────────
#  插值前後對比圖
# ─────────────────────────────────────────────────────────────
def save_interp_figure(raw_before, raw_after, bads: list,
                       file_stem: str, out_dir: str):
    """儲存插值前後波形對比圖 (interp_compare.png)。"""
    t0, t1 = 0, 30
    i0 = 0
    i1 = min(int(t1 * SFREQ), raw_before.n_times)
    tvec = np.linspace(t0, t1, i1 - i0)
    n_ch = len(CH_NAMES)
    sc   = 500

    d_bef = raw_before.get_data()[:, i0:i1] * 1e6
    d_aft = raw_after.get_data()[:, i0:i1]  * 1e6

    fig, axes = plt.subplots(1, 2, figsize=(20, 8), sharey=True)
    for col, (dat, title) in enumerate([
        (d_bef, 'Before Interpolation'),
        (d_aft, 'After Interpolation'),
    ]):
        ax = axes[col]
        for i, ch in enumerate(CH_NAMES):
            off    = (n_ch - 1 - i) * sc
            is_bad = ch in bads
            if col == 0:
                color = C['danger'] if is_bad else '#3B82F6'
                lw    = 1.0 if is_bad else 0.5
            else:
                color = '#16A34A' if is_bad else '#3B82F6'
                lw    = 1.0 if is_bad else 0.5
            ax.plot(tvec, dat[i] + off, color=color, linewidth=lw)
            ax.text(-0.3, off, ch, ha='right', va='center', fontsize=7,
                    color=(C['danger'] if col == 0 and is_bad
                           else '#16A34A' if col == 1 and is_bad
                           else C['text']))
        ax.set_title(title, fontsize=13)
        ax.set_xlabel('Time (s)', fontsize=10)
        ax.set_yticks([])
        ax.spines[['top', 'right', 'left']].set_visible(False)

    if bads:
        fig.text(0.5, 0.01,
                 f'Red = bad channels | Green = interpolated: {", ".join(bads)}',
                 ha='center', fontsize=9, color=C['text_sub'])
    plt.suptitle(f'Interpolation Compare — {file_stem}', fontsize=13, y=1.01)
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig(os.path.join(out_dir, 'interp_compare.png'),
                dpi=200, bbox_inches='tight')
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
#  ICA 圖表
# ─────────────────────────────────────────────────────────────
def save_ica_figures(raw_before, raw_after, ica,
                     eog_idx: list, emg_idx: list,
                     file_stem: str, output_dir: str):
    """
    儲存 ICA 前後波形對比圖（ICA_before_after.png）
    與 IC topography 圖（ICA_components_topo.png）。
    """
    import mne
    ica_dir = os.path.join(output_dir, 'ICA_check')
    os.makedirs(ica_dir, exist_ok=True)

    t0, t1  = 0, 30
    i0, i1  = int(t0 * SFREQ), min(int(t1 * SFREQ), raw_before.n_times)
    tvec    = np.linspace(t0, t1, i1 - i0)
    pchs    = [c for c in ['Fp1', 'Fp2', 'F3', 'T3', 'O1', 'O2']
               if c in raw_before.ch_names]
    cidx    = [raw_before.ch_names.index(c) for c in pchs]
    n_ch    = len(pchs)

    db = raw_before.get_data()[cidx, i0:i1] * 1e6
    da = raw_after.get_data()[cidx, i0:i1]  * 1e6
    dr = db - da
    sc = max(float(np.max(np.abs(db))) * 1.5, 1e-9)
    offs = np.arange(n_ch) * sc

    # Before / After / Removed
    fig, axes = plt.subplots(1, 3, figsize=(24, 8), sharey=True)
    for ax, dat, title, color in zip(
        axes,
        [db, da, dr],
        [f'Before ICA (4-40Hz)',
         f'After ICA ({len(ica.exclude)} IC removed: {ica.exclude})',
         'Removed components'],
        ['#3B82F6', '#16A34A', '#DC2626'],
    ):
        for i, (ch, off) in enumerate(zip(pchs, offs)):
            ax.plot(tvec, dat[i] + off, color=color, linewidth=0.6)
            ax.text(t0 - 0.3, off, ch, ha='right', va='center', fontsize=8)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel('Time (s)', fontsize=9)
        ax.set_xlim(t0, t1); ax.set_yticks([])
        ax.spines[['top', 'right', 'left']].set_visible(False)

    plt.suptitle(
        f'ICA Before/After — {file_stem}\nEOG:{eog_idx}  EMG:{emg_idx}',
        fontsize=12, y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(ica_dir, 'ICA_before_after.png'),
                dpi=200, bbox_inches='tight')
    plt.close(fig)

    # IC Topography (前 8 個)
    from config import N_ICA_COMP
    n_ic_p  = min(8, N_ICA_COMP)
    ic_data = ica.get_sources(raw_before).get_data()
    fig2, axes2 = plt.subplots(2, n_ic_p, figsize=(n_ic_p * 2.5, 6))
    for ic_i in range(n_ic_p):
        ax_t = axes2[0, ic_i]; ax_s = axes2[1, ic_i]
        excl = ic_i in ica.exclude
        mne.viz.plot_topomap(
            ica.get_components()[:, ic_i], raw_before.info,
            axes=ax_t, show=False, contours=0, sensors=True)
        ax_t.set_title(
            f'IC{ic_i:02d} [{"EXCL" if excl else "keep"}]',
            fontsize=7,
            color=C['danger'] if excl else C['text'],
            fontweight='bold' if excl else 'normal')
        ts = ic_data[ic_i, :10 * SFREQ]
        ax_s.plot(np.arange(len(ts)) / SFREQ, ts,
                  linewidth=0.5,
                  color=C['danger'] if excl else '#3B82F6')
        ax_s.set_xticks([0, 5, 10])
        ax_s.set_xticklabels(['0s', '5s', '10s'], fontsize=6)
        ax_s.set_yticks([])
        ax_s.spines[['top', 'right', 'left']].set_visible(False)

    plt.suptitle(f'ICA Components — {file_stem}', fontsize=11, y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(ica_dir, 'ICA_components_topo.png'),
                dpi=200, bbox_inches='tight')
    plt.close(fig2)
