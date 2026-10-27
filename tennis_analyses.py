"""Analysis functions; all results are observational, not causal conclusions.

Q1: descriptive recovery tables + exploratory adjusted rate regression.
Q2: pre-specified chronological predictive comparison with paired uncertainty.
Q3: same-player comparisons + within-player adjusted linear probability model.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import logging
import warnings

import numpy as np
import pandas as pd
from scipy.stats import t as student_t
import statsmodels.formula.api as smf
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

if TYPE_CHECKING:
    from tennis_project import Config

LOG = logging.getLogger("tennis")


def coefficient_table(result) -> pd.DataFrame:
    ci = result.conf_int()
    return pd.DataFrame({"term": result.params.index, "coefficient": result.params.to_numpy(),
                         "standard_error": result.bse.to_numpy(), "ci95_lower": ci.iloc[:, 0].to_numpy(),
                         "ci95_upper": ci.iloc[:, 1].to_numpy()})


def clustered_mean(values: pd.Series, player_ids: pd.Series) -> dict:
    """Mean with a focal-player sandwich interval; missing outcomes stay missing."""
    keep = values.notna()
    y, ids = values.loc[keep].astype(float), player_ids.loc[keep]
    n, g = len(y), ids.nunique()
    result = {"mean": float(y.mean()) if n else np.nan, "n": n,
              "players": int(g), "ci95_lower": np.nan, "ci95_upper": np.nan}
    if n and g >= 20:
        sums = (y - y.mean()).groupby(ids).sum()
        se = np.sqrt(g / (g - 1) * np.square(sums).sum() / n ** 2)
        critical = student_t.ppf(.975, g - 1)
        result.update(ci95_lower=float(y.mean() - critical * se),
                      ci95_upper=float(y.mean() + critical * se))
    return result


def select_nonoverlapping(events: pd.DataFrame, k: int = 3) -> pd.Series:
    """Greedily keep earliest complete windows, using index AND follow-up IDs.

    Selection uses dates/checked rounds and availability, never the win outcomes.
    This changes the target sample and is a sensitivity check, not a cure for
    shared-opponent dependence. Each player's windows are selected separately.
    """
    selected = pd.Series(False, index=events.index)
    complete = events["followup_complete"] if k == 3 else events["next1_usable"]
    candidates = events.loc[complete].sort_values(
        ["player_id", "tourney_date", "round_order", "tourney_id", "match_id"])
    for _, player in candidates.groupby("player_id", sort=False):
        occupied = set()
        for idx, row in player.iterrows():
            ids = {row["match_id"], *(row[f"next{i}_match_id"] for i in range(1, k + 1))}
            if not (ids & occupied):
                selected.loc[idx] = True
                occupied.update(ids)
    return selected


def recovery_contrast(fit, weights: dict, *, label: str, outcome: str,
                      sample: str, events: int, players: int, subgroup: str = "all") -> dict:
    """Linear contrast using c' V c, including every covariance cross-term."""
    vector = np.array([weights.get(term, 0.0) for term in fit.params.index])
    estimate = float(vector @ fit.params)
    variance = float(vector @ fit.cov_params() @ vector)
    se = float(np.sqrt(variance)) if variance >= 0 and players >= 20 else np.nan
    critical = student_t.ppf(.975, players - 1) if players >= 20 else np.nan
    return {"outcome": outcome, "sample": sample, "contrast": label,
            "subgroup": subgroup, "events": events, "players": players, "subgroup_players": players,
            "estimate_pp": 100 * estimate, "standard_error_pp": 100 * se,
            "ci95_lower_pp": 100 * (estimate - critical * se),
            "ci95_upper_pp": 100 * (estimate + critical * se),
            "inference_status": "available" if np.isfinite(se) else "unavailable"}


