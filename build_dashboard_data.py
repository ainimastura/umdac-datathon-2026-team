"""
build_dashboard_data.py - recomputes every number shown in claude_dashboard.py from the team's extract files
and embeds the result in the dashboard (the _DATA block).

Usage:
    python build_dashboard_data.py <folder with the extract CSVs> [path/to/claude_dashboard.py]

Needs: pandas, numpy, scipy, scikit-learn. Runtime: a few minutes (the CEO file is 145 MB).
Files expected in the folder (a prefix before the name is fine, e.g. '590769ab-claude_romance_scam.csv'):
    claude_routing_currency_party.csv, claude_romance_scam.csv, claude_duplicates.csv,
    claude_fat_finger_mini.csv, claude_scam.csv, claude_ceo_scam.csv, claude_recall.csv,
    claude_recall_details.csv
Intermediate files are written to the current working directory.
"""
import os, re, sys, glob
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
DASHBOARD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "claude_dashboard.py")
def P(name):
    hits = sorted(glob.glob(os.path.join(DATA_DIR, name)) + glob.glob(os.path.join(DATA_DIR, "*-" + name)))
    if not hits:
        sys.exit(f"Missing input file: {name} in {DATA_DIR}")
    return hits[0]

# ======================================================================================
# Stage: load and align
# ======================================================================================
# Load raw files once, align anomaly rows to account-level files, cache as pickles.
import pandas as pd, numpy as np
R=pd.read_csv(P('claude_routing_currency_party.csv'),dtype={'ANOMALY_TYPE':str})
R['A']=R.ANOMALY_TYPE.fillna('NORMAL')
src={'ROMANCE_SCAM':(P('claude_romance_scam.csv'),None),
     'DUPLICATE_PAYMENT':(P('claude_duplicates.csv'),None),
     'FAT_FINGER_MISTAKE':(P('claude_fat_finger_mini.csv'),['ANOMALY_TYPE','ORDERING_ACCOUNT','BENEFICIARY_ACCOUNT','USD_AMOUNT','EPOCH_SECONDS']),
     'ACCOUNT_REPLACEMENT_SCAM':(P('claude_scam.csv'),None),
     'CEO_SCAM':(P('claude_ceo_scam.csv'),['ANOMALY_TYPE','ORDERING_ACCOUNT','BENEFICIARY_ACCOUNT','USD_AMOUNT']),
     'CUSTOMER_RECALL':(P('claude_recall.csv'),None)}
R['ORDERING_ACCOUNT']=None; R['BENEFICIARY_ACCOUNT']=None; R['EPOCH_SECONDS']=np.nan
full={}
for a,(f,cols) in src.items():
    s=pd.read_csv(f,dtype={'ANOMALY_TYPE':str},usecols=cols)
    full[a]=s
    an=s[s.ANOMALY_TYPE.notna()].reset_index(drop=True); x=R[R.A==a]
    ok=len(an)==len(x) and np.allclose(an.USD_AMOUNT.values,x.USD_AMOUNT.values)
    print(a,len(an),len(x),'aligned' if ok else 'NOT ALIGNED')
    assert ok
    R.loc[x.index,'ORDERING_ACCOUNT']=an.ORDERING_ACCOUNT.values; R.loc[x.index,'BENEFICIARY_ACCOUNT']=an.BENEFICIARY_ACCOUNT.values
    if 'EPOCH_SECONDS' in an: R.loc[x.index,'EPOCH_SECONDS']=an.EPOCH_SECONDS.values
R.to_pickle('R.pkl')
for a,s in full.items(): s.to_pickle(f'full_{a}.pkl')
rd=pd.read_csv(P('claude_recall_details.csv'),dtype={'ANOMALY_TYPE':str}); rd.to_pickle('recall_details.pkl')
print(R.A.value_counts().to_dict())

# ======================================================================================
# Stage: routing, party, currency (dashboards 1, 3, 4, 8, 9)
# ======================================================================================
# Routing / currency / party aggregates (dashboards 1, 3, 4, 8, 9)
import pandas as pd, numpy as np, json, warnings; warnings.filterwarnings('ignore')
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder
R=pd.read_pickle('R.pkl'); rd=pd.read_pickle('recall_details.pkl'); rf=pd.read_pickle('full_CUSTOMER_RECALL.pkl')
TYPES=['ROMANCE_SCAM','CEO_SCAM','ACCOUNT_REPLACEMENT_SCAM','FAT_FINGER_MISTAKE','DUPLICATE_PAYMENT','CUSTOMER_RECALL']
def feats(d):
    p=d.BIC8_PATH.str.split(';'); d['ngap']=d.BIC8_PATH.str.count(r'\.\.\.'); d['nb']=p.str.len()-d.ngap
    d['first']=p.str[0]; d['last']=p.str[-1]; d['N']=d.CONTINUITY_QFLAG=='N'; d['ctrs']=[[b[4:6] for b in x if b!='...'] for x in p]
    d['ctry_changes']=d.ctrs.map(lambda x:sum(a!=b for a,b in zip(x,x[1:]))); return d
