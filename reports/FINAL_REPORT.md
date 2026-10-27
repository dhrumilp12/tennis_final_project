# Digital Archeology of ATP Match Histories

**Team:** Phouvadeth Vathana, Joseph Bronyah, Dhrumil Patel

Run ID: `20261027T121134Z-20f069d1`. Generated from verified outputs; all numerical claims below refer to this run.

## Objectives and motivation

Historical sports records allow us to reconstruct the information available before successive matches. We ask whether performance after ranking upsets varies with age and observed experience; whether previous meetings add predictive information beyond strength, form and surface; and whether within-player results differ against left- and right-handed opponents. These are observational and predictive questions, not measurements of psychological recovery or causal effects.

## Data and acquisition

Annual ATP singles files cover the 2000–2024 study period and a 1990–1999 warm-up. Jeff Sackmann compiled the data; the Aneeshers archival mirror supplies revision `83733587353df8a41f2fd4f516147d5aa83f5a8d`. The run read 35 annual files, 112,056 raw records and 63,784 eligible study matches. The cache preserves source bytes, pinned URLs, SHA-256 hashes and retrieval records. This run used existing cached files offline. Source: [`run_summary.json`](../outputs_final/run_summary.json), `inputs`, `configuration.offline`, and raw/eligible counts.

The code is MIT-licensed under `LICENSE`; the data and derived data retain the separate CC BY-NC-SA 4.0 attribution in `DATA_LICENSE.txt`. The project uses match-level annual ATP data. No betting odds, point-level charting data, dashboard or deep-learning model is used. See [SOURCES.md](../SOURCES.md).

## Cleaning and history reconstruction

We preserve source-file/row references, remove exact duplicate records, and exclude conflicting keys, invalid identities, missing dates, unrecognized or unfinished scores, unsupported ordering, and events outside individual A/M/G knockout scope. Retirement, walkover and team-event exclusions remain in the event sequence when identities/dates are usable. Invalid service totals are masked independently of match eligibility. The completion screen is not a full tennis-score validator.

Tournament dates describe tournament weeks, not match days. Checked round order and synchronous feature updates avoid using arbitrary match numbers or CSV positions. Unresolved records are retained in a blocker ledger so later matches cannot silently substitute for the next recorded matches. Same-date and unsupported-round ambiguity is flagged; uncertain cross-event overlap remains a limitation. [DATA_QUALITY.md](DATA_QUALITY.md) contains mutually exclusive attrition, overlapping flags, coverage, missingness and traceable spot checks.

Two player perspectives preserve each side's pre-match history. Experience counts earlier eligible recorded matches since 1990, with up to ten earlier results for form. Head-to-head history includes only previous eligible meetings. Q2 retains exactly one outcome-independent orientation: the lower numeric player ID is Player A. Both views used in Q3 are dependent observations, accounted for explicitly in inference. See [DATA_DICTIONARY.md](../docs/DATA_DICTIONARY.md).

## Methods

**Q1.** A ranking upset is a top-50 player losing to an opponent at least 30 ranking places lower. Upset and ordinary losses are compared within the same top-50, known-ranks population. Outcomes are the next recorded match result and the mean win indicator over the next three recorded matches when all are eligible and resolved. Missing or unusable follow-up stays missing. Age and experience have separate descriptive groupings, and both enter the adjusted model continuously with upset interactions. Controls include initial rank, recent form, initial surface/season, and following-opponent strength, surface and match format. OLS estimates probability-point differences; focal-player cluster covariance and t critical values account for repeated/overlapping windows within players. Full-covariance standardized contrasts average each fitted upset difference over the stated sample. Subsequent-context adjustment changes the estimand to a conditional association.

**Q2.** Three prespecified logistic models use strength, age/experience differences, recent form, surface, round, format, level and both hands: baseline; baseline plus shared meeting count; and baseline plus count and previous head-to-head results. Median imputation, scaling and category encoding fit training data only. A chronological split uses training before 2020 with a 21-day boundary gap, and the same 2020–2024 test matches for all models. Current scores, service statistics, winner labels and follow-up outcomes are excluded from predictors. Earlier test results can update later histories while fitted parameters stay frozen. Brier score and log loss assess probability predictions; accuracy is secondary. Paired opponent-pair bootstrap intervals use 500 seeded resamples, with remaining cross-pair shared-player dependence acknowledged. No repeated tuning on inspected test performance was performed.

