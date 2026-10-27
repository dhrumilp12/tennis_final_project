"""Synthetic cases test logic; the bundled real excerpt tests source parsing.

Synthetic records are NOT tennis findings and must never be reported as data.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from tennis_project import (Config, REVISION, clean_matches, make_player_rows, add_history,
                            build_recovery_events, load_files, download_data, run_project)


def row(n=1, date=20240101, winner=1, loser=2, **changes):
    d = dict(tourney_id=f"2024-T{n}", tourney_name="SYNTHETIC TEST", surface="Hard", tourney_level="A",
             tourney_date=date, match_num=n, round="R32", best_of=3, score="6-4 6-4",
             winner_id=winner, loser_id=loser, winner_name=f"Test {winner}", loser_name=f"Test {loser}",
             winner_age=24.0, loser_age=29.0, winner_hand="R", loser_hand="L", winner_rank=10, loser_rank=70,
             source_file="SYNTHETIC", source_csv_row=n + 1)
    for side in ['w', 'l']:
        d.update({f"{side}_svpt":60, f"{side}_1stIn":40, f"{side}_1stWon":30, f"{side}_2ndWon":12,
                  f"{side}_df":2, f"{side}_ace":5, f"{side}_bpSaved":3, f"{side}_bpFaced":4})
    d.update(changes)
    return d


def process(rows):
    cfg = Config(history_start=2000, analysis_start=2000, end_year=2024, make_plots=False)
    m, dup, audit = clean_matches(pd.DataFrame(rows), cfg)
    p = add_history(make_player_rows(m), cfg)
    return m, p, build_recovery_events(p, cfg), audit


def test_current_outcome_not_in_own_history():
    m, p, _, _ = process([row(1), row(2, 20240108, 2, 1), row(3, 20240115, 1, 2)])
    a = p[p.player_id.eq(1)].sort_values('tourney_date')
    assert a.prior_matches.tolist() == [0, 1, 2]
    assert a.prior_h2h_meetings.tolist() == [0, 1, 2]
    assert a.prior_h2h_wins.tolist() == [0, 1, 1]
    assert np.isnan(a.recent_win_rate.iloc[0])
    assert a.recent_win_rate.iloc[2] == .5


def test_future_results_cannot_change_past_features():
    rows = [row(1), row(2, 20240108, 2, 1), row(3, 20240115, 1, 2)]
    _, p, _, _ = process(rows)
    rows[-1] = row(3, 20240115, 2, 1)
    _, changed, _, _ = process(rows)
    cols = ['player_id','prior_matches','prior_h2h_wins','recent_win_rate']
    pd.testing.assert_frame_equal(p.loc[p.tourney_date.lt('2024-01-15'), cols].reset_index(drop=True),
                                  changed.loc[changed.tourney_date.lt('2024-01-15'), cols].reset_index(drop=True))


def test_one_prediction_orientation_not_always_winner():
    _, p, _, _ = process([row(1), row(2, 20240108, 2, 1)])
    a = p[p.is_player_a]
    assert a.match_id.nunique() == len(a) == 2
    assert a.won.tolist() == [1,0]


def test_rounds_not_csv_order():
    rows = [row(2,winner=1,loser=3,tourney_id='T',round='F'), row(1,tourney_id='T',round='SF')]
    _, p, _, _ = process(rows)
    a = p[p.player_id.eq(1)]
    assert a['round'].tolist() == ['SF','F']
    assert a.prior_matches.tolist() == [0,1]


def test_unknown_hand_not_right_handed():
    _, p, _, _ = process([row(winner_hand=np.nan,loser_hand='U')])
    assert set(p.player_hand) == {'U'}


def test_missing_rank_not_labeled_upset():
    _, _, e, _ = process([row(winner_rank=np.nan)])
    assert e.loss_type.iloc[0] == 'unknown_rank'
    assert not e.ranking_upset.iloc[0]


def test_upset_definition_and_age_experience_separate():
    _, _, e, _ = process([row(winner_rank=90, loser_rank=10, loser_age=21)])
    assert e.ranking_upset.iloc[0]
    assert e.age_group.iloc[0] == 'under_23'
    assert e.experience_group.iloc[0] == 'under_100'


def test_missing_followup_is_not_a_loss():
    _, _, e, _ = process([row()])
    assert not e.followup_complete.iloc[0]
    assert pd.isna(e.next3_win_rate.iloc[0])
    assert pd.isna(e.next1_win.iloc[0])


def test_next_three_calculated_for_correct_player():
    rows = [row(1,winner=2,loser=1,winner_rank=90,loser_rank=10),
            row(2,20240108,1,3), row(3,20240115,4,1), row(4,20240122,1,5)]
    _, _, e, _ = process(rows)
    first = e[e.match_id.eq('2024-T1:1')].iloc[0]
    assert first.followup_complete
    assert first.next3_win_rate == pytest.approx(2/3)


def test_walkovers_and_retirements_not_completed():
    m, _, _, a = process([row(1,score='W/O'), row(2,20240108,score='6-2 1-0 RET')])
    assert not m.eligible.any()
    assert a['eligible_history_matches'] == 0


def test_do_not_skip_bad_followup_to_find_three_wins():
    rows = [row(1,winner=2,loser=1), row(2,20240108,1,3,score='6-4 0-0 RET'),
            row(3,20240115,1,4), row(4,20240122,1,5), row(5,20240129,1,6)]
    _, _, e, _ = process(rows)
    assert not e.followup_complete.iloc[0]
    assert pd.isna(e.next3_win_rate.iloc[0])
    assert 'excluded' in e.followup_status.iloc[0]


def test_simultaneous_different_events_flagged():
    m, _, _, _ = process([row(1,winner=1,loser=2), row(2,winner=1,loser=3)])
    assert not m.order_reliable.any()


def test_round_robin_not_assigned_fake_chronology():
    m, _, _, _ = process([row(round='RR')])
    assert not m.order_reliable.iloc[0]


def test_team_event_not_silently_called_individual_knockout():
    m, _, _, _ = process([row(tourney_name='United Cup')])
    assert not m.in_scope.iloc[0]


def test_conflicting_duplicate_keys_excluded():
    m, _, _, _ = process([row(),row(score='6-0 6-0')])
    assert m.conflicting_key.all()
    assert not m.eligible.any()


def test_exact_duplicate_removed():
    m, _, _, audit = process([row(),row()])
    assert len(m) == 1 and audit['exact_duplicates_removed'] == 1


def test_bad_service_stats_masked_but_match_kept():
    m, p, _, _ = process([row(w_1stWon=90)])
    assert m.eligible.iloc[0]
    assert pd.isna(p.loc[p.won.eq(1),'service_win_rate'].iloc[0])
    assert p.loc[p.won.eq(0),'service_win_rate'].iloc[0] == pytest.approx(.7)


def test_offline_missing_year_raises(tmp_path):
    cfg = Config(raw_dir=str(tmp_path),history_start=2024,analysis_start=2024,end_year=2024,offline=True)
    with pytest.raises(FileNotFoundError,match='Offline file missing'):
        download_data(cfg)


def test_cached_hash_change_raises(tmp_path):
    import json
    root = tmp_path / REVISION
    root.mkdir()
    (root / 'LICENSE').write_text('changed')
    (root / 'manifest.json').write_text(json.dumps({'files':[{'filename':'LICENSE','sha256':'wrong'}]}))
    cfg = Config(raw_dir=str(tmp_path),history_start=2024,analysis_start=2024,end_year=2024,offline=True)
    with pytest.raises(ValueError,match='Cached file changed'):
        download_data(cfg)


def test_real_excerpt_matches_schema_and_exclusions():
    path = Path(__file__).parent / 'fixtures' / 'brisbane_2024_excerpt.csv'
    raw = load_files([path])
    cfg = Config(history_start=2024,analysis_start=2024,end_year=2024,make_plots=False)
    m,_,audit = clean_matches(raw,cfg)
    assert len(raw) == 31
    assert audit['eligible_analysis_matches'] == 29
    assert set(m.loc[~m.eligible,'score']) == {'W/O','6-4 6-7(4) 0-0 RET'}
    p = add_history(make_player_rows(m),cfg)
    assert p[p.player_id.eq(105777)].prior_matches.tolist() == [0,1,2,3,4]


def test_entire_demo_runs_and_models_are_honestly_skipped(tmp_path):
    path = Path(__file__).parent / 'fixtures' / 'brisbane_2024_excerpt.csv'
    cfg = Config(output_dir=str(tmp_path),history_start=2024,analysis_start=2024,end_year=2024,make_plots=False)
    result = run_project(cfg,[path])
    assert result['eligible_analysis_matches'] == 29
    assert result['q2']['training_matches'] == 0
    assert 'insufficient' in result['q2']['status']
    assert (tmp_path/'run_summary.json').exists()


def synthetic_seasons(n=1500):
    """Artificial independent fixtures, for exercising model code ONLY."""
    rng = np.random.default_rng(726)
    rows = []
    for i in range(n):
        a,b = rng.choice(np.arange(1,61),size=2,replace=False)
        rank_a,rank_b = int(1+a*4+rng.integers(0,10)),int(1+b*4+rng.integers(0,10))
        a_wins = rng.random() < (1/(1+np.exp(-.5*np.log(rank_b/rank_a))))
        w,l = (int(a),int(b)) if a_wins else (int(b),int(a))
        wr,lr = (rank_a,rank_b) if a_wins else (rank_b,rank_a)
        date = pd.Timestamp('1998-01-01')+pd.Timedelta(days=6*i)
        rows.append(row(i+1,int(date.strftime('%Y%m%d')),w,l,
            tourney_id=f'{date.year}-SYNTH-{i}',surface=['Hard','Clay','Grass'][i%3],
            winner_rank=wr,loser_rank=lr,winner_age=18+w%18+((date.year-1998)/6),loser_age=18+l%18+((date.year-1998)/6),
            winner_hand='L' if w%4==0 else 'R',loser_hand='L' if l%4==0 else 'R'))
    return pd.DataFrame(rows)


def test_all_models_fit_on_clearly_synthetic_multiseason_data(tmp_path):
    path = tmp_path/'SYNTHETIC_NOT_RESEARCH.csv'
    synthetic_seasons().to_csv(path,index=False)
    cfg = Config(output_dir=str(tmp_path/'results'),history_start=1998,analysis_start=2000,end_year=2024,
                 test_start=2020,make_plots=False,bootstrap_samples=50,min_hand_matches=5,upset_max_rank=100)
    result = run_project(cfg,[path])
    assert 'regression fitted' in result['q1']['status'], result['q1']
    assert 'comparison fitted' in result['q2']['status'], result['q2']
    assert 'model fitted' in result['q3']['status'], result['q3']
    metrics = pd.read_csv(tmp_path/'results'/'q2_model_metrics.csv')
    assert metrics.brier_score.between(0,1).all()
    pred = pd.read_csv(tmp_path/'results'/'q2_test_predictions.csv.gz')
    assert pred.match_id.is_unique
    assert pred.filter(like='p_').apply(lambda s:s.between(0,1).all()).all()


def test_declared_history_window_enforced():
    cfg=Config(history_start=2000,analysis_start=2000,end_year=2024)
    m,_,_=clean_matches(pd.DataFrame([row(date=20250101)]),cfg)
    assert not m.eligible.iloc[0]
    assert 'outside_history_window' in m.exclusion_reasons.iloc[0]


def test_warmup_used_but_not_reported_as_study_event():
    cfg=Config(history_start=1999,analysis_start=2000,end_year=2024)
    raw=pd.DataFrame([row(1,19990101),row(2,20000101,2,1)])
    m,_,_=clean_matches(raw,cfg)
    p=add_history(make_player_rows(m),cfg)
    assert p.loc[p.tourney_date.eq('2000-01-01'),'prior_matches'].eq(1).all()
    assert not p.loc[p.tourney_date.eq('1999-01-01'),'in_analysis_period'].any()


def test_rerun_does_not_leave_stale_model_outputs(tmp_path):
    (tmp_path/'q2_model_metrics.csv').write_text('STALE RESULT')
    (tmp_path/'q1_adjusted_coefficients.csv').write_text('STALE RESULT')
    path=Path(__file__).parent/'fixtures'/'brisbane_2024_excerpt.csv'
    cfg=Config(output_dir=str(tmp_path),history_start=2024,analysis_start=2024,end_year=2024,make_plots=False)
    run_project(cfg,[path])
    assert not (tmp_path/'q2_model_metrics.csv').exists()
    assert not (tmp_path/'q1_adjusted_coefficients.csv').exists()


def test_downloader_uses_pinned_url_and_reuses_cache(tmp_path,monkeypatch):
    from tennis_project import REQUIRED
    calls=[]
    content=pd.DataFrame([row()]).to_csv(index=False).encode()
    class Response:
        def __init__(self,body): self.content=body
        def raise_for_status(self): pass
    def fake_get(self,url,timeout):
        calls.append(url)
        return Response(content if url.endswith('.csv') else b'TEST DOCUMENT')
    monkeypatch.setattr('requests.Session.get',fake_get)
    cfg=Config(raw_dir=str(tmp_path),history_start=2024,analysis_start=2024,end_year=2024)
    paths=download_data(cfg)
    assert len(paths)==1 and len(calls)==5
    assert all(REVISION in url for url in calls)
    download_data(cfg)
    assert len(calls)==5