R=feats(R); R['oc']=R.ORDERING_BIC8.str[4:6]; R['bc']=R.BENEFICIARY_BIC8.str[4:6]; R['pc']=R.PARTICIPANT_COUNT; R['fx']=R.CURRENCY_CONVERSION_COUNT
R['combo']=R.ORDERING_TYPE+'→'+R.BENEFICIARY_TYPE; R['slow']=R.TOTAL_DURATION>300; R['multi']=R.pc>2; R['cov']=R.TRANSACTION_TYPE_CODE=='Covered'
R['ord_ok']=R['first']==R.ORDERING_BIC8; R['ben_ok']=R['last']==R.BENEFICIARY_BIC8
n=R[R.A=='NORMAL']
home=n.groupby('oc').CURRENCY_CODE.agg(lambda x:x.value_counts().index[0]).to_dict()
R['home_o']=R.oc.map(home); R['home_b']=R.bc.map(home)
R['zone_changes']=R.ctrs.map(lambda c:sum(a!=b for a,b in zip([home.get(x,x) for x in c],[home.get(x,x) for x in c][1:])))
# event key
R['ev']=np.where(R.A.isin(['ROMANCE_SCAM','DUPLICATE_PAYMENT']),R.A+'|'+R.ORDERING_ACCOUNT.astype(str)+'|'+R.BENEFICIARY_ACCOUNT.astype(str),R.index.astype(str))
E=R.drop_duplicates('ev'); n=R[R.A=='NORMAL']
O={}
# ---------- D1
O['rows']={a:int((R.A==a).sum()) for a in TYPES+['NORMAL']}; O['events']={a:int((E.A==a).sum()) for a in TYPES}
rf=rf.reset_index(drop=True); rd=rd.reset_index(drop=True)
assert (rf.ORDERING_ACCOUNT.values==rd.ORDERING_ACCOUNT.values).all()
rd['TRANSACTION_TYPE_CODE']=rf.TRANSACTION_TYPE_CODE.values; rd=feats(rd)
inv=[]
for nm,d in [('Main sample (all 7,006 anomalies + 50,000 normal)',R),('Recall-account file (428,494 rows)',rd)]:
    inv.append({'source':nm,'rows':len(d),
      'PARTICIPANT_COUNT = visible banks':int((d.PARTICIPANT_COUNT==d.nb).sum()),
      "Flag N ⇔ '...' in path":int(((d.CONTINUITY_QFLAG=='N')==(d.ngap>0)).sum()),
      'Direct ⇔ exactly 2 banks':int(((d.TRANSACTION_TYPE_CODE=='Direct')==(d.PARTICIPANT_COUNT==2)).sum())})
O['invariants']=inv; print(inv)
# ---------- D3 party types
combos=['B→C','B→B','C→C','C→B']; base=n.combo.value_counts(normalize=True).reindex(combos)
pt={}
for unit,D in [('rows',R),('events',E)]:
    pt[unit]={}
    for a in ['NORMAL']+TYPES:
        x=D[D.A==a]; c=x.combo.value_counts().reindex(combos).fillna(0).astype(int)
        p=float(stats.chisquare(c.values,base.values*len(x)).pvalue) if a!='NORMAL' else None
        pt[unit][a]={'counts':c.to_dict(),'n':len(x),'p_vs_normal':p,'ordB':float((x.ORDERING_TYPE=='B').mean()),'benC':float((x.BENEFICIARY_TYPE=='C').mean())}
O['party']=pt; O['party_indep_p']=float(stats.chi2_contingency(pd.crosstab(n.ORDERING_TYPE,n.BENEFICIARY_TYPE))[1])
for a in TYPES: print(a,pt['events'][a]['counts'],'p=%.3g'%pt['events'][a]['p_vs_normal'])
# ---------- D4 currency / FX
c=n[~n.N]
O['fx_matrix']={'zone':pd.crosstab(c.zone_changes.clip(upper=5),c.fx.clip(upper=5)).to_dict(),'border':pd.crosstab(c.ctry_changes.clip(upper=5),c.fx.clip(upper=5)).to_dict()}
O['fx_fit']={'zone':float((c.fx==c.zone_changes).mean()),'border':float((c.fx==c.ctry_changes).mean()),'n_continuous':len(c),
  'broken_n':int(n.N.sum()),'broken_fit':float((n[n.N].fx==n[n.N].zone_changes).mean()),
  'all_rows_fit':int((R.fx==R.zone_changes).sum()),'all_rows':len(R)}
O['fx_by_type']={a:{'fit':float((R[R.A==a].fx==R[R.A==a].zone_changes).mean()),'fx_mean':float(E[E.A==a].fx.mean()),'fx0':float((E[E.A==a].fx==0).mean())} for a in ['NORMAL']+TYPES}
O['home_ccy']={a:{'k':int((E[E.A==a].CURRENCY_CODE==E[E.A==a].home_o).sum()),'n':int((E.A==a).sum())} for a in ['NORMAL']+TYPES}
x=n[n.CURRENCY_CODE!=n.home_o]; O['nonhome']={'share':float(len(x)/len(n)),'EUR':float((x.CURRENCY_CODE=='EUR').mean()),'USD':float((x.CURRENCY_CODE=='USD').mean()),'ben_home':float((x.CURRENCY_CODE==x.home_b).mean())}
O['ccy_mix']={a:E[E.A==a].CURRENCY_CODE.value_counts(normalize=True).round(4).head(10).to_dict() for a in ['NORMAL']+TYPES}
O['n_ccy']=int(n.CURRENCY_CODE.nunique()); O['n_countries']=int(n.oc.nunique())
rom=E[E.A=='ROMANCE_SCAM']; nc=n[n.ORDERING_TYPE=='C']
O['romance_geo']={'victim_ctry':rom.oc.value_counts(normalize=True).round(4).head(12).to_dict(),'normalC_ctry':nc.oc.value_counts(normalize=True).round(4).head(40).to_dict(),
  'victim_ccy':rom.CURRENCY_CODE.value_counts(normalize=True).round(4).head(10).to_dict(),'normalC_ccy':nc.CURRENCY_CODE.value_counts(normalize=True).round(4).head(40).to_dict(),'n_bursts':len(rom)}
