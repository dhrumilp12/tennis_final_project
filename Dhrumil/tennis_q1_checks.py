"""Later Q1 interpretation and retention checks using saved recovery events only.

No primary formula or analysis module is modified. The original Q1 entry point
is executed in a temporary directory so its actual fitted samples, formulae and
cluster covariance are reused and compared to the historical outputs.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pandas as pd

import tennis_analyses as analysis
from tennis_project import Config


NUMERIC_RTOL = 1e-9
NUMERIC_ATOL = 1e-10
PRELOSS_MEASURES = ["prior_matches", "player_age", "player_rank", "recent_win_rate"]
AGE_GROUPS = ["under_23", "23_to_29", "30_plus"]
EXPERIENCE_GROUPS = ["under_100", "100_to_299", "300_plus"]
CONTRASTS = [
    ("age_post_upset_per_year", {"age_centered": 1., "ranking_upset:age_centered": 1.},
     "percentage points per one year of age"),
    ("experience_post_upset_log_unit", {"log_experience": 1., "ranking_upset:log_experience": 1.},
     "percentage points per one unit of log(1 + prior recorded matches)"),
    ("age_interaction_per_year", {"ranking_upset:age_centered": 1.},
     "percentage points per one year: upset slope minus ordinary-loss slope"),
    ("experience_interaction_log_unit", {"ranking_upset:log_experience": 1.},
     "percentage points per one log-experience unit: upset slope minus ordinary-loss slope"),
]


def post_upset_contrasts(fit, data, outcome, sample):
    """Use the existing full-covariance contrasts and focal-player t intervals."""
    n, players = len(data), int(data.player_id.nunique())
    upset = data.loc[data.ranking_upset.eq(1)]
    full_rank = np.linalg.matrix_rank(fit.model.exog) == fit.model.exog.shape[1]
    rows = []
    for label, weights, units in CONTRASTS:
        missing = set(weights) - set(fit.params.index)
        if missing:
            raise ValueError(f"Original Q1 fit lacks required terms: {sorted(missing)}")
        row = analysis.recovery_contrast(fit, weights, label=label, outcome=outcome,
                                        sample=sample, events=n, players=players)
        vector = np.array([weights.get(term, 0.) for term in fit.params.index])
        covariance = np.asarray(fit.cov_params(), float)
        variance = float(vector @ covariance @ vector)
        active = np.flatnonzero(vector)
        diagonal = float(sum(vector[i] ** 2 * covariance[i, i] for i in active))
        cross = float(sum(vector[i] * covariance[i, j] * vector[j]
                          for i in active for j in active if i != j))
        row.update(variance_probability_units=variance,
                   coefficient_terms=" + ".join(weights),
                   covariance_diagonal_contribution=diagonal,
                   covariance_cross_term_contribution=cross)
        if players < 20:
            row["inference_status"] = "unavailable_insufficient_player_clusters"
        elif not np.isfinite(variance):
            row["inference_status"] = "unavailable_nonfinite_contrast_variance"
        elif variance < 0:
            row["inference_status"] = "unavailable_negative_contrast_variance"
        if not full_rank:
            row["inference_status"] = "unavailable_rank_deficient_design"
        if row["inference_status"] != "available":
            row.update(standard_error_pp=np.nan, ci95_lower_pp=np.nan, ci95_upper_pp=np.nan)
        row.update(upset_events=len(upset), upset_players=int(upset.player_id.nunique()),
                   units=units, covariance_t_df=players - 1,
                   contrast_kind="post_upset_association" if "post_upset" in label else "upset_minus_ordinary_interaction")
        rows.append(row)
    return rows


def design_diagnostics(fit, data, outcome, sample):
    """Report collinearity descriptively; do not choose a significance cutoff."""
    x = np.asarray(fit.model.exog, float)
    scales = x.std(axis=0)
    scaled = x / np.where(scales > 1e-12, scales, 1.)
    row = dict(outcome=outcome, sample=sample, events=len(data),
               players=int(data.player_id.nunique()), design_columns=x.shape[1],
               design_rank=int(np.linalg.matrix_rank(x)),
               condition_number_unscaled=float(np.linalg.cond(x)),
               condition_number_column_scaled=float(np.linalg.cond(scaled)),
               age_log_experience_correlation=float(data.age_centered.corr(data.log_experience)))
    for name in ["age_centered", "log_experience"]:
        j = fit.model.exog_names.index(name)
        y, others = x[:, j], np.delete(x, j, axis=1)
        residual = y - others @ np.linalg.lstsq(others, y, rcond=None)[0]
        total = np.square(y - y.mean()).sum()
        residual_sum = np.square(residual).sum()
        row[f"{name}_vif"] = float(total / residual_sum) if residual_sum > 0 else np.inf
    row["interpretation"] = (
        "Condition numbers depend on coding/scaling. VIF is total/residual sum of squares "
        "after projection onto all other original design columns. No cutoff changes the model."
    )
    return row


def support_table(populations):
    rows = []
    for name, data in populations.items():
        d = data.copy()
        for field in ["age_group", "experience_group"]:
            d[field] = d[field].astype(object).fillna("unknown")
        ages = AGE_GROUPS + (["unknown"] if d.age_group.eq("unknown").any() else [])
        experience = EXPERIENCE_GROUPS + (["unknown"] if d.experience_group.eq("unknown").any() else [])
        for age in ages:
            for prior in experience:
                for loss in ["ranking_upset", "other_ranked_loss"]:
                    g = d.loc[d.age_group.eq(age) & d.experience_group.eq(prior) & d.loss_type.eq(loss)]
                    rows.append(dict(population=name, age_group=age, experience_group=prior,
                                     loss_type=loss, events=len(g), players=int(g.player_id.nunique())))
    return pd.DataFrame(rows)


def preloss_distributions(data, population, retention_status="all"):
    rows = []
    groups = [("overall", "all", data)]
    for dimension, labels in [("age_group", AGE_GROUPS), ("experience_group", EXPERIENCE_GROUPS)]:
        values = data[dimension].astype(object).fillna("unknown")
        for label in labels + (["unknown"] if values.eq("unknown").any() else []):
            groups.append((dimension, label, data.loc[values.eq(label)]))
    for dimension, group, part in groups:
        for loss_type in ["all", "ranking_upset", "other_ranked_loss"]:
            g = part if loss_type == "all" else part.loc[part.loss_type.eq(loss_type)]
            for measure in PRELOSS_MEASURES:
                values = g[measure].dropna()
                row = dict(population=population, retention_status=retention_status,
                           dimension=dimension, group=group,
                           loss_type=loss_type, measure=measure, events=len(g),
                           players=int(g.player_id.nunique()), nonmissing=len(values),
                           mean=values.mean(), standard_deviation=values.std())
                row.update({f"q{int(q * 100):02d}": values.quantile(q) if len(values) else np.nan
                            for q in [.05, .25, .5, .75, .95]})
                rows.append(row)
    return rows


def retention_reasons(common, model_data, outcome, sample):
    """Mutually exclusive omitted-event reasons, with nonoverlap kept separate.

    Missing next records mean the end of the available recorded history, not a
    known retirement or a known unsuccessful follow-up. Blocked windows stay
    distinct from these unavailable records.
    """
    k = 1 if outcome == "next1_win" else 3
    available = common[outcome].notna()
    selected = analysis.select_nonoverlapping(common, k) if sample == "nonoverlapping" else available
    keys = pd.MultiIndex.from_frame(common[["player_id", "match_id"]])
    retained_keys = pd.MultiIndex.from_frame(model_data[["player_id", "match_id"]])
    retained = pd.Series(keys.isin(retained_keys), index=common.index)
    if (retained & ~selected).any():
        raise ValueError("A fitted Q1 observation is outside the original availability/nonoverlap selection.")
    reason = pd.Series("retained", index=common.index, dtype=object)
    reason.loc[~retained & available & selected] = "missing_model_covariates"
    reason.loc[available & ~selected] = "nonoverlap_selection"
    unavailable = ~available
    if k == 1:
        blocked = common.next1_unresolved_record.eq(True)
        unobserved = common.next1_match_id.isna()
    else:
        blocked = common.followup_unresolved_record.eq(True)
        unobserved = common[[f"next{i}_match_id" for i in range(1, 4)]].isna().any(axis=1)
    reason.loc[unavailable] = "excluded_or_ambiguous_followup"
    reason.loc[unavailable & unobserved] = "end_of_recorded_data_unobserved_followup"
    reason.loc[unavailable & blocked] = "unresolved_record_blocks_followup"
    if not reason.eq("retained").equals(retained):
        raise AssertionError("Retention classification disagrees with exact fitted IDs.")
    return reason, available, selected


def retention_table(common, model_data, outcome, sample):
    reason, available, selected = retention_reasons(common, model_data, outcome, sample)
    d = common.copy()
    d["_reason"], d["_available"], d["_selected"] = reason, available, selected
    for field in ["age_group", "experience_group"]:
        d[field] = d[field].astype(object).fillna("unknown")
    rows = []
    definitions = [("overall", []), ("age_group", ["age_group"]),
                   ("experience_group", ["experience_group"]),
                   ("age_experience", ["age_group", "experience_group"])]
    reasons = ["end_of_recorded_data_unobserved_followup", "unresolved_record_blocks_followup",
               "excluded_or_ambiguous_followup", "nonoverlap_selection", "missing_model_covariates", "retained"]
    for dimension, columns in definitions:
        for key, g in d.groupby(columns + ["loss_type"], observed=True, dropna=False, sort=True):
            key = key if isinstance(key, tuple) else (key,)
            row = dict(outcome=outcome, sample=sample, dimension=dimension,
                       group=" / ".join(map(str, key[:-1])) if columns else "all", loss_type=key[-1],
                       denominator_events=len(g), denominator_players=int(g.player_id.nunique()),
                       usable_next1_events=int(g.next1_usable.sum()),
                       usable_next1_players=int(g.loc[g.next1_usable, "player_id"].nunique()),
                       complete_next3_events=int(g.followup_complete.sum()),
                       complete_next3_players=int(g.loc[g.followup_complete, "player_id"].nunique()),
                       outcome_available_events=int(g._available.sum()),
                       selected_before_covariates_events=int(g._selected.sum()))
            for label in reasons:
                subset = g.loc[g._reason.eq(label)]
                row[f"{label}_events"] = len(subset)
                row[f"{label}_players"] = int(subset.player_id.nunique())
            row["model_events"] = row["retained_events"]
            row["model_players"] = row["retained_players"]
            row["model_retention_share"] = row["model_events"] / len(g)
            if sum(row[f"{label}_events"] for label in reasons) != len(g):
                raise AssertionError("Mutually exclusive retention reasons do not sum to denominator.")
            rows.append(row)
    return rows, reason


def capture_original_models(events, cfg, temporary):
    """Run the original implementation, capturing real fit inputs and results."""
    original = analysis.smf.ols
    captured = []

    class CaptureModel:
        def __init__(self, formula, data, args, kwargs):
            self.formula, self.data = formula, data.copy()
            self.model = original(formula, data=data, *args, **kwargs)

        def fit(self, *args, **kwargs):
            fit = self.model.fit(*args, **kwargs)
            if list(fit.model.data.row_labels) != list(self.data.index):
                raise ValueError("Original formula fit silently dropped additional rows.")
            captured.append(dict(formula=self.formula, data=self.data, fit=fit))
            return fit

    def ols(formula, data, *args, **kwargs):
        return CaptureModel(formula, data, args, kwargs)

    with patch.object(analysis.smf, "ols", side_effect=ols):
        info = analysis.analyze_recovery(events, cfg, temporary)
    return captured, info


def verify_reconstructed_models(source, temporary, captured):
    """Exact ordered windows plus numerical coefficient/SE/interval checks."""
    windows = pd.read_csv(temporary / "q1_model_windows.csv.gz")
    historical_windows = pd.read_csv(source / "q1_model_windows.csv.gz")
    pd.testing.assert_frame_equal(windows, historical_windows, check_dtype=False, check_exact=True)
    for name in ["q1_all_adjusted_coefficients.csv", "q1_adjusted_contrasts.csv", "q1_model_samples.csv"]:
        pd.testing.assert_frame_equal(pd.read_csv(temporary / name), pd.read_csv(source / name),
                                      check_dtype=False, rtol=NUMERIC_RTOL, atol=NUMERIC_ATOL)
    models = []
    consumed = set()
    for item in captured:
        outcome = item["formula"].split("~")[0].strip()
        d = item["data"]
        for sample in ["all_windows", "nonoverlapping"]:
            key = (outcome, sample)
            if key in consumed:
                continue
            expected = windows.loc[windows.outcome.eq(outcome) & windows["sample"].eq(sample)]
            if len(expected) != len(d):
                continue
            actual_ids = d[["player_id", "match_id"]].reset_index(drop=True)
            try:
                pd.testing.assert_frame_equal(actual_ids, expected[["player_id", "match_id"]].reset_index(drop=True),
                                              check_dtype=False, check_exact=True)
            except AssertionError:
                continue
            consumed.add(key)
            models.append({**item, "outcome": outcome, "sample": sample})
            break
        else:
            raise ValueError("Captured fit has no exact historical sample-ID match.")
    expected_models = set(map(tuple, windows[["outcome", "sample"]].drop_duplicates().to_numpy()))
    if consumed != expected_models or len(models) != 4:
        raise ValueError("The four original Q1 fitted models were not exactly reconstructed.")
    return models, windows


def run_q1(source: Path, output: Path, summary: dict):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError("Supplemental Q1 outputs must be separate from the historical run.")
    output.mkdir(parents=True, exist_ok=True)
    cfg = Config(**summary["configuration"])
    events = pd.read_csv(source / "q1_recovery_events.csv.gz")
    # Dates are restored because original nonoverlap selection orders chronology.
    events["tourney_date"] = pd.to_datetime(events.tourney_date)
    # CSV does not retain the original pd.cut categorical order. Restoring it
    # preserves the order of historical subgroup contrast rows as well.
    events["age_group"] = pd.Categorical(events.age_group, categories=AGE_GROUPS, ordered=True)
    events["experience_group"] = pd.Categorical(events.experience_group, categories=EXPERIENCE_GROUPS, ordered=True)
    ranked = events.player_rank.notna() & events.opponent_rank.notna()
    common = events.loc[ranked & events.player_rank.le(cfg.upset_max_rank)].copy()
    if common.duplicated(["player_id", "match_id"]).any():
        raise ValueError("Duplicate Q1 loss-event identifiers.")
    with TemporaryDirectory(prefix="q1-original-fit-") as directory:
        temporary = Path(directory)
        captured, original_info = capture_original_models(events, cfg, temporary)
        models, windows = verify_reconstructed_models(source, temporary, captured)
    windows.to_csv(output / "q1_model_ids.csv.gz", index=False,
                   compression={"method": "gzip", "mtime": 0})
    contrasts, diagnostics, retention, distributions, model_counts = [], [], [], [], []
    populations = {"common_rank_eligible": common}
    distributions.extend(preloss_distributions(common, "common_rank_eligible"))
    for item in models:
        d, fit, outcome, sample = item["data"], item["fit"], item["outcome"], item["sample"]
        name = f"{outcome}/{sample}"
        populations[name] = d
        contrasts.extend(post_upset_contrasts(fit, d, outcome, sample))
        diagnostics.append(design_diagnostics(fit, d, outcome, sample))
        rows, reason = retention_table(common, d, outcome, sample)
        retention.extend(rows)
        distributions.extend(preloss_distributions(d, name, "retained"))
        distributions.extend(preloss_distributions(common.loc[~reason.eq("retained")], name, "omitted"))
        upset = d.loc[d.ranking_upset.eq(1)]
        model_counts.append(dict(outcome=outcome, sample=sample, events=len(d),
                                 players=int(d.player_id.nunique()), upset_events=len(upset),
                                 upset_players=int(upset.player_id.nunique()), formula=item["formula"]))
    pd.DataFrame(contrasts).to_csv(output / "q1_post_upset_contrasts.csv", index=False)
    pd.DataFrame(diagnostics).to_csv(output / "q1_model_diagnostics.csv", index=False)
    support_table(populations).to_csv(output / "q1_support.csv", index=False)
    pd.DataFrame(retention).to_csv(output / "q1_retention.csv", index=False)
    pd.DataFrame(distributions).to_csv(output / "q1_distributions.csv", index=False)
    return {
        "checks": {
            "original_four_models_reexecuted_from_saved_events": True,
            "exact_ordered_event_and_followup_ids_match": True,
            "coefficients_standard_errors_and_intervals_match": True,
            "historical_contrasts_and_model_counts_match": True,
            "no_silent_formula_row_drops": True,
            "retention_reason_counts_sum_to_denominators": True,
            "numerical_rtol": NUMERIC_RTOL, "numerical_atol": NUMERIC_ATOL,
        },
        "common_population": {"events": len(common), "players": int(common.player_id.nunique())},
        "models": model_counts,
        "original_analysis_status": original_info["analysis_status"],
        "uncertainty": "Original focal-player cluster sandwich; full covariance for sums; t critical value with players minus one df.",
        "interpretation": "Post-upset sums describe age/experience associations after upset losses; interactions describe their difference from ordinary-loss associations. Neither is causal.",
    }
