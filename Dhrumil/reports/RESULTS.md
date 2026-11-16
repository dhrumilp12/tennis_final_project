# Results: ATP match histories, 2000–2024

**Team:** Phouvadeth Vathana, Joseph Bronyah, Dhrumil Patel

Run ID: `20261027T121134Z-20f069d1`. Generated from verified outputs; primary numerical claims below refer to this run.
The separately labeled opponent-comparability validation was produced later.
The supplemental Q1/Q2 validation is separate from the historical primary analysis.

The study uses **63,784 eligible physical matches** from **112,056 input records**, with 1990–1999 as history warm-up. Two player views are not two independent matches. Source: [`attrition.csv`](../outputs_final/attrition.csv), `study_eligible_matches` and `raw_records`.

## 1. Performance after ranking upsets

**Historical primary analysis.** We did not find clear evidence that the upset-related difference varied with age or prior recorded match experience. This does not show that all players recover identically. After a ranking upset, adjusted next-three-match performance differed from ordinary losses by -1.37 pp (95% interval -2.24 to -0.51 pp) across 18,471 complete, covariate-usable loss events from 341 players. The next-match difference was -1.46 pp (95% interval -2.84 to -0.07 pp). Age modification was +0.03 pp (95% interval -0.29 to +0.35 pp) per year; experience modification was +1.08 pp (95% interval -0.50 to +2.66 pp) per unit of log(1 + prior matches). For age, the interval includes zero; for experience, the interval includes zero. Interpret the joint age and experience interactions using their intervals, rather than treating descriptive age bands as experience groups. Adjustment includes subsequent playing context, so this is a conditional association, not a causal recovery effect.

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

**Historical primary analysis.** On 11,340 held-out matches, meeting count alone changed Brier performance by -0.000021 (95% interval -0.000091 to +0.000039); the interval includes zero. Adding previous head-to-head results changed Brier performance by +0.000586 (95% interval +0.000095 to +0.001019). Positive improvement means lower prediction error; for previous results, the interval is above zero. Meeting count and previous outcomes answer different questions. Pair-cluster intervals leave shared-player dependence across pairs unresolved.

Source: [`q2_paired_improvements.csv`](../outputs_final/q2_paired_improvements.csv), metric=brier; first_model=baseline; run `20261027T121134Z-20f069d1`.

| model | test_matches | brier_score | log_loss | accuracy |
| --- | --- | --- | --- | --- |
| baseline | 11340 | 0.216957 | 0.622392 | 0.646561 |
| plus_meeting_count | 11340 | 0.216979 | 0.622421 | 0.647531 |
| plus_h2h_results | 11340 | 0.216371 | 0.620970 | 0.648148 |

Source: [`q2_model_metrics.csv`](../outputs_final/q2_model_metrics.csv), meeting_group=all; run `20261027T121134Z-20f069d1`.

Training used 52,444 matches, with a 21-day exclusion gap before 2020; test seasons were 2020–2024. Parameters and preprocessing remain frozen. Earlier test-period results update later pre-match histories. Meeting count is shared by both players and does not inherently favor either one. No test-driven tuning was performed. Source: [`run_summary.json`](../outputs_final/run_summary.json), `q2`.

The same generated table contains results by zero, one, two-to-four and five-plus prior meetings. [`q2_paired_improvements.csv`](../outputs_final/q2_paired_improvements.csv) includes paired Brier, log-loss and accuracy intervals for all three model comparisons. [`q2_calibration.csv`](../outputs_final/q2_calibration.csv) gives fixed-bin denominators and observed versus predicted rates.

### Supplemental Q1/Q2 validation

Later validation of unchanged source run `20261027T121134Z-20f069d1`: exact Q1 samples/coefficients and original Q2 prediction results were reproduced. [Checks and settings](../validation/q1_q2_checks/summary.json) · [Separate provenance](../validation/q1_q2_checks/manifest.json).

**Q1: separate the questions.** The primary overall upset-minus-ordinary difference remains -1.37 pp (95% interval -2.24 to -0.51 pp). Interactions measure changes in that difference; post-upset slopes measure age/experience associations within upset cases. Uncertain interactions do not imply zero post-upset slopes.

Post-upset slopes sum the existing main and upset-interaction coefficients, using `Vaa + Vbb + 2Vab`, original player-cluster covariance and t(players−1) intervals. Units are percentage points per age year or natural-log(1 + prior eligible recorded matches) unit, holding other predictors fixed. Counts below are model-wide; [full contrasts](../validation/q1_q2_checks/q1_post_upset_contrasts.csv) include upset-only support, SEs and separate interaction rows:

