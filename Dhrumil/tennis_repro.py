"""Run provenance, mutually exclusive flow tables and internal source spot checks."""
from __future__ import annotations
from collections import Counter
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import hashlib
import json
import platform
import subprocess
import numpy as np
import pandas as pd


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_provenance():
    root = Path(__file__).resolve().parent
    def git(*args):
        result = subprocess.run(['git', *args], cwd=root, text=True, capture_output=True)
        return result.stdout.strip() if result.returncode == 0 else None
    status = git('status', '--porcelain', '--untracked-files=normal')
    files = sorted(set(root.glob('*.py')) | {root / 'requirements.txt', root / 'requirements-lock.txt'})
    return {'revision': git('rev-parse', 'HEAD'), 'dirty': bool(status), 'status_porcelain': status,
            'source_hashes': {p.name: sha256(p) for p in files},
            'note': 'Revision identifies the base commit; source hashes identify the actual working code used.'}


def environment():
    result = {'python': platform.python_version(), 'platform': platform.platform()}
    for name in ['numpy','pandas','scipy','scikit-learn','statsmodels','matplotlib','requests',
                 'pytest','nbformat','nbclient','ipykernel','jupyterlab']:
        try: result[name.replace('-', '_')] = version(name)
        except PackageNotFoundError: result[name.replace('-', '_')] = None
    return result


def input_records(files):
    records = []
    for p in files:
        p = Path(p)
        manifest = p.parent / 'manifest.json'
        cached = {}
        if manifest.exists():
            cached = next((x for x in json.loads(manifest.read_text()).get('files', []) if x['filename'] == p.name), {})
        if cached.get('sha256') and cached['sha256'] != sha256(p):
            raise ValueError(f'Input disagrees with cached manifest hash: {p}')
        records.append({**cached, 'path': str(p), 'sha256': sha256(p), 'bytes': p.stat().st_size,
                        'origin': cached.get('origin', 'provided_local_file')})
    return records


