"""One prespecified, outcome-blind Q3 matching sensitivity.

This module does not change the primary analysis. The 1.5 rank-ratio caliper is
a pragmatic diagnostic choice, not a universal standard or a tuned parameter.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tennis_handedness import _adequate, _contrast_rows, _within_fit, dyadic_covariance


CALIPER = float(np.log(1.5))
PAIR_COLUMNS = ["player_id", "surface", "season", "left_match_id", "right_match_id",
                "player_log_rank_difference", "opponent_log_rank_difference"]
MATCHING_RULE = (
    "Within the same focal player, surface and calendar season, traverse left-opponent "
    "observations in stable match-ID order. Require each absolute log-rank difference "
    "(focal and opponent separately) <= log(1.5). Choose the unused right-opponent "
    "observation minimizing the sum of those two differences; break ties by stable "
    "right match ID. No replacement within a focal player's records. Missing, "
    "nonfinite or nonpositive ranks are not candidates. Outcomes, scores and fitted "
    "effects do not enter selection. Reapply the primary per-player minimum of "
    "opportunities against each hand before refitting. The caliper is pragmatic, "
    "not universal; this is the only matched-sample rule."
)


def match_observations(d, caliper=CALIPER):
    """Return selected original observations and an auditable table of pairs.

    Selection only reads identifiers, surface, season, opponent hand and the two
    historical ranks. A physical match may remain in different focal players'
    records, as in the primary sample; it is not an independent observation.
    """
    if not np.isfinite(caliper) or caliper < 0:
        raise ValueError("The log-rank caliper must be finite and nonnegative.")
    if d[["player_id", "match_id"]].isna().any().any():
        raise ValueError("Matching requires stable nonmissing player and match IDs.")
    if d.duplicated(["player_id", "match_id"]).any():
        raise ValueError("Duplicate player-match observations cannot be matched.")
    # Positions identify original records without trusting their DataFrame index.
    work = d[["player_id", "match_id", "surface", "season", "opponent_hand",
              "player_rank", "opponent_rank"]].copy()
    work["_position"] = np.arange(len(d))
    ranks = work[["player_rank", "opponent_rank"]].to_numpy(dtype=float)
    valid = np.isfinite(ranks).all(axis=1) & (ranks > 0).all(axis=1)
    valid &= work[["surface", "season"]].notna().all(axis=1).to_numpy()
    work = work.loc[valid].copy()
    # Match IDs are source identifiers, not dates, scores, wins or row ordering.
    work["_match_sort"] = work.match_id.astype(str)
    work = work.sort_values(["player_id", "_match_sort"], kind="stable")
    chosen, records = [], []
    for (player, surface, season), group in work.groupby(
            ["player_id", "surface", "season"], sort=True):
        left = group.loc[group.opponent_hand.eq("L")]
        right = group.loc[group.opponent_hand.eq("R")]
        if left.empty or right.empty:
            continue
        right_logs = np.log(right[["player_rank", "opponent_rank"]].to_numpy(float))
        available = np.ones(len(right), dtype=bool)
        for _, row in left.iterrows():
            differences = np.abs(right_logs - np.log(
                row[["player_rank", "opponent_rank"]].to_numpy(float)))
            allowed = available & (differences <= caliper + 1e-12).all(axis=1)
            if not allowed.any():
                continue
            distances = np.where(allowed, differences.sum(axis=1), np.inf)
            nearest = int(np.argmin(distances))  # stable right-ID order resolves ties
            candidate = right.iloc[nearest]
            available[nearest] = False
            chosen.extend([int(row["_position"]), int(candidate["_position"])])
            records.append({"player_id": player, "surface": surface, "season": season,
                            "left_match_id": row.match_id,
                            "right_match_id": candidate.match_id,
                            "player_log_rank_difference": differences[nearest, 0],
                            "opponent_log_rank_difference": differences[nearest, 1]})
    selected = d.iloc[chosen].copy()
    # Canonical output ordering makes shuffled-input checks straightforward.
    if not selected.empty:
        selected = selected.assign(_match_sort=selected.match_id.astype(str)).sort_values(
            ["player_id", "_match_sort"], kind="stable").drop(columns="_match_sort")
    return selected.reset_index(drop=True), pd.DataFrame(records, columns=PAIR_COLUMNS)


def _unavailable(d, reason):
    rows = []
    for hand in ["R", "L"]:
        group = d.loc[d.player_hand.eq(hand)]
        rows.append({"method": "matched_dyadic", "player_hand": hand,
                     "contrast": "opponent_L_minus_R", "players": int(group.player_id.nunique()),
                     "player_match_rows": len(group), "unique_matches": int(group.match_id.nunique()),
                     **{name: np.nan for name in ["coefficient", "variance", "standard_error",
                        "ci95_lower", "ci95_upper", "difference_pp", "standard_error_pp",
                        "ci95_lower_pp", "ci95_upper_pp"]}, "inference_status": reason})
    return pd.DataFrame(rows)


def refit_matched(selected, minimum=10):
    """Refit the unchanged Q3 specification and primary dyadic uncertainty.

    All original IDs survive selection. Reapply opportunity minima and preserve
    the existing global, subgroup, identification and contrast-variance checks.
    """
    if minimum < 1:
        raise ValueError("The opportunity minimum must be positive.")
    d = _adequate(selected, minimum).reset_index(drop=True)
    n, nf = len(d), int(d.player_id.nunique())
    info = {"matched_rows_before_opportunity_minimum": len(selected),
            "min_hand_matches": minimum, "player_match_rows": n,
            "unique_matches": int(d.match_id.nunique()), "players": nf,
            "removed_rows_for_opportunity_minimum": len(selected) - n,
            "covariance": "Original shared-player dyadic sandwich; original player and match IDs retained.",
            "warnings": []}
    if n < 200 or nf < 20:
        info["status"] = "unavailable_insufficient_global_support"
        return _unavailable(d, info["status"]), info, d
    fit, xw = _within_fit(d)
    rank = int(np.linalg.matrix_rank(xw))
    df = n - nf - rank
    info.update(within_design_rank=rank, within_design_columns=xw.shape[1],
                within_condition_number=float(np.linalg.cond(xw)),
                absorbed_player_intercepts=nf, effective_parameters=nf + rank,
                residual_degrees_of_freedom=df)
    if df <= 0:
        info["status"] = "unavailable_nonpositive_residual_degrees_of_freedom"
        return _unavailable(d, info["status"]), info, d
    correction = (n - 1) / df
    scores = xw.to_numpy() * fit.resid.to_numpy()[:, None]
    covariance = dyadic_covariance(scores, fit.normalized_cov_params,
                                  d.player_id, d.opponent_id, correction)
    identified = rank == xw.shape[1]
    contrasts = pd.DataFrame(_contrast_rows(fit, covariance, d, "matched_dyadic", identified))
    minimum_eigenvalue = float(np.linalg.eigvalsh(covariance).min())
    info.update(dyadic_finite_sample_factor=float(correction),
                dyadic_nodes=int(pd.unique(pd.concat([d.player_id, d.opponent_id])).size),
                dyadic_pairs=int(d.pair_id.nunique()),
                primary_negative_variance_terms=int((np.diag(covariance) < 0).sum()),
                primary_minimum_covariance_eigenvalue=minimum_eigenvalue,
                contrast_inference=dict(zip(contrasts.player_hand, contrasts.inference_status)),
                status="fitted" if contrasts.inference_status.eq("available").all()
                else "fitted_with_unavailable_inference")
    if not identified:
        info["warnings"].append("Rank-deficient within-player design: contrast inference unavailable.")
    if minimum_eigenvalue < 0:
        info["warnings"].append("Dyadic covariance is indefinite; nonpositive contrast variances are unavailable. Positive contrasts remain exploratory.")
    info["warnings"].append("Exploratory dyadic intervals assume no remaining dependence between disjoint participant pairs; restrictions select a narrower sample.")
    return contrasts, info, d
