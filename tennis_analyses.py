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
from scipy.stats import norm
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.sandwich_covariance import cov_cluster_2groups
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


def analyze_recovery(events: pd.DataFrame, cfg: Config, output: Path) -> dict:
    info = {"index_losses": len(events), "ranking_upsets": int(events["ranking_upset"].sum()),
            "complete_three_match_followups": int(events["followup_complete"].sum()),
            "status": "Descriptive outputs saved; adjusted model not fitted."}
    for group, filename in [("age_group", "q1_summary_age.csv"), ("experience_group", "q1_summary_experience.csv")]:
        summary = events.groupby(["loss_type", group], observed=True, dropna=False).agg(
            index_losses=("match_id", "size"), unique_players=("player_id", "nunique"),
            usable_next_matches=("next1_usable", "sum"), next_match_win_rate=("next1_win", "mean"),
            complete_three_match_windows=("followup_complete", "sum"), next_three_win_rate=("next3_win_rate", "mean"),
            mean_age=("player_age", "mean"), mean_prior_matches=("prior_matches", "mean"))
        summary.to_csv(output / filename)
    # Threshold sensitivity is descriptive. It is NOT a search for a significant cutoff.
    sensitivity = []
    for gap in sorted({20, cfg.upset_rank_gap, 50}):
        candidate = events.loc[events["player_rank"].le(cfg.upset_max_rank) & events["rank_gap"].ge(gap)]
        for age, group in candidate.groupby("age_group", observed=True):
            sensitivity.append({"rank_gap_threshold": gap, "age_group": str(age), "index_losses": len(group),
                                "complete_windows": int(group["followup_complete"].sum()),
                                "next_three_win_rate": group["next3_win_rate"].mean()})
    pd.DataFrame(sensitivity, columns=["rank_gap_threshold", "age_group", "index_losses", "complete_windows", "next_three_win_rate"]).to_csv(output / "q1_threshold_sensitivity.csv", index=False)
    # Compare upsets with other losses by the SAME rank-eligible population.
    e = events.loc[events["followup_complete"] & events["loss_type"].ne("unknown_rank") &
                   events["player_rank"].le(cfg.upset_max_rank)].copy()
    required = ["next3_win_rate", "player_age", "prior_matches", "recent_win_rate", "player_rank", "followup_mean_log_rank_advantage"]
    e = e.dropna(subset=required)
    info["adjusted_model_eligible_events"] = len(e)
    if len(e) < 100 or e["player_id"].nunique() < 20 or e["ranking_upset"].nunique() < 2:
        info["status"] = "Descriptive Q1 tables saved; insufficient follow-up, players, or upset variation for the adjusted model."
        return info
    e["ranking_upset"] = e["ranking_upset"].astype(int)
    e["age_centered"] = e["player_age"] - 25
    e["log_experience"] = np.log1p(e["prior_matches"])
    e["log_player_rank"] = np.log(e["player_rank"])
    formula = ("next3_win_rate ~ ranking_upset * (age_centered + log_experience) + "
               "recent_win_rate + log_player_rank + followup_mean_log_rank_advantage + "
               "followup_clay_share + followup_grass_share + followup_carpet_share + "
               "followup_unknown_share + followup_best_of_5_share + C(surface) + C(season)")
    for term in ["followup_clay_share", "followup_grass_share", "followup_carpet_share", "followup_unknown_share", "followup_best_of_5_share"]:
        if e[term].nunique() < 2:
            formula = formula.replace(term + " + ", "")
    try:
        fit = smf.ols(formula, data=e).fit(cov_type="cluster", cov_kwds={"groups": e["player_id"]})
        table = coefficient_table(fit)
        table.to_csv(output / "q1_adjusted_coefficients.csv", index=False)
        text = ("Exploratory OLS for next-three-match win rate.\n"
                "Player-clustered standard errors; no omnibus significance claim.\n"
                f"Formula: {formula}\nRows: {len(e)}; players: {e['player_id'].nunique()}\n\n" + table.to_string(index=False))
        (output / "q1_adjusted_model.txt").write_text(text, encoding="utf-8")
        info.update(status="Q1 descriptive tables and exploratory adjusted recovery-rate regression fitted.",
                    model_events=len(e), model_players=int(e["player_id"].nunique()),
                    model_formula=formula, uncertainty="Player-clustered standard errors; not full opponent/network dependence.")
    except (ValueError, np.linalg.LinAlgError) as exc:
        info["status"] = f"Q1 descriptive tables saved; adjusted model could not be fitted: {exc}"
    return info


def prediction_pipeline(numeric: list[str], categories: list[str], seed: int) -> Pipeline:
    preprocess = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)),
                              ("scale", StandardScaler())]), numeric),
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                                  ("encode", OneHotEncoder(handle_unknown="ignore"))]), categories)])
    return Pipeline([("prepare", preprocess), ("model", LogisticRegression(max_iter=2500, C=1.0, random_state=seed))])