O['sender_ctry']={a:E[E.A==a].oc.value_counts(normalize=True).round(4).head(15).to_dict() for a in ['NORMAL']+TYPES}
print('fx fit',O['fx_fit']); print('romance geo',list(O['romance_geo']['victim_ctry'].items())[:4])
# ---------- D8 routing signature
rn=rd[rd.ANOMALY_TYPE.isna()]
known=set(rn['first']+'>'+rn['last'])
mh=rn[rn.PARTICIPANT_COUNT>2].copy(); mh['pair']=mh['first']+'>'+mh['last']; mh['cov']=mh.TRANSACTION_TYPE_CODE=='Covered'
pp=mh.groupby('pair')['cov'].agg(['mean','size']); p5=pp[pp['size']>=5]
O['cover_pairs']={'n_pairs':len(p5),'consistent':int(((p5['mean']==0)|(p5['mean']==1)).sum()),'cover_pairs':int((p5['mean']==1).sum()),
  'hist':np.histogram(p5['mean'],np.linspace(0,1,11))[0].tolist(),'overall_cov':float(mh['cov'].mean()),
  'random_hist':np.histogram(np.random.default_rng(0).binomial(p5['size'].values,mh['cov'].mean())/p5['size'].values,np.linspace(0,1,11))[0].tolist()}
cover_set=set(pp[pp['mean']==1].index)
sig={}
for unit,D in [('rows',R),('events',E)]:
    sig[unit]={}
    for a in ['NORMAL']+TYPES:
        x=D[D.A==a]; m=x[x.multi]; pr=x['first']+'>'+x['last']
        sig[unit][a]={'ben_mis':[int((~x.ben_ok).sum()),len(x)],'ord_mis':[int((~x.ord_ok).sum()),len(x)],'cov_multi':[int(m['cov'].sum()),len(m)],
                      'domestic':[int((x.oc==x.bc).sum()),len(x)],'fx0':[int((x.fx==0).sum()),len(x)],'known_pair':[int(pr.isin(known).sum()),len(x)],
                      'flagN':[int(x.N.sum()),len(x)],'direct':[int((x.pc==2).sum()),len(x)]}
O['signature']=sig
for a in ['NORMAL']+TYPES: print(a,{k:round(v[0]/v[1],4) for k,v in sig['events'][a].items()})
scam=E[E.A.isin(['ROMANCE_SCAM','CEO_SCAM','ACCOUNT_REPLACEMENT_SCAM'])]
O['scam_combined']={'events':len(scam),'ben_mis':int((~scam.ben_ok).sum()),'cov':int(scam[scam.multi]['cov'].sum()),'multi':int(scam.multi.sum()),'domestic':int((scam.oc==scam.bc).sum())}
print(O['scam_combined'])
# ---------- D9 topology / duration
vc=n.pc.value_counts().sort_index(); O['pc_dist']={int(k):int(v) for k,v in vc.items()}
hid=float(n.ngap.sum()/(n.pc-1).sum()); O['hidden_rate']=hid
O['N_by_pc']={int(k):[int(v.N.sum()),len(v)] for k,v in n.groupby(n.pc.clip(upper=8))}
bins=np.round(np.arange(0.2,4.21,0.1),2).tolist(); O['dur_bins']=bins
dh={}
for a in ['NORMAL']+TYPES:
    x=E[E.A==a]; dh[a]={}
    for k,lab in [(2,'2'),(3,'3'),(4,'4'),(5,'5+')]:
        y=x[x.pc==k] if k<5 else x[x.pc>=5]
        dh[a][lab]=np.histogram(np.log10(y.TOTAL_DURATION),bins)[0].tolist()
O['dur_hist']=dh
O['slow_by_pc']={a:{str(k):[int(v.slow.sum()),len(v)] for k,v in E[E.A==a].groupby(E[E.A==a].pc.clip(upper=6))} for a in ['NORMAL']+TYPES}
O['mode_medians']={'fast':{int(k):float(v) for k,v in n[~n.slow].groupby(n.pc.clip(upper=6)).TOTAL_DURATION.median().items()},'slow':{int(k):float(v) for k,v in n[n.slow].groupby(n.pc.clip(upper=6)).TOTAL_DURATION.median().items()}}
top_o=n.oc.value_counts(); top_b=n.bc.value_counts()
prep=lambda x: pd.DataFrame({'o':x.oc.where(x.oc.map(top_o).fillna(0)>=40,'other'),'b':x.bc.where(x.bc.map(top_b).fillna(0)>=40,'other'),'t':x.ORDERING_TYPE})
enc=OneHotEncoder(handle_unknown='ignore').fit(prep(n)); Xn=enc.transform(prep(n)); geo={}
for col in ['slow','multi','N']:
    m=LogisticRegression(C=1.0,max_iter=3000).fit(Xn,n[col].astype(int)); geo[col]={}
    for a in TYPES:
        x=E[E.A==a]; pr=m.predict_proba(enc.transform(prep(x)))[:,1]; obs=x[col].sum(); e=pr.sum(); z=(obs-e)/np.sqrt((pr*(1-pr)).sum())
        geo[col][a]={'observed':float(obs/len(x)),'expected':float(e/len(x)),'p':float(2*stats.norm.sf(abs(z))),'n':len(x)}
    geo[col]['NORMAL']={'observed':float(n[col].mean())}
