# -*- coding: utf-8 -*-
"""analysis/biomarker/plots.py — All visualization output functions."""
import os
import numpy as np
import pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch
from scipy.interpolate import RBFInterpolator
from sklearn.metrics import roc_curve as _roc_curve

from analysis.biomarker.bio_config import (
    ROI_KEY_MAP, ROI_SHORT_LABELS, ROI_FULL_NAMES,
    REGION_COLORS, GROUP_COLORS, TOPOMAP_CMAP, INTERP_RES,
    HEAD_ASPECT, DPI_OUTPUT, THRESHOLD, ALPHA_FDR, EFFECT_MIN, AUC_MIN,
)
from analysis.biomarker.coords import load_roi_coords, build_norm_coords

_ROI_MNI  = load_roi_coords()
_ROI_NORM = build_norm_coords(_ROI_MNI)


def _draw_head(ax, r=1.05):
    import numpy as np
    t = np.linspace(0,2*np.pi,300)
    ax.plot(np.cos(t)*r, np.sin(t)*r*HEAD_ASPECT, 'k-', lw=1.5, zorder=5)
    ax.plot([-0.1,0,0.1],[r*HEAD_ASPECT-0.02,r*HEAD_ASPECT+0.15,r*HEAD_ASPECT-0.02],
            'k-',lw=1.5,zorder=5)
    for s in [-1,1]:
        ex=s*(r+0.04)
        ax.plot([ex,ex+s*.09,ex+s*.09,ex],[.22,.12,-.12,-.22],'k-',lw=1.5,zorder=5)


def _rbf_topo(pts, vals, ax, vmin=None, vmax=None, cmap=TOPOMAP_CMAP, alpha=1.0):
    res = INTERP_RES
    xi=np.linspace(-1.1,1.1,res); yi=np.linspace(-1.35,1.35,res)
    Xi,Yi=np.meshgrid(xi,yi)
    rbf=RBFInterpolator(pts,vals,kernel='thin_plate_spline',smoothing=0)
    Zi=rbf(np.column_stack([Xi.ravel(),Yi.ravel()])).reshape(res,res)
    msk=(Xi**2+(Yi/HEAD_ASPECT)**2)>1.0
    Zi_m=np.ma.array(Zi,mask=msk)
    vn=vmin if vmin is not None else float(np.min(vals))
    vx=vmax if vmax is not None else float(np.max(vals))
    if vx<=vn: vx=vn+1e-9
    norm=Normalize(vmin=vn,vmax=vx)
    ax.pcolormesh(Xi,Yi,Zi_m,cmap=cmap,norm=norm,shading='auto',zorder=1,alpha=alpha)
    return norm


def plot_top10(df_top, comparison_name, out_path):
    top10=df_top.head(10)
    if top10.empty: return
    fig,ax=plt.subplots(figsize=(13,6))
    labels=[f"{r['feat_type'].upper()}\n{r['roi']}\n{r['band']}\n{r['state']}" +
            (f"\n->{r['region']}" if r['feat_type']=='cross' else '') for _,r in top10.iterrows()]
    colors=['#E74C3C' if r>0 else '#3498DB' for r in top10['r']]
    bars=ax.bar(range(len(top10)),top10['score'],color=colors,alpha=0.85,edgecolor='black',lw=0.8)
    for i,(bar,(_,row)) in enumerate(zip(bars,top10.iterrows())):
        ax.text(i,bar.get_height()+0.05,f"AUC={row['auc']:.2f}\n{row['stars']}",
                ha='center',va='bottom',fontsize=7.5,fontweight='bold')
    ax.set_xticks(range(len(top10))); ax.set_xticklabels(labels,fontsize=7)
    ax.set_ylabel('Biomarker Score  ( |r| x -log10(p_FDR) )',fontsize=10)
    ax.set_title(f"Top Biomarkers — {comparison_name}\n[threshold={THRESHOLD}]",
                 fontsize=11,fontweight='bold')
    ax.grid(axis='y',alpha=0.3)
    ax.legend(handles=[Line2D([0],[0],color='#E74C3C',lw=4,label='Group2 higher'),
                       Line2D([0],[0],color='#3498DB',lw=4,label='Group1 higher')],fontsize=9)
    plt.tight_layout()
    plt.savefig(out_path,dpi=DPI_OUTPUT,bbox_inches='tight',facecolor='white')
    plt.close(fig)