def analyze_recovery(events: pd.DataFrame, cfg: Config, output: Path) -> dict:
    # Identical rank eligibility in descriptive and adjusted upset comparisons.
    ranked = events["player_rank"].notna() & events["opponent_rank"].notna()
    common = events.loc[ranked & events["player_rank"].le(cfg.upset_max_rank)].copy()
    info = {"index_losses": len(events), "index_players": int(events["player_id"].nunique()),
            "ranking_upsets": int(events["ranking_upset"].sum()),
            "complete_three_match_followups": int(events["followup_complete"].sum()),
            "rank_eligible_losses": len(common), "rank_eligible_players": int(common["player_id"].nunique()),
            "status": "Descriptive outputs saved; adjusted model not fitted.",
            "warnings": ["Follow-up context adjustment estimates a conditional association; focal-player clustering does not cover all shared-opponent dependence."],
            "descriptive_population": f"Both ranks known and focal rank <= {cfg.upset_max_rank}.",
            "nonoverlap_rule": "Greedily retain earliest available complete windows in sequence per focal player; neither index nor follow-up match can be reused. Selection precedes covariate exclusion and does not use outcomes.",
            "uncertainty": "Focal-player cluster sandwich with t critical value (players minus one degrees of freedom); shared-opponent/network dependence remains."}
    # Mutually exclusive index eligibility counts, distinct from outcome censoring.
    flow = [{"stage": "all_eligible_study_losses", "events": len(events)},
            {"stage": "excluded_unknown_rank", "events": int((~ranked).sum())},
            {"stage": "excluded_focal_rank_above_cutoff", "events": int((ranked & events["player_rank"].gt(cfg.upset_max_rank)).sum())},
            {"stage": "common_rank_eligible_population", "events": len(common)}]
    pd.DataFrame(flow).to_csv(output / "q1_population_flow.csv", index=False)
    statuses = common.groupby(["loss_type", "followup_status"], observed=True).agg(
        index_losses=("match_id", "size"), players=("player_id", "nunique")).reset_index()
    statuses.to_csv(output / "q1_followup_status.csv", index=False)
    for group, filename in [(None, "q1_summary_overall.csv"), ("age_group", "q1_summary_age.csv"),
                            ("experience_group", "q1_summary_experience.csv")]:
        records = []
        keys = ["loss_type"] + ([group] if group else [])
        for key, part in common.groupby(keys, observed=True, dropna=False):
            key = key if isinstance(key, tuple) else (key,)
            record = dict(zip(keys, key))
            record.update(index_losses=len(part), unique_players=int(part["player_id"].nunique()),
                          usable_next_matches=int(part["next1_usable"].sum()),
                          complete_three_match_windows=int(part["followup_complete"].sum()),
                          incomplete_or_unusable_windows=int((~part["followup_complete"]).sum()),
                          mean_age=part["player_age"].mean(), median_age=part["player_age"].median(),
                          mean_prior_matches=part["prior_matches"].mean(), median_prior_matches=part["prior_matches"].median())
            for field, prefix in [("next1_win", "next_match"), ("next3_win_rate", "next_three")]:
                result = clustered_mean(part[field], part["player_id"])
                record[f"{prefix}_win_rate"] = result["mean"]
                record[f"{prefix}_ci95_lower"] = result["ci95_lower"]
                record[f"{prefix}_ci95_upper"] = result["ci95_upper"]
                record[f"{prefix}_players"] = result["players"]
            records.append(record)
        columns = keys + ["index_losses", "unique_players", "usable_next_matches", "complete_three_match_windows",
                          "incomplete_or_unusable_windows", "mean_age", "median_age", "mean_prior_matches", "median_prior_matches",
                          "next_match_win_rate", "next_match_ci95_lower", "next_match_ci95_upper", "next_match_players",
                          "next_three_win_rate", "next_three_ci95_lower", "next_three_ci95_upper", "next_three_players"]
        pd.DataFrame(records, columns=columns).to_csv(output / filename, index=False)
    # Always retain all three predeclared gaps; no choosing based on findings.
    sensitivity = []
    for gap in sorted({20, 30, cfg.upset_rank_gap, 50}):
        gap_events = common.copy()
        gap_events["gap_loss_type"] = np.where(gap_events["rank_gap"].ge(gap), "ranking_upset", "other_ranked_loss")
        for (kind, age), part in gap_events.groupby(["gap_loss_type", "age_group"], observed=True):
            sensitivity.append({"rank_gap_threshold": gap, "loss_type": kind, "age_group": str(age),
                                "index_losses": len(part), "players": int(part["player_id"].nunique()),
                                "complete_windows": int(part["followup_complete"].sum()),
                                "next_match_win_rate": part["next1_win"].mean(),
                                "next_three_win_rate": part["next3_win_rate"].mean()})
    pd.DataFrame(sensitivity, columns=["rank_gap_threshold", "loss_type", "age_group", "index_losses", "players",
                                      "complete_windows", "next_match_win_rate", "next_three_win_rate"]).to_csv(output / "q1_threshold_sensitivity.csv", index=False)
    contrasts, models, window_records, coefficients = [], [], [], []
    for outcome, k in [("next3_win_rate", 3), ("next1_win", 1)]:
        nonoverlap = select_nonoverlapping(common, k)
        for sample in ["all_windows", "nonoverlapping"]:
            e = common.loc[nonoverlap if sample == "nonoverlapping" else common[outcome].notna()].copy()
            if k == 1:
                e["context_rank_advantage"] = e["next1_log_rank_advantage"]
                context = "context_rank_advantage + C(next1_surface) + C(next1_best_of)"
            else:
                e["context_rank_advantage"] = e["followup_mean_log_rank_advantage"]
                varying = [f"followup_{s}_share" for s in ["clay", "grass", "carpet", "unknown", "best_of_5"]
                           if e[f"followup_{s}_share"].nunique() > 1]
                context = "context_rank_advantage" + (" + " + " + ".join(varying) if varying else "")
            before = len(e)
            e = e.dropna(subset=[outcome, "player_age", "prior_matches", "recent_win_rate", "player_rank", "context_rank_advantage"])
            g = int(e["player_id"].nunique())
            model = {"outcome": outcome, "sample": sample, "available_windows": before,
                     "excluded_missing_covariates": before - len(e), "model_events": len(e), "model_players": g,
                     "status": "insufficient", "design_columns": None, "design_rank": None}
            if sample == "all_windows" and k == 3:
                info["adjusted_model_eligible_events"] = len(e)
            if len(e) < 100 or g < 20 or e["ranking_upset"].nunique() < 2:
                models.append(model)
                continue
            e["ranking_upset"] = e["ranking_upset"].astype(int)
            e["age_centered"] = e["player_age"] - 25
            e["log_experience"] = np.log1p(e["prior_matches"])
            e["log_player_rank"] = np.log(e["player_rank"])
            formula = (f"{outcome} ~ ranking_upset * (age_centered + log_experience) + "
                       f"recent_win_rate + log_player_rank + {context} + C(surface) + C(season)")
            try:
                fit = smf.ols(formula, data=e).fit(cov_type="cluster", cov_kwds={"groups": e["player_id"]}, use_t=True)
                model.update(status="fitted", design_columns=fit.model.exog.shape[1],
                             design_rank=int(np.linalg.matrix_rank(fit.model.exog)), formula=formula)
                if model["design_rank"] < model["design_columns"]:
                    model["status"] = "rank_deficient_inference_unavailable"
                    info["warnings"].append(f"{outcome}/{sample}: rank-deficient design; adjusted inference withheld.")
                    models.append(model)
                    continue
                table = coefficient_table(fit)
                if sample == "all_windows":
                    filename = "q1_adjusted_coefficients.csv" if k == 3 else "q1_next_match_adjusted_coefficients.csv"
                    table.to_csv(output / filename, index=False)
                for _, r in table.iterrows():
                    coefficients.append({"outcome": outcome, "sample": sample, **r.to_dict()})
                for idx in e.index:
                    window_records.append({"outcome": outcome, "sample": sample, "player_id": e.at[idx, "player_id"],
                                           "match_id": e.at[idx, "match_id"], **{f"next{i}_match_id": e.at[idx, f"next{i}_match_id"] for i in range(1, k + 1)}})
                groupings = [("all", e)]
                for field in ["age_group", "experience_group"]:
                    groupings += [(f"{field}:{label}", part) for label, part in e.groupby(field, observed=True)]
                for label, part in groupings:
                    weights = {"ranking_upset": 1, "ranking_upset:age_centered": part["age_centered"].mean(),
                               "ranking_upset:log_experience": part["log_experience"].mean()}
                    contrasts.append(recovery_contrast(fit, weights, label="average_upset_minus_ordinary",
                        outcome=outcome, sample=sample, events=len(part), players=g, subgroup=label))
                    contrasts[-1]["subgroup_players"] = int(part["player_id"].nunique())
                for term, label in [("ranking_upset:age_centered", "age_interaction_per_year"),
                                    ("ranking_upset:log_experience", "experience_interaction_log_unit")]:
                    contrasts.append(recovery_contrast(fit, {term: 1}, label=label, outcome=outcome,
                                                       sample=sample, events=len(e), players=g))
                if sample == "all_windows" and k == 3:
                    info.update(model_events=len(e), model_players=g, model_formula=formula)
                    (output / "q1_adjusted_model.txt").write_text(
                        "Conditional association with subsequent context, not a causal recovery effect.\n"
                        "Focal-player cluster covariance accounts for repeated and overlapping windows.\n"
                        f"Formula: {formula}\nEvents: {len(e)}; players: {g}\n\n" + table.to_string(index=False))
            except (ValueError, np.linalg.LinAlgError) as exc:
                model["status"] = "failed"
                info["warnings"].append(f"{outcome}/{sample}: {exc}")
            models.append(model)
    pd.DataFrame(models).to_csv(output / "q1_model_samples.csv", index=False)
    pd.DataFrame(contrasts, columns=["outcome", "sample", "contrast", "subgroup", "events", "players", "subgroup_players", "estimate_pp",
                                   "standard_error_pp", "ci95_lower_pp", "ci95_upper_pp", "inference_status"]).to_csv(output / "q1_adjusted_contrasts.csv", index=False)
    pd.DataFrame(coefficients, columns=["outcome", "sample", "term", "coefficient", "standard_error", "ci95_lower", "ci95_upper"]).to_csv(output / "q1_all_adjusted_coefficients.csv", index=False)
    pd.DataFrame(window_records, columns=["outcome", "sample", "player_id", "match_id", "next1_match_id", "next2_match_id", "next3_match_id"]).to_csv(output / "q1_model_windows.csv.gz", index=False)
    info["models"] = models
    info["analysis_status"] = "fitted_with_limitations" if any(m["status"] == "fitted" for m in models) else "insufficient"
    info["status"] = ("Q1 descriptive tables and exploratory adjusted recovery-rate regression fitted; conditional associations with dependence limitations."
                      if info["analysis_status"] == "fitted_with_limitations" else
                      "Descriptive Q1 tables saved; insufficient data or identification for adjusted inference.")
    return info