def paired_cluster_interval(predictions: pd.DataFrame, first: str, second: str, cfg: Config) -> dict:
    """Positive Brier difference means the second model has lower prediction error."""
    temp = predictions.copy()
    y = temp["won"].to_numpy()
    temp["difference"] = (y - temp[first]) ** 2 - (y - temp[second]) ** 2
    clusters = temp.groupby("pair_id")["difference"].agg(["sum", "count"])
    if len(clusters) < 20:
        return {"status": "Too few distinct opponent pairs for a cluster interval.", "pair_clusters": len(clusters)}
    rng = np.random.default_rng(cfg.random_seed)
    sums, counts = clusters["sum"].to_numpy(), clusters["count"].to_numpy()
    draws = np.empty(cfg.bootstrap_samples)
    for i in range(cfg.bootstrap_samples):
        selected = rng.integers(0, len(clusters), len(clusters))
        draws[i] = sums[selected].sum() / counts[selected].sum()
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {"status": "Computed", "mean_brier_improvement": float(temp["difference"].mean()),
            "ci95_lower": float(lo), "ci95_upper": float(hi), "pair_clusters": len(clusters),
            "resamples": cfg.bootstrap_samples,
            "limitation": "Pair-cluster resampling does not capture every shared-player dependence across different pairs."}


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
    info.update(status="Chronological Q2 comparison fitted: baseline, +meeting count, +head-to-head results.",
                paired_brier_comparison=paired_cluster_interval(pred, "p_baseline", "p_plus_h2h_results", cfg),
                convergence_warnings=convergence_notes,
                primary_metric="Brier score (lower is better). Both models are evaluated on exactly the same held-out matches.",
                test_history_policy="Earlier held-out results can update later held-out pre-match histories; model parameters stay frozen.")
    return info