def plot_roc(df_all, top_feats, g1_name, g2_name, g1_groups, g2_groups, out_path, title_suffix=''):
    fig,ax=plt.subplots(figsize=(7,6))
    ax.plot([0,1],[0,1],'k--',alpha=0.4,label='Chance (AUC=0.50)')
    colors=plt.cm.tab10(np.linspace(0,0.8,min(5,len(top_feats))))
    for color,(_,row) in zip(colors,top_feats.head(5).iterrows()):
        sub=df_all[(df_all['feat_id']==row['feat_id'])&(df_all['state']==row['state'])&
                   (df_all['group'].isin(g1_groups+g2_groups))]
        labels_b=(sub['group'].isin(g2_groups)).astype(int).values
        if len(np.unique(labels_b))<2: continue
        fpr,tpr,_=_roc_curve(labels_b,sub['value'].values)
        lbl=f"{row['feat_type'].upper()} {row['roi']} {row['band']} {row['state']}"
        ax.plot(fpr,tpr,color=color,lw=2,label=f"{lbl}\n(AUC={row['auc']:.3f})")
    ax.set_xlabel('False Positive Rate',fontsize=11); ax.set_ylabel('True Positive Rate',fontsize=11)
    ax.set_title(f"ROC — {g1_name} vs {g2_name}{title_suffix}",fontsize=11,fontweight='bold')
    ax.legend(fontsize=7.5,loc='lower right'); ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path,dpi=DPI_OUTPUT,bbox_inches='tight',facecolor='white'); plt.close(fig)


def plot_roc_combo(df_all, selected, y_arr, probs, loocv_auc, g1_name, g2_name, out_path):
    fig,ax=plt.subplots(figsize=(6,5))
    ax.plot([0,1],[0,1],'k--',alpha=0.4,label='Chance')
    if probs is not None and len(np.unique(y_arr))==2:
        fpr,tpr,_=_roc_curve(y_arr,probs)
        ax.plot(fpr,tpr,color='#E74C3C',lw=2.5,label=f'Combo LOOCV AUC={loocv_auc:.3f}')
    feat_str='\n+ '.join([f'{f}[{s}]' for f,s in selected[:3]])
    ax.set_title(f"Best Combo ROC — {g1_name} vs {g2_name}\n{feat_str}",fontsize=10,fontweight='bold')
    ax.set_xlabel('FPR',fontsize=11); ax.set_ylabel('TPR',fontsize=11)
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path,dpi=DPI_OUTPUT,bbox_inches='tight',facecolor='white'); plt.close(fig)


def plot_group_boxplot(df_all, top_feats, g1_name, g2_name, g1_groups, g2_groups, out_path, n=5):
    top_n=top_feats.head(n)
    if top_n.empty: return
    fig,axes=plt.subplots(1,len(top_n),figsize=(3.2*len(top_n),5),sharey=False)
    if len(top_n)==1: axes=[axes]
    for ax,(_,row) in zip(axes,top_n.iterrows()):
        sub=df_all[(df_all['feat_id']==row['feat_id'])&(df_all['state']==row['state'])&
                   (df_all['group'].isin(g1_groups+g2_groups))]
        v1=sub[sub['group'].isin(g1_groups)]['value'].values
        v2=sub[sub['group'].isin(g2_groups)]['value'].values
        bp=ax.boxplot([v1,v2],labels=[g1_name,g2_name],patch_artist=True,
            medianprops=dict(color='black',linewidth=2))
        for patch,c in zip(bp['boxes'],[GROUP_COLORS.get(g1_name,'#3498DB'),
                                         GROUP_COLORS.get(g2_name,'#E74C3C')]):
            patch.set_facecolor(c); patch.set_alpha(0.6)
        rng=np.random.default_rng(42)
        for xi,vals in [(1,v1),(2,v2)]:
            jitter=rng.uniform(-0.12,0.12,len(vals))
            ax.scatter(np.full(len(vals),xi)+jitter,vals,s=20,alpha=0.55,color='black',zorder=3)
        lbl=(f"{row['feat_type'].upper()}\n{row['roi']}\n{row['band']} | {row['state']}" +
             (f"\n->{row['region']}" if row['feat_type']=='cross' else ''))
        ax.set_title(lbl,fontsize=8,fontweight='bold'); ax.set_ylabel('wPLI Strength',fontsize=8)
        ax.grid(axis='y',alpha=0.3)
        ax.text(0.5,0.97,f"AUC={row['auc']:.2f}  r={row['r']:+.2f}\n{row['stars']}",
                ha='center',va='top',transform=ax.transAxes,fontsize=7.5,fontweight='bold')
    plt.suptitle(f"Group Distribution — Top {len(top_n)} Biomarkers",fontsize=12,fontweight='bold',y=1.02)
    plt.tight_layout()
    plt.savefig(out_path,dpi=DPI_OUTPUT,bbox_inches='tight',facecolor='white'); plt.close(fig)


