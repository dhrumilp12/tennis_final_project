"""Synthetic checks of tracing existing chronology evidence, not new research data."""
import pandas as pd
import pytest
from pathlib import Path
import json
import shutil

from tennis_q1_q2_checks import chronology_views, prior_candidate_counts


def test_candidate_events_are_specific_to_player_and_event():
    matches = pd.DataFrame([
        dict(match_id='a', tourney_id='A', tourney_date='2020-01-01', round_order=1,
             eligible=True, winner_id=1, loser_id=2),
        dict(match_id='b', tourney_id='B', tourney_date='2020-01-04', round_order=1,
             eligible=True, winner_id=1, loser_id=3),
        dict(match_id='c', tourney_id='C', tourney_date='2020-02-01', round_order=1,
             eligible=True, winner_id=1, loser_id=2),
    ])
    candidates = pd.DataFrame([dict(player_id=1, earlier_tourney_id='A', later_tourney_id='B')])
    views = chronology_views(matches, candidates)
    flagged = views.loc[views.candidate_event]
    assert set(zip(flagged.player_id, flagged.match_id)) == {(1, 'a'), (1, 'b')}
    assert len(views) == 6


def test_history_trace_excludes_current_block_and_future_candidates():
    history = pd.DataFrame([
        dict(player_id=1, match_id='past', tourney_date='2020-01-01', round_order=1, candidate_event=True),
        dict(player_id=1, match_id='same', tourney_date='2020-01-08', round_order=2, candidate_event=True),
        dict(player_id=1, match_id='future', tourney_date='2020-01-09', round_order=1, candidate_event=True),
        dict(player_id=2, match_id='other', tourney_date='2020-01-01', round_order=1, candidate_event=True),
    ])
    query = pd.DataFrame([dict(player_id=1, match_id='test', tourney_date='2020-01-08', round_order=2)])
    traced, used = prior_candidate_counts(history, query)
    assert traced.prior_candidate_records.tolist() == [1]
    assert traced.recent_candidate_records.tolist() == [1]
    assert used == {(1, 'past')}


def test_recent_history_trace_has_original_ten_match_limit():
    history = pd.DataFrame([dict(player_id=1, match_id=str(i), tourney_date=f'2020-01-{i+1:02d}',
                                 round_order=1, candidate_event=i==0) for i in range(11)])
    query = pd.DataFrame([dict(player_id=1, match_id='test', tourney_date='2020-02-01', round_order=1)])
    traced, used = prior_candidate_counts(history, query)
    assert traced.prior_candidate_records.tolist() == [1]
    assert traced.recent_candidate_records.tolist() == [0]
    assert used == {(1, '0')}


def test_rendered_claims_follow_supplemental_tables_and_sample_labels(tmp_path):
    """Real table readback, then synthetic changes confined to a temporary copy."""
    from tennis_q1_q2_checks import write_report
    from tennis_reporting import one, interval
    source = Path('outputs_final')
    evidence = Path('validation/q1_q2_checks')
    if not (evidence/'summary.json').exists():
        pytest.skip('Supplement not present; software-only chronology tests still run.')
    for name in ['q1_post_upset_contrasts.csv', 'q2_comparisons.csv', 'q2_scores.csv',
                 'q1_support.csv', 'q1_retention.csv', 'q1_model_diagnostics.csv',
                 'q1_distributions.csv', 'chronology_summary.csv']:
        shutil.copy2(evidence/name, tmp_path/name)
    summary = json.loads((source/'run_summary.json').read_text())
    result = json.loads((evidence/'summary.json').read_text())
    write_report(source, tmp_path, summary, result)
    text = (tmp_path/'REPORT.md').read_text()
    q1 = pd.read_csv(tmp_path/'q1_post_upset_contrasts.csv')
    for row in q1.itertuples(index=False):
        if row.contrast_kind == 'post_upset_association':
            assert interval(pd.Series(row._asdict())) in text
    assert 'all_windows' in text and 'nonoverlapping' in text
    q2 = pd.read_csv(tmp_path/'q2_comparisons.csv')
    assert {'ALL', 'REPEAT', 'FIRST'} <= set(pd.read_csv(tmp_path/'q2_compact.csv').Subset)
    for row in q2.loc[q2.metric.eq('brier')].itertuples():
        assert f'{row.mean_improvement:+.6f}' in text
        assert f'[{row.ci95_lower:+.6f}, {row.ci95_upper:+.6f}]' in text
    # A different result must change both the estimate and ordinary-English claim.
    selected = q1.outcome.eq('next3_win_rate') & q1['sample'].eq('all_windows') & q1.contrast.eq('age_post_upset_per_year')
    q1.loc[selected, ['estimate_pp', 'ci95_lower_pp', 'ci95_upper_pp']] = [2., 1., 3.]
    q1.to_csv(tmp_path/'q1_post_upset_contrasts.csv', index=False)
    q2.loc[q2.method.eq('shared_player_dyadic'), 'inference_status'] = 'unavailable_test_fixture'
    q2.to_csv(tmp_path/'q2_comparisons.csv', index=False)
    write_report(source, tmp_path, summary, result)
    changed = (tmp_path/'REPORT.md').read_text()
    assert '+2.00 pp (95% interval +1.00 to +3.00 pp)' in changed
    assert 'Next three (primary): age has a positive conditional association.' in changed
    assert 'shared-player dyadic has unavailable inference' in changed
    assert 'inference unavailable' in changed