def prediction_pipeline(numeric: list[str], categories: list[str], seed: int) -> Pipeline:
    preprocess = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)),
                              ("scale", StandardScaler())]), numeric),
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                                  ("encode", OneHotEncoder(handle_unknown="ignore"))]), categories)])
    return Pipeline([("prepare", preprocess), ("model", LogisticRegression(max_iter=2500, C=1.0, random_state=seed))])


def paired_cluster_interval(predictions: pd.DataFrame, first: str, second: str, cfg: Config,
                            metric: str = "brier") -> dict:
    """Paired opponent-pair resampling; positive always favors the second model."""
    temp = predictions.copy()
    y = temp["won"].to_numpy()
    a, b = temp[first].to_numpy(), temp[second].to_numpy()
    if metric == "brier":
        difference = (y - a) ** 2 - (y - b) ** 2
    elif metric == "log_loss":
        a, b = np.clip(a, 1e-15, 1 - 1e-15), np.clip(b, 1e-15, 1 - 1e-15)
        difference = (-y * np.log(a) - (1-y) * np.log1p(-a)) - (-y * np.log(b) - (1-y) * np.log1p(-b))
    elif metric == "accuracy":
        difference = ((b >= .5) == y).astype(float) - ((a >= .5) == y).astype(float)
    else:
        raise ValueError(f"Unsupported metric: {metric}")
    temp["difference"] = difference
    clusters = temp.groupby("pair_id")["difference"].agg(["sum", "count"])
    result = {"metric": metric, "test_matches": len(temp), "mean_improvement": float(np.mean(difference)),
              "ci95_lower": None, "ci95_upper": None, "pair_clusters": len(clusters),
              "resamples": cfg.bootstrap_samples,
              "limitation": "Pair-cluster resampling does not capture every shared-player dependence across different pairs."}
    if metric == "brier":
        result["mean_brier_improvement"] = result["mean_improvement"]
    if len(clusters) < 20:
        result["status"] = "Too few distinct opponent pairs for a cluster interval."
        return result
    rng = np.random.default_rng(cfg.random_seed)
    sums, counts = clusters["sum"].to_numpy(), clusters["count"].to_numpy()
    draws = np.empty(cfg.bootstrap_samples)
    for i in range(cfg.bootstrap_samples):
        selected = rng.integers(0, len(clusters), len(clusters))
        draws[i] = sums[selected].sum() / counts[selected].sum()
    lo, hi = np.quantile(draws, [0.025, 0.975])
    result.update(status="Computed", ci95_lower=float(lo), ci95_upper=float(hi))
    return result