def quality_extensions(raw, matches, players, events, cfg, output, analyses):
    """Counts label their units and do not pretend two views are two matches."""
    study = matches.loc[matches.in_analysis_period]
    eligible = study.loc[study.eligible]
    sp = players.loc[players.in_analysis_period]
    ranked = events.loc[events.player_rank.le(cfg.upset_max_rank) & events.opponent_rank.notna()]
    rows = []
    def count(stage, n, unit, population, note=''):
        rows.append(dict(stage=stage, count=int(n), unit=unit, population=population, note=note))
    count('raw_records', len(raw), 'source_rows', 'all_input_files')
    count('exact_duplicates_removed', len(raw)-len(matches), 'source_rows', 'all_input_files')
    count('warmup_records', matches.season.between(cfg.history_start,cfg.analysis_start-1).sum(), 'deduplicated_source_rows', 'history')
    count('study_period_records', len(study), 'deduplicated_source_rows', 'study')
    usable_key = study.tourney_id.ne('') & study.match_num.notna()
    count('study_unique_match_keys', study.loc[usable_key,'match_id'].nunique(), 'distinct_source_match_keys', 'study', 'Conflicting keys are unresolved physical matches, counted once here.')
    unambiguous = study.loc[usable_key & ~study.conflicting_key & study.identity_ok]
    count('study_resolved_unique_physical_matches', unambiguous.match_id.nunique(), 'physical_matches', 'study')
    count('study_eligible_matches', eligible.match_id.nunique(), 'physical_matches', 'study')
    count('study_player_perspective_rows', len(sp), 'player_views', 'study', 'Includes excluded records retained for follow-up; not independent matches.')
    count('study_eligible_player_perspective_rows', sp.eligible.sum(), 'player_views', 'study')
    count('q1_all_eligible_index_losses', len(events), 'loss_events', 'Q1')
    count('q1_rank_eligible_known_rank_losses', len(ranked), 'loss_events', 'Q1')
    count('q1_complete_next3_windows', ranked.followup_complete.sum(), 'loss_events', 'Q1')
    for key, name, unit in [('q1','model_events','loss_events'),('q2','training_matches','physical_matches'),('q2','test_matches','physical_matches'),('q3','unique_matches','physical_matches'),('q3','adjusted_unique_matches','physical_matches'),('q3','adjusted_player_match_rows','player_views')]:
        if name in analyses[key]: count(f'{key}_{name}', analyses[key][name],unit,key)
    pd.DataFrame(rows).to_csv(output/'attrition.csv',index=False)
    # Each row is assigned its FIRST reason only. Separate non-exclusive flags remain in summary.
    reason = matches.exclusion_reasons.str.split(';').str[0].where(~matches.eligible, 'eligible')
    periods = np.where(matches.season.lt(cfg.analysis_start),'warmup', np.where(matches.in_analysis_period,'study','outside_or_undated'))
    pd.DataFrame({'period':periods,'first_reason':reason}).groupby(['period','first_reason']).size().rename('records').to_csv(output/'exclusion_flow.csv')
    coverage=[]
    for dim in ['season','surface','tourney_level']:
        for label,g in matches.groupby(dim,dropna=False):
            coverage.append(dict(dimension=dim,group=str(label),source_rows=len(g),unique_match_keys=g.match_id.nunique(),eligible_matches=int(g.eligible.sum()),missing_date=int(g.tourney_date.isna().sum()),missing_either_rank=int((g.winner_rank.isna()|g.loser_rank.isna()).sum()),unknown_either_hand=int((g.winner_hand.eq('U')|g.loser_hand.eq('U')).sum()),ambiguous_order=int((~g.order_reliable).sum())))
    pd.DataFrame(coverage).to_csv(output/'coverage_by_group.csv',index=False)
    p=sp.copy()
    p['age_group']=pd.cut(p.player_age,[-np.inf,23,30,np.inf],right=False,labels=['under_23','23_to_29','30_plus']).astype('object').fillna('unknown')
    p['experience_group']=pd.cut(p.prior_matches,[-1,100,300,np.inf],right=False,labels=['under_100','100_to_299','300_plus']).astype('object').fillna('unknown')
    missing=[]
    for dim in ['season','surface','player_hand','age_group','experience_group']:
        for label,g in p.groupby(dim,dropna=False):
            for field in ['player_rank','opponent_rank','player_age','recent_win_rate','service_win_rate','player_hand','opponent_hand']:
                n=(g[field].eq('U')|g[field].isna()).sum() if 'hand' in field else g[field].isna().sum()
                missing.append(dict(dimension=dim,group=str(label),field=field,player_views=len(g),missing=int(n),missing_percent=100*float(n)/len(g)))
    pd.DataFrame(missing).to_csv(output/'missingness_by_group.csv',index=False)
    chronology = {'unreliable_order_records':int((~matches.order_reliable).sum()),
                  'invalid_identity_records':int((~matches.identity_ok).sum())}
    chronology.update(missing_dates=int(matches.tourney_date.isna().sum()),conflicting_source_rows=int(matches.conflicting_key.sum()),conflicting_match_keys=int(matches.loc[matches.conflicting_key,'match_id'].nunique()))
    for c in ['same_date_multiple_events','repeated_player_round','unsupported_round_event',
              'missing_tournament_date','potential_cross_date_overlap']:
        if c in matches: chronology[c]=int(matches[c].sum())
    pd.DataFrame([{'check':k,'records_or_keys':v} for k,v in chronology.items()]).to_csv(output/'chronology_checks.csv',index=False)
    return {'chronology':chronology,'study_unique_match_keys':int(study.loc[usable_key,'match_id'].nunique()),'q1_rank_eligible_losses':len(ranked)}


