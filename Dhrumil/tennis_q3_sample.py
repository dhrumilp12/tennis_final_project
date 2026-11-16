"""Reconstruct and verify the saved Q3 adjusted sample without refitting it.

The historical analysis source remains unchanged. Rank validation checks its
saved features; it does not introduce another eligibility rule or impute ranks.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pandas as pd

import tennis_handedness as handedness
from tennis_project import Config


COMPLETE_COVARIATES = [
    "log_rank_advantage", "player_age", "recent_win_rate",
    "opponent_recent_win_rate", "prior_matches",
]


def reconstruct_adjusted_sample(players, minimum=10):
    """Apply exactly the original adjusted-sample rules, in their original order."""
    known = players.loc[
        players.eligible & players.player_hand.isin(["L", "R"])
        & players.opponent_hand.isin(["L", "R"])
    ].copy()
    changing = known.groupby("player_id").player_hand.nunique()
    changing = changing.index[changing.gt(1)]
    complete = known.dropna(subset=COMPLETE_COVARIATES)
    consistent = complete.loc[~complete.player_id.isin(changing)]
    return handedness._adequate(consistent, minimum).reset_index(drop=True)


def sample_id_hash(d):
    """Hash the ordered directed observation identifiers, including their order."""
    ids = d[["player_id", "match_id"]].to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(ids.encode()).hexdigest()


def verify_adjusted_sample(players, d, summary, source_output):
    """Compare to the original sampler and saved counts, support and player IDs.

    The saved run has no explicit row-ID list. Execute its unchanged sampler,
    intercept the first model fit, and check exact ordered IDs. Independently
    compare the historical summary, subgroup support and exposure tables.
    """
    source_output = Path(source_output)
    captured = {}

    class SampleCaptured(Exception):
        pass

    def capture(sample):
        captured["sample"] = sample.copy()
        raise SampleCaptured

    cfg = Config(**summary["configuration"])
    with TemporaryDirectory(prefix="q3-sample-verification-") as tmp:
        with patch.object(handedness, "_within_fit", side_effect=capture):
            try:
                handedness.analyze_handedness(players, cfg, Path(tmp))
            except SampleCaptured:
                pass
    if "sample" not in captured:
        raise ValueError("The historical sampler did not reach adjustment; exact fit-sample verification unavailable.")
    pd.testing.assert_frame_equal(
        d[["player_id", "match_id"]].reset_index(drop=True),
        captured["sample"][["player_id", "match_id"]].reset_index(drop=True),
    )
    if d.duplicated(["player_id", "match_id"]).any():
        raise ValueError("Duplicate directed observation IDs in adjusted sample.")
    actual_counts = {
        "adjusted_player_match_rows": len(d),
        "adjusted_unique_matches": int(d.match_id.nunique()),
        "adjusted_players": int(d.player_id.nunique()),
    }
    for name, value in actual_counts.items():
        if value != summary["q3"][name]:
            raise ValueError(f"Historical Q3 count mismatch: {name}.")
    historical_support = pd.read_csv(source_output / "q3_subgroup_support.csv")
    historical_support = historical_support.loc[historical_support["sample"].eq("adjusted")]
    support = pd.DataFrame(handedness._support(d, "adjusted"))
    keys = ["player_hand", "opponent_hand"]
    pd.testing.assert_frame_equal(
        support.sort_values(keys).reset_index(drop=True),
        historical_support.sort_values(keys).reset_index(drop=True),
        check_dtype=False, rtol=1e-12, atol=1e-12,
    )
    historical_exposure = pd.read_csv(source_output / "q3_player_exposure.csv")
    exposure = d.groupby(["player_hand", "player_id"]).size().rename("rows").reset_index()
    columns = ["player_hand", "player_id", "rows"]
    pd.testing.assert_frame_equal(
        exposure.sort_values(columns[:2]).reset_index(drop=True),
        historical_exposure[columns].sort_values(columns[:2]).reset_index(drop=True),
        check_dtype=False,
    )
    ranks = d[["player_rank", "opponent_rank"]].to_numpy(float)
    if not (np.isfinite(ranks).all() and (ranks > 0).all()):
        raise ValueError("Adjusted sample has missing, nonfinite or nonpositive historical ranks; no imputation is allowed.")
    np.testing.assert_allclose(
        d.log_rank_advantage.to_numpy(float),
        np.log(d.opponent_rank.to_numpy(float) / d.player_rank.to_numpy(float)),
        rtol=1e-12, atol=1e-12,
    )
    return {
        "exact_ordered_ids_match_original_sampler": True,
        "directed_observation_ids_unique": True,
        "historical_summary_counts_match": True,
        "historical_subgroup_support_matches": True,
        "historical_exposure_player_ids_and_counts_match": True,
        "historical_ranks_finite_and_positive": True,
        "saved_log_rank_advantage_matches_historical_rank_ratio": True,
        "ordered_sample_ids_sha256": sample_id_hash(d),
        **actual_counts,
        "verification_scope": (
            "Exact ordered (player_id, match_id) equality with the unchanged historical sampler, "
            "plus historical summary/support/exposure checks. The historical run did not save "
            "an explicit adjusted row-ID list; no historical manifest was amended."
        ),
    }
