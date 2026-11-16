"""Synthetic tests of exact Q3 sample rules; these are not research findings."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

import tennis_handedness as handedness
from tennis_project import Config
from tennis_q3_sample import reconstruct_adjusted_sample, sample_id_hash
from tennis_q3_comparability import distribution_summary, overlap_diagnostics


def sample_rows(player_id, left=2, right=3, player_hand="R"):
    rows = []
    for other, count in [("L", left), ("R", right)]:
        for i in range(count):
            opponent_id = 1000 + player_id * 10 + i
            rows.append(dict(
                player_id=player_id, opponent_id=opponent_id,
                match_id=f"{player_id}-{other}-{i}", player_hand=player_hand,
                opponent_hand=other, eligible=True, log_rank_advantage=np.log(2),
                player_rank=20., opponent_rank=40., player_age=25.,
                recent_win_rate=.5, opponent_recent_win_rate=.4, prior_matches=30,
                player_name=f"Synthetic {player_id}", won=i % 2,
                pair_id=f"{player_id}:{opponent_id}", tourney_id=f"event-{i}",
                valid_service_stats=True, service_points_won=30.,
                service_points_observed=50.,
            ))
    return rows


def test_exact_adjusted_selection_order_and_unequal_group_counts():
    rows = sample_rows(1)  # Two left, three right: unequal counts are eligible.
    rows += sample_rows(2, left=1)  # Insufficient left opportunities.
    incomplete = sample_rows(3)
    incomplete[0]["recent_win_rate"] = np.nan  # Minimum applied AFTER completeness.
    rows += incomplete
    changing = sample_rows(4)
    changing[0].update(player_hand="L", player_age=np.nan)
    rows += changing  # Conflicting hand remains disqualifying despite missing age.
    unknown = sample_rows(5)
    unknown[0]["opponent_hand"] = "U"
    rows += unknown
    ineligible = sample_rows(6)
    ineligible[0]["eligible"] = False
    rows += ineligible
    unknown_own = sample_rows(7, player_hand="U")
    rows += unknown_own
    result = reconstruct_adjusted_sample(pd.DataFrame(rows), minimum=2)
    assert result.player_id.unique().tolist() == [1]
    assert result.match_id.tolist() == [r["match_id"] for r in sample_rows(1)]
    assert result.opponent_hand.value_counts().to_dict() == {"R": 3, "L": 2}
    assert result.index.tolist() == list(range(5))


@pytest.mark.parametrize("field", ["log_rank_advantage", "player_age", "recent_win_rate", "opponent_recent_win_rate", "prior_matches"])
def test_each_original_covariate_is_required_before_opportunity_minimum(field):
    rows = sample_rows(1)
    rows[0][field] = np.nan
    assert reconstruct_adjusted_sample(pd.DataFrame(rows), minimum=2).empty


def test_missing_rank_is_not_imputed_or_replaced_with_zero():
    rows = sample_rows(1, left=3)
    rows[0].update(player_rank=np.nan, log_rank_advantage=np.nan)
    rows[1].update(opponent_rank=np.nan, log_rank_advantage=np.nan)
    assert reconstruct_adjusted_sample(pd.DataFrame(rows), minimum=2).empty
    original = pd.DataFrame(rows)
    result = reconstruct_adjusted_sample(original, minimum=1)
    assert result.player_rank.eq(20).all() and result.opponent_rank.eq(40).all()
    assert original.player_rank.isna().sum() == 1
    assert original.opponent_rank.isna().sum() == 1


def test_known_hand_filter_precedes_consistent_hand_filter():
    rows = sample_rows(1)
    rows.append({**rows[0], "match_id": "unknown-opponent", "player_hand": "L", "opponent_hand": "U"})
    rows.append({**rows[0], "match_id": "ineligible", "player_hand": "L", "eligible": False})
    assert len(reconstruct_adjusted_sample(pd.DataFrame(rows), minimum=2)) == 5


def test_exact_ids_match_sample_passed_to_original_model():
    rows = [r for pid in range(1, 21) for r in sample_rows(pid, left=5, right=6)]
    rows += sample_rows(99, left=1, right=10)
    players = pd.DataFrame(rows)
    expected = reconstruct_adjusted_sample(players, minimum=5)
    captured = []

    class Captured(Exception):
        pass

    def capture(d):
        captured.append(d)
        raise Captured

    with TemporaryDirectory() as tmp, patch.object(handedness, "_within_fit", side_effect=capture):
        with pytest.raises(Captured):
            handedness.analyze_handedness(players, Config(min_hand_matches=5), Path(tmp))
    pd.testing.assert_frame_equal(expected, captured[0])
    assert sample_id_hash(expected) == sample_id_hash(captured[0])
    assert sample_id_hash(expected) != sample_id_hash(expected.iloc[::-1])


def diagnostic_rows(player_id, left, right, player_hand="R"):
    return [{**row, "surface": "Hard", "season": 2020}
            for row in sample_rows(player_id, left, right, player_hand)]


def test_overlap_distinguishes_absence_sparse_data_and_rank_separation():
    rows = diagnostic_rows(1, 2, 0)
    rows += diagnostic_rows(2, 2, 3)
    rows += diagnostic_rows(3, 5, 7)
    separated = diagnostic_rows(4, 5, 7)
    for row in separated:
        if row["opponent_hand"] == "R":
            row["opponent_rank"] = 400.
            row["log_rank_advantage"] = np.log(20.)
    rows += separated
    strata, coverage = overlap_diagnostics(pd.DataFrame(rows))
    assert strata.set_index("player_id").status.to_dict() == {
        1: "one_hand_only", 2: "insufficient_observations",
        3: "assessable", 4: "no_rank_candidates",
    }
    total = coverage.loc[coverage.player_hand.eq("all")].set_index("opponent_hand")
    assert total.loc["L", "player_match_rows"] == 14
    assert total.loc["R", "player_match_rows"] == 17
    assert total.loc["L", "both_hand_share"] == pytest.approx(12 / 14)
    assert total.loc["R", "both_hand_share"] == 1
    assert total.loc["L", "rank_candidate_share"] == pytest.approx(7 / 14)
    assert total.loc["R", "rank_candidate_share"] == pytest.approx(10 / 17)
    assert total.loc["L", "adequately_observed_share"] == pytest.approx(10 / 14)
    assert total.loc["R", "adequately_observed_share"] == pytest.approx(14 / 17)
    assert total.loc["L", "both_hand_strata"] == 3
    assert total.loc["L", "one_hand_strata"] == 1
    assert total.loc["L", "no_rank_candidate_strata"] == 1
    assert total.loc["L", "sparse_both_hand_strata"] == 1
    absent = coverage.loc[coverage.player_hand.eq("L")]
    assert absent.player_match_rows.eq(0).all()
    assert absent.both_hand_share.isna().all()


def test_overlap_requires_both_ranks_and_rejects_missing_rank_candidates():
    rows = diagnostic_rows(1, 2, 4)
    rows[0]["player_rank"] = np.nan
    rows[2]["opponent_rank"] = np.nan
    rows[3]["player_rank"] = 31.  # Similar opponent rank alone is insufficient.
    rows[4]["opponent_rank"] = 61.  # Similar focal rank alone is insufficient.
    strata, _ = overlap_diagnostics(pd.DataFrame(rows))
    assert strata.with_rank_candidate_L.iloc[0] == 1
    assert strata.with_rank_candidate_R.iloc[0] == 1
    no_candidates = pd.DataFrame(rows[:-1])
    strata, _ = overlap_diagnostics(no_candidates)
    assert strata.status.iloc[0] == "no_rank_candidates"
    assert strata.with_rank_candidate_L.iloc[0] == 0
    assert strata.with_rank_candidate_R.iloc[0] == 0


def test_overlap_caliper_includes_exact_one_point_five_rank_ratio():
    rows = diagnostic_rows(1, 1, 1)
    rows[1].update(player_rank=30., opponent_rank=60.)
    strata, _ = overlap_diagnostics(pd.DataFrame(rows))
    assert strata.with_rank_candidate_L.iloc[0] == 1
    assert strata.with_rank_candidate_R.iloc[0] == 1


def test_ecdf_is_normalized_per_hand_despite_unequal_counts():
    rows = diagnostic_rows(1, 2, 10)
    for row in rows:
        i = int(row["match_id"].rsplit("-", 1)[1])
        row["opponent_rank"] = 40. if i % 2 else 80.
        row["log_rank_advantage"] = np.log(row["opponent_rank"] / row["player_rank"])
    strata, _ = overlap_diagnostics(pd.DataFrame(rows))
    assert strata.n_L.iloc[0] == 2 and strata.n_R.iloc[0] == 10
    assert strata.opponent_rank_ecdf_distance.iloc[0] == 0
    assert strata.log_rank_advantage_ecdf_distance.iloc[0] == 0
    assert strata.status.iloc[0] == "insufficient_observations"


def test_distribution_quantiles_keep_observation_units_and_missing_denominators():
    rows = diagnostic_rows(1, 2, 5)
    rows[0]["opponent_recent_win_rate"] = np.nan
    data = pd.DataFrame(rows)
    result = distribution_summary(data, "synthetic")
    overall = result.loc[result.dimension.eq("overall")]
    form = overall.loc[overall.measure.eq("opponent_recent_win_rate")].set_index("opponent_hand")
    assert form.loc["L", "player_match_rows"] == 2
    assert form.loc["L", "nonmissing"] == 1
    assert form.loc["L", "q50"] == .4
    ranks = overall.loc[overall.measure.eq("opponent_rank")].set_index("opponent_hand")
    assert ranks.loc["R", "player_match_rows"] == 5
    assert ranks.loc["R", "focal_players"] == 1
    assert ranks.loc["R", "distinct_opponents"] == 5
    assert ranks.loc["R", "unique_matches"] == 5
    assert ranks.loc["R", "q25"] == 40.
    assert ranks.loc["R", "q50"] == 40.
    assert ranks.loc["R", "q75"] == 40.
    assert ranks.loc["R", "iqr"] == 0
    assert set(result.dimension) == {"overall", "player_hand", "surface", "season"}


def test_overlap_does_not_pool_across_players_surfaces_or_seasons():
    rows = diagnostic_rows(1, 1, 1)
    rows[1]["surface"] = "Clay"
    rows += diagnostic_rows(2, 1, 1)
    rows[3]["season"] = 2021
    rows += diagnostic_rows(3, 1, 0) + diagnostic_rows(4, 0, 1)
    strata, coverage = overlap_diagnostics(pd.DataFrame(rows))
    assert len(strata) == 6
    assert strata.status.eq("one_hand_only").all()
    assert coverage.rank_candidate_rows.eq(0).all()
    assert coverage.both_hand_rows.eq(0).all()