def calibration_table(predictions: pd.DataFrame) -> pd.DataFrame:
    """Fixed probability deciles, decided independently of held-out outcomes."""
    records = []
    for name in ["baseline", "plus_meeting_count", "plus_h2h_results"]:
        d = predictions[["won", f"p_{name}"]].copy()
        d["bin"] = pd.cut(d[f"p_{name}"], np.linspace(0, 1, 11), include_lowest=True, labels=False)
        for number, part in d.groupby("bin"):
            records.append({"model": name, "probability_bin": int(number),
                            "bin_lower": float(number / 10), "bin_upper": float((number + 1) / 10),
                            "matches": len(part), "mean_prediction": float(part[f"p_{name}"].mean()),
                            "observed_win_rate": float(part["won"].mean())})
    return pd.DataFrame(records)


def analyze_head_to_head(players: pd.DataFrame, cfg: Config, output: Path) -> dict:
    d = players.loc[players["eligible"] & players["is_player_a"]].copy()
    if d["match_id"].duplicated().any():
        raise ValueError("Q2 must have one orientation per physical match.")
    d["meeting_group"] = pd.cut(d["prior_h2h_meetings"], [-1, 0, 1, 4, np.inf], labels=["0", "1", "2_to_4", "5_plus"])
    d.groupby("meeting_group", observed=True).agg(matches=("match_id", "size"), player_a_win_rate=("won", "mean")).to_csv(output / "q2_meeting_count_summary.csv")
    # Models are fitted before the held-out years. The additional 21-day gap
    # avoids treating late-year tournament results as known on Jan 1.
    test_date = pd.Timestamp(year=cfg.test_start, month=1, day=1)
    train = d.loc[d["tourney_date"] < test_date - pd.Timedelta(days=21)].copy()
    test = d.loc[d["tourney_date"] >= test_date].copy()
    info = {"status": "Q2 model comparison not fitted.", "training_matches": len(train), "test_matches": len(test),
            "test_start": cfg.test_start, "orientation": "Player A has the smaller numeric player ID, independent of match outcome."}
    if len(train) < 100 or len(test) < 30 or train["won"].nunique() < 2 or test["won"].nunique() < 2:
        info["status"] = "Q2 history features saved; insufficient earlier/later data or outcome variation for a model comparison."
        return info
    base_numeric = ["log_rank_advantage", "age_difference", "log_experience_difference", "recent_form_difference"]
    categories = ["surface", "round", "best_of", "tourney_level", "player_hand", "opponent_hand"]
    # Values outside the training categories are safely ignored by the encoder.
    for c in categories:
        train[c] = train[c].fillna("Unknown").astype(str)
        test[c] = test[c].fillna("Unknown").astype(str)
    variants = {
        "baseline": base_numeric,
        "plus_meeting_count": base_numeric + ["log_prior_h2h_meetings"],
        "plus_h2h_results": base_numeric + ["log_prior_h2h_meetings", "h2h_smoothed_advantage",
                                            "prior_h2h_last_won", "surface_h2h_smoothed_advantage"]}
    pred = test[["match_id", "pair_id", "tourney_date", "player_id", "opponent_id", "won", "prior_h2h_meetings", "meeting_group"]].copy()
    metrics, convergence_notes = [], []
    for name, features in variants.items():
        # Explicit whitelist: no scores, current-match service stats, future
        # wins, winner-oriented fields, or recovery outcomes enter predictors.
        pipe = prediction_pipeline(features, categories, cfg.random_seed)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            pipe.fit(train, train["won"])
        for w in caught:
            if issubclass(w.category, ConvergenceWarning):
                convergence_notes.append(f"{name}: {w.message}")
        probability = pipe.predict_proba(test)[:, 1]
        pred[f"p_{name}"] = probability
        for group_name, mask in [("all", np.ones(len(test), dtype=bool))] + [(str(g), test["meeting_group"].eq(g).to_numpy()) for g in test["meeting_group"].cat.categories]:
            if not mask.any():
                continue
            y, pp = test.loc[mask, "won"].to_numpy(), probability[mask]
            metrics.append({"model": name, "meeting_group": group_name, "test_matches": len(y),
                            "brier_score": float(np.mean((y - pp) ** 2)),
                            "log_loss": float(log_loss(y, pp, labels=[0, 1])),
                            "accuracy": float(accuracy_score(y, pp >= 0.5))})
    pred.to_csv(output / "q2_test_predictions.csv.gz", index=False)
    pd.DataFrame(metrics).to_csv(output / "q2_model_metrics.csv", index=False)
    comparisons = []
    for first, second in [("baseline", "plus_meeting_count"), ("baseline", "plus_h2h_results"),
                          ("plus_meeting_count", "plus_h2h_results")]:
        for metric in ["brier", "log_loss", "accuracy"]:
            comparisons.append({"first_model": first, "second_model": second,
                                **paired_cluster_interval(pred, f"p_{first}", f"p_{second}", cfg, metric)})
    pd.DataFrame(comparisons).to_csv(output / "q2_paired_improvements.csv", index=False)
    calibration_table(pred).to_csv(output / "q2_calibration.csv", index=False)
    info.update(status="Chronological Q2 comparison fitted: baseline, +meeting count, +head-to-head results.",
                analysis_status="fitted_with_limitations",
                warnings=["Paired intervals cluster opponent pairs; shared-player dependence across pairs remains."],
                paired_comparisons=comparisons,
                model_features={name: features + categories for name, features in variants.items()},
                train_last_tournament_date=str(train["tourney_date"].max().date()),
                test_first_tournament_date=str(test["tourney_date"].min().date()),
                train_test_boundary_gap_days=21,
                preprocessing="Median imputation, scaling, and category vocabulary fitted on training data only.",
                meeting_count_interpretation="Meeting count is shared by both players; it is not a directional advantage. Orientation is fixed by player ID.",
                paired_brier_comparison=paired_cluster_interval(pred, "p_baseline", "p_plus_h2h_results", cfg),
                convergence_warnings=convergence_notes,
                primary_metric="Brier score (lower is better). All three models are evaluated on exactly the same held-out matches.",
                test_history_policy="Earlier held-out results can update later held-out pre-match histories; model parameters stay frozen.")
    return info