| Outcome | Sample | Events / players | Age, pp/year (95% interval) | Experience, pp/log unit (95% interval) |
| --- | --- | --- | --- | --- |
| Next three (primary) | all_windows | 18,471 / 341 | -1.43 pp (95% interval -1.81 to -1.04 pp) | +7.73 pp (95% interval +5.95 to +9.51 pp) |
| Next match (secondary) | all_windows | 21,206 / 345 | -1.85 pp (95% interval -2.34 to -1.37 pp) | +9.47 pp (95% interval +7.00 to +11.94 pp) |
| Next three (primary) | nonoverlapping | 9,684 / 341 | -1.49 pp (95% interval -1.92 to -1.05 pp) | +7.74 pp (95% interval +5.68 to +9.80 pp) |
| Next match (secondary) | nonoverlapping | 16,263 / 345 | -1.80 pp (95% interval -2.40 to -1.20 pp) | +8.85 pp (95% interval +5.99 to +11.70 pp) |

Next three (primary): age has a negative conditional association. Next three (primary): prior experience has a positive conditional association. Next match (secondary): age has a negative conditional association. Next match (secondary): prior experience has a positive conditional association.

The separate primary next-three interactions are +0.03 pp (95% interval -0.29 to +0.35 pp) per age year and +1.08 pp (95% interval -0.50 to +2.66 pp) per log-experience unit. The nonoverlapping rows use the existing sensitivity rule and model.

**Q1 support/selection.** Among 24,021 common top-50, known-rank losses (345 players), only 52 combine age under 23 with 300+ prior matches, and 34 combine age 30+ with fewer than 100. The primary design is full rank (40/40), but age/log-experience correlation is 0.709; sparse combinations limit practical overlap. [Cross-tabulations](../validation/q1_q2_checks/q1_support.csv) and [conditioning diagnostics](../validation/q1_q2_checks/q1_model_diagnostics.csv) document this without an arbitrary failure cutoff.

| Loss type | Index events / players | Usable next match | Complete next three | Adjusted next match | Adjusted next three |
| --- | --- | --- | --- | --- | --- |
| other_ranked_loss | 16,485 / 339 | 14550 | 12661 | 14524 | 12610 |
| ranking_upset | 7,536 / 326 | 6695 | 5885 | 6682 | 5861 |

For next-three windows, 77 events lack enough recorded follow-ups, 0 are blocked by unresolved records, 5,398 contain excluded/ambiguous follow-ups, and 75 otherwise available windows lack model covariates. End of recorded history does not establish retirement or administrative study-end censoring. Missing outcomes stay missing. Omitted cases have stronger mean pre-loss rankings (26.05 versus 27.89; lower is better) and higher recent form (0.604 versus 0.589). [Group retention denominators/reasons](../validation/q1_q2_checks/q1_retention.csv) and [age/experience, rank and form distributions](../validation/q1_q2_checks/q1_distributions.csv) therefore warrant caution about selection.

**Q2: paired prediction-error differences.** Positive Brier improvement means lower prediction error for the second model, not a percentage-point rise in winning chances. REPEAT uses `prior_h2h_meetings >= 1`; FIRST uses zero prior meetings. Both methods use the same paired differences and frozen predictions, without subset refits:

| Subset | Comparison | Matches / players / pairs | Brier improvement | Pair bootstrap 95% | Shared-player dyadic 95% |
| --- | --- | --- | --- | --- | --- |
| ALL | Baseline → count | 11,340 / 512 / 7,824 | -0.000021 | [-0.000091, +0.000039] | [-0.000065, +0.000022] |
| ALL | Baseline → H2H results | 11,340 / 512 / 7,824 | +0.000586 | [+0.000095, +0.001019] | [+0.000149, +0.001023] |
| ALL | Count → H2H results | 11,340 / 512 / 7,824 | +0.000607 | [+0.000113, +0.001039] | [+0.000174, +0.001041] |
| REPEAT | Baseline → count | 4,880 / 258 / 3,022 | -0.000048 | [-0.000133, +0.000021] | [-0.000121, +0.000024] |
| REPEAT | Baseline → H2H results | 4,880 / 258 / 3,022 | +0.001056 | [+0.000093, +0.001883] | [+0.000058, +0.002054] |
| REPEAT | Count → H2H results | 4,880 / 258 / 3,022 | +0.001105 | [+0.000128, +0.001943] | [+0.000115, +0.002094] |
| FIRST | Baseline → count | 6,460 / 510 / 6,460 | -0.000001 | [-0.000097, +0.000086] | [-0.000086, +0.000084] |
| FIRST | Baseline → H2H results | 6,460 / 510 / 6,460 | +0.000231 | [+0.000096, +0.000378] | [+0.000060, +0.000402] |
| FIRST | Count → H2H results | 6,460 / 510 / 6,460 | +0.000232 | [+0.000102, +0.000371] | [+0.000083, +0.000381] |

