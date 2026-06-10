# -*- coding: utf-8 -*-
"""analysis/biomarker/statistics.py — Mann-Whitney, FDR, AUC, LOOCV."""
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, roc_curve
from analysis.biomarker.bio_config import (
    ALPHA_FDR, EFFECT_MIN, AUC_MIN, MAX_COMBO,
    TREND_P_RAW, TREND_EFFECT, TREND_AUC, TOP_TREND_N,
)

def fdr_correction(pvals):
    n = len(pvals); idx = np.argsort(pvals); ranks = np.arange(1,n+1)
    adj = np.minimum(1.0, pvals[idx]*n/ranks)
    for i in range(n-2,-1,-1): adj[i] = min(adj[i], adj[i+1])
    result = np.empty(n); result[idx] = adj
    return result

def rank_biserial(x, y):
    nx,ny = len(x),len(y)
    if nx==0 or ny==0: return 0.0
    u,_ = stats.mannwhitneyu(x,y,alternative='two-sided')
    return round(float(1-2*u/(nx*ny)),4)

def sig_stars(p):
    if p<0.001: return '***'
    if p<0.01:  return '**'
    if p<0.05:  return '*'
    return 'ns'

def _safe_auc(labels, vals):
    if len(np.unique(labels))<2: return 0.5
    try:
        a = roc_auc_score(labels, vals)
        return float(max(a,1-a))
    except: return 0.5

def run_stats(df_all, g1_name, g2_name, g1_groups, g2_groups):
    g1 = df_all[df_all['group'].isin(g1_groups)]
    g2 = df_all[df_all['group'].isin(g2_groups)]
    feat_cols = ['feat_id','feat_type','roi','band','region','state']
    combos = df_all[feat_cols].drop_duplicates().values.tolist()
    rows = []
    for feat_id,ftype,roi,band,region,state in combos:
        v1 = g1[(g1['feat_id']==feat_id)&(g1['state']==state)]['value'].values
        v2 = g2[(g2['feat_id']==feat_id)&(g2['state']==state)]['value'].values
        if len(v1)<3 or len(v2)<3: continue
        try: _,p = stats.mannwhitneyu(v1,v2,alternative='two-sided')
        except: p = 1.0
        r = rank_biserial(v1,v2)
        rows.append({'feat_id':feat_id,'feat_type':ftype,'roi':roi,'band':band,
            'region':region,'state':state,
            f'n_{g1_name}':len(v1),f'n_{g2_name}':len(v2),
            f'median_{g1_name}':round(float(np.median(v1)),4),
            f'median_{g2_name}':round(float(np.median(v2)),4),
            'direction':'↑' if np.median(v2)>np.median(v1) else '↓',
            'p_raw':round(p,6),'r':r})
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    df['p_fdr'] = fdr_correction(df['p_raw'].values).round(6)
    df['significant'] = (df['p_fdr']<ALPHA_FDR)&(df['r'].abs()>=EFFECT_MIN)
    df['stars'] = df['p_fdr'].apply(sig_stars)
    df['score'] = (df['r'].abs()*(-np.log10(df['p_fdr'].clip(1e-10)))).round(4)
    return df.sort_values('score',ascending=False).reset_index(drop=True)

def run_trend_search(df_all, g1_name, g2_name, g1_groups, g2_groups):
    g1 = df_all[df_all['group'].isin(g1_groups)]
    g2 = df_all[df_all['group'].isin(g2_groups)]
    feat_cols = ['feat_id','feat_type','roi','band','region','state']
    combos = df_all[feat_cols].drop_duplicates().values.tolist()
    rows = []
    for feat_id,ftype,roi,band,region,state in combos:
        v1 = g1[(g1['feat_id']==feat_id)&(g1['state']==state)]['value'].values
        v2 = g2[(g2['feat_id']==feat_id)&(g2['state']==state)]['value'].values
        if len(v1)<3 or len(v2)<3: continue
        try: _,p = stats.mannwhitneyu(v1,v2,alternative='two-sided')
        except: p = 1.0
        r = rank_biserial(v1,v2)
        if p>=TREND_P_RAW or abs(r)<TREND_EFFECT: continue
        labels = np.array([0]*len(v1)+[1]*len(v2))
        auc = _safe_auc(labels,np.concatenate([v1,v2]))
        if auc<TREND_AUC: continue
        rows.append({'feat_id':feat_id,'feat_type':ftype,'roi':roi,'band':band,
            'region':region,'state':state,
            f'n_{g1_name}':len(v1),f'n_{g2_name}':len(v2),
            f'median_{g1_name}':round(float(np.median(v1)),4),
            f'median_{g2_name}':round(float(np.median(v2)),4),
            'direction':'↑' if np.median(v2)>np.median(v1) else '↓',
            'p_raw':round(p,6),'r':r,'auc':round(auc,4),
            'stars':sig_stars(p),'trend_note':f'p_raw={p:.4f} (uncorrected)'})
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    df['score'] = (df['r'].abs()*(-np.log10(df['p_raw'].clip(1e-10)))).round(4)
    return df.sort_values('score',ascending=False).head(TOP_TREND_N).reset_index(drop=True)