def plot_biomarker_topomap(df_all, top_feats, band, state, g1_name, g2_name,
                            g1_groups, g2_groups, out_path, max_marks=6):
    g2_sub=df_all[(df_all['group'].isin(g2_groups))&(df_all['band']==band)&
                  (df_all['state']==state)&(df_all['feat_type']=='self')]
    bg_vals=np.array([float(np.median(g2_sub[g2_sub['roi']==roi]['value'].values))
                      if len(g2_sub[g2_sub['roi']==roi])>0 else 0.0 for roi in ROI_KEY_MAP])
    pts=np.array([_ROI_NORM[k] for k in ROI_KEY_MAP])
    fig,ax=plt.subplots(figsize=(7,8)); ax.set_aspect('equal')
    ax.set_xlim(-1.35,1.35); ax.set_ylim(-1.5,1.65); ax.axis('off')
    norm=_rbf_topo(pts,bg_vals,ax,cmap=TOPOMAP_CMAP,alpha=0.5)
    _draw_head(ax)
    for key in ROI_KEY_MAP:
        xp,yp=_ROI_NORM[key]
        ax.scatter(xp,yp,s=80,c='white',marker='o',edgecolors='gray',lw=0.8,zorder=5,alpha=0.7)
        ax.text(xp,yp,ROI_SHORT_LABELS[key],ha='center',va='center',fontsize=4.5,color='gray',zorder=6)
    feats_this=top_feats[(top_feats['band']==band)&(top_feats['state']==state)].head(max_marks)
    for _,row in feats_this.iterrows():
        if row['roi'] not in _ROI_NORM: continue
        xp,yp=_ROI_NORM[row['roi']]
        size=200+(row['auc']-0.7)*1000
        color='#E74C3C' if row['r']>0 else '#3498DB'
        marker='D' if row['feat_type']=='cross' else 'o'
        ax.scatter(xp,yp,s=size,c=color,marker=marker,edgecolors='black',lw=1.5,alpha=0.88,zorder=10)
        lbl=(f"{row['roi']}\n{row['feat_type'].upper()}" +
             (f"\n->{row['region']}" if row['feat_type']=='cross' else ''))
        ax.text(xp,yp+0.13,lbl,ha='center',va='bottom',fontsize=5.5,fontweight='bold',
                color=color,zorder=11,bbox=dict(boxstyle='round,pad=0.08',fc='white',ec='none',alpha=0.7))
        ax.text(xp,yp-0.13,f"AUC={row['auc']:.2f}",ha='center',va='top',fontsize=5,color=color,zorder=11)
    ax.text(-1.2,0,'L',ha='center',va='center',fontsize=11,fontweight='bold',color='#555')
    ax.text(1.2,0,'R',ha='center',va='center',fontsize=11,fontweight='bold',color='#555')
    legend=[Line2D([0],[0],marker='o',color='w',markerfacecolor='#E74C3C',
                   markeredgecolor='black',markersize=9,label=f'{g2_name} higher (self)'),
            Line2D([0],[0],marker='o',color='w',markerfacecolor='#3498DB',
                   markeredgecolor='black',markersize=9,label=f'{g1_name} higher (self)'),
            Line2D([0],[0],marker='D',color='w',markerfacecolor='gray',
                   markeredgecolor='black',markersize=8,label='Cross-connection')]
    ax.legend(handles=legend,loc='lower center',bbox_to_anchor=(0.5,-0.08),
              fontsize=7.5,framealpha=0.85,ncol=3)
    ax.set_title(f"Biomarker Map — {g1_name} vs {g2_name}\n{band} | {state}",
                 fontsize=10,fontweight='bold',pad=6)
    plt.colorbar(ScalarMappable(norm=norm,cmap=TOPOMAP_CMAP),ax=ax,
                 fraction=0.032,pad=0.02,aspect=22).set_label(f'{g2_name} Median Self-Strength',fontsize=7.5)
    plt.tight_layout()
    plt.savefig(out_path,dpi=DPI_OUTPUT,bbox_inches='tight',facecolor='white'); plt.close(fig)


