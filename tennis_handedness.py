"""Within-player handedness comparisons with explicit dyadic inference.

The primary covariance clusters score contributions through either participant,
including repeat meetings and complementary views of the same match. See
Aronow, Samii & Assenova (2015), https://arxiv.org/abs/1312.3398.
The original focal-player x match covariance is retained as a sensitivity;
negative variances are unavailable estimates, never clipped or absolutized.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
from scipy.stats import norm
import statsmodels.api as sm
from statsmodels.stats.sandwich_covariance import cov_cluster, cov_cluster_2groups

HAND_TERMS = ["opponent_left", "opponent_left_x_player_left"]


def dyadic_covariance(scores, bread, player_ids, opponent_ids, correction=1.0):
    """Sandwich for repeated undirected dyads, retaining all directed views.

    Sum scores over each unordered pair first. Each node sum contains all pair
    scores incident to that node. The node outer products count each within-pair
    product twice; subtracting pair outer products counts it exactly once.
    Cross-pair products sharing either participant are then counted once too.
    This is the direct shared-node covariance, not player-role two-way clustering.
    No PSD repair is applied: a negative contrast variance is reported unavailable.
    """
    scores = np.asarray(scores, dtype=float)
    a, b = np.asarray(player_ids), np.asarray(opponent_ids)
    if np.any(a == b):
        raise ValueError("Dyadic covariance requires two distinct participants.")
    pair_index = pd.MultiIndex.from_arrays([np.minimum(a, b), np.maximum(a, b)])
    pair_scores = pd.DataFrame(scores).groupby(pair_index, sort=False).sum()
    pair_nodes = np.array(pair_scores.index.tolist())
    twice = pd.concat([pair_scores.reset_index(drop=True)] * 2, ignore_index=True)
    nodes = np.concatenate([pair_nodes[:, 0], pair_nodes[:, 1]])
    node_scores = twice.groupby(nodes, sort=False).sum().to_numpy()
    ps = pair_scores.to_numpy()
    meat = node_scores.T @ node_scores - ps.T @ ps
    covariance = correction * np.asarray(bread) @ meat @ np.asarray(bread)
    return (covariance + covariance.T) / 2


def linear_contrast(params, covariance, weights, *, identified=True, supported=True):
    """Full covariance: var(a'b) = a' V a, including all cross terms."""
    params, weights = np.asarray(params, float), np.asarray(weights, float)
    estimate = float(weights @ params)
    variance = float(weights @ np.asarray(covariance) @ weights)
    reason = "available"
    if not identified:
        reason = "unavailable_rank_deficient_design"
    elif not supported:
        reason = "unavailable_insufficient_subgroup_support"
    elif not np.isfinite(variance) or variance <= 0:
        reason = "unavailable_nonpositive_variance"
    se = float(np.sqrt(variance)) if reason == "available" else np.nan
    return {"coefficient": estimate, "variance": variance, "standard_error": se,
            "ci95_lower": estimate - norm.ppf(.975) * se,
            "ci95_upper": estimate + norm.ppf(.975) * se,
            "difference_pp": 100 * estimate, "standard_error_pp": 100 * se,
            "ci95_lower_pp": 100 * (estimate - norm.ppf(.975) * se),
            "ci95_upper_pp": 100 * (estimate + norm.ppf(.975) * se),
            "inference_status": reason}


def _within_fit(d):
    x = pd.DataFrame(index=d.index)
    x["opponent_left"] = d["opponent_hand"].eq("L").astype(float)
    x["opponent_left_x_player_left"] = x["opponent_left"] * d["player_hand"].eq("L").astype(float)
    x["log_rank_advantage"] = d["log_rank_advantage"]
    x["age"] = d["player_age"]
    x["recent_win_rate"] = d["recent_win_rate"]
    x["opponent_recent_win_rate"] = d["opponent_recent_win_rate"]
    x["log_prior_matches"] = np.log1p(d["prior_matches"])
    x = pd.concat([x, pd.get_dummies(d[["surface", "season"]].astype(str), drop_first=True, dtype=float)], axis=1)
    xw = x - x.groupby(d["player_id"]).transform("mean")
    yw = d["won"] - d.groupby("player_id")["won"].transform("mean")
    # Keep the scientific contrasts even when unidentified, so rank checks can
    # explicitly withhold inference rather than silently change their meaning.
    keep = xw.std().gt(1e-10) | xw.columns.isin(HAND_TERMS)
    xw = xw.loc[:, keep].astype(float)
    return sm.OLS(yw, xw).fit(), xw


def _adequate(d, minimum):
    counts = d.groupby(["player_id", "opponent_hand"]).size().unstack(fill_value=0).reindex(columns=["L", "R"], fill_value=0)
    return d.loc[d["player_id"].isin(counts.index[(counts >= minimum).all(axis=1)])].copy()


def _support(d, sample):
    rows = []
    for (own, other), group in d.groupby(["player_hand", "opponent_hand"]):
        counts = group.groupby("player_id").size().sort_values(ascending=False)
        rows.append({"sample": sample, "player_hand": own, "opponent_hand": other,
                     "player_match_rows": len(group), "unique_matches": group.match_id.nunique(),
                     "players": group.player_id.nunique(), "opponents": group.opponent_id.nunique(),
                     "opponent_pairs": group.pair_id.nunique(), "tournaments": group.tourney_id.nunique(),
                     "largest_player_share": counts.iloc[0] / len(group),
                     "top5_player_share": counts.head(5).sum() / len(group)})
    return rows


def _contrast_rows(fit, covariance, d, method, identified):
    rows = []
    for hand in ["R", "L"]:
        group = d.loc[d.player_hand.eq(hand)]
        weights = np.zeros(len(fit.params))
        weights[fit.params.index.get_loc(HAND_TERMS[0])] = 1
        if hand == "L":
            weights[fit.params.index.get_loc(HAND_TERMS[1])] = 1
        # This is an explicit minimum, not a guarantee of accurate asymptotics.
        enough = group.player_id.nunique() >= 20 and group.opponent_id.nunique() >= 20
        rows.append({"method": method, "player_hand": hand,
                     "contrast": "opponent_L_minus_R", "players": group.player_id.nunique(),
                     "player_match_rows": len(group), "unique_matches": group.match_id.nunique(),
                     **linear_contrast(fit.params, covariance, weights, identified=identified, supported=enough)})
    return rows


def _descriptives(d, cfg, output):
    summary = d.groupby(["player_id", "opponent_hand"]).agg(
        matches=("match_id", "size"), wins=("won", "sum"), win_rate=("won", "mean"),
        service_matches=("valid_service_stats", "sum"),
        service_points_won=("service_points_won", lambda x: x.sum(min_count=1)),
        service_points_observed=("service_points_observed", lambda x: x.sum(min_count=1)))
    summary["service_win_rate"] = summary.service_points_won / summary.service_points_observed
    summary.to_csv(output / "q3_by_player_and_hand.csv")
    stats = ["matches", "win_rate", "service_matches", "service_points_observed", "service_win_rate"]
    wide = summary[stats].unstack("opponent_hand")
    wide.columns = [f"{stat}_{hand}" for stat, hand in wide.columns]
    for stat in stats:
        for hand in ["L", "R"]:
            if f"{stat}_{hand}" not in wide:
                wide[f"{stat}_{hand}"] = np.nan
    metadata = d.drop_duplicates("player_id").set_index("player_id")
    for column in ["player_name", "player_hand"]:
        wide[column] = metadata[column]
    wide["win_rate_difference_L_minus_R"] = wide.win_rate_L - wide.win_rate_R
    valid_service = wide.service_matches_L.ge(cfg.min_hand_matches) & wide.service_matches_R.ge(cfg.min_hand_matches)
    wide["service_comparison_eligible"] = valid_service
    wide["service_rate_difference_L_minus_R"] = (wide.service_win_rate_L - wide.service_win_rate_R).where(valid_service)
    paired = wide.loc[wide.matches_L.ge(cfg.min_hand_matches) & wide.matches_R.ge(cfg.min_hand_matches)].copy()
    paired.to_csv(output / "q3_paired_player_comparison.csv")
    rows = []
    for hand, group in paired.groupby("player_hand"):
        rows.append({"player_hand": hand, "players": len(group),
                     "matches_vs_L": int(group.matches_L.sum()), "matches_vs_R": int(group.matches_R.sum()),
                     "mean_player_win_difference_pp": 100 * group.win_rate_difference_L_minus_R.mean(),
                     "median_player_win_difference_pp": 100 * group.win_rate_difference_L_minus_R.median(),
                     "service_eligible_players": int(group.service_comparison_eligible.sum()),
                     "mean_player_service_difference_pp": 100 * group.service_rate_difference_L_minus_R.mean(),
                     "service_points_vs_L": group.loc[group.service_comparison_eligible, "service_points_observed_L"].sum(),
                     "service_points_vs_R": group.loc[group.service_comparison_eligible, "service_points_observed_R"].sum(),
                     "interpretation": "Unadjusted equal-player means; service differences require minimum valid service matches against each hand."})
    pd.DataFrame(rows, columns=["player_hand", "players", "matches_vs_L", "matches_vs_R", "mean_player_win_difference_pp", "median_player_win_difference_pp", "service_eligible_players", "mean_player_service_difference_pp", "service_points_vs_L", "service_points_vs_R", "interpretation"]).to_csv(output / "q3_descriptive_contrasts.csv", index=False)
    return paired


def analyze_handedness(players, cfg, output: Path):
    d = players.loc[players.eligible & players.player_hand.isin(["L", "R"]) & players.opponent_hand.isin(["L", "R"])].copy()
    notes = []
    info = {"status": "Q3 descriptive tables saved; adjusted model not fitted.", "analysis_status": "descriptive_only",
            "player_match_rows": len(d), "unique_matches": int(d.match_id.nunique()), "warnings": notes}
    paired = _descriptives(d, cfg, output)
    info["players_meeting_raw_comparison_minimum"] = len(paired)
    support = _support(d, "known_hand_descriptive")
    # Fixed own-hand contrasts are undefined for inconsistent identity metadata.
    changing = d.groupby("player_id").player_hand.nunique()
    changing = changing.index[changing.gt(1)]
    if len(changing):
        notes.append(f"Excluded {len(changing)} players with inconsistent focal handedness from adjustment.")
    complete = d.dropna(subset=["log_rank_advantage", "player_age", "recent_win_rate", "opponent_recent_win_rate", "prior_matches"])
    d = _adequate(complete.loc[~complete.player_id.isin(changing)], cfg.min_hand_matches).reset_index(drop=True)
    support.extend(_support(d, "adjusted"))
    pd.DataFrame(support, columns=["sample", "player_hand", "opponent_hand", "player_match_rows", "unique_matches", "players", "opponents", "opponent_pairs", "tournaments", "largest_player_share", "top5_player_share"]).to_csv(output / "q3_subgroup_support.csv", index=False)
    info.update(adjusted_player_match_rows=len(d), adjusted_unique_matches=int(d.match_id.nunique()),
                adjusted_players=int(d.player_id.nunique()))
    if len(d) < 200 or d.player_id.nunique() < 20:
        info["status"] = "Q3 descriptive tables saved; insufficient players with both opponent hands and complete covariates for adjustment."
        notes.append("Adjusted inference unavailable: fewer than 200 rows or 20 focal players.")
        return info
    fit, xw = _within_fit(d)
    rank = int(np.linalg.matrix_rank(xw))
    nf, n = int(d.player_id.nunique()), len(d)
    effective_parameters = nf + rank
    correction = (n - 1) / (n - effective_parameters)
    identified = rank == xw.shape[1]
    if not identified:
        notes.append("Within-player design is rank deficient; all adjusted contrast inference is unavailable.")
    scores = xw.to_numpy() * fit.resid.to_numpy()[:, None]
    covariance = dyadic_covariance(scores, fit.normalized_cov_params, d.player_id, d.opponent_id, correction)
    old, _, _ = cov_cluster_2groups(fit, pd.factorize(d.player_id)[0], pd.factorize(d.match_id)[0])
    # The old statsmodels correction counts the within slopes but not absorbed
    # player constants. Scale the sensitivity to include those absorbed df.
    old *= (n - xw.shape[1]) / (n - effective_parameters)
    event = cov_cluster(fit, pd.factorize(d.tourney_id)[0]) * (n - xw.shape[1]) / (n - effective_parameters)
    diagnostics = {"within_design_rank": rank, "within_design_columns": xw.shape[1],
                   "within_condition_number": float(np.linalg.cond(xw)), "absorbed_player_intercepts": nf,
                   "effective_parameters": effective_parameters, "residual_degrees_of_freedom": n - effective_parameters,
                   "dyadic_finite_sample_factor": float(correction),
                   "dyadic_nodes": int(pd.unique(pd.concat([d.player_id, d.opponent_id])).size),
                   "dyadic_pairs": int(d.pair_id.nunique()), "tournament_clusters": int(d.tourney_id.nunique()),
                   "primary_negative_variance_terms": int((np.diag(covariance) < 0).sum()),
                   "primary_minimum_covariance_eigenvalue": float(np.linalg.eigvalsh(covariance).min()),
                   "legacy_two_way_negative_variance_terms": int((np.diag(old) < 0).sum()),
                   "legacy_two_way_minimum_covariance_eigenvalue": float(np.linalg.eigvalsh(old).min())}
    info.update(diagnostics)
    if diagnostics["legacy_two_way_negative_variance_terms"]:
        notes.append("Legacy player-by-match covariance has negative coefficient variance(s); affected intervals are unavailable. Primary dyadic covariance clusters through either participant.")
    if diagnostics["primary_minimum_covariance_eigenvalue"] < 0:
        notes.append("Primary dyadic covariance is indefinite; nonpositive contrast variances are unavailable. Positive contrasts remain exploratory.")
    coefficient_rows = []
    for method, cov in [("dyadic_primary", covariance), ("legacy_player_match", old)]:
        for j, term in enumerate(fit.params.index):
            weight = np.eye(len(fit.params))[j]
            coefficient_rows.append({"method": method, "term": term,
                                     **linear_contrast(fit.params, cov, weight, identified=identified)})
    coef = pd.DataFrame(coefficient_rows)
    coef.loc[coef.method.eq("dyadic_primary")].to_csv(output / "q3_adjusted_coefficients.csv", index=False)
    coef.loc[coef.method.ne("dyadic_primary")].to_csv(output / "q3_legacy_coefficients.csv", index=False)
    pd.DataFrame(covariance, index=fit.params.index, columns=fit.params.index).to_csv(output / "q3_adjusted_covariance.csv")
    contrasts = _contrast_rows(fit, covariance, d, "dyadic_primary", identified)
    sensitivity = (_contrast_rows(fit, old, d, "legacy_player_match", identified) +
                   _contrast_rows(fit, event, d, "tournament_only", identified))
    # Fixed SHA-256 orientation is outcome-independent and reproducible across
    # platforms; it removes complementary views, not all shared-player dependence.
    low = d.player_id.lt(d.opponent_id)
    choose_low = d.match_id.map(lambda value: int(hashlib.sha256(str(value).encode()).hexdigest()[:8], 16) % 2 == 0)
    single = _adequate(d.loc[low.eq(choose_low)], cfg.min_hand_matches).copy()
    if len(single) >= 200 and single.player_id.nunique() >= 20:
        sfit, sx = _within_fit(single)
        srank = int(np.linalg.matrix_rank(sx))
        scov = cov_cluster(sfit, pd.factorize(single.player_id)[0])
        scov *= (len(single) - sx.shape[1]) / (len(single) - single.player_id.nunique() - srank)
        sensitivity += _contrast_rows(sfit, scov, single, "single_hash_view_player_cluster", srank == sx.shape[1])
    pd.DataFrame(contrasts).to_csv(output / "q3_adjusted_contrasts.csv", index=False)
    pd.DataFrame(sensitivity).to_csv(output / "q3_inference_sensitivity.csv", index=False)
    # Influence checks select the five most exposed focal players in EACH hand
    # group by exposure count rather than outcomes, then remove their matches
    # in EITHER participant role and reapply the opportunity minimum.
    exposure = d.groupby(["player_hand", "player_id"]).size().rename("rows").reset_index()
    exposure["opponent_rows"] = exposure.player_id.map(d.groupby("opponent_id").size()).fillna(0).astype(int)
    exposure["focal_rows"] = exposure["rows"]
    exposure["total_perspective_involvements"] = exposure.focal_rows + exposure.opponent_rows
    exposure = exposure.sort_values(["player_hand", "rows", "player_id"], ascending=[True, False, True])
    exposure.to_csv(output / "q3_player_exposure.csv", index=False)
    selected = exposure.groupby("player_hand").head(5)
    influence = []
    for row in selected.itertuples():
        reduced = _adequate(d.loc[d.player_id.ne(row.player_id) & d.opponent_id.ne(row.player_id)], cfg.min_hand_matches)
        rfit, rx = _within_fit(reduced)
        rrank = int(np.linalg.matrix_rank(rx))
        for hand, terms in [("R", [HAND_TERMS[0]]), ("L", HAND_TERMS)]:
            influence.append({"excluded_player_id": int(row.player_id), "excluded_player_hand": row.player_hand,
                              "excluded_focal_rows": int(row.rows), "player_hand": hand,
                              "remaining_players": int(reduced.player_id.nunique()),
                              "remaining_unique_matches": int(reduced.match_id.nunique()),
                              "remaining_player_match_rows": len(reduced),
                              "sample": "drop_player_as_either_participant_reapply_opportunity_minimum",
                              "difference_pp": float(100 * rfit.params[terms].sum()),
                              "identified": rrank == rx.shape[1],
                              "interpretation": "Point-estimate sensitivity; removes all selected-player involvement and reapplies opportunity minima; no inferential interval."})
    pd.DataFrame(influence).to_csv(output / "q3_player_influence.csv", index=False)
    unavailable = [r for r in contrasts if r["inference_status"] != "available"]
    if unavailable:
        notes.append("At least one focal-hand contrast has unavailable inference; retain descriptive results and do not infer a subgroup effect.")
    notes.append("Dyadic intervals assume no residual dependence between disjoint player pairs; tournament-wide shocks and indirect network dependence may remain. Tournament-only sensitivity does not address serial player dependence.")
    notes.append("Left-handed subgroup support is smaller; asymptotic intervals and the exposure-based deletion checks do not establish uniform effects across players.")
    info.update(status="Q3 within-player adjusted model fitted with explicit inference warnings.",
                analysis_status="fitted_with_warnings" if notes else "fitted",
                covariance="Primary shared-player dyadic sandwich, preserving repeat dyads and both physical-match views; no clipping or absolute-value variance repair.",
                ci_note="Exploratory normal 95% intervals; (n-1)/(n-player_intercepts-within_rank) finite-sample scaling includes absorbed fixed effects.",
                negative_variance_terms=diagnostics["primary_negative_variance_terms"],
                contrast_inference={r["player_hand"]: r["inference_status"] for r in contrasts},
                method_reference="https://arxiv.org/abs/1312.3398",
                interpretation="Adjusted opponent L-minus-R probability contrasts are reported separately by focal hand in percentage points. L uses the coefficient sum and full covariance.")
    return info