def spot_checks(matches, players, events, output):
    """Deterministic machine rechecks against local source rows, not human/external review."""
    checks=[]
    eligible=players.loc[players.eligible & players.in_analysis_period]
    chosen=eligible.player_id.value_counts().head(3).index
    histories=players.loc[players.player_id.isin(chosen)].copy()
    histories.to_csv(output/'spotcheck_player_histories.csv',index=False)
    source=matches.loc[~matches.conflicting_key].drop_duplicates('match_id').set_index('match_id')
    for pid in chosen:
        g=players.loc[players.player_id.eq(pid)].sort_values(['tourney_date','round_order'])
        targets=pd.concat([g.head(1),g.iloc[[len(g)//2]],g.tail(1)]).drop_duplicates('match_id')
        for r in targets.itertuples():
            prior=g.loc[g.eligible & ((g.tourney_date<r.tourney_date)|((g.tourney_date==r.tourney_date)&(g.round_order<r.round_order)))]
            checks.append(dict(kind='history_count',player_id=pid,match_id=r.match_id,evidence=f'{r.source_file}: CSV row {r.source_csv_row}',expected=len(prior),observed=r.prior_matches,passed=len(prior)==r.prior_matches))
            raw=source.loc[r.match_id]
            checks.append(dict(kind='source_outcome',player_id=pid,match_id=r.match_id,evidence=f'{r.source_file}: CSV row {r.source_csv_row}',expected=int(raw.winner_id==pid),observed=r.won,passed=int(raw.winner_id==pid)==r.won))
    windows=events.loc[events.ranking_upset].sort_values(['followup_status','tourney_date','player_id']).groupby('followup_status',sort=True).head(3)
    windows.to_csv(output/'spotcheck_recovery_windows.csv',index=False)
    for r in windows.loc[windows.followup_complete].itertuples():
        observed=np.mean([getattr(r,f'next{k}_won') for k in (1,2,3)])
        checks.append(dict(kind='window_mean',player_id=r.player_id,match_id=r.match_id,evidence='; '.join(str(getattr(r,f'next{k}_match_id')) for k in (1,2,3)),expected=observed,observed=r.next3_win_rate,passed=np.isclose(observed,r.next3_win_rate)))
    pairs=eligible.loc[eligible.is_player_a].sort_values(['prior_h2h_meetings','pair_id'],ascending=[False,True]).pair_id.drop_duplicates().head(3)
    pair_history=players.loc[players.pair_id.isin(pairs)&players.is_player_a]
    pair_history.to_csv(output/'spotcheck_opponent_pairs.csv',index=False)
    for pair in pairs:
        g=pair_history.loc[pair_history.pair_id.eq(pair)].sort_values(['tourney_date','round_order'])
        for r in g.tail(2).itertuples():
            prior=g.loc[g.eligible & ((g.tourney_date<r.tourney_date)|((g.tourney_date==r.tourney_date)&(g.round_order<r.round_order)))]
            checks.append(dict(kind='prior_meetings',player_id=r.player_id,match_id=r.match_id,evidence=f'{r.source_file}: CSV row {r.source_csv_row}; pair {pair}',expected=len(prior),observed=r.prior_h2h_meetings,passed=len(prior)==r.prior_h2h_meetings))
    table=pd.DataFrame(checks,columns=['kind','player_id','match_id','evidence','expected','observed','passed'])
    table.to_csv(output/'spotcheck_evidence.csv',index=False)
    if len(table) and not table.passed.all(): raise ValueError('Internal history spot checks failed; see staging evidence.')
    return {'checks':len(table),'all_passed':bool(table.passed.all()),'scope':'Automated local source/history consistency only; no independent external verification or human review.'}


def output_inventory(output):
    return [{'path':str(p.relative_to(output)),'bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted(output.rglob('*')) if p.is_file() and p.name!='run_summary.json']


def verify_output(output, summary=None):
    output=Path(output)
    summary=summary or json.loads((output/'run_summary.json').read_text())
    if summary.get('publication_status')!='verified': raise ValueError('Run not verified.')
    for record in summary['output_inventory']:
        p=output/record['path']
        if not p.exists() or sha256(p)!=record['sha256']: raise ValueError(f'Output hash mismatch: {p}')
    for record in summary['inputs']:
        p=Path(record['path'])
        if not p.exists() or sha256(p)!=record['sha256']: raise ValueError(f'Input hash mismatch: {p}')
    pred=output/'q2_test_predictions.csv.gz'
    if pred.exists():
        p=pd.read_csv(pred)
        if not p.match_id.is_unique or len(p)!=summary['q2']['test_matches']: raise ValueError('Q2 match/sample inconsistency.')
    events=pd.read_csv(output/'q1_recovery_events.csv.gz')
    if events.loc[~events.followup_complete,'next3_win_rate'].notna().any(): raise ValueError('Missing follow-up encoded as observed rate.')
    return summary