O['geo']=geo
for a in ['ROMANCE_SCAM','CEO_SCAM','ACCOUNT_REPLACEMENT_SCAM']:
    g=geo['slow'][a]; b=geo['slow']['NORMAL']['observed']; print(a,'slow raw %.3f expected %.3f base %.3f explained %.2f p=%.3g'%(g['observed'],g['expected'],b,(g['expected']-b)/(g['observed']-b),g['p']))
# ---------- D2 mule destination countries (from routing file BIC)
mc={}
for a in ['ROMANCE_SCAM','CEO_SCAM','ACCOUNT_REPLACEMENT_SCAM']:
    mc[a]=E[E.A==a].bc.value_counts().to_dict()
O['mule_ctry_counts']=mc; O['normal_bc_share']=n.bc.value_counts(normalize=True).to_dict()
json.dump(O,open('out_routing.json','w'),default=lambda o:o.item() if hasattr(o,'item') else str(o))
R.to_pickle('R_feat.pkl')

# ======================================================================================
# Stage: mule pool and romance (dashboards 2, 5)
# ======================================================================================
# Mule pool (dashboard 2) and romance bursts (dashboard 5)
import pandas as pd, numpy as np, json
from scipy import stats
R=pd.read_pickle('R_feat.pkl'); O={}
ar=pd.read_pickle('full_ACCOUNT_REPLACEMENT_SCAM.pkl'); ce=pd.read_pickle('full_CEO_SCAM.pkl')
arS=ar[ar.ANOMALY_TYPE.notna()]; ceS=ce[ce.ANOMALY_TYPE.notna()]; roS=R[R.A=='ROMANCE_SCAM']
rb=roS.drop_duplicates(['ORDERING_ACCOUNT','BENEFICIARY_ACCOUNT'])
ev=pd.concat([rb.assign(t='ROMANCE_SCAM')[['BENEFICIARY_ACCOUNT','ORDERING_ACCOUNT','t']],ceS.assign(t='CEO_SCAM')[['BENEFICIARY_ACCOUNT','ORDERING_ACCOUNT','t']],arS.assign(t='ACCOUNT_REPLACEMENT_SCAM')[['BENEFICIARY_ACCOUNT','ORDERING_ACCOUNT','t']]])
S={t:set(g.BENEFICIARY_ACCOUNT) for t,g in ev.groupby('t')}
r,c,a=S['ROMANCE_SCAM'],S['CEO_SCAM'],S['ACCOUNT_REPLACEMENT_SCAM']
O['venn']={'R':len(r-c-a),'C':len(c-r-a),'A':len(a-r-c),'RC':len((r&c)-a),'RA':len((r&a)-c),'CA':len((c&a)-r),'RCA':len(r&c&a),
  'tot_R':len(r),'tot_C':len(c),'tot_A':len(a),'union':len(r|c|a)}
O['venn']['multi']=O['venn']['union']-O['venn']['R']-O['venn']['C']-O['venn']['A']
O['lincoln_petersen']={'CEO×ACCT':len(c)*len(a)/len(c&a),'CEO×ROM':len(c)*len(r)/len(c&r),'ACCT×ROM':len(a)*len(r)/len(a&r)}
print(O['venn'],O['lincoln_petersen'])
pm=ev.groupby('BENEFICIARY_ACCOUNT').agg(events=('t','size'),victims=('ORDERING_ACCOUNT','nunique'),types=('t','nunique'))
O['reuse_all']=pm.events.value_counts().sort_index().to_dict(); O['reuse_by_type']={t:g.groupby('BENEFICIARY_ACCOUNT').size().value_counts().sort_index().to_dict() for t,g in ev.groupby('t')}
O['reuse_share_events_on_reused']=float(pm[pm.events>1].events.sum()/pm.events.sum()); O['reused_share']=float((pm.events>1).mean())
O['repeat_victim_same_mule']=int((pm.events>pm.victims).sum())
O['reuse_type_shares']={t:float((g.groupby('BENEFICIARY_ACCOUNT').size()>1).mean()) for t,g in ev.groupby('t')}
O['scam_events']={t:int((ev.t==t).sum()) for t in S}
print('reuse',O['reuse_all'],O['reused_share'],O['reuse_type_shares'],'repeat victims',O['repeat_victim_same_mule'])
# ---------- Romance
ro=pd.read_csv(P('claude_romance_scam.csv'),dtype={'ANOMALY_TYPE':str})
s=ro[ro.ANOMALY_TYPE.notna()].sort_values(['ORDERING_ACCOUNT','BENEFICIARY_ACCOUNT','EPOCH_SECONDS']).reset_index(drop=True); n=ro[ro.ANOMALY_TYPE.isna()]
g=s.groupby(['ORDERING_ACCOUNT','BENEFICIARY_ACCOUNT'],sort=False); s['burst']=g.ngroup(); s['step']=g.cumcount(); s['K']=g.USD_AMOUNT.transform('size')
s['rel']=s.USD_AMOUNT/g.USD_AMOUNT.transform('first'); s['gap']=g.EPOCH_SECONDS.diff(); s['t']=s.EPOCH_SECONDS-g.EPOCH_SECONDS.transform('min')
med=n.groupby('ORDERING_ACCOUNT').USD_AMOUNT.median(); cnt=n.groupby('ORDERING_ACCOUNT').size()
s['vmed']=s.ORDERING_ACCOUNT.map(med); s['vn']=s.ORDERING_ACCOUNT.map(cnt).fillna(0).astype(int)
O['romance_rows']={'burst':s.burst.tolist(),'step':s.step.tolist(),'K':s.K.tolist(),'amt':s.USD_AMOUNT.round(2).tolist(),'t':s.t.astype(int).tolist(),
  'gap':s.gap.fillna(-1).astype(int).tolist(),'btype':s.BENEFICIARY_TYPE.tolist(),'vmed':s.vmed.round(2).fillna(-1).tolist(),'vn':s.vn.tolist()}
