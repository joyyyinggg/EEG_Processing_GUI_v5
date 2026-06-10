# -*- coding: utf-8 -*-
"""analysis/biomarker/pipeline.py — Main orchestrator."""
import os, time, glob, warnings
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd

from analysis.biomarker.bio_config import (
    COMPARISONS, ALPHA_FDR, AUC_MIN, THRESHOLD,
    TREND_P_RAW, TREND_EFFECT, TREND_AUC, MAX_COMBO, STATE_ORDER,
)
from analysis.biomarker.features   import load_all_data
from analysis.biomarker.statistics import (
    run_stats, run_trend_search, compute_auc,
    greedy_feature_sel, loocv_logistic,
)
from analysis.biomarker.plots import (
    plot_top10, plot_roc, plot_roc_combo,
    plot_group_boxplot, plot_biomarker_topomap,
    plot_node_strength_map, write_report,
)


def run_pipeline(drug_path, excel_folders, out_root=None,
                 threshold=THRESHOLD, verbose=True):
    t_start = time.time()
    if out_root is None:
        out_root = os.path.join(os.path.dirname(excel_folders[0]),'biomarker_output')
    plots_dir = os.path.join(out_root,'plots')
    for d in [out_root, plots_dir]:
        os.makedirs(d, exist_ok=True)

    if verbose:
        print("="*62)
        print(f"  Biomarker Analysis Pipeline  [threshold={threshold}]")
        print("="*62)

    drug_df = pd.read_excel(drug_path, engine='openpyxl')
    drug_df['編號'] = drug_df['編號'].str.lower().str.strip()

    excel_files = []
    for folder in excel_folders:
        found = glob.glob(os.path.join(folder,'**','*.xlsx'),recursive=True)
        excel_files += [f for f in found
                        if 'biomarker' not in f.lower() and 'step' not in f.lower()]
    excel_files = sorted(set(excel_files))
    if verbose: print(f"  {len(excel_files)} Excel files found")

    df_all = load_all_data(excel_files, drug_df, threshold)
    df_all.to_csv(os.path.join(out_root,'raw_features.csv'), index=False)

    # Node Strength Topomaps for all group/state combos
    for state in STATE_ORDER:
        for groups, gname in [
            (['Normal','Low-dose','High-dose'],'All Groups'),
            (['Normal'],'Normal'),
            (['Low-dose','High-dose'],'Epilepsy'),
        ]:
            if df_all[df_all['group'].isin(groups)].empty: continue
            fname = f"node_strength_{'_'.join(groups)}_{state}.png"
            try:
                plot_node_strength_map(df_all, groups, state, gname,
                                       os.path.join(plots_dir, fname))
            except Exception as e:
                if verbose: print(f"  [WARN] node_strength {gname}/{state}: {e}")

    comp_results = {}
    for ckey,(g1n,g2n,g1l,g2l) in COMPARISONS.items():
        t1 = time.time()
        if verbose: print(f"\n-- [{ckey}]  {g1n} vs {g2n}")

        df_stats = run_stats(df_all, g1n, g2n, g1l, g2l)
        if df_stats.empty:
            comp_results[ckey] = {'n_sig':0}; continue

        df_sig = df_stats[df_stats['significant']].copy()
        if verbose: print(f"  Significant: {len(df_sig)} / {len(df_stats)}")
        df_stats.to_excel(os.path.join(out_root,f'all_features_{ckey}.xlsx'),
                          index=False, engine='openpyxl')

        trend_mode = False
        if df_sig.empty:
            df_trend = run_trend_search(df_all, g1n, g2n, g1l, g2l)
            if df_trend.empty:
                comp_results[ckey]={'n_sig':0,'n_trend':0}; continue
            df_trend.to_excel(os.path.join(out_root,f'trend_features_{ckey}.xlsx'),
                              index=False, engine='openpyxl')
            df_sig = df_trend.copy(); df_top = df_trend.copy(); trend_mode = True
        else:
            df_sig.to_excel(os.path.join(out_root,f'significant_{ckey}.xlsx'),
                            index=False, engine='openpyxl')
            df_sig  = compute_auc(df_all, df_sig, g1l, g2l)
            df_top  = df_sig[df_sig['auc']>=AUC_MIN].sort_values('score',ascending=False)
            if not df_top.empty:
                df_top.to_excel(os.path.join(out_root,f'top_biomarkers_{ckey}.xlsx'),
                                index=False, engine='openpyxl')

        df_combo=pd.DataFrame(); selected=[]; combo_probs=None
        if len(df_top)>=2:
            df_combo, selected, y_arr, subj_list = greedy_feature_sel(
                df_all, df_top, g1l, g2l, MAX_COMBO)
            if not df_combo.empty:
                df_combo.to_excel(os.path.join(out_root,f'best_combo_{ckey}.xlsx'),
                                  index=False, engine='openpyxl')
                def _vec(feat_id, state_):
                    return np.array([
                        float(df_all[(df_all['subj']==s)&(df_all['feat_id']==feat_id)&
                                     (df_all['state']==state_)]['value'].values[0])
                        if len(df_all[(df_all['subj']==s)&(df_all['feat_id']==feat_id)&
                                      (df_all['state']==state_)])>0 else np.nan
                        for s in subj_list])
                cols  = [_vec(f,s) for f,s in selected]
                X     = np.column_stack(cols)
                mask  = ~np.any(np.isnan(X),axis=1)
                if mask.sum()>=6:
                    combo_probs,_ = loocv_logistic(X[mask], y_arr[mask])

        comp_results[ckey] = {
            'n_sig':len(df_sig),'top_feats':df_top,'combo':df_combo,
            'selected':selected,'combo_probs':combo_probs,
            'g1n':g1n,'g2n':g2n,'g1l':g1l,'g2l':g2l,'trend_mode':trend_mode,
        }

        title_sfx = ' [Trend]' if trend_mode else ''
        if not df_top.empty:
            try: plot_top10(df_top,f"{g1n} vs {g2n}{title_sfx}",
                            os.path.join(plots_dir,f'top10_{ckey}.png'))
            except Exception as e:
                if verbose: print(f"  [WARN] top10: {e}")
            try: plot_roc(df_all,df_top,g1n,g2n,g1l,g2l,
                          os.path.join(plots_dir,f'roc_{ckey}.png'),title_sfx)
            except Exception as e:
                if verbose: print(f"  [WARN] roc: {e}")
            if not df_combo.empty and combo_probs is not None:
                try:
                    best_auc=float(df_combo.iloc[-1]['loocv_auc'])
                    plot_roc_combo(df_all,selected,y_arr,combo_probs,best_auc,
                                   g1n,g2n,os.path.join(plots_dir,f'roc_combo_{ckey}.png'))
                except Exception as e:
                    if verbose: print(f"  [WARN] roc_combo: {e}")
            try: plot_group_boxplot(df_all,df_top,g1n,g2n,g1l,g2l,
                                    os.path.join(plots_dir,f'boxplot_{ckey}.png'))
            except Exception as e:
                if verbose: print(f"  [WARN] boxplot: {e}")
            done_bs=set()
            for _,row in df_top.head(15).iterrows():
                bs=(row['band'],row['state'])
                if bs in done_bs: continue
                done_bs.add(bs)
                try:
                    plot_biomarker_topomap(
                        df_all,df_top,row['band'],row['state'],g1n,g2n,g1l,g2l,
                        os.path.join(plots_dir,
                            f"topomap_{ckey}_{row['band']}_{row['state']}.png"))
                except Exception as e:
                    if verbose: print(f"  [WARN] topomap: {e}")

        if verbose: print(f"  {ckey}: {time.time()-t1:.1f}s")

    write_report(comp_results, os.path.join(out_root,'summary_report.txt'))
    if verbose:
        print(f"\n{'='*62}")
        print(f"  Done!  {time.time()-t_start:.1f}s  |  Output: {out_root}")
        print(f"{'='*62}")
    return comp_results
