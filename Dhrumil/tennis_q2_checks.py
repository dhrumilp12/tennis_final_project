"""Paired Q2 checks of saved held-out predictions; no model refitting.

The additional uncertainty method is a shared-participant dyadic sandwich for
the mean paired score difference. Its centered scores have bread 1/n, no finite
sample multiplier (correction=1), and normal 95% intervals. At least 20 distinct
participants and 20 distinct pairs are required; this heuristic does not ensure
accurate asymptotics. Dependence between disjoint pairs can still remain.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from tennis_analyses import paired_cluster_interval
from tennis_handedness import dyadic_covariance
from tennis_project import Config


MODELS = ["baseline", "plus_meeting_count", "plus_h2h_results"]
COMPARISONS = [("baseline", "plus_meeting_count"), ("baseline", "plus_h2h_results"),
               ("plus_meeting_count", "plus_h2h_results")]
METRICS = ["brier", "log_loss", "accuracy"]
LOG_LOSS_CLIP = 1e-15  # Identical to the historical paired-score helper.


def validate_predictions(predictions, test_start, end_year):
    """Reject invalid saved data rather than dropping observations or repairing it."""
    needed = {"match_id", "pair_id", "tourney_date", "player_id", "opponent_id",
              "won", "prior_h2h_meetings", *(f"p_{model}" for model in MODELS)}
    missing = needed.difference(predictions.columns)
    if missing:
        raise ValueError(f"Missing saved prediction columns: {sorted(missing)}")
    d = predictions.copy()
    if d.empty:
        raise ValueError("No saved held-out predictions.")
    if d.match_id.isna().any() or d.match_id.astype(str).str.strip().eq("").any():
        raise ValueError("Missing physical match IDs.")
    if d.match_id.duplicated().any():
        raise ValueError("Duplicate physical match IDs in saved predictions.")
    for column in ["player_id", "opponent_id", "prior_h2h_meetings"]:
        values = pd.to_numeric(d[column], errors="coerce").to_numpy(float)
        minimum = 0 if column == "prior_h2h_meetings" else 1
        if not (np.isfinite(values).all() and (values >= minimum).all()
                and (values == np.floor(values)).all()):
            raise ValueError(f"Invalid integer values in {column}.")
        d[column] = values.astype("int64")
    if not d.player_id.lt(d.opponent_id).all():
        raise ValueError("Distinct participants and smaller-numeric-ID Player A orientation are required.")
    canonical = d.player_id.astype(str) + ":" + d.opponent_id.astype(str)
    if not d.pair_id.eq(canonical).all():
        raise ValueError("Pair IDs must match the canonical unordered participant pair.")
    y = pd.to_numeric(d.won, errors="coerce")
    if not y.isin([0, 1]).all():
        raise ValueError("Saved outcome labels must be binary and nonmissing.")
    d["won"] = y.astype(int)
    for model in MODELS:
        column = f"p_{model}"
        p = pd.to_numeric(d[column], errors="coerce")
        if not (np.isfinite(p).all() and p.between(0, 1).all()):
            raise ValueError(f"Saved probabilities must be finite and in [0,1]: {column}.")
        d[column] = p.astype(float)
    d["tourney_date"] = pd.to_datetime(d.tourney_date, errors="coerce")
    start, stop = pd.Timestamp(test_start, 1, 1), pd.Timestamp(end_year + 1, 1, 1)
    if not (d.tourney_date.notna() & d.tourney_date.ge(start) & d.tourney_date.lt(stop)).all():
        raise ValueError("Saved prediction dates fall outside the configured test period.")
    return d


def verify_saved_features(d, source, summary):
    """Check the exact test population and pre-match history against saved features."""
    fields = ["match_id", "pair_id", "tourney_date", "player_id", "opponent_id", "won",
              "prior_h2h_meetings", "eligible", "is_player_a"]
    features = pd.read_csv(Path(source) / "player_match_features.csv.gz", usecols=fields)
    features["tourney_date"] = pd.to_datetime(features.tourney_date)
    start = pd.Timestamp(summary["configuration"]["test_start"], 1, 1)
    expected = features.loc[features.eligible & features.is_player_a & features.tourney_date.ge(start)]
    if expected.match_id.duplicated().any():
        raise ValueError("Saved features contain duplicate Player-A test observations.")
    columns = fields[:-2]
    try:
        pd.testing.assert_frame_equal(
            d[columns].sort_values("match_id").reset_index(drop=True),
            expected[columns].sort_values("match_id").reset_index(drop=True),
            check_dtype=False, check_exact=True)
    except AssertionError as error:
        raise ValueError("Saved prediction IDs, participant roles, labels, dates or prior history differ from saved features.") from error
    if len(d) != summary["q2"]["test_matches"]:
        raise ValueError("Saved prediction count disagrees with the historical Q2 summary.")


def subsets(d):
    """Partition by earlier meetings only; later repeat status never enters."""
    return {"ALL": d, "REPEAT": d.loc[d.prior_h2h_meetings.ge(1)],
            "FIRST": d.loc[d.prior_h2h_meetings.eq(0)]}


def metric_scores(y, probabilities, metric):
    y, p = np.asarray(y, float), np.asarray(probabilities, float)
    if metric == "brier":
        return np.square(y - p)
    if metric == "log_loss":
        p = np.clip(p, LOG_LOSS_CLIP, 1 - LOG_LOSS_CLIP)
        return -y * np.log(p) - (1 - y) * np.log1p(-p)
    if metric == "accuracy":
        return ((p >= .5) == y).astype(float)
    raise ValueError(f"Unsupported metric: {metric}")


def paired_difference(d, first, second, metric):
    """Positive always favors the second model, for losses AND accuracy."""
    a = metric_scores(d.won, d[f"p_{first}"], metric)
    b = metric_scores(d.won, d[f"p_{second}"], metric)
    return b - a if metric == "accuracy" else a - b


def dyadic_mean_interval(difference, player_ids, opponent_ids, minimum=20):
    """Mean paired improvement, preserving repeated pairs and shared participants."""
    difference = np.asarray(difference, dtype=float)
    a, b = np.asarray(player_ids), np.asarray(opponent_ids)
    if len(a) != len(difference) or len(b) != len(difference):
        raise ValueError("Scores and participant IDs must have equal lengths.")
    n = len(difference)
    participants = len(np.unique(np.concatenate([a, b])))
    pairs = len(set(zip(np.minimum(a, b), np.maximum(a, b))))
    finite = bool(np.isfinite(difference).all())
    estimate = float(difference.mean()) if n and finite else np.nan
    variance = np.nan
    if n and finite:
        scores = (difference - estimate)[:, None]
        variance = float(dyadic_covariance(scores, np.array([[1 / n]]), a, b, correction=1.0)[0, 0])
    if participants < minimum or pairs < minimum:
        status = "unavailable_insufficient_dyadic_support"
    elif not np.isfinite(variance) or variance <= 0:
        status = "unavailable_nonpositive_or_nonfinite_variance"
    else:
        status = "available"
    se = float(np.sqrt(variance)) if status == "available" else np.nan
    return {"mean_improvement": estimate, "variance": variance, "standard_error": se,
            "ci95_lower": float(estimate - norm.ppf(.975) * se),
            "ci95_upper": float(estimate + norm.ppf(.975) * se),
            "inference_status": status, "n_matches": n, "players": participants, "pairs": pairs}


def compare_predictions(d, cfg):
    comparisons, scores, population = [], [], []
    for subset, part in subsets(d).items():
        n = len(part)
        participants = int(pd.unique(pd.concat([part.player_id, part.opponent_id])).size)
        pair_count = int(part.pair_id.nunique())
        sizes = {"n_matches": n, "players": participants, "pairs": pair_count}
        population.append({"subset": subset, **sizes})
        for model in MODELS:
            scores.append({"subset": subset, "model": model, **sizes,
                           **{metric: float(metric_scores(part.won, part[f"p_{model}"], metric).mean())
                              if n else np.nan for metric in METRICS}})
        for first, second in COMPARISONS:
            for metric in METRICS:
                common = {"subset": subset, "metric": metric, "first_model": first,
                          "second_model": second, "metric_role": "primary" if metric == "brier" else "secondary"}
                difference = paired_difference(part, first, second, metric)
                dyadic = dyadic_mean_interval(difference, part.player_id, part.opponent_id)
                comparisons.append({**common, "method": "shared_player_dyadic", **dyadic,
                                    "resamples": 0, "random_seed": cfg.random_seed})
                if n:
                    original = paired_cluster_interval(part, f"p_{first}", f"p_{second}", cfg, metric)
                else:
                    original = {"mean_improvement": np.nan, "ci95_lower": np.nan,
                                "ci95_upper": np.nan, "status": "No observations"}
                comparisons.append({**common, "method": "opponent_pair_bootstrap", **sizes,
                                    **{k: original[k] for k in ["mean_improvement", "ci95_lower", "ci95_upper"]},
                                    "standard_error": np.nan, "variance": np.nan,
                                    "inference_status": "available" if original["status"] == "Computed" else "unavailable_insufficient_pair_support",
                                    "resamples": cfg.bootstrap_samples, "random_seed": cfg.random_seed})
    return pd.DataFrame(comparisons), pd.DataFrame(scores), population


def verify_historical_metrics(comparisons, scores, source):
    """Recomputed ALL pair-bootstrap results must reproduce all nine saved rows."""
    saved = pd.read_csv(Path(source) / "q2_paired_improvements.csv")
    actual = comparisons.loc[comparisons.subset.eq("ALL") & comparisons.method.eq("opponent_pair_bootstrap")]
    keys = ["first_model", "second_model", "metric"]
    if saved.duplicated(keys).any() or len(saved) != len(actual):
        raise ValueError("Historical paired-comparison rows are missing or duplicated.")
    columns = keys + ["mean_improvement", "ci95_lower", "ci95_upper", "test_matches", "pair_clusters", "resamples"]
    actual = actual.rename(columns={"n_matches": "test_matches", "pairs": "pair_clusters"})
    pd.testing.assert_frame_equal(actual[columns].sort_values(keys).reset_index(drop=True),
                                  saved[columns].sort_values(keys).reset_index(drop=True),
                                  check_dtype=False, atol=1e-12, rtol=1e-10)
    saved_scores = pd.read_csv(Path(source) / "q2_model_metrics.csv")
    saved_scores = saved_scores.loc[saved_scores.meeting_group.eq("all")]
    columns = ["model", "test_matches", "brier_score", "log_loss", "accuracy"]
    actual_scores = scores.loc[scores.subset.eq("ALL")].rename(
        columns={"n_matches": "test_matches", "brier": "brier_score"})
    pd.testing.assert_frame_equal(actual_scores[columns].sort_values("model").reset_index(drop=True),
                                  saved_scores[columns].sort_values("model").reset_index(drop=True),
                                  check_dtype=False, atol=1e-12, rtol=1e-10)


def run_q2(source: Path, output: Path, summary: dict) -> dict:
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError("Q2 validation output must be separate from the historical source run.")
    cfg = Config(**summary["configuration"])
    d = validate_predictions(pd.read_csv(source / "q2_test_predictions.csv.gz"), cfg.test_start, cfg.end_year)
    verify_saved_features(d, source, summary)
    comparisons, scores, population = compare_predictions(d, cfg)
    subset_sizes = {row["subset"]: row["n_matches"] for row in population}
    if subset_sizes["REPEAT"] + subset_sizes["FIRST"] != subset_sizes["ALL"]:
        raise AssertionError("Prior-meeting subsets do not partition the saved test matches.")
    verify_historical_metrics(comparisons, scores, source)
    output.mkdir(parents=True, exist_ok=True)
    comparisons.to_csv(output / "q2_comparisons.csv", index=False)
    scores.to_csv(output / "q2_scores.csv", index=False)
    d[["match_id", "player_id", "opponent_id", "pair_id", "prior_h2h_meetings"]].to_csv(
        output / "q2_prediction_ids.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    return {
        "checks": {"saved_prediction_schema_valid": True, "unique_physical_matches": True,
                   "probabilities_finite_in_unit_interval": True, "binary_outcomes": True,
                   "valid_distinct_participant_ids_and_fixed_player_a_orientation": True,
                   "canonical_pair_ids": True, "nonnegative_integer_prior_meetings": True,
                   "dates_within_test_period": True, "exact_test_ids_history_and_outcomes_match_saved_features": True,
                   "all_nine_historical_pair_bootstrap_comparisons_reproduced": True,
                   "historical_all_model_scores_reproduced": True,
                   "repeat_and_first_subsets_partition_all_by_prior_meetings_only": True,
                   "models_refitted": False},
        "counts": population,
        "settings": {"bootstrap_resamples": cfg.bootstrap_samples, "random_seed": cfg.random_seed,
                     "subsets": {"ALL": "All saved held-out physical matches", "REPEAT": "prior_h2h_meetings >= 1",
                                 "FIRST": "prior_h2h_meetings == 0"},
                     "dyadic_finite_sample_correction": 1.0, "dyadic_critical_value": float(norm.ppf(.975)),
                     "dyadic_minimum_participants": 20, "dyadic_minimum_pairs": 20,
                     "support_note": "Explicit heuristics, not guarantees of accurate asymptotic inference.",
                     "log_loss_probability_clip": LOG_LOSS_CLIP,
                     "primary_metric": "brier", "secondary_metrics": ["log_loss", "accuracy"],
                     "direction": "Positive improvement favors the second model.",
                     "dependence_note": "Dyadic scores account for repeated pairs and pairs sharing either participant. Residual dependence between disjoint pairs, including tournament shocks, is not addressed.",
                     "original_meeting_groups": "Finer saved groups remain in outputs_final/q2_model_metrics.csv; no new model fits or subgroup search."},
    }