lr=np.log(s.USD_AMOUNT/g.USD_AMOUNT.shift()); s['lr']=lr; s['lrp']=s.groupby('burst').lr.shift(); x=s.dropna(subset=['lr','lrp'])
gp=s.gap.dropna()
O['romance_stats']={'bursts':int(s.burst.nunique()),'rows':len(s),'autocorr':float(np.corrcoef(x.lr,x.lrp)[0,1]),'step_gmean':float(np.exp(lr.mean())),
  'step_ci':[float(np.exp(lr.mean()-1.96*lr.std()/np.sqrt(lr.notna().sum()))),float(np.exp(lr.mean()+1.96*lr.std()/np.sqrt(lr.notna().sum())))],'step_median':float(np.exp(lr.median())),
  'gap_mean':float(gp.mean()),'gap_median':float(gp.median()),'gap_sd':float(gp.std()),'gap_ks_p':float(stats.kstest(gp,'expon',args=(0,gp.mean())).pvalue),
  'span_median':float(g.EPOCH_SECONDS.agg(lambda v:v.max()-v.min()).median()),'span_max':float(g.EPOCH_SECONDS.agg(lambda v:v.max()-v.min()).max()),
  'K_mean':float(g.size().mean()),'K_p_uniform':float(stats.chisquare(g.size().value_counts().sort_index().values).pvalue),
  'steps_up':float((lr>0).sum()/lr.notna().sum()),'last_largest':float(np.mean([v.values.argmax()==len(v)-1 for _,v in g.USD_AMOUNT])),
  'victims_with_history':int((s.drop_duplicates('burst').vn>0).sum()),'noise_sd_hint':0.289}
# route cloning check from routing file
rr=R[R.A=='ROMANCE_SCAM'].groupby(['ORDERING_ACCOUNT','BENEFICIARY_ACCOUNT'])[['BIC8_PATH','TOTAL_DURATION','CURRENCY_CODE']].nunique()
O['romance_stats']['route_cloned']=int((rr.max(axis=1)==1).sum()); O['romance_stats']['route_bursts']=len(rr)
print(O['romance_stats'])
json.dump(O,open('out_mules_romance.json','w'),default=lambda o:o.item() if hasattr(o,'item') else str(o))

# ======================================================================================
# Stage: CEO and account replacement (dashboards 6, 7)
# ======================================================================================
# CEO (dashboard 6) and account replacement (dashboard 7)
import pandas as pd, numpy as np, json, re
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import norm
from scipy.ndimage import gaussian_filter1d
O={}; rng=np.random.default_rng(0)
# ---------- CEO
ce=pd.read_csv(P('claude_ceo_scam.csv'),dtype={'ANOMALY_TYPE':str}); ce['rec']=ce.ANOMALY_TYPE.notna()
s=ce[ce.rec].copy(); n=ce[~ce.rec]
gv=n.groupby('ORDERING_ACCOUNT').USD_AMOUNT; med=gv.median(); cnt=gv.size(); vmax=gv.max()
s['vmed']=s.ORDERING_ACCOUNT.map(med); s['vn']=s.ORDERING_ACCOUNT.map(cnt).fillna(0).astype(int); s['vmax']=s.ORDERING_ACCOUNT.map(vmax)
pairs=set(zip(n.ORDERING_ACCOUNT,n.BENEFICIARY_ACCOUNT)); s['novel']=[(a,b) not in pairs for a,b in zip(s.ORDERING_ACCOUNT,s.BENEFICIARY_ACCOUNT)]
vn=n[n.ORDERING_ACCOUNT.isin(s.ORDERING_ACCOUNT)]; samp=vn.groupby('ORDERING_ACCOUNT').sample(n=20,replace=True,random_state=0)
samp=samp.assign(vmed=samp.ORDERING_ACCOUNT.map(med),vn=samp.ORDERING_ACCOUNT.map(cnt))
ok=s.vn>0
O['ceo_scam']={'lr':np.log10(s[ok].USD_AMOUNT/s[ok].vmed).round(4).tolist(),'vn':s[ok].vn.tolist(),'vmed':s[ok].vmed.round(2).tolist(),'amt':s[ok].USD_AMOUNT.round(2).tolist(),'over_max':(s[ok].USD_AMOUNT>s[ok].vmax).astype(int).tolist()}
O['ceo_normal']={'lr':np.log10(samp.USD_AMOUNT/samp.vmed).round(4).tolist(),'vn':samp.vn.tolist(),'amt':samp.USD_AMOUNT.round(2).tolist()}
O['ceo_counts']={'scams':len(s),'victims':int(s.ORDERING_ACCOUNT.nunique()),'novel':int(s.novel.sum()),'no_history':int((~ok).sum()),'mules':int(s.BENEFICIARY_ACCOUNT.nunique()),
  'ge_1M':float((s.USD_AMOUNT>=1e6).mean()),'normal_ge_1M':float((samp.USD_AMOUNT>=1e6).mean())}
