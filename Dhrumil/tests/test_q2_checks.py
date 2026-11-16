"""Synthetic Q2 software checks plus saved-data validation; no model fitting."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tennis_project import Config
from tennis_q2_checks import (compare_predictions, dyadic_mean_interval, metric_scores,
                              paired_difference, run_q2, subsets, validate_predictions,
                              verify_saved_features)


def predictions(n=30):
    player = 100 + 2 * np.arange(n)
    opponent = player + 1
    y = np.arange(n) % 2
    return pd.DataFrame({"match_id": [f"synthetic-{i}" for i in range(n)],
                         "player_id": player, "opponent_id": opponent,
                         "pair_id": [f"{a}:{b}" for a, b in zip(player, opponent)],
                         "tourney_date": "2024-01-01", "won": y,
                         "prior_h2h_meetings": np.arange(n) % 3,
                         "meeting_group": "deliberately_untrusted",
                         "p_baseline": np.where(y, .4, .6), "p_plus_meeting_count": .5,
                         "p_plus_h2h_results": np.where(y, .9, .1)})


@pytest.mark.parametrize("metric", ["brier", "log_loss", "accuracy"])
def test_paired_improvement_direction_always_favors_second_model(metric):
    d = predictions()
    difference = paired_difference(d, "baseline", "plus_h2h_results", metric)
    inverse = paired_difference(d, "plus_h2h_results", "baseline", metric)
    assert (difference > 0).all()
    np.testing.assert_allclose(inverse, -difference)
    comparisons, scores, counts = compare_predictions(d, Config(bootstrap_samples=30))
    all_rows = comparisons.loc[comparisons.subset.eq("ALL") & comparisons.metric.eq(metric)
                              & comparisons.first_model.eq("baseline")
                              & comparisons.second_model.eq("plus_h2h_results")]
    assert len(all_rows) == 2
    np.testing.assert_allclose(all_rows.mean_improvement, difference.mean())
    assert len(scores) == 9 and len(counts) == 3


def test_unique_physical_match_ids_required():
    d = predictions()
    with pytest.raises(ValueError, match="Duplicate physical"):
        validate_predictions(pd.concat([d, d.iloc[[0]]]), 2020, 2024)


@pytest.mark.parametrize("column,value,message", [
    ("p_baseline", np.nan, "probabilities"), ("p_baseline", np.inf, "probabilities"),
    ("p_plus_meeting_count", -0.01, "probabilities"), ("p_plus_h2h_results", 1.01, "probabilities"),
    ("won", np.nan, "binary"), ("won", 2, "binary"),
    ("player_id", 0, "integer"), ("opponent_id", np.inf, "integer"),
    ("player_id", 100.5, "integer"), ("opponent_id", 100, "Distinct"),
    ("pair_id", "101:100", "canonical"), ("prior_h2h_meetings", -1, "integer"),
    ("prior_h2h_meetings", .5, "integer"), ("tourney_date", "2019-12-30", "test period"),
    ("tourney_date", "2025-01-01", "test period"), ("match_id", "", "match IDs"),
])
def test_invalid_predictions_are_rejected_without_repair(column, value, message):
    d = predictions()
    d[column] = d[column].astype(object)
    d.loc[0, column] = value
    with pytest.raises(ValueError, match=message):
        validate_predictions(d, 2020, 2024)


def test_missing_columns_and_reversed_player_orientation_are_rejected():
    with pytest.raises(ValueError, match="Missing saved"):
        validate_predictions(predictions().drop(columns="opponent_id"), 2020, 2024)
    d = predictions()
    d.loc[0, ["player_id", "opponent_id"]] = [101, 100]
    with pytest.raises(ValueError, match="orientation"):
        validate_predictions(d, 2020, 2024)


def test_probability_endpoints_are_valid_and_clipped_only_for_log_score():
    d = predictions()
    d.loc[0, "p_baseline"] = 0
    d.loc[1, "p_baseline"] = 1
    actual = validate_predictions(d, 2020, 2024)
    assert actual.p_baseline.iloc[:2].tolist() == [0, 1]
    score = metric_scores([1, 0], [0, 1], "log_loss")
    assert np.isfinite(score).all()


def test_repeat_selection_uses_prior_meetings_not_outcomes_or_future_membership():
    d = predictions(6)
    groups = subsets(d)
    assert groups["REPEAT"].match_id.tolist() == ["synthetic-1", "synthetic-2", "synthetic-4", "synthetic-5"]
    assert groups["FIRST"].match_id.tolist() == ["synthetic-0", "synthetic-3"]
    changed = d.assign(won=1-d.won, meeting_group="5_plus", future_h2h_meetings=999)
    for name in ["ALL", "REPEAT", "FIRST"]:
        assert subsets(changed)[name].match_id.tolist() == groups[name].match_id.tolist()


def test_dyadic_variance_matches_enumeration_for_repeated_pairs_and_shared_graph():
    a = np.array([1, 1, 1, 2, 4, 3])
    b = np.array([2, 2, 3, 3, 5, 5])
    difference = np.array([.2, -.1, .3, -.05, .15, -.2])
    centered = difference - difference.mean()
    expected = sum(centered[i] * centered[j]
                   for i in range(len(a)) for j in range(len(a))
                   if {a[i], b[i]} & {a[j], b[j]}) / len(a) ** 2
    actual = dyadic_mean_interval(difference, a, b, minimum=1)
    assert actual["variance"] == pytest.approx(expected, abs=1e-15)
    reversed_roles = dyadic_mean_interval(difference, b, a, minimum=1)
    assert reversed_roles["variance"] == pytest.approx(expected, abs=1e-15)
    assert actual["pairs"] == 5 and actual["players"] == 5


@pytest.mark.parametrize("variance", [-.1, 0, np.nan, np.inf])
def test_nonpositive_or_nonfinite_dyadic_variance_remains_unavailable(monkeypatch, variance):
    monkeypatch.setattr("tennis_q2_checks.dyadic_covariance", lambda *args, **kwargs: np.array([[variance]]))
    d = predictions()
    result = dyadic_mean_interval(np.arange(len(d), dtype=float), d.player_id, d.opponent_id)
    assert result["inference_status"] == "unavailable_nonpositive_or_nonfinite_variance"
    assert np.isnan(result["standard_error"]) and np.isnan(result["ci95_lower"])
    if np.isfinite(variance):
        assert result["variance"] == variance


def test_sparse_participant_or_pair_support_withholds_dyadic_inference():
    result = dyadic_mean_interval([.1, -.1] * 20, [1] * 40, [2] * 40)
    assert result["inference_status"] == "unavailable_insufficient_dyadic_support"
    assert np.isnan(result["ci95_upper"])
    # Many participants alone are insufficient when there are fewer than 20 pairs.
    a, b = np.arange(19), np.arange(19) + 100
    result = dyadic_mean_interval(np.linspace(-.1, .2, 19), a, b)
    assert result["players"] == 38 and result["pairs"] == 19
    assert result["inference_status"] == "unavailable_insufficient_dyadic_support"


@pytest.mark.parametrize("field", ["won", "prior_h2h_meetings", "opponent_id", "match_id"])
def test_crosscheck_rejects_prediction_history_outcome_or_identifier_mismatch(tmp_path, field):
    d = validate_predictions(predictions(), 2020, 2024)
    features = d.assign(eligible=True, is_player_a=True)
    features.to_csv(tmp_path / "player_match_features.csv.gz", index=False)
    summary = {"configuration": {"test_start": 2020}, "q2": {"test_matches": len(d)}}
    verify_saved_features(d, tmp_path, summary)
    altered = d.copy()
    altered.loc[0, field] = "missing" if field == "match_id" else d.loc[0, field] + 1
    with pytest.raises(ValueError, match="differ from saved features"):
        verify_saved_features(altered, tmp_path, summary)


def test_saved_q2_checks_reproduce_primary_results_without_refitting(tmp_path):
    source = Path("outputs_final")
    if not (source / "q2_test_predictions.csv.gz").exists():
        pytest.skip("Authoritative saved held-out predictions are not present.")
    summary = json.loads((source / "run_summary.json").read_text())
    result = run_q2(source, tmp_path, summary)
    comparisons = pd.read_csv(tmp_path / "q2_comparisons.csv")
    scores = pd.read_csv(tmp_path / "q2_scores.csv")
    assert len(comparisons) == 54 and len(scores) == 9
    assert result["checks"]["all_nine_historical_pair_bootstrap_comparisons_reproduced"]
    assert not result["checks"]["models_refitted"]
    counts = {row["subset"]: row["n_matches"] for row in result["counts"]}
    assert counts["REPEAT"] + counts["FIRST"] == counts["ALL"] == summary["q2"]["test_matches"]