def compute_auc(df_all, df_sig, g1_groups, g2_groups):
    if df_sig.empty:
        df_sig = df_sig.copy(); df_sig['auc'] = pd.Series(dtype=float); return df_sig
    aucs = []
    for _,row in df_sig.iterrows():
        sub = df_all[(df_all['feat_id']==row['feat_id'])&
                     (df_all['state']==row['state'])&
                     (df_all['group'].isin(g1_groups+g2_groups))]
        labels = (sub['group'].isin(g2_groups)).astype(int).values
        aucs.append(round(_safe_auc(labels,sub['value'].values),4))
    df_sig = df_sig.copy(); df_sig['auc'] = aucs
    return df_sig.sort_values('auc',ascending=False).reset_index(drop=True)

def loocv_logistic(X, y):
    n = len(y); probs = np.zeros(n)
    for i in range(n):
        X_tr = np.delete(X,i,axis=0); y_tr = np.delete(y,i)
        X_te = X[i:i+1]
        if len(np.unique(y_tr))<2: probs[i]=0.5; continue
        sc = StandardScaler(); X_tr_s=sc.fit_transform(X_tr); X_te_s=sc.transform(X_te)
        clf = LogisticRegression(max_iter=1000,random_state=42,C=1.0)
        try: clf.fit(X_tr_s,y_tr); probs[i]=clf.predict_proba(X_te_s)[0,1]
        except: probs[i]=0.5
    return probs, round(_safe_auc(y,probs),4)

def greedy_feature_sel(df_all, top_feats, g1_groups, g2_groups, max_combo=MAX_COMBO):
    subjs_g1 = df_all[df_all['group'].isin(g1_groups)]['subj'].unique()
    subjs_g2 = df_all[df_all['group'].isin(g2_groups)]['subj'].unique()
    all_subjs = list(subjs_g1)+list(subjs_g2)
    y = np.array([0]*len(subjs_g1)+[1]*len(subjs_g2))
    def _vec(feat_id, state_):
        vec = []
        for s in all_subjs:
            val = df_all[(df_all['subj']==s)&(df_all['feat_id']==feat_id)&
                         (df_all['state']==state_)]['value'].values
            vec.append(float(val[0]) if len(val)>0 else np.nan)
        return np.array(vec)
    selected=[]; best_auc=0.5; step_rows=[]
    for _ in range(max_combo):
        best_gain=0.0; best_feat=None
        for _,row in top_feats.iterrows():
            fkey=(row['feat_id'],row['state'])
            if fkey in selected: continue
            cols=[_vec(f,s) for f,s in selected+[fkey]]
            X=np.column_stack(cols); mask=~np.any(np.isnan(X),axis=1)
            if mask.sum()<6: continue
            _,auc = loocv_logistic(X[mask],y[mask])
            if auc-best_auc>best_gain: best_gain=auc-best_auc; best_feat=fkey; best_new_auc=auc
        if best_feat is None or best_gain<=0.005: break
        selected.append(best_feat); best_auc=best_new_auc
        step_rows.append({'n_features':len(selected),
            'features':' + '.join([f'{f}[{s}]' for f,s in selected]),
            'loocv_auc':best_auc})
        print(f"    add {best_feat}  LOOCV AUC={best_auc:.3f}")
    return pd.DataFrame(step_rows), selected, y, all_subjs