# two-part model on victims with >=30 normals (same method as analysis)
x=s[s.vn>=30]; l=np.log10(x.USD_AMOUNT/x.vmed).values
b=vn[vn.ORDERING_ACCOUNT.isin(x.ORDERING_ACCOUNT)].groupby('ORDERING_ACCOUNT').sample(n=60,replace=True,random_state=0); lb=np.log10(b.USD_AMOUNT/b.ORDERING_ACCOUNT.map(med)).values
gr=np.arange(-8,8,0.02); h=np.histogram(lb,np.append(gr,8))[0].astype(float); h=gaussian_filter1d(h,6); h/=h.sum()*0.02
f=lambda v: np.interp(v,gr+0.01,h,left=1e-9,right=1e-9)+1e-9
def nll(p,l=l):
    w=1/(1+np.exp(-p[0])); return -np.log((1-w)*f(l)+w*norm.pdf(l,p[1],np.exp(p[2]))).sum()
r=minimize(nll,[-1.5,3,-1.2],method='Nelder-Mead'); w=1/(1+np.exp(-r.x[0]))
B=[]
for i in range(200):
    lb_=rng.choice(l,len(l)); rr=minimize(nll,r.x,args=(lb_,),method='Nelder-Mead',options={'maxiter':1500}); B.append((1/(1+np.exp(-rr.x[0])),rr.x[1]))
B=np.array(B)
O['ceo_model']={'share':float(w),'log_mult':float(r.x[1]),'sd':float(np.exp(r.x[2])),'n':len(l),'share_ci':np.percentile(B[:,0],[2.5,97.5]).tolist(),'mult_ci':(10**np.percentile(B[:,1],[2.5,97.5])).tolist(),
  'll_model':float(-r.fun),'ll_null':float(np.log(f(l)).sum())}
hi=x[np.log10(x.USD_AMOUNT/x.vmed)>2.3]; O['ceo_massive_usd']=hi.USD_AMOUNT.quantile([.05,.5,.95]).tolist()
print(O['ceo_counts'],O['ceo_model'],O['ceo_massive_usd'])
# keywords
kw=['URGENT','INVOICE','CEO','CONFIDENTIAL','IMMEDIATE','DIRECTOR','BOSS','ASAP','PRIORITY','SECRET','ACQUISITION','MERGER','WIRE','TRANSFER','PAYMENT','FRAUD','SCAM','EXECUTIVE','PRESIDENT','CHAIRMAN','MANAGER','TODAY','NOW','IMPORTANT','PRIVATE','DEAL','LEGAL','LAWYER','ATTORNEY','TAX']
ns=vn.groupby('ORDERING_ACCOUNT').sample(n=20,replace=True,random_state=1)
O['ceo_keywords']=[{'word':k,'scam':int(s.ORDERING_DETAILS.str.contains(r'\b'+k+r'\b',case=False).sum()),'scam_n':len(s),
   'normal':int(ns.ORDERING_DETAILS.str.contains(r'\b'+k+r'\b',case=False).sum()),'normal_n':len(ns)} for k in kw]
print([d for d in O['ceo_keywords'] if d['scam'] or d['normal']])
del ce,n,vn
# ---------- Account replacement
ar=pd.read_csv(P('claude_scam.csv'),dtype={'ANOMALY_TYPE':str}); ar['rec']=ar.ANOMALY_TYPE.notna(); s=ar[ar.rec].copy(); n=ar[~ar.rec].copy()
pairs=set(zip(n.ORDERING_ACCOUNT,n.BENEFICIARY_ACCOUNT)); vb=n.groupby('ORDERING_ACCOUNT').BENEFICIARY_BIC8.agg(set); vc=n.assign(c=n.BENEFICIARY_BIC8.str[4:6]).groupby('ORDERING_ACCOUNT').c.agg(set)
s['paid_before']=[(a,b) in pairs for a,b in zip(s.ORDERING_ACCOUNT,s.BENEFICIARY_ACCOUNT)]
s['bank_known']=[b in vb.get(o,set()) for o,b in zip(s.ORDERING_ACCOUNT,s.BENEFICIARY_BIC8)]; s['ctry_known']=[b[4:6] in vc.get(o,set()) for o,b in zip(s.ORDERING_ACCOUNT,s.BENEFICIARY_BIC8)]
hist=s.ORDERING_ACCOUNT.isin(n.ORDERING_ACCOUNT)
perm_b=[];perm_c=[]
for i in range(200):
    p=rng.permutation(len(s)); bb=s.BENEFICIARY_BIC8.values[p]
    perm_b.append(np.mean([x in vb.get(o,()) for o,x in zip(s.ORDERING_ACCOUNT,bb)])); perm_c.append(np.mean([x[4:6] in vc.get(o,()) for o,x in zip(s.ORDERING_ACCOUNT,bb)]))
amts={o:np.sort(v.values) for o,v in n.groupby('ORDERING_ACCOUNT').USD_AMOUNT}; ts={o:np.sort(v.values) for o,v in n.groupby('ORDERING_ACCOUNT').EPOCH_SECONDS}
pa=[];pt=[];vns=[]
for o,a,t in zip(s.ORDERING_ACCOUNT,s.USD_AMOUNT,s.EPOCH_SECONDS):
    v=amts.get(o)
    if v is None: continue
    pa.append((rng.uniform(np.searchsorted(v,a,'left'),np.searchsorted(v,a,'right'))+rng.uniform())/(len(v)+1)); tt=ts[o]; pt.append((np.searchsorted(tt,t)+rng.uniform())/(len(tt)+1)); vns.append(len(v))
