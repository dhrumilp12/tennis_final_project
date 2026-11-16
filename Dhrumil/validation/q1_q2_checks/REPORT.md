Later validation of unchanged source run `20261027T121134Z-20f069d1`: exact Q1 samples/coefficients and original Q2 prediction results were reproduced. [Checks and settings](summary.json) · [Separate provenance](manifest.json).

**Q1: separate the questions.** The primary overall upset-minus-ordinary difference remains -1.37 pp (95% interval -2.24 to -0.51 pp). Interactions measure changes in that difference; post-upset slopes measure age/experience associations within upset cases. Uncertain interactions do not imply zero post-upset slopes.

Post-upset slopes sum the existing main and upset-interaction coefficients, using `Vaa + Vbb + 2Vab`, original player-cluster covariance and t(players−1) intervals. Units are percentage points per age year or natural-log(1 + prior eligible recorded matches) unit, holding other predictors fixed. Counts below are model-wide; [full contrasts](q1_post_upset_contrasts.csv) include upset-only support, SEs and separate interaction rows:

| Outcome | Sample | Events / players | Age, pp/year (95% interval) | Experience, pp/log unit (95% interval) |
| --- | --- | --- | --- | --- |
| Next three (primary) | all_windows | 18,471 / 341 | -1.43 pp (95% interval -1.81 to -1.04 pp) | +7.73 pp (95% interval +5.95 to +9.51 pp) |
| Next match (secondary) | all_windows | 21,206 / 345 | -1.85 pp (95% interval -2.34 to -1.37 pp) | +9.47 pp (95% interval +7.00 to +11.94 pp) |
| Next three (primary) | nonoverlapping | 9,684 / 341 | -1.49 pp (95% interval -1.92 to -1.05 pp) | +7.74 pp (95% interval +5.68 to +9.80 pp) |
| Next match (secondary) | nonoverlapping | 16,263 / 345 | -1.80 pp (95% interval -2.40 to -1.20 pp) | +8.85 pp (95% interval +5.99 to +11.70 pp) |

Next three (primary): age has a negative conditional association. Next three (primary): prior experience has a positive conditional association. Next match (secondary): age has a negative conditional association. Next match (secondary): prior experience has a positive conditional association.

The separate primary next-three interactions are +0.03 pp (95% interval -0.29 to +0.35 pp) per age year and +1.08 pp (95% interval -0.50 to +2.66 pp) per log-experience unit. The nonoverlapping rows use the existing sensitivity rule and model.

**Q1 support/selection.** Among 24,021 common top-50, known-rank losses (345 players), only 52 combine age under 23 with 300+ prior matches, and 34 combine age 30+ with fewer than 100. The primary design is full rank (40/40), but age/log-experience correlation is 0.709; sparse combinations limit practical overlap. [Cross-tabulations](q1_support.csv) and [conditioning diagnostics](q1_model_diagnostics.csv) document this without an arbitrary failure cutoff.

| Loss type | Index events / players | Usable next match | Complete next three | Adjusted next match | Adjusted next three |
| --- | --- | --- | --- | --- | --- |
| other_ranked_loss | 16,485 / 339 | 14550 | 12661 | 14524 | 12610 |
| ranking_upset | 7,536 / 326 | 6695 | 5885 | 6682 | 5861 |

For next-three windows, 77 events lack enough recorded follow-ups, 0 are blocked by unresolved records, 5,398 contain excluded/ambiguous follow-ups, and 75 otherwise available windows lack model covariates. End of recorded history does not establish retirement or administrative study-end censoring. Missing outcomes stay missing. Omitted cases have stronger mean pre-loss rankings (26.05 versus 27.89; lower is better) and higher recent form (0.604 versus 0.589). [Group retention denominators/reasons](q1_retention.csv) and [age/experience, rank and form distributions](q1_distributions.csv) therefore warrant caution about selection.

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

The added dyadic sandwich accounts for either shared player and repeated pairs, with 1/n² mean scaling, no finite-sample multiplier and normal intervals. Insufficient support or invalid variance withholds inference. The original pair bootstrap uses 500 draws, seed 42. [Paired estimates/SEs/statuses](q2_comparisons.csv), [Brier and secondary scores](q2_scores.csv), and [original finer groups](../../outputs_final/q2_model_metrics.csv) are retained. First-meeting gains can reflect different global fitted coefficients, not benefits from nonexistent prior meetings.

ALL, Baseline → count: both methods leave the direction uncertain. ALL, Baseline → H2H results: both methods support lower prediction error. REPEAT, Baseline → count: both methods leave the direction uncertain. REPEAT, Baseline → H2H results: both methods support lower prediction error.

**Chronology and remaining limits.** The existing screen flags candidate-event exposure in 3,222/18,471 primary Q1 windows for their focal player, 565/11,340 Q2 evaluation matches for either participant, and 2,387/11,340 Q2 matches through either player’s last-ten eligible history. [Traceable counts](chronology_summary.csv) use tournament-week/round order, not verified match dates. These are candidate overlaps, not proven errors; no dates or replacement windows were invented.

Q1 remains a complete-case conditional association. Focal-player clustering does not remove follow-up selection, persistent player-level confounding or all shared-opponent dependence; adjustment for subsequent context prevents a simple causal recovery interpretation. Match outcomes do not measure psychological recovery. Q2 dyadic intervals assume negligible dependence between disjoint pairs; tournament shocks may remain. Both Q2 methods condition on fitted models/period, omit training uncertainty, and do not establish causal or universal gains or performance in a new era. The existing primary results and Q3 validation are preserved.
