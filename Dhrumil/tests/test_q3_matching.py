"""Synthetic unit checks and a predictors-only saved-data selection audit.

Synthetic fixtures test software behavior and are not research findings.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from tennis_q3_matching import CALIPER, match_observations, refit_matched


def row(match, hand, player_rank=40, opponent_rank=50, player=1, surface="Hard", season=2020):
    return dict(match_id=match, player_id=player, opponent_id=100 + len(match),
                player_hand="R", opponent_hand=hand, player_rank=player_rank,
                opponent_rank=opponent_rank, surface=surface, season=season, won=0,
                score="6-0 6-0", pair_id=f"{player}:100")


def test_both_rank_calipers_and_exact_strata_are_required():
    rows = [row("L", "L"), row("R-player", "R", player_rank=61),
            row("R-opponent", "R", opponent_rank=76),
            row("R-surface", "R", surface="Clay"), row("R-season", "R", season=2021),
            row("R-player-id", "R", player=2), row("R-boundary", "R", 60, 75)]
    selected, pairs = match_observations(pd.DataFrame(rows))
    assert set(selected.match_id) == {"L", "R-boundary"}
    assert pairs.player_log_rank_difference.iloc[0] == pytest.approx(CALIPER)
    assert pairs.opponent_log_rank_difference.iloc[0] == pytest.approx(CALIPER)


def test_nearest_sum_no_reuse_and_stable_ties():
    d = pd.DataFrame([row("L-1", "L"), row("L-2", "L"), row("L-3", "L"),
                      row("R-far", "R", 45, 60), row("R-a", "R"), row("R-b", "R")])
    selected, pairs = match_observations(d)
    assert pairs.right_match_id.tolist() == ["R-a", "R-b", "R-far"]
    assert not selected.duplicated(["player_id", "match_id"]).any()
    assert pairs.left_match_id.is_unique and pairs.right_match_id.is_unique


def test_selection_is_deterministic_and_outcome_blind():
    d = pd.DataFrame([row("L-2", "L"), row("R-b", "R"), row("L-1", "L"), row("R-a", "R")])
    expected, pairs = match_observations(d)
    changed = d.sample(frac=1, random_state=77).copy()
    changed["won"] = 1
    changed["score"] = "0-6 0-6"
    changed["fitted_effect"] = np.arange(len(changed))
    actual, changed_pairs = match_observations(changed)
    pd.testing.assert_frame_equal(pairs, changed_pairs)
    assert actual[["player_id", "match_id"]].equals(expected[["player_id", "match_id"]])


def test_missing_nonpositive_ranks_and_one_hand_strata_have_no_pairs():
    d = pd.DataFrame([row("L-missing", "L", np.nan), row("L-zero", "L", 0),
                      row("L-inf", "L", np.inf), row("R", "R"),
                      row("L-only", "L", surface="Clay")])
    selected, pairs = match_observations(d)
    assert selected.empty and pairs.empty


def test_duplicate_observation_is_rejected_but_different_players_can_share_match():
    d = pd.DataFrame([row("L", "L"), row("R", "R")])
    with pytest.raises(ValueError, match="Duplicate"):
        match_observations(pd.concat([d, d.iloc[[0]]]))
    other = d.assign(player_id=2)
    selected, _ = match_observations(pd.concat([d, other]))
    assert len(selected) == 4 and selected.match_id.nunique() == 2


def test_opportunity_minimum_and_global_support_remain_required():
    d = pd.DataFrame([row("L", "L"), row("R", "R")])
    contrasts, info, sample = refit_matched(d, minimum=2)
    assert sample.empty and info["removed_rows_for_opportunity_minimum"] == 2
    assert contrasts.inference_status.eq("unavailable_insufficient_global_support").all()
    assert contrasts.ci95_lower_pp.isna().all()


def _model_sample(right_players=30, left_players=10):
    rng = np.random.default_rng(123)
    rows = []
    for player in range(right_players + left_players):
        for j in range(20):
            r = row(f"{player:03d}-{j:02d}", "L" if j % 2 else "R", player=player + 1)
            r.update(player_hand="R" if player < right_players else "L",
                     opponent_id=1000 + player * 20 + j,
                     pair_id=f"{player + 1}:{1000 + player * 20 + j}",
                     log_rank_advantage=rng.normal(), player_age=25 + rng.normal(),
                     recent_win_rate=rng.uniform(), opponent_recent_win_rate=rng.uniform(),
                     prior_matches=int(rng.integers(10, 500)), won=int(rng.integers(0, 2)))
            rows.append(r)
    return pd.DataFrame(rows)


def test_insufficient_focal_hand_subgroup_withholds_only_its_inference():
    contrasts, info, d = refit_matched(_model_sample())
    assert len(d) == 800
    assert info["within_design_rank"] == info["within_design_columns"]
    by_hand = contrasts.set_index("player_hand")
    assert by_hand.loc["L", "inference_status"] == "unavailable_insufficient_subgroup_support"
    assert np.isnan(by_hand.loc["L", "ci95_lower_pp"])
    assert by_hand.loc["R", "inference_status"] == "available"


def test_rank_deficient_hand_interaction_keeps_inference_unavailable():
    contrasts, info, _ = refit_matched(_model_sample(right_players=30, left_players=0))
    assert info["within_design_rank"] < info["within_design_columns"]
    assert contrasts.inference_status.eq("unavailable_rank_deficient_design").all()
    assert contrasts.ci95_upper_pp.isna().all()


def test_nonpositive_contrast_variance_is_not_repaired(monkeypatch):
    def negative_covariance(scores, bread, *args):
        return -np.eye(len(bread))
    monkeypatch.setattr("tennis_q3_matching.dyadic_covariance", negative_covariance)
    contrasts, _, _ = refit_matched(_model_sample(right_players=20, left_players=20))
    assert contrasts.inference_status.eq("unavailable_nonpositive_variance").all()
    assert contrasts.ci95_upper_pp.isna().all()


def verify_saved_matching(source, validation):
    """Reproduce saved selection using predictors only; never fit/read outcomes."""
    from tennis_handedness import _adequate
    from tennis_q3_sample import reconstruct_adjusted_sample

    source, validation = Path(source), Path(validation)
    summary = json.loads((source / "run_summary.json").read_text())
    columns = ["eligible", "player_hand", "opponent_hand", "log_rank_advantage", "player_age",
               "recent_win_rate", "opponent_recent_win_rate", "prior_matches", "player_id",
               "opponent_id", "match_id", "surface", "season", "player_rank", "opponent_rank"]
    minimum = summary["configuration"]["min_hand_matches"]
    d = reconstruct_adjusted_sample(pd.read_csv(source / "player_match_features.csv.gz",
                                               usecols=columns), minimum)
    selected, pairs = match_observations(d)
    saved = pd.read_csv(validation / "matched_pairs.csv.gz")
    pd.testing.assert_frame_equal(pairs, saved, check_dtype=False, atol=1e-12, rtol=1e-12)
    assert not selected.duplicated(["player_id", "match_id"]).any()
    assert len(selected) == 2 * len(saved)
    sides = []
    for label, hand in [("left", "L"), ("right", "R")]:
        side = saved.merge(d, left_on=["player_id", f"{label}_match_id"],
                           right_on=["player_id", "match_id"], how="left",
                           validate="one_to_one", suffixes=("", "_original"), indicator=True)
        assert side["_merge"].eq("both").all()
        assert side.opponent_hand.eq(hand).all()
        for field in ["surface", "season"]:
            assert side[field].eq(side[field + "_original"]).all()
        sides.append(side)
    left, right = sides
    for field in ["player_rank", "opponent_rank"]:
        a, b = left[field].to_numpy(), right[field].to_numpy()
        assert np.isfinite(a).all() and np.isfinite(b).all()
        assert (a > 0).all() and (b > 0).all()
        assert (np.maximum(a, b) / np.minimum(a, b) <= 1.5).all()
        np.testing.assert_allclose(np.abs(np.log(a) - np.log(b)),
                                   saved[field.replace("_rank", "_log_rank_difference")],
                                   atol=1e-12, rtol=1e-12)
    long_ids = pd.concat([saved[["player_id", "left_match_id"]].rename(
        columns={"left_match_id": "match_id"}), saved[["player_id", "right_match_id"]].rename(
        columns={"right_match_id": "match_id"})], ignore_index=True)
    assert not long_ids.duplicated(["player_id", "match_id"]).any()
    analyzed = _adequate(selected, minimum).reset_index(drop=True)
    ids = ["player_id", "match_id", "opponent_id"]
    saved_ids = pd.read_csv(validation / "matched_analysis_ids.csv.gz")
    pd.testing.assert_frame_equal(analyzed[ids], saved_ids, check_dtype=False)
    original_ids = saved_ids.merge(d[ids], on=["player_id", "match_id"], how="left",
                                  validate="one_to_one", suffixes=("", "_original"))
    assert original_ids.opponent_id.eq(original_ids.opponent_id_original).all()
    opportunities = analyzed.groupby(["player_id", "opponent_hand"]).size().unstack(fill_value=0)
    assert opportunities[["L", "R"]].ge(minimum).all().all()
    return {
        "source_run_id": summary["run_id"],
        "reproduction_command": "python -m pytest tests/test_q3_matching.py::test_saved_matching_selection_and_original_ids -q",
        "checks_executed": {
            "saved_pairs_equal_predictors_only_reconstruction": True,
            "all_pair_ids_exist_in_original_adjusted_sample": True,
            "both_opponent_hands_correct": True,
            "same_focal_player_surface_and_season": True,
            "both_original_rank_ratios_at_most_1_5": True,
            "stored_log_rank_differences_recomputed": True,
            "no_directed_observation_reused": True,
            "analysis_ids_exactly_reapply_original_opportunity_minimum": True,
            "original_focal_opponent_and_match_ids_preserved": True,
            "outcomes_or_sensitivity_contrasts_loaded": False,
            "model_refitted": False,
        },
        "counts": {
            "pairs": len(saved), "selected_player_match_rows": len(selected),
            "selected_focal_players": int(selected.player_id.nunique()),
            "selected_unique_matches": int(selected.match_id.nunique()),
            "analyzed_player_match_rows": len(analyzed),
            "analyzed_focal_players": int(analyzed.player_id.nunique()),
            "analyzed_unique_matches": int(analyzed.match_id.nunique()),
            "minimum_opportunities_per_hand": minimum,
        },
    }


def test_saved_matching_selection_and_original_ids():
    source = Path("outputs_final")
    validation = Path("validation/q3_comparability")
    required = [source / "player_match_features.csv.gz", source / "run_summary.json",
                validation / "matched_pairs.csv.gz", validation / "matched_analysis_ids.csv.gz"]
    if not all(path.exists() for path in required):
        pytest.skip("Saved full-study matching validation is not present.")
    verify_saved_matching(source, validation)