**Q3.** Known-hand player views are compared within player. The descriptive minimum is ten opportunities against each opponent hand; service differences independently require ten valid service-stat matches per hand. Adjustment requires complete strength/age/form covariates and the opportunity minimum after filtering. A within-player linear probability model absorbs player intercepts and adjusts rank advantage, age, experience, each side's form, surface and season, including opponent-hand × focal-hand interaction. The within design has rank 34 of 34 columns, with 420 absorbed player intercepts. Source: [`run_summary.json`](../outputs_final/run_summary.json), `q3`.

The original focal-player × physical-match covariance omitted cross-role/shared-opponent dependence and produced a negative interaction variance with the design rank reported above. Primary inference now uses the [shared-player dyadic sandwich of Aronow, Samii and Assenova](https://arxiv.org/abs/1312.3398): sum score vectors per unordered pair, sum incident pair scores per player, and subtract pair outer products from node outer products to remove double counting. Repeat meetings and complementary views remain in the same dyads. The finite-sample factor includes absorbed player intercepts. This covariance change addresses dependence structure; it was not selected to obtain significance. No negative variance is clipped, absolutized or replaced with zero. Right-handed contrast is the opponent-left coefficient; left-handed contrast adds the interaction using the full covariance. These remain exploratory normal intervals under assumptions about disjoint dyads.

## Findings

### Performance following ranking upsets

After a ranking upset, adjusted next-three-match performance differed from ordinary losses by -1.37 pp (95% interval -2.24 to -0.51 pp) across 18,471 complete, covariate-usable loss events from 341 players. The next-match difference was -1.46 pp (95% interval -2.84 to -0.07 pp). Age modification was +0.03 pp (95% interval -0.29 to +0.35 pp) per year; experience modification was +1.08 pp (95% interval -0.50 to +2.66 pp) per unit of log(1 + prior matches). For age, the interval includes zero; for experience, the interval includes zero. Interpret the joint age and experience interactions using their intervals, rather than treating descriptive age bands as experience groups. Adjustment includes subsequent playing context, so this is a conditional association, not a causal recovery effect.

Source: [`q1_adjusted_contrasts.csv`](../outputs_final/q1_adjusted_contrasts.csv), sample=all_windows, subgroup=all; run `20261027T121134Z-20f069d1`.

### Previous meetings and prediction

On 11,340 held-out matches, meeting count alone changed Brier performance by -0.000021 (95% interval -0.000091 to +0.000039); the interval includes zero. Adding previous head-to-head results changed Brier performance by +0.000586 (95% interval +0.000095 to +0.001019). Positive improvement means lower prediction error; for previous results, the interval is above zero. Meeting count and previous outcomes answer different questions. Pair-cluster intervals leave shared-player dependence across pairs unresolved.

Source: [`q2_paired_improvements.csv`](../outputs_final/q2_paired_improvements.csv), metric=brier, first_model=baseline; run `20261027T121134Z-20f069d1`.

| model | test_matches | brier_score | log_loss | accuracy |
| --- | --- | --- | --- | --- |
| baseline | 11340 | 0.216957 | 0.622392 | 0.646561 |
| plus_meeting_count | 11340 | 0.216979 | 0.622421 | 0.647531 |
| plus_h2h_results | 11340 | 0.216371 | 0.620970 | 0.648148 |

Source: [`q2_model_metrics.csv`](../outputs_final/q2_model_metrics.csv), meeting_group=all; run `20261027T121134Z-20f069d1`.

### Opponent handedness

Adjusted opponent-left-minus-right win-probability differences were +1.11 pp (95% interval -0.86 to +3.08 pp) for 365 right-handed focal players and +0.99 pp (95% interval -0.63 to +2.62 pp) for 55 left-handed focal players. For right-handed players, the interval includes zero; for left-handed players, the interval includes zero. The results do not establish a uniform handedness advantage. Dyadic intervals account for matches sharing either participant; the smaller left-handed subgroup and remaining event/network dependence warrant caution.

Source: [`q3_adjusted_contrasts.csv`](../outputs_final/q3_adjusted_contrasts.csv), method=dyadic_primary; run `20261027T121134Z-20f069d1`.

Unadjusted service comparisons use valid point totals and equal-player differences, separately from adjusted match-result estimates:

| player_hand | players | matches_vs_L | matches_vs_R | service_eligible_players | mean_player_service_difference_pp | service_points_vs_L | service_points_vs_R |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L | 56 | 1890 | 12759 | 56 | -0.126 | 149,398.000 | 1,025,885.000 |
| R | 371 | 13219 | 86506 | 370 | 0.869 | 1,058,530.000 | 6,961,834.000 |

Source: [`q3_descriptive_contrasts.csv`](../outputs_final/q3_descriptive_contrasts.csv), all rows; run `20261027T121134Z-20f069d1`.

## Sensitivity checks

Q1 retains rank-gap thresholds 20, 30 and 50 in [`q1_threshold_sensitivity.csv`](../outputs_final/q1_threshold_sensitivity.csv), with both loss types and age groups; these are descriptive checks, not a threshold search. Non-overlap sensitivity greedily selects the earliest available complete windows in sequence for each focal player without using its wins, forbids reuse of all index/follow-up IDs, and then applies covariate exclusions. Selection changes the sample. Estimates for both outcomes and their age/experience interactions are:

| outcome | sample | contrast | events | estimate_pp | ci95_lower_pp | ci95_upper_pp |
| --- | --- | --- | --- | --- | --- | --- |
| next3_win_rate | all_windows | average_upset_minus_ordinary | 18471 | -1.375 | -2.238 | -0.511 |
| next3_win_rate | all_windows | age_interaction_per_year | 18471 | 0.027 | -0.295 | 0.349 |
| next3_win_rate | all_windows | experience_interaction_log_unit | 18471 | 1.080 | -0.496 | 2.655 |
| next3_win_rate | nonoverlapping | average_upset_minus_ordinary | 9684 | -1.621 | -2.866 | -0.376 |
| next3_win_rate | nonoverlapping | age_interaction_per_year | 9684 | -0.079 | -0.505 | 0.346 |
| next3_win_rate | nonoverlapping | experience_interaction_log_unit | 9684 | 1.276 | -0.832 | 3.384 |
| next1_win | all_windows | average_upset_minus_ordinary | 21206 | -1.460 | -2.844 | -0.075 |
| next1_win | all_windows | age_interaction_per_year | 21206 | -0.497 | -1.026 | 0.033 |
| next1_win | all_windows | experience_interaction_log_unit | 21206 | 2.239 | -0.403 | 4.880 |
| next1_win | nonoverlapping | average_upset_minus_ordinary | 16263 | -1.744 | -3.383 | -0.106 |
| next1_win | nonoverlapping | age_interaction_per_year | 16263 | -0.434 | -1.045 | 0.176 |
| next1_win | nonoverlapping | experience_interaction_log_unit | 16263 | 1.612 | -1.291 | 4.515 |

Source: [`q1_adjusted_contrasts.csv`](../outputs_final/q1_adjusted_contrasts.csv), subgroup=all; run `20261027T121134Z-20f069d1`.

Q2 reports paired metrics and fixed calibration bins for all models, and metrics by previous-meeting group, without further parameter selection. See [RESULTS.md](RESULTS.md) and the generated calibration plot.

Q3 retains the original covariance, a tournament-only covariance, and a deterministic outcome-independent single-view/focal-player-cluster model as sensitivities. Tournament clustering alone misses serial player dependence; single-view clustering misses shared-opponent dependence and changes the sample.

| method | player_hand | players | difference_pp | ci95_lower_pp | ci95_upper_pp | inference_status |
| --- | --- | --- | --- | --- | --- | --- |
| legacy_player_match | R | 365 | 1.111 | 0.279 | 1.942 | available |
| legacy_player_match | L | 55 | 0.993 | 0.627 | 1.360 | available |
| tournament_only | R | 365 | 1.111 | 0.325 | 1.897 | available |
| tournament_only | L | 55 | 0.993 | -0.154 | 2.141 | available |
| single_hash_view_player_cluster | R | 237 | 0.430 | -0.864 | 1.723 | available |
| single_hash_view_player_cluster | L | 34 | 1.374 | -0.968 | 3.715 | available |

Source: [`q3_inference_sensitivity.csv`](../outputs_final/q3_inference_sensitivity.csv), all rows; run `20261027T121134Z-20f069d1`.

To examine concentration, the five most exposed focal players of each hand are selected by exposure, not outcomes. Each is removed in either participant role, opportunity minima are reapplied, and fixed effects are refitted. The resulting point-estimate ranges are:

| player_hand | min | max |
| --- | --- | --- |
| L | 0.903 | 1.681 |
| R | 1.015 | 2.057 |

Source: [`q3_player_influence.csv`](../outputs_final/q3_player_influence.csv), grouped by player_hand, min/max difference_pp; point estimates only, no deletion confidence intervals; run `20261027T121134Z-20f069d1`.

Subgroup support and concentration are explicit:

| sample | player_hand | opponent_hand | player_match_rows | unique_matches | players | opponents | opponent_pairs | tournaments | largest_player_share | top5_player_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adjusted | L | L | 1850 | 1036 | 55 | 120 | 602 | 663 | 0.069 | 0.282 |
| adjusted | L | R | 12549 | 12549 | 55 | 760 | 6423 | 1554 | 0.084 | 0.304 |
| adjusted | R | L | 13001 | 13001 | 365 | 173 | 6802 | 1568 | 0.012 | 0.054 |
| adjusted | R | R | 85103 | 46338 | 365 | 1052 | 24605 | 1585 | 0.014 | 0.054 |

Source: [`q3_subgroup_support.csv`](../outputs_final/q3_subgroup_support.csv), sample=adjusted; run `20261027T121134Z-20f069d1`.

The deletion ranges show how high-exposure participants can affect the magnitude; they are not confidence intervals or evidence of a universal effect. The smaller left-handed group has fewer players and larger exposure concentration. Neither a handful of prominent players nor these average associations establishes a universal handedness effect.

## Limitations and warnings

- **Q1**: Follow-up context adjustment estimates a conditional association; focal-player clustering does not cover all shared-opponent dependence.
- **Q2**: Paired intervals cluster opponent pairs; shared-player dependence across pairs remains.
- **Q3**: Legacy player-by-match covariance has negative coefficient variance(s); affected intervals are unavailable. Primary dyadic covariance clusters through either participant.
- **Q3**: Dyadic intervals assume no residual dependence between disjoint player pairs; tournament-wide shocks and indirect network dependence may remain. Tournament-only sensitivity does not address serial player dependence.
- **Q3**: Left-handed subgroup support is smaller; asymptotic intervals and the exposure-based deletion checks do not establish uniform effects across players.

Additional limitations include source incompleteness/errors, selected ATP scope, left-truncated history, nonrandom follow-up/covariate missingness, coarse chronology, a ranking-based upset definition, and unmeasured conditions or injuries. The models are exploratory; multiple contrasts are not multiplicity-adjusted. Q1's post-index controls preclude a simple causal interpretation. A linear probability model can predict outside zero to one and is used for conditional mean contrasts. Q2 uses an already inspected holdout and its small gain needs future independent replication. Dyadic Q3 inference assumes no remaining dependence between disjoint player pairs; tournament-wide shocks and indirect network dependence can violate that assumption. Available uncertainty is not proof that every analysis is definitive.

## Reproducibility and sources

Use the commands in [README.md](../README.md). [`run_summary.json`](../outputs_final/run_summary.json) records run ID/timestamps, configuration, actual inputs, source revision, code hashes, git base/dirty state, package versions, analysis warnings and output hashes. Results were staged and hash-verified before publication; the original saved `outputs/` remain intact. The actual environment is also frozen in `requirements-lock.txt`. [TEST_RESULTS.md](../TEST_RESULTS.md) distinguishes full-data execution, real-demo smoke testing and explicitly synthetic regressions. The executed [Tennis_Project.ipynb](../Tennis_Project.ipynb) uses the same modules and final output directory; its displayed findings are read from the same tables. [SOURCES.md](../SOURCES.md), [DATA_LICENSE.txt](../DATA_LICENSE.txt), [METHODS.md](../docs/METHODS.md), and [DATA_QUALITY.md](DATA_QUALITY.md) provide the source, method and audit details.