The added dyadic sandwich accounts for either shared player and repeated pairs, with 1/n² mean scaling, no finite-sample multiplier and normal intervals. Insufficient support or invalid variance withholds inference. The original pair bootstrap uses 500 draws, seed 42. [Paired estimates/SEs/statuses](../validation/q1_q2_checks/q2_comparisons.csv), [Brier and secondary scores](../validation/q1_q2_checks/q2_scores.csv), and [original finer groups](../outputs_final/q2_model_metrics.csv) are retained. First-meeting gains can reflect different global fitted coefficients, not benefits from nonexistent prior meetings.

ALL, Baseline → count: both methods leave the direction uncertain. ALL, Baseline → H2H results: both methods support lower prediction error. REPEAT, Baseline → count: both methods leave the direction uncertain. REPEAT, Baseline → H2H results: both methods support lower prediction error.

**Chronology and remaining limits.** The existing screen flags candidate-event exposure in 3,222/18,471 primary Q1 windows for their focal player, 565/11,340 Q2 evaluation matches for either participant, and 2,387/11,340 Q2 matches through either player’s last-ten eligible history. [Traceable counts](../validation/q1_q2_checks/chronology_summary.csv) use tournament-week/round order, not verified match dates. These are candidate overlaps, not proven errors; no dates or replacement windows were invented.

Q1 remains a complete-case conditional association. Focal-player clustering does not remove follow-up selection, persistent player-level confounding or all shared-opponent dependence; adjustment for subsequent context prevents a simple causal recovery interpretation. Match outcomes do not measure psychological recovery. Q2 dyadic intervals assume negligible dependence between disjoint pairs; tournament shocks may remain. Both Q2 methods condition on fitted models/period, omit training uncertainty, and do not establish causal or universal gains or performance in a new era. The existing primary results and Q3 validation are preserved.

Separate validation: `q1-q2-checks-20261116T222522Z`; [validation manifest](../validation/q1_q2_checks/manifest.json).


## 3. Does opponent handedness matter?

**Primary analysis.** We found no clear evidence of an adjusted difference against left- versus right-handed opponents in either focal-hand group. Adjusted opponent-left-minus-right win-probability differences were +1.11 pp (95% interval -0.86 to +3.08 pp) for 365 right-handed focal players and +0.99 pp (95% interval -0.63 to +2.62 pp) for 55 left-handed focal players. For right-handed players, the interval includes zero; for left-handed players, the interval includes zero. The results do not establish a uniform handedness advantage. Dyadic intervals account for matches sharing either participant; the smaller left-handed subgroup and remaining event/network dependence warrant caution.

Source: [`q3_adjusted_contrasts.csv`](../outputs_final/q3_adjusted_contrasts.csv), method=dyadic_primary; player_hand=R and L; run `20261027T121134Z-20f069d1`.

The adjusted sample has 61,412 unique physical matches and 112,503 focal-player rows from 420 players. Subgroup match counts overlap when both views of a match qualify. Source: [`run_summary.json`](../outputs_final/run_summary.json), `q3`.

These equal-player service and match summaries are **unadjusted**, not evidence of a controlled handedness effect:

| player_hand | players | mean_player_win_difference_pp | service_eligible_players | mean_player_service_difference_pp | service_points_vs_L | service_points_vs_R |
| --- | --- | --- | --- | --- | --- | --- |
| L | 56 | 1.672 | 56 | -0.126 | 149,398.000 | 1,025,885.000 |
| R | 371 | 3.445 | 370 | 0.869 | 1,058,530.000 | 6,961,834.000 |

Source: [`q3_descriptive_contrasts.csv`](../outputs_final/q3_descriptive_contrasts.csv), all rows; run `20261027T121134Z-20f069d1`.

