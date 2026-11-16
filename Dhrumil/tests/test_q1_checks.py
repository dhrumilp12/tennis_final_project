"""Synthetic Q1 validation tests; synthetic values are not research findings."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from scipy.stats import t

from tennis_q1_checks import (post_upset_contrasts, preloss_distributions, retention_table,
                             support_table, verify_reconstructed_models)


def synthetic_fit():
    names = ["age_centered", "ranking_upset:age_centered", "log_experience", "ranking_upset:log_experience"]
    params = pd.Series([.10, .001, .20, -.002], index=names)
    covariance = np.diag([.0004, .0009, .0009, .0004])
    covariance[0, 1] = covariance[1, 0] = -.0002
    fit = SimpleNamespace(params=params, cov_params=lambda: pd.DataFrame(covariance, index=names, columns=names),
                          model=SimpleNamespace(exog=np.eye(4)))
    data = pd.DataFrame({"player_id": range(30), "ranking_upset": [1]*20+[0]*10})
    return fit, data


def test_post_upset_sum_uses_full_covariance_t_intervals_and_pp_units():
    fit, data = synthetic_fit()
    rows = pd.DataFrame(post_upset_contrasts(fit, data, "next1_win", "all_windows")).set_index("contrast")
    age = rows.loc["age_post_upset_per_year"]
    assert age.estimate_pp == pytest.approx(10.1)
    assert age.standard_error_pp == pytest.approx(100*np.sqrt(.0004+.0009-2*.0002))
    assert age.variance_probability_units == pytest.approx(.0009)
    assert age.covariance_diagonal_contribution == pytest.approx(.0013)
    assert age.covariance_cross_term_contribution == pytest.approx(-.0004)
    assert age.variance_probability_units == pytest.approx(
        age.covariance_diagonal_contribution + age.covariance_cross_term_contribution)
    assert age.coefficient_terms == "age_centered + ranking_upset:age_centered"
    assert rows.loc["age_interaction_per_year", "covariance_cross_term_contribution"] == 0
    assert age.ci95_lower_pp == pytest.approx(age.estimate_pp-t.ppf(.975, 29)*age.standard_error_pp)
    assert age.covariance_t_df == 29
    assert age.events == 30 and age.players == 30
    assert age.upset_events == 20 and age.upset_players == 20
    assert "one year" in age.units
    assert "log(1 + prior recorded matches)" in rows.loc["experience_post_upset_log_unit", "units"]


def test_uncertain_interaction_can_coexist_with_nonzero_post_upset_association():
    fit, data = synthetic_fit()
    rows = pd.DataFrame(post_upset_contrasts(fit, data, "next3_win_rate", "all_windows")).set_index("contrast")
    interaction = rows.loc["age_interaction_per_year"]
    summed = rows.loc["age_post_upset_per_year"]
    assert interaction.ci95_lower_pp < 0 < interaction.ci95_upper_pp
    assert summed.ci95_lower_pp > 0
    assert summed.contrast_kind == "post_upset_association"
    assert interaction.contrast_kind == "upset_minus_ordinary_interaction"


def test_post_upset_contrast_keeps_insufficient_support_and_rank_safeguards():
    fit, data = synthetic_fit()
    small = pd.DataFrame(post_upset_contrasts(fit, data.iloc[:10], "next1_win", "all_windows"))
    assert small.inference_status.eq("unavailable_insufficient_player_clusters").all()
    assert small.ci95_lower_pp.isna().all()
    fit.model.exog = np.ones((30, 4))
    deficient = pd.DataFrame(post_upset_contrasts(fit, data, "next1_win", "all_windows"))
    assert deficient.inference_status.eq("unavailable_rank_deficient_design").all()
    assert deficient.ci95_lower_pp.isna().all()


def test_negative_post_upset_variance_remains_unavailable():
    fit, data = synthetic_fit()
    covariance = fit.cov_params()
    covariance.iloc[0, 0] = -.01
    fit.cov_params = lambda: covariance
    result = pd.DataFrame(post_upset_contrasts(fit, data, "next1_win", "all_windows"))
    age = result.loc[result.contrast.eq("age_post_upset_per_year")].iloc[0]
    assert age.inference_status == "unavailable_negative_contrast_variance"
    assert age[["standard_error_pp", "ci95_lower_pp", "ci95_upper_pp"]].isna().all()


@pytest.mark.parametrize("nonfinite", [np.inf, np.nan])
def test_nonfinite_post_upset_variance_clears_all_uncertainty_fields(nonfinite):
    fit, data = synthetic_fit()
    covariance = fit.cov_params()
    covariance.iloc[0, 0] = nonfinite
    fit.cov_params = lambda: covariance
    # Other contrasts multiply zero by the intentionally invalid entry.
    with np.errstate(invalid="ignore"):
        result = pd.DataFrame(post_upset_contrasts(fit, data, "next1_win", "all_windows"))
    age = result.loc[result.contrast.eq("age_post_upset_per_year")].iloc[0]
    assert age.inference_status == "unavailable_nonfinite_contrast_variance"
    assert age.estimate_pp == pytest.approx(10.1)
    unavailable = result.loc[result.inference_status.ne("available")]
    assert unavailable[["standard_error_pp", "ci95_lower_pp", "ci95_upper_pp"]].isna().all().all()


def retention_data():
    rows = []
    for i in range(6):
        rows.append(dict(player_id=i+1, match_id=f"m{i}", next1_match_id=f"n{i}",
                         next2_match_id=f"o{i}", next3_match_id=f"p{i}",
                         tourney_date=pd.Timestamp(f"2020-01-{i+1:02d}"),
                         round_order=1, tourney_id=f"event{i}", next1_usable=True,
                         followup_complete=True, next1_win=1., next3_win_rate=2/3,
                         next1_unresolved_record=False, followup_unresolved_record=False,
                         age_group="under_23", experience_group="under_100",
                         loss_type="ranking_upset" if i % 2 == 0 else "other_ranked_loss"))
    rows[1].update(next1_match_id=np.nan, next2_match_id=np.nan, next3_match_id=np.nan,
                   next1_usable=False, followup_complete=False, next1_win=np.nan, next3_win_rate=np.nan)
    rows[2].update(next1_unresolved_record=True, followup_unresolved_record=True,
                   next1_usable=False, followup_complete=False, next1_win=np.nan, next3_win_rate=np.nan)
    rows[3].update(next1_usable=False, followup_complete=False, next1_win=np.nan, next3_win_rate=np.nan)
    # Event 5 overlaps event 0 within the same player's recorded sequence.
    rows[5].update(player_id=1, match_id="n0", next1_match_id="future")
    return pd.DataFrame(rows)


def test_retention_denominators_and_missing_followup_reasons_are_distinct():
    common = retention_data()
    rows, reasons = retention_table(common, common.iloc[[0, 5]], "next1_win", "all_windows")
    assert reasons.tolist() == ["retained", "end_of_recorded_data_unobserved_followup",
                                "unresolved_record_blocks_followup", "excluded_or_ambiguous_followup",
                                "missing_model_covariates", "retained"]
    overall = pd.DataFrame(rows).query("dimension == 'overall'")
    assert overall.denominator_events.sum() == 6
    assert overall.usable_next1_events.sum() == 3
    assert overall.model_events.sum() == 2
    assert overall.missing_model_covariates_events.sum() == 1
    assert overall.end_of_recorded_data_unobserved_followup_events.sum() == 1
    assert set(pd.DataFrame(rows).dimension) == {"overall", "age_group", "experience_group", "age_experience"}
    assert np.isnan(common.next1_win.iloc[1])  # No outcome imputation.


def test_nonoverlap_omissions_are_separate_from_missing_covariates():
    common = retention_data()
    rows, reasons = retention_table(common, common.iloc[[0]], "next1_win", "nonoverlapping")
    assert reasons.iloc[5] == "nonoverlap_selection"
    assert reasons.iloc[4] == "missing_model_covariates"
    overall = pd.DataFrame(rows).query("dimension == 'overall'")
    assert overall.nonoverlap_selection_events.sum() == 1
    assert overall.missing_model_covariates_events.sum() == 1
    assert overall.model_events.sum() == 1


def test_support_crosses_original_age_experience_and_loss_type_groups():
    data = retention_data()
    data.loc[0, "age_group"] = "30_plus"
    data.loc[0, "experience_group"] = "300_plus"
    result = support_table({"common_rank_eligible": data})
    row = result.loc[result.age_group.eq("30_plus") & result.events.gt(0)].iloc[0]
    assert row.experience_group == "300_plus" and row.loss_type == "ranking_upset"
    assert row.events == 1 and row.players == 1
    assert result.events.sum() == len(data)
    assert len(result) == 18
    assert result.events.eq(0).any()  # Absent age-by-experience cells remain visible.


def test_preloss_distributions_are_grouped_and_keep_missing_denominators():
    data = retention_data().assign(prior_matches=[10, 20, 30, 40, 50, 60],
                                   player_age=[20, 21, 22, 20, 21, 22],
                                   player_rank=[1, 2, 3, 4, 5, 6],
                                   recent_win_rate=[.5, .5, np.nan, .5, .5, .5])
    table = pd.DataFrame(preloss_distributions(data, "next1_win/all_windows", "omitted"))
    assert set(table.dimension) == {"overall", "age_group", "experience_group"}
    row = table.loc[table.dimension.eq("age_group") & table.group.eq("under_23") &
                    table.loss_type.eq("ranking_upset") & table.measure.eq("recent_win_rate")].iloc[0]
    assert row.events == 3 and row.nonmissing == 2
    assert row.players == 3 and row.q50 == .5
    assert row.retention_status == "omitted"
    assert table.loc[table.dimension.eq("experience_group") & table.group.eq("300_plus"), "events"].eq(0).all()


def test_model_verification_requires_exact_ordered_window_ids(tmp_path):
    source, temp = tmp_path/"source", tmp_path/"temp"
    source.mkdir(); temp.mkdir()
    rows, captured = [], []
    for outcome in ["next1_win", "next3_win_rate"]:
        for sample, n in [("all_windows", 3), ("nonoverlapping", 2)]:
            records = [dict(outcome=outcome, sample=sample, player_id=i, match_id=f"{outcome}-{i}",
                            next1_match_id=f"next-{i}", next2_match_id=np.nan, next3_match_id=np.nan)
                       for i in range(n)]
            rows.extend(records)
            captured.append(dict(formula=f"{outcome} ~ original_terms", data=pd.DataFrame(records), fit=None))
    windows = pd.DataFrame(rows)
    for folder in [source, temp]:
        windows.to_csv(folder/"q1_model_windows.csv.gz", index=False)
        for filename in ["q1_all_adjusted_coefficients.csv", "q1_adjusted_contrasts.csv", "q1_model_samples.csv"]:
            pd.DataFrame({"value": [1.]}).to_csv(folder/filename, index=False)
    models, verified = verify_reconstructed_models(source, temp, captured)
    assert len(models) == 4 and len(verified) == len(windows)
    windows.iloc[::-1].to_csv(temp/"q1_model_windows.csv.gz", index=False)
    with pytest.raises(AssertionError):
        verify_reconstructed_models(source, temp, captured)