from tennis_handedness import analyze_handedness


def make_charts(output: Path) -> None:
    """Label adjusted estimates and unadjusted descriptions separately."""
    import os
    import tempfile
    cache = Path(os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "tennis-project-matplotlib")))
    cache.mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    charts = output / "charts"
    charts.mkdir(exist_ok=True)
    age = pd.read_csv(output / "q1_summary_age.csv")
    age = age.loc[age["next_three_win_rate"].notna()]
    labels = {"under_23": "Under 23", "23_to_29": "23–29", "30_plus": "30+"}
    if not age.empty:
        fig, ax = plt.subplots(figsize=(9, 5))
        for offset, kind, color, label in [(-.12, "other_ranked_loss", "#507a9c", "Ordinary loss"),
                                           (.12, "ranking_upset", "#bb663a", "Ranking upset")]:
            part = age.loc[age["loss_type"].eq(kind)].copy()
            xx = np.array([list(labels).index(v) for v in part["age_group"]]) + offset
            yy = 100 * part["next_three_win_rate"]
            err = np.array([yy - 100 * part["next_three_ci95_lower"], 100 * part["next_three_ci95_upper"] - yy])
            ax.errorbar(xx, yy, yerr=err, fmt="o", color=color, capsize=4, label=label)
            for x, y, n in zip(xx, yy, part["complete_three_match_windows"]):
                ax.annotate(f"n={n:,}", (x, y), xytext=(0, 9 if offset > 0 else -17),
                            textcoords="offset points", ha="center", fontsize=8)
        ax.set(xticks=range(3), xticklabels=list(labels.values()), ylabel="Next-three-match win rate (%)",
               xlabel="Focal player's age at index loss", title="Unadjusted follow-up in the same rank-eligible population")
        ax.legend(frameon=False)
        fig.text(.02, .01, "n = complete windows; 95% focal-player clustered intervals when ≥20 players. Windows may overlap.", fontsize=8)
        fig.tight_layout(rect=(0, .04, 1, 1)); fig.savefig(charts / "q1_recovery_by_age.png", dpi=180); plt.close(fig)
    contrast_path = output / "q1_adjusted_contrasts.csv"
    if contrast_path.exists():
        c = pd.read_csv(contrast_path)
        c = c.loc[c["contrast"].eq("average_upset_minus_ordinary") & c["subgroup"].eq("all") & c["ci95_lower_pp"].notna()]
        if not c.empty:
            fig, ax = plt.subplots(figsize=(9, 4))
            yy = np.arange(len(c))
            names = [f"{'Next match' if r.outcome == 'next1_win' else 'Next three'} / {r.sample.replace('_', ' ')} (n={r.events:,})" for r in c.itertuples()]
            ax.errorbar(c["estimate_pp"], yy, xerr=np.array([c["estimate_pp"]-c["ci95_lower_pp"], c["ci95_upper_pp"]-c["estimate_pp"]]), fmt="o", capsize=4)
            ax.axvline(0, color="grey", linestyle="--")
            ax.set(yticks=yy, yticklabels=names, xlabel="Adjusted ranking-upset minus ordinary-loss difference (percentage points)",
                   title="Conditional follow-up associations: 95% player-clustered intervals")
            fig.tight_layout(); fig.savefig(charts / "q1_adjusted_contrasts.png", dpi=180); plt.close(fig)
    metrics_path = output / "q2_model_metrics.csv"
    if metrics_path.exists():
        metrics = pd.read_csv(metrics_path)
        metrics = metrics.loc[metrics["meeting_group"].eq("all")]
        fig, ax = plt.subplots(figsize=(8, 4))
        names = {"baseline": "Baseline", "plus_meeting_count": "+ Meeting count", "plus_h2h_results": "+ Head-to-head results"}
        bars = ax.bar(metrics["model"].map(names), metrics["brier_score"], color=["#7596ad", "#acb9a0", "#c88355"])
        ax.bar_label(bars, fmt="%.5f", padding=3)
        ax.set(ylabel="Held-out Brier score (lower is better)",
               title=f"Same held-out matches for all models (n={int(metrics['test_matches'].iloc[0]):,})")
        fig.tight_layout(); fig.savefig(charts / "q2_model_comparison.png", dpi=180); plt.close(fig)
    calibration_path = output / "q2_calibration.csv"
    if calibration_path.exists():
        c = pd.read_csv(calibration_path)
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.plot([0, 1], [0, 1], color="grey", linestyle="--", label="Perfect calibration")
        for model, part in c.groupby("model", sort=False):
            ax.plot(part["mean_prediction"], part["observed_win_rate"], marker="o", label=model.replace("_", " "))
        ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean predicted win probability", ylabel="Observed win proportion",
               title=f"Held-out calibration in fixed deciles (n={int(c.groupby('model')['matches'].sum().iloc[0]):,})")
        ax.legend(frameon=False, fontsize=8)
        fig.text(.04, .01, "Descriptive bin rates; bin denominators are in q2_calibration.csv.", fontsize=8)
        fig.tight_layout(rect=(0, .04, 1, 1)); fig.savefig(charts / "q2_calibration.png", dpi=180); plt.close(fig)
    paired = pd.read_csv(output / "q3_paired_player_comparison.csv")
    if not paired.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(100 * paired["win_rate_difference_L_minus_R"].dropna(), bins=20, color="#7596ad", edgecolor="white")
        ax.axvline(0, color="grey", linestyle="--")
        ax.set(xlabel="Win rate vs left minus right-handed opponents (percentage points)", ylabel="Players",
               title=f"Unadjusted within-player match-result differences (n={len(paired):,} players)")
        fig.tight_layout(); fig.savefig(charts / "q3_handedness_differences.png", dpi=180); plt.close(fig)
    adjusted_path = output / "q3_adjusted_contrasts.csv"
    if adjusted_path.exists():
        c = pd.read_csv(adjusted_path)
        c = c.loc[c["ci95_lower_pp"].notna() & c["ci95_upper_pp"].notna()]
        if not c.empty:
            fig, ax = plt.subplots(figsize=(8, 4))
            y = np.arange(len(c))
            labels = [f"{'Right' if r.player_hand == 'R' else 'Left'}-handed focal players (n={r.players:,})" for r in c.itertuples()]
            ax.errorbar(c["difference_pp"], y,
                        xerr=np.array([c["difference_pp"]-c["ci95_lower_pp"], c["ci95_upper_pp"]-c["difference_pp"]]),
                        fmt="o", capsize=4)
            ax.axvline(0, color="grey", linestyle="--")
            ax.set(yticks=y, yticklabels=labels, xlabel="Adjusted opponent L-minus-R difference (percentage points)",
                   title="Within-player match-result contrasts with 95% dyadic intervals")
            fig.tight_layout(); fig.savefig(charts / "q3_adjusted_contrasts.png", dpi=180); plt.close(fig)