pa=np.array(pa);pt=np.array(pt);vns=np.array(vns)
med=n.groupby('ORDERING_ACCOUNT').USD_AMOUNT.median()
nb=n[n.ORDERING_ACCOUNT.isin(s.ORDERING_ACCOUNT)].groupby('ORDERING_ACCOUNT').sample(n=20,replace=True,random_state=0)
O['ar']={'scams':len(s),'victims':int(s.ORDERING_ACCOUNT.nunique()),'with_history':int(hist.sum()),'paid_before':int(s.paid_before.sum()),
  'new_bank':float(1-s[hist].bank_known.mean()),'new_ctry':float(1-s[hist].ctry_known.mean()),'perm_bank_known':float(np.mean(perm_b)),'perm_ctry_known':float(np.mean(perm_c)),
  'obs_bank_known':float(s[hist].bank_known.mean()),'obs_ctry_known':float(s[hist].ctry_known.mean()),
  'pct_amt':pa.round(4).tolist(),'pct_time':pt.round(4).tolist(),'pct_vn':vns.tolist(),
  'lr_scam':np.log10(s[hist].USD_AMOUNT/s[hist].ORDERING_ACCOUNT.map(med)).round(4).tolist(),'lr_normal':np.log10(nb.USD_AMOUNT/nb.ORDERING_ACCOUNT.map(med)).round(4).tolist(),
  'mules':int(s.BENEFICIARY_ACCOUNT.nunique()),'reused':int((s.BENEFICIARY_ACCOUNT.value_counts()>1).sum())}
m20=vns>=20; print({k:v for k,v in O['ar'].items() if not isinstance(v,list)}, 'amt pct mean %.3f KS p %.3f ; time %.3f p %.3f (>=20 normals n=%d)'%(pa[m20].mean(),stats.kstest(pa[m20],'uniform').pvalue,pt[m20].mean(),stats.kstest(pt[m20],'uniform').pvalue,m20.sum()))
json.dump(O,open('out_ceo_ar.json','w'),default=lambda o:o.item() if hasattr(o,'item') else str(o))

# ======================================================================================
# Stage: fat finger and duplicates (dashboard 10)
# ======================================================================================
# Fat finger, duplicates (dashboard 10)
import pandas as pd, numpy as np, json
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import norm
O={}
ff=pd.read_csv(P('claude_fat_finger_mini.csv')).dropna(subset=['MEDIAN_NORMAL_AMOUNT'])
l=np.log10(ff.USD_AMOUNT/ff.MEDIAN_NORMAL_AMOUNT).values; S=np.array([-2,1,2,3,4])
def nll(p):
    mu,s=p[0],np.exp(p[1]); w=np.exp(p[2:])/np.exp(p[2:]).sum(); return -np.log((w*norm.pdf(l[:,None],S+mu,s)).sum(1)+1e-300).sum()
r=minimize(nll,[0,-0.1,0,0,0,0,0],method='Nelder-Mead',options={'maxiter':40000,'maxfev':40000,'xatol':1e-7,'fatol':1e-7})
w=np.exp(r.x[2:])/np.exp(r.x[2:]).sum()
def nll_u(p): mu,s=p[0],np.exp(p[1]); return -np.log(norm.pdf(l[:,None],S+mu,s).mean(1)+1e-300).sum()
ru=minimize(nll_u,[0,-0.1],method='Nelder-Mead')
O['ff']={'lr':np.round(l,4).tolist(),'weights':dict(zip(S.tolist(),w.round(4).tolist())),'mu':float(r.x[0]),'sd':float(np.exp(r.x[1])),'n':len(l),'n_total':1940,
  'lrt_p':float(stats.chi2.sf(2*(ru.fun-r.fun),4)),'mu_u':float(ru.x[0]),'sd_u':float(np.exp(ru.x[1])),'up_share':float((l>0).mean())}
c=np.round(ff.USD_AMOUNT*100).astype('int64'); tz=c.map(lambda v:len(str(v))-len(str(v).rstrip('0')))
usd=ff.CURRENCY_CODE=='USD'; up=usd&(l>0.5)
O['ff']['usd_up']=int(up.sum()); O['ff']['usd_up_zero_cents']=int((tz[up]>=1).sum()); O['ff']['nonusd_zero_cent_share']=float((tz[~usd]>=1).mean())
print({k:v for k,v in O['ff'].items() if k!='lr'})
# duplicates
d=pd.read_csv(P('claude_duplicates.csv'),dtype={'ANOMALY_TYPE':str}); d=d[d.ANOMALY_TYPE.notna()]
g=d.groupby(['ORDERING_ACCOUNT','BENEFICIARY_ACCOUNT']); c=g.agg(n=('EPOCH_SECONDS','size'),t0=('EPOCH_SECONDS','min'),t1=('EPOCH_SECONDS','max')); c['span']=c.t1-c.t0
def nllw(W): return -sum(stats.beta.logpdf(s/W,k-1,2)-np.log(W) for s,k in zip(c.span,c.n))
Ws=np.arange(7044,9000,2); ll=np.array([-nllw(W) for W in Ws]); ci=Ws[ll>ll.max()-1.92]
d=d.merge(c[['t0','t1']],left_on=['ORDERING_ACCOUNT','BENEFICIARY_ACCOUNT'],right_index=True); d['pos']=(d.EPOCH_SECONDS-d.t0)/(d.t1-d.t0).replace(0,np.nan)
inner=d[(d.EPOCH_SECONDS>d.t0)&(d.EPOCH_SECONDS<d.t1)].pos
O['dup']={'sizes':c.n.value_counts().sort_index().to_dict(),'span':c.span.tolist(),'n':c.n.tolist(),'W_mle':int(Ws[ll.argmax()]),'W_ci':[int(ci.min()),int(ci.max())],
  'max_span':int(c.span.max()),'clusters':len(c),'rows':len(d),'size_p_uniform':float(stats.chisquare(c.n.value_counts().sort_index().values).pvalue),
  'ks_modelA':float(stats.kstest([stats.beta.cdf(s/7200,k-1,2) for s,k in zip(c.span,c.n)],'uniform').pvalue),
  'ks_modelB':float(stats.kstest([(s/7200)**(k-1) for s,k in zip(c.span,c.n)],'uniform').pvalue),'inner_pos':inner.round(4).tolist()}