def plot_node_strength_map(df_all, groups, state, group_name, out_path):
    bands=['Theta','Alpha','Beta']; n_cols=len(groups)
    fig,axes=plt.subplots(len(bands),n_cols,figsize=(4*n_cols,4.5*len(bands)))
    if n_cols==1: axes=[[ax] for ax in axes]
    global_range={}
    for band in bands:
        all_v=[]
        for grp in groups:
            sub=df_all[(df_all['group']==grp)&(df_all['band']==band)&
                       (df_all['state']==state)&(df_all['feat_type']=='self')]
            for roi in ROI_KEY_MAP:
                v=sub[sub['roi']==roi]['value'].values
                if len(v)>0: all_v.append(np.median(v))
        global_range[band]=(np.percentile(all_v,2),np.percentile(all_v,98)) if all_v else (0,1)
    for row_i,band in enumerate(bands):
        vmin,vmax=global_range[band]
        for col_i,grp in enumerate(groups):
            ax=axes[row_i][col_i]
            sub=df_all[(df_all['group']==grp)&(df_all['band']==band)&
                       (df_all['state']==state)&(df_all['feat_type']=='self')]
            vals=np.array([float(np.median(sub[sub['roi']==roi]['value'].values))
                           if len(sub[sub['roi']==roi])>0 else 0.0 for roi in ROI_KEY_MAP])
            pts=np.array([_ROI_NORM[k] for k in ROI_KEY_MAP])
            ax.set_aspect('equal'); ax.axis('off')
            ax.set_xlim(-1.35,1.35); ax.set_ylim(-1.5,1.65)
            norm=_rbf_topo(pts,vals,ax,vmin=vmin,vmax=vmax,cmap=TOPOMAP_CMAP)
            _draw_head(ax)
            ax.scatter([_ROI_NORM[k][0] for k in ROI_KEY_MAP],
                       [_ROI_NORM[k][1] for k in ROI_KEY_MAP],
                       s=vals/(vals.max()+1e-9)*200+30,c=vals,cmap=TOPOMAP_CMAP,norm=norm,
                       edgecolors='black',lw=0.8,zorder=8)
            for ki,key in enumerate(ROI_KEY_MAP):
                xp,yp=_ROI_NORM[key]
                ax.text(xp,yp+0.09,ROI_SHORT_LABELS[key],ha='center',va='bottom',
                        fontsize=5.5,color='black',zorder=10,
                        bbox=dict(boxstyle='round,pad=0.1',fc='white',ec='none',alpha=0.55))
            ax.text(-1.2,0,'L',ha='center',va='center',fontsize=9,fontweight='bold',color='#555')
            ax.text(1.2,0,'R',ha='center',va='center',fontsize=9,fontweight='bold',color='#555')
            ax.set_title(f'{grp} — {band}',fontsize=10,fontweight='bold',pad=4)
            if col_i==n_cols-1:
                plt.colorbar(ScalarMappable(norm=norm,cmap=TOPOMAP_CMAP),ax=ax,
                    fraction=0.038,pad=0.02,aspect=20).set_label('Node Strength',fontsize=7)
    plt.suptitle(f"Node Strength Map  |  {group_name}  |  {state}",
                 fontsize=13,fontweight='bold',y=1.01)
    plt.tight_layout()
    plt.savefig(out_path,dpi=DPI_OUTPUT,bbox_inches='tight',facecolor='white'); plt.close(fig)


def write_report(comp_results, out_path):
    from analysis.biomarker.bio_config import ALPHA_FDR, EFFECT_MIN, AUC_MIN, THRESHOLD, TREND_P_RAW, TREND_AUC, TREND_EFFECT
    lines=["="*62,"  Biomarker Analysis Summary Report","="*62,"",
           f"  Threshold = {THRESHOLD}",f"  FDR alpha = {ALPHA_FDR}",
           f"  |r| min  = {EFFECT_MIN}",f"  AUC min  = {AUC_MIN}",""]
    for cname,info in comp_results.items():
        df_top=info.get('top_feats',pd.DataFrame())
        df_combo=info.get('combo',pd.DataFrame())
        is_trend=info.get('trend_mode',False)
        mode='[TREND MODE]' if is_trend else '[SIGNIFICANT]'
        lines+=[f"-- {cname}  {mode}",
                f"   Features: {info.get('n_sig',0)}",
                f"   AUC >= {AUC_MIN}: {len(df_top)}"]
        if is_trend:
            lines.append(f"   Trend: p_raw<{TREND_P_RAW}, |r|>={TREND_EFFECT}, AUC>={TREND_AUC}")
        if not df_top.empty:
            lines.append("   Top 3:")
            for _,r in df_top.head(3).iterrows():
                lbl=(f"     {r['feat_type'].upper():5s} {r['roi']:10s} {r['band']:6s} {r['state']:8s}" +
                     (f" ->{r['region']}" if r['feat_type']=='cross' else '   --'))
                lines.append(lbl+f"  AUC={r['auc']:.3f}  r={r['r']:+.3f}  score={r['score']:.3f}")
        if not df_combo.empty:
            best=df_combo.iloc[-1]
            lines.append(f"   Best combo ({best['n_features']} feat) LOOCV AUC={best['loocv_auc']:.3f}")
        lines.append("")
    with open(out_path,'w',encoding='utf-8') as f: f.write('\n'.join(lines))
    print(f"  Report saved: {out_path}")
