"""Explicitly synthetic regression tests; none of these values are findings."""
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from scipy.stats import t

from tennis_project import Config
from tennis_analyses import (analyze_recovery, clustered_mean, select_nonoverlapping,
                             recovery_contrast, paired_cluster_interval,
                             calibration_table, prediction_pipeline)
from test_pipeline import row, process


def test_q1_descriptives_share_rank_eligible_population(tmp_path):
    _, _, events, _ = process([
        row(1, winner_rank=90, loser_rank=10),
        row(2, 20240108, winner=3, loser=4, winner_rank=20, loser_rank=40),
        row(3, 20240115, winner=5, loser=6, winner_rank=20, loser_rank=80),
        row(4, 20240122, winner=7, loser=8, winner_rank=np.nan, loser_rank=30),
    ])
    result = analyze_recovery(events, Config(), tmp_path)
    summary = pd.read_csv(tmp_path / 'q1_summary_overall.csv')
    assert result['index_losses'] == 4
    assert result['rank_eligible_losses'] == 2
    assert summary.index_losses.sum() == 2
    assert set(summary.loss_type) == {'ranking_upset', 'other_ranked_loss'}
    assert summary.next_three_win_rate.isna().all()
    assert summary.next_match_win_rate.isna().all()
    assert summary.complete_three_match_windows.sum() == 0
    assert set(pd.read_csv(tmp_path / 'q1_threshold_sensitivity.csv').rank_gap_threshold) == {20, 30, 50}


def test_nonoverlap_includes_index_and_followup_matches_and_ignores_outcomes():
    _, _, events, _ = process([
        row(i, 20240101 + 7 * (i-1), winner=i+10, loser=1, loser_rank=10, winner_rank=90)
        for i in range(1, 5)
    ] + [row(5, 20240201, 15, 1, loser_rank=10), row(6, 20240208, 16, 1, loser_rank=10)])
    selected = select_nonoverlapping(events, 3)
    kept = events.loc[selected]
    assert len(kept) == 1
    assert kept.match_id.iloc[0] == '2024-T1:1'
    changed = events.copy()
    changed['next3_win_rate'] = 1 - changed['next3_win_rate']
    pd.testing.assert_series_equal(select_nonoverlapping(changed, 3), selected)
    # Next-match windows can retain first, third, and fifth losses.
    assert list(events.loc[select_nonoverlapping(events, 1), 'match_id']) == ['2024-T1:1', '2024-T3:3', '2024-T5:5']


def test_recovery_linear_contrast_uses_full_covariance():
    covariance = np.array([[4., -1.5], [-1.5, 1.]])
    fake = SimpleNamespace(params=pd.Series([.1, .2], index=['a', 'b']), cov_params=lambda: covariance)
    actual = recovery_contrast(fake, {'a': 1, 'b': 2}, label='sum', outcome='next1_win',
                               sample='synthetic', events=100, players=25)
    assert actual['estimate_pp'] == pytest.approx(50)
    # 4 + 4*1 + 2*1*2*(-1.5) = 2, rather than a sum of SEs.
    assert actual['standard_error_pp'] == pytest.approx(100 * np.sqrt(2))
    assert actual['ci95_upper_pp'] == pytest.approx(50 + t.ppf(.975, 24) * 100 * np.sqrt(2))


def test_recovery_negative_variance_does_not_create_interval():
    fake = SimpleNamespace(params=pd.Series([.1], index=['a']), cov_params=lambda: np.array([[-.1]]))
    actual = recovery_contrast(fake, {'a': 1}, label='test', outcome='next1_win', sample='test', events=100, players=30)
    assert actual['inference_status'] == 'unavailable'
    assert np.isnan(actual['standard_error_pp'])


def test_player_clustered_mean_does_not_treat_repeated_windows_as_independent():
    values = pd.Series(np.tile([0., 1.], 10))
    ids = pd.Series(np.arange(20))
    base = clustered_mean(values, ids)
    repeated = clustered_mean(values.repeat(10).reset_index(drop=True), ids.repeat(10).reset_index(drop=True))
    assert repeated['n'] == 200
    assert repeated['players'] == 20
    assert repeated['ci95_lower'] == pytest.approx(base['ci95_lower'])
    assert repeated['ci95_upper'] == pytest.approx(base['ci95_upper'])


def test_paired_intervals_use_identical_outcomes_all_three_metrics():
    pred = pd.DataFrame({'pair_id': np.arange(30), 'won': np.tile([0, 1], 15)})
    pred['a'] = .5
    pred['b'] = np.where(pred.won.eq(1), .8, .2)
    cfg = Config(bootstrap_samples=50)
    for metric in ['brier', 'log_loss', 'accuracy']:
        result = paired_cluster_interval(pred, 'a', 'b', cfg, metric)
        assert result['test_matches'] == len(pred)
        assert result['mean_improvement'] > 0
        assert result['ci95_lower'] > 0
        inverse = paired_cluster_interval(pred, 'b', 'a', cfg, metric)
        assert inverse['mean_improvement'] == pytest.approx(-result['mean_improvement'])
        assert inverse['ci95_upper'] == pytest.approx(-result['ci95_lower'])


def test_calibration_fixed_bins_preserve_all_test_matches():
    pred = pd.DataFrame({'won': [0, 0, 1, 1]})
    for name in ['baseline', 'plus_meeting_count', 'plus_h2h_results']:
        pred[f'p_{name}'] = [0., .1, .5, 1.]
    table = calibration_table(pred)
    assert table.groupby('model').matches.sum().eq(len(pred)).all()
    assert table.bin_lower.between(0, .9).all()
    assert table.bin_upper.between(.1, 1).all()


def test_q2_preprocessing_fits_training_only():
    train = pd.DataFrame({'x': [0., 1., np.nan, 3.], 'surface': ['Hard', 'Clay', 'Hard', 'Clay']})
    test = pd.DataFrame({'x': [1000., np.nan], 'surface': ['FutureOnly', 'Hard']})
    pipe = prediction_pipeline(['x'], ['surface'], 42).fit(train, [0, 1, 0, 1])
    prep = pipe.named_steps['prepare']
    medians = prep.named_transformers_['numeric'].named_steps['impute'].statistics_.copy()
    means = prep.named_transformers_['numeric'].named_steps['scale'].mean_.copy()
    assert medians[0] == 1.
    assert 'FutureOnly' not in prep.named_transformers_['categorical'].named_steps['encode'].categories_[0]
    pipe.predict_proba(test)
    np.testing.assert_array_equal(medians, prep.named_transformers_['numeric'].named_steps['impute'].statistics_)
    np.testing.assert_array_equal(means, prep.named_transformers_['numeric'].named_steps['scale'].mean_)
