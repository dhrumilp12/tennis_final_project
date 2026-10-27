# Results: ATP match histories, 2000–2024

**Team:** Phouvadeth Vathana, Joseph Bronyah, Dhrumil Patel

Run ID: `20261027T121134Z-20f069d1`. Generated from verified outputs; all numerical claims below refer to this run.

The study uses **63,784 eligible physical matches** from **112,056 input records**, with 1990–1999 as history warm-up. Two player views are not two independent matches. Source: [`attrition.csv`](../outputs_final/attrition.csv), `study_eligible_matches` and `raw_records`.

## 1. Performance after ranking upsets

After a ranking upset, adjusted next-three-match performance differed from ordinary losses by -1.37 pp (95% interval -2.24 to -0.51 pp) across 18,471 complete, covariate-usable loss events from 341 players. The next-match difference was -1.46 pp (95% interval -2.84 to -0.07 pp). Age modification was +0.03 pp (95% interval -0.29 to +0.35 pp) per year; experience modification was +1.08 pp (95% interval -0.50 to +2.66 pp) per unit of log(1 + prior matches). For age, the interval includes zero; for experience, the interval includes zero. Interpret the joint age and experience interactions using their intervals, rather than treating descriptive age bands as experience groups. Adjustment includes subsequent playing context, so this is a conditional association, not a causal recovery effect.

Source: [`q1_adjusted_contrasts.csv`](../outputs_final/q1_adjusted_contrasts.csv), sample=all_windows, subgroup=all; average and age/experience interaction rows; run `20261027T121134Z-20f069d1`.

The descriptive comparison uses the same top-50, both-ranks-known loss population as adjustment. Counts of complete and unusable windows are:

| loss_type | index_losses | unique_players | usable_next_matches | complete_three_match_windows | incomplete_or_unusable_windows |
| --- | --- | --- | --- | --- | --- |
| other_ranked_loss | 16485 | 339 | 14550 | 12661 | 3824 |
| ranking_upset | 7536 | 326 | 6695 | 5885 | 1651 |

Source: [`q1_summary_overall.csv`](../outputs_final/q1_summary_overall.csv), all rows; run `20261027T121134Z-20f069d1`.

Age and experience are separately described in [`q1_summary_age.csv`](../outputs_final/q1_summary_age.csv) and [`q1_summary_experience.csv`](../outputs_final/q1_summary_experience.csv). Their raw patterns mix differences in strength, exposure and playing conditions. The continuous interactions above are the appropriate joint adjusted comparison. Experience is observed eligible history since 1990, not a complete career.

The non-overlapping-window check greedily retains the earliest available complete windows in sequence for each player, forbidding reuse of its index or follow-up matches. All primary and sensitivity contrasts are shown below; intervals cluster by player, accounting for repeated and overlapping windows within that player.

| outcome | sample | contrast | events | players | estimate_pp | ci95_lower_pp | ci95_upper_pp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| next3_win_rate | all_windows | average_upset_minus_ordinary | 18471 | 341 | -1.375 | -2.238 | -0.511 |
| next3_win_rate | all_windows | age_interaction_per_year | 18471 | 341 | 0.027 | -0.295 | 0.349 |
| next3_win_rate | all_windows | experience_interaction_log_unit | 18471 | 341 | 1.080 | -0.496 | 2.655 |
| next3_win_rate | nonoverlapping | average_upset_minus_ordinary | 9684 | 341 | -1.621 | -2.866 | -0.376 |
| next3_win_rate | nonoverlapping | age_interaction_per_year | 9684 | 341 | -0.079 | -0.505 | 0.346 |
| next3_win_rate | nonoverlapping | experience_interaction_log_unit | 9684 | 341 | 1.276 | -0.832 | 3.384 |
| next1_win | all_windows | average_upset_minus_ordinary | 21206 | 345 | -1.460 | -2.844 | -0.075 |
| next1_win | all_windows | age_interaction_per_year | 21206 | 345 | -0.497 | -1.026 | 0.033 |
| next1_win | all_windows | experience_interaction_log_unit | 21206 | 345 | 2.239 | -0.403 | 4.880 |
| next1_win | nonoverlapping | average_upset_minus_ordinary | 16263 | 345 | -1.744 | -3.383 | -0.106 |
| next1_win | nonoverlapping | age_interaction_per_year | 16263 | 345 | -0.434 | -1.045 | 0.176 |
| next1_win | nonoverlapping | experience_interaction_log_unit | 16263 | 345 | 1.612 | -1.291 | 4.515 |

Source: [`q1_adjusted_contrasts.csv`](../outputs_final/q1_adjusted_contrasts.csv), subgroup=all; run `20261027T121134Z-20f069d1`.