The original player-by-match covariance still has 1 negative coefficient variance term(s). It is retained as a sensitivity with unavailable affected intervals, never replaced by zero or an absolute value. The primary dyadic method uses dependence through either player and includes absorbed fixed-effect degrees of freedom. Left-handed contrasts use the coefficient sum and **the full covariance including its cross term**. See [`q3_inference_sensitivity.csv`](../outputs_final/q3_inference_sensitivity.csv), [`q3_subgroup_support.csv`](../outputs_final/q3_subgroup_support.csv), and [`q3_player_influence.csv`](../outputs_final/q3_player_influence.csv).

### Opponent comparability

Unequal counts do not automatically invalidate this comparison. Ranking and prior-form adjustment are already present, but do not guarantee comparable observations. This separate check reconstructs the exact adjusted sample: 11,071 player × surface × season strata, with 14,851 left-opponent and 97,652 right-opponent observations (61,412 physical matches; 420 focal players). Player-match observations, physical matches, focal players and distinct opponents are counted separately in the [detailed check](../validation/q3_comparability/DETAILS.md); totals across groups overlap.

Left-opponent historical rank has median 57 (middle half 33–95), versus 51 (22–88) for right opponents; lower rank numbers indicate higher rankings. 6,271/11,071 strata contain both hands, covering 14,579/14,851 (98.2%) left and 78,743/97,652 (80.6%) right observations. 5,608 both-hand strata have fewer than five observations in at least one hand; 1,091 have no pair meeting both rank calipers. Sparse observations and absent comparable observations are different limitations. Only 78.5% of left and 32.1% of right observations have such a candidate. A shared season does not ensure identical conditions.

Coverage remained uncertain, so **one matched sensitivity** used the [outcome-blind recorded rule](../validation/q3_comparability/protocol.json): same player, surface and season; both focal and opponent ranks within a factor of 1.5; nearest summed log-rank differences, without replacement, with stable-ID ties. The caliper is pragmatic, not universal. Original opportunity/support checks and shared-player dyadic uncertainty were retained. The refit retains 21,266 observations, 19,499 physical matches and 330 players: 71.6% of original left-opponent and 10.9% of right-opponent observations. See [retention by focal hand](../validation/q3_comparability/retention.csv).

| Focal hand | Primary L-minus-R | Matched sensitivity |
| --- | --- | --- |
| R | +1.11 pp (95% interval -0.86 to +3.08 pp) | +0.62 pp (95% interval -1.18 to +2.42 pp) |
| L | +0.99 pp (95% interval -0.63 to +2.62 pp) | -0.13 pp (95% interval -3.20 to +2.94 pp) |

Right-handed: the point estimate keeps its direction; the interval is narrower and includes zero. Left-handed: the point estimate changes direction; the interval is wider and includes zero.

The mean log-opponent-rank gap (L-minus-R) falls from 0.163 to 0.000. Prior-form gaps fall from -0.009 to -0.002 for focal players and -0.024 to -0.008 for opponents. Form is a prior win proportion; see [full rank/form balance](../validation/q3_comparability/balance.csv).

The matched covariance matrix is indefinite; both reported contrast variances are positive. Under the unchanged safeguards their intervals remain available but exploratory; no variance repair was applied.

Rankings imperfectly measure strength; restrictions select a narrower sample and do not remove all form or playing-condition differences. This remains observational, not causal. **Primary Q1/Q2/Q3 results are preserved.** [Normalized rank plot](../validation/q3_comparability/rank_distributions.png) · [Within-player coverage](../validation/q3_comparability/within_player_coverage.png) · [Summary table](../validation/q3_comparability/compact_summary.csv) · [Detailed distributions and limitations](../validation/q3_comparability/DETAILS.md) · [Validation provenance](../validation/q3_comparability/manifest.json).

Separate validation: `q3-comparability-20261110T065912Z`; [validation manifest](../validation/q3_comparability/manifest.json).


## Interpretation limits

These are exploratory observational results. Ranking upsets are a ranking-based operational definition, not a measure of surprise or psychological recovery. Tournament-week dates and checked rounds approximate chronology; exact match days and recovery durations are unavailable. Missing follow-up is missing, never zero wins. Player and pair intervals do not remove every source of dependence, selection bias or unmeasured confounding. All thresholds, including rank gaps 20, 30 and 50, are reported rather than selected for a preferred finding.