print({k:v for k,v in O['dup'].items() if k not in('span','n','inner_pos')})
json.dump(O,open('out_ops.json','w'),default=lambda o:o.item() if hasattr(o,'item') else str(o))

# ======================================================================================
# Stage: baselines for dashboards 2 and 7
# ======================================================================================
import pandas as pd, numpy as np, json
O={}
ar=pd.read_csv(P('claude_scam.csv'),dtype={'ANOMALY_TYPE':str},usecols=['ANOMALY_TYPE','ORDERING_ACCOUNT','BENEFICIARY_ACCOUNT','BENEFICIARY_BIC8','EPOCH_SECONDS'])
ce=pd.read_csv(P('claude_ceo_scam.csv'),dtype={'ANOMALY_TYPE':str},usecols=['ANOMALY_TYPE','BENEFICIARY_ACCOUNT'])
rc=pd.read_pickle('full_CUSTOMER_RECALL.pkl')
benef=set(ar.BENEFICIARY_ACCOUNT)|set(ce.BENEFICIARY_ACCOUNT)|set(rc.BENEFICIARY_ACCOUNT)
O['n_benef_accounts']=len(benef); print('distinct beneficiary accounts across files',len(benef))
n=ar[ar.ANOMALY_TYPE.isna()].sort_values('EPOCH_SECONDS').copy(); n['c']=n.BENEFICIARY_BIC8.str[4:6]
n['new_payee']=~n.duplicated(['ORDERING_ACCOUNT','BENEFICIARY_ACCOUNT']); n['new_bank']=~n.duplicated(['ORDERING_ACCOUNT','BENEFICIARY_BIC8']); n['new_ctry']=~n.duplicated(['ORDERING_ACCOUNT','c'])
# exclude each victim's first payment (nothing is "known" yet) and weight victims equally
n['k']=n.groupby('ORDERING_ACCOUNT').cumcount(); m=n[n.k>0]; w=1/m.groupby('ORDERING_ACCOUNT').k.transform('size')
O['ar_novelty_baseline']={c:float(np.average(m[c],weights=w)) for c in ['new_payee','new_bank','new_ctry']}
print(O['ar_novelty_baseline'])
json.dump(O,open('out_extra.json','w'))

# ======================================================================================
# Stage: bundle and embed
# ======================================================================================
import json, gzip, base64
B={}
for f in ['out_routing.json','out_mules_romance.json','out_ceo_ar.json','out_ops.json','out_extra.json']: B.update(json.load(open(f)))
# trim heavy arrays: round and subsample normal comparison samples
import numpy as np
def r3(a): return [round(float(x),3) for x in a]
B['ceo_normal']={k:(r3(v) if k=='lr' else v) for k,v in B['ceo_normal'].items()}
B['ceo_scam']['lr']=r3(B['ceo_scam']['lr']); B['ar']['lr_scam']=r3(B['ar']['lr_scam']); B['ar']['lr_normal']=r3(B['ar']['lr_normal'])
B['ar']['pct_amt']=r3(B['ar']['pct_amt']); B['ar']['pct_time']=r3(B['ar']['pct_time']); B['ff']['lr']=r3(B['ff']['lr']); B['dup']['inner_pos']=r3(B['dup']['inner_pos'])
B['normal_bc_share']={k:round(v,6) for k,v in B['normal_bc_share'].items()}
del B['ceo_normal']['amt']
raw=json.dumps(B,separators=(',',':'),ensure_ascii=False).encode()
z=base64.b64encode(gzip.compress(raw,9)).decode()
print('json KB',len(raw)//1024,'blob KB',len(z)//1024)
open('blob.txt','w').write(z); json.dump(B,open('bundle.json','w'))

# ==========================================================================================
# Embed the bundle into the dashboard
# ==========================================================================================
if os.path.exists(DASHBOARD):
    lines = "\n".join(z[i:i + 120] for i in range(0, len(z), 120))
    src = open(DASHBOARD, encoding="utf-8").read()
    src = re.sub(r'_DATA = """.*?"""', lambda m: '_DATA = """\n' + lines + '\n"""', src, flags=re.S)
    open(DASHBOARD, "w", encoding="utf-8").write(src)
    print("Embedded data into", DASHBOARD)
else:
    print("Dashboard not found; data written to blob.txt")