## 2. Do previous meetings improve prediction?

On 11,340 held-out matches, meeting count alone changed Brier performance by -0.000021 (95% interval -0.000091 to +0.000039); the interval includes zero. Adding previous head-to-head results changed Brier performance by +0.000586 (95% interval +0.000095 to +0.001019). Positive improvement means lower prediction error; for previous results, the interval is above zero. Meeting count and previous outcomes answer different questions. Pair-cluster intervals leave shared-player dependence across pairs unresolved.

Source: [`q2_paired_improvements.csv`](../outputs_final/q2_paired_improvements.csv), metric=brier; first_model=baseline; run `20261027T121134Z-20f069d1`.

| model | test_matches | brier_score | log_loss | accuracy |
| --- | --- | --- | --- | --- |
| baseline | 11340 | 0.216957 | 0.622392 | 0.646561 |
| plus_meeting_count | 11340 | 0.216979 | 0.622421 | 0.647531 |
| plus_h2h_results | 11340 | 0.216371 | 0.620970 | 0.648148 |

Source: [`q2_model_metrics.csv`](../outputs_final/q2_model_metrics.csv), meeting_group=all; run `20261027T121134Z-20f069d1`.

Training used 52,444 matches, with a 21-day exclusion gap before 2020; test seasons were 2020–2024. Parameters and preprocessing remain frozen. Earlier test-period results update later pre-match histories. Meeting count is shared by both players and does not inherently favor either one. No test-driven tuning was performed. Source: [`run_summary.json`](../outputs_final/run_summary.json), `q2`.

The same generated table contains results by zero, one, two-to-four and five-plus prior meetings. [`q2_paired_improvements.csv`](../outputs_final/q2_paired_improvements.csv) includes paired Brier, log-loss and accuracy intervals for all three model comparisons. [`q2_calibration.csv`](../outputs_final/q2_calibration.csv) gives fixed-bin denominators and observed versus predicted rates.

## 3. Does opponent handedness matter?

Adjusted opponent-left-minus-right win-probability differences were +1.11 pp (95% interval -0.86 to +3.08 pp) for 365 right-handed focal players and +0.99 pp (95% interval -0.63 to +2.62 pp) for 55 left-handed focal players. For right-handed players, the interval includes zero; for left-handed players, the interval includes zero. The results do not establish a uniform handedness advantage. Dyadic intervals account for matches sharing either participant; the smaller left-handed subgroup and remaining event/network dependence warrant caution.

Source: [`q3_adjusted_contrasts.csv`](../outputs_final/q3_adjusted_contrasts.csv), method=dyadic_primary; player_hand=R and L; run `20261027T121134Z-20f069d1`.

The adjusted sample has 61,412 unique physical matches and 112,503 focal-player rows from 420 players. Subgroup match counts overlap when both views of a match qualify. Source: [`run_summary.json`](../outputs_final/run_summary.json), `q3`.

These equal-player service and match summaries are **unadjusted**, not evidence of a controlled handedness effect:

| player_hand | players | mean_player_win_difference_pp | service_eligible_players | mean_player_service_difference_pp | service_points_vs_L | service_points_vs_R |
| --- | --- | --- | --- | --- | --- | --- |
| L | 56 | 1.672 | 56 | -0.126 | 149,398.000 | 1,025,885.000 |
| R | 371 | 3.445 | 370 | 0.869 | 1,058,530.000 | 6,961,834.000 |

Source: [`q3_descriptive_contrasts.csv`](../outputs_final/q3_descriptive_contrasts.csv), all rows; run `20261027T121134Z-20f069d1`.

The original player-by-match covariance still has 1 negative coefficient variance term(s). It is retained as a sensitivity with unavailable affected intervals, never replaced by zero or an absolute value. The primary dyadic method uses dependence through either player and includes absorbed fixed-effect degrees of freedom. Left-handed contrasts use the coefficient sum and **the full covariance including its cross term**. See [`q3_inference_sensitivity.csv`](../outputs_final/q3_inference_sensitivity.csv), [`q3_subgroup_support.csv`](../outputs_final/q3_subgroup_support.csv), and [`q3_player_influence.csv`](../outputs_final/q3_player_influence.csv).

## Interpretation limits

These are exploratory observational results. Ranking upsets are a ranking-based operational definition, not a measure of surprise or psychological recovery. Tournament-week dates and checked rounds approximate chronology; exact match days and recovery durations are unavailable. Missing follow-up is missing, never zero wins. Player and pair intervals do not remove every source of dependence, selection bias or unmeasured confounding. All thresholds, including rank gaps 20, 30 and 50, are reported rather than selected for a preferred finding.
