"""Explicitly synthetic verification of Q3 covariance and subgroup reporting."""
from pathlib import Path
import numpy as np
import pandas as pd
from tennis_handedness import dyadic_covariance, linear_contrast, analyze_handedness
from tennis_project import Config


def test_dyadic_covariance_matches_shared_participant_enumeration():
    # Includes two views of one match, a repeated meeting, a reversed participant
    # role, and a disjoint pair. Each ordered score product appears exactly once.
    a = np.array([1, 2, 1, 3, 5])
    b = np.array([2, 1, 2, 1, 6])
    score = np.array([[1., 2.], [-.5, .7], [.2, -.4], [1.3, .1], [-.4, .8]])
    expected = np.zeros((2, 2))
    for i in range(len(a)):
        for j in range(len(a)):
            if {a[i], b[i]} & {a[j], b[j]}:
                expected += np.outer(score[i], score[j])
    actual = dyadic_covariance(score, np.eye(2), a, b)
    np.testing.assert_allclose(actual, expected, atol=1e-14)
    np.testing.assert_allclose(dyadic_covariance(score, np.eye(2), b, a), expected, atol=1e-14)


def test_subgroup_sum_uses_full_covariance():
    covariance = np.array([[.04, -.015], [-.015, .09]])
    result = linear_contrast([.1, .2], covariance, [1, 1])
    assert np.isclose(result['coefficient'], .3)
    assert np.isclose(result['variance'], .10)
    assert np.isclose(result['standard_error'], np.sqrt(.10))
    assert not np.isclose(result['standard_error'], .2 + .3)
    assert result['inference_status'] == 'available'


def test_negative_variance_is_unavailable_not_clipped_or_absolutized():
    result = linear_contrast([.1, .2], np.diag([.04, -.09]), [0, 1])
    assert result['variance'] < 0
    assert np.isnan(result['standard_error'])
    assert np.isnan(result['ci95_lower'])
    assert result['coefficient'] == .2
    assert result['inference_status'] == 'unavailable_nonpositive_variance'


def test_rank_and_support_prevent_false_precision():
    for flag in ['identified', 'supported']:
        result = linear_contrast([.1], [[.01]], [1], **{flag: False})
        assert np.isnan(result['standard_error'])
        assert result['inference_status'].startswith('unavailable_')


def test_dyadic_covariance_rejects_self_matches():
    import pytest
    with pytest.raises(ValueError, match='distinct'):
        dyadic_covariance([[1.]], [[1.]], [1], [1])


def test_service_comparison_requires_valid_service_opportunities(tmp_path):
    rows = []
    for hand in ['L', 'R']:
        for i in range(12):
            valid = hand == 'R' or i < 2
            rows.append(dict(player_id=1, opponent_id=i+2, player_name='Synthetic focal',
                             player_hand='R', opponent_hand=hand, eligible=True, won=i%2,
                             match_id=f'{hand}-{i}',pair_id=f'1:{i+2}',tourney_id=f'event-{i}',
                             valid_service_stats=valid,service_points_won=35 if valid else np.nan,
                             service_points_observed=50 if valid else np.nan,
                             log_rank_advantage=.2,player_age=25,recent_win_rate=.5,
                             opponent_recent_win_rate=.5,prior_matches=50))
    info = analyze_handedness(pd.DataFrame(rows), Config(min_hand_matches=10), tmp_path)
    paired = pd.read_csv(tmp_path/'q3_paired_player_comparison.csv')
    assert paired.matches_L.iloc[0] == 12
    assert paired.service_matches_L.iloc[0] == 2
    assert np.isnan(paired.service_rate_difference_L_minus_R.iloc[0])
    assert info['analysis_status'] == 'descriptive_only'