def analyze_handedness(players: pd.DataFrame, cfg: Config, output: Path) -> dict:
    d = players.loc[players["eligible"] & players["player_hand"].isin(["L", "R"]) & players["opponent_hand"].isin(["L", "R"])].copy()
    info = {"status": "Q3 descriptive tables saved; adjusted model not fitted.", "player_match_rows": len(d),
            "unique_matches": int(d["match_id"].nunique())}
    columns = ["player_id", "opponent_hand", "matches", "wins", "win_rate", "service_points_won", "service_points_observed", "service_win_rate"]
    if d.empty:
        pd.DataFrame(columns=columns).to_csv(output / "q3_by_player_and_hand.csv", index=False)
        pd.DataFrame(columns=["player_id", "win_rate_difference_L_minus_R"]).to_csv(output / "q3_paired_player_comparison.csv", index=False)
        return info
    summary = d.groupby(["player_id", "opponent_hand"]).agg(
        matches=("match_id", "size"), wins=("won", "sum"), win_rate=("won", "mean"),
        service_matches=("valid_service_stats", "sum"),
        service_points_won=("service_points_won", lambda x: x.sum(min_count=1)),
        service_points_observed=("service_points_observed", lambda x: x.sum(min_count=1)))
    summary["service_win_rate"] = summary["service_points_won"] / summary["service_points_observed"]
    summary.to_csv(output / "q3_by_player_and_hand.csv")
    wide = summary[["matches", "win_rate", "service_win_rate"]].unstack("opponent_hand")
    wide.columns = [f"{stat}_{hand}" for stat, hand in wide.columns]
    for stat in ["matches", "win_rate", "service_win_rate"]:
        for hand in ["L", "R"]:
            if f"{stat}_{hand}" not in wide:
                wide[f"{stat}_{hand}"] = np.nan
    wide["win_rate_difference_L_minus_R"] = wide["win_rate_L"] - wide["win_rate_R"]
    wide["service_rate_difference_L_minus_R"] = wide["service_win_rate_L"] - wide["service_win_rate_R"]
    names = d.drop_duplicates("player_id").set_index("player_id")["player_name"]
    wide["player_name"] = names
    paired = wide.loc[wide["matches_L"].ge(cfg.min_hand_matches) & wide["matches_R"].ge(cfg.min_hand_matches)].copy()
    paired.to_csv(output / "q3_paired_player_comparison.csv")
    info["players_meeting_raw_comparison_minimum"] = len(paired)
    d = d.dropna(subset=["log_rank_advantage", "player_age", "recent_win_rate", "opponent_recent_win_rate"])
    hand_counts = d.groupby(["player_id", "opponent_hand"]).size().unstack(fill_value=0).reindex(columns=["L", "R"], fill_value=0)
    adequate = hand_counts.index[(hand_counts >= cfg.min_hand_matches).all(axis=1)]
    d = d.loc[d["player_id"].isin(adequate)].copy()
    if len(d) < 200 or d["player_id"].nunique() < 20:
        info["status"] = "Q3 descriptive tables saved; insufficient players with both opponent hands and complete covariates for adjustment."
        return info
    x = pd.DataFrame(index=d.index)
    x["opponent_left"] = d["opponent_hand"].eq("L").astype(float)
    x["opponent_left_x_player_left"] = x["opponent_left"] * d["player_hand"].eq("L").astype(float)
    x["log_rank_advantage"] = d["log_rank_advantage"]
    x["age"] = d["player_age"]
    x["recent_win_rate"] = d["recent_win_rate"]
    x["opponent_recent_win_rate"] = d["opponent_recent_win_rate"]
    x["log_prior_matches"] = np.log1p(d["prior_matches"])
    x = pd.concat([x, pd.get_dummies(d[["surface", "season"]].astype(str), drop_first=True, dtype=float)], axis=1)
    # Demeaning removes a separate constant for every player, providing a
    # within-player comparison without constructing thousands of dummy columns.
    x_within = x - x.groupby(d["player_id"]).transform("mean")
    y_within = d["won"] - d.groupby("player_id")["won"].transform("mean")
    x_within = x_within.loc[:, x_within.std().gt(1e-10)]
    try:
        fit = sm.OLS(y_within, x_within.astype(float)).fit()
        player_clusters = pd.factorize(d["player_id"])[0]
        match_clusters = pd.factorize(d["match_id"])[0]
        covariance, _, _ = cov_cluster_2groups(fit, player_clusters, match_clusters)
        diag = np.diag(covariance)
        se = np.sqrt(np.maximum(diag, 0))
        se[diag < 0] = np.nan  # Do not manufacture a confidence interval.
        table = pd.DataFrame({"term": fit.params.index, "coefficient": fit.params.to_numpy(),
                              "standard_error": se, "ci95_lower": fit.params.to_numpy() - norm.ppf(.975) * se,
                              "ci95_upper": fit.params.to_numpy() + norm.ppf(.975) * se})
        table.to_csv(output / "q3_adjusted_coefficients.csv", index=False)
        info.update(status="Q3 descriptive tables and within-player adjusted linear probability model fitted.",
                    adjusted_player_match_rows=len(d), adjusted_unique_matches=int(d["match_id"].nunique()),
                    adjusted_players=int(d["player_id"].nunique()),
                    covariance="Two-way clustered by focal player and physical match; other shared-opponent dependence may remain.",
                    ci_note="Large-sample normal intervals; exploratory, not causal.",
                    negative_variance_terms=int((diag < 0).sum()),
                    interpretation="opponent_left is the adjusted L-minus-R contrast for right-handed focal players; add the interaction for left-handed focal players. Coefficients are probability units.")
    except (ValueError, np.linalg.LinAlgError) as exc:
        info["status"] = f"Q3 descriptive tables saved; adjustment could not be fitted: {exc}"
    return info


def make_charts(output: Path) -> None:
    """Separate, default-style plots. No interpretation is baked into titles."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    charts = output / "charts"
    charts.mkdir(exist_ok=True)
    age = pd.read_csv(output / "q1_summary_age.csv")
    age = age.loc[age["loss_type"].eq("ranking_upset") & age["next_three_win_rate"].notna()]
    if not age.empty:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(age["age_group"], age["next_three_win_rate"])
        ax.set(ylabel="Win rate in next three recorded matches", xlabel="Age at ranking upset", ylim=(0, 1),
               title="After ranking upsets: unadjusted comparison")
        fig.tight_layout(); fig.savefig(charts / "q1_recovery_by_age.png", dpi=180); plt.close(fig)
    metrics_path = output / "q2_model_metrics.csv"
    if metrics_path.exists():
        metrics = pd.read_csv(metrics_path)
        metrics = metrics.loc[metrics["meeting_group"].eq("all")]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(metrics["model"], metrics["brier_score"])
        ax.set(ylabel="Held-out Brier score (lower is better)", title="Does previous meeting history improve predictions?")
        ax.tick_params(axis="x", labelrotation=12)
        fig.tight_layout(); fig.savefig(charts / "q2_model_comparison.png", dpi=180); plt.close(fig)
    paired = pd.read_csv(output / "q3_paired_player_comparison.csv")
    if not paired.empty:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(paired["win_rate_difference_L_minus_R"].dropna(), bins=20)
        ax.axvline(0, linestyle="--")
        ax.set(xlabel="Win rate vs left-handers minus win rate vs right-handers", ylabel="Players",
               title="Within-player differences: unadjusted")
        fig.tight_layout(); fig.savefig(charts / "q3_handedness_differences.png", dpi=180); plt.close(fig)
