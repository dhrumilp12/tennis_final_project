This separate validation uses the exact adjusted Q3 sample from run `20261027T121134Z-20f069d1`: 112,503 player-match observations, 61,412 physical matches and 420 focal players. Two views of a match are dependent; match/player/opponent totals across groups can overlap and must not be added as independent observations.

Unequal group sizes are not automatically a problem. The primary model already adjusts for rank advantage and both players’ prior recent form, but adjustment does not ensure comparable opponents. Only saved historical rankings are used; missing ranks are not invented.

| opponent_hand | player_match_rows | unique_matches | focal_players | distinct_opponents |
| --- | --- | --- | --- | --- |
| L | 14851 | 14037 | 420 | 176 |
| R | 97652 | 58887 | 420 | 1076 |

Within focal-player × surface × calendar-season strata, 6,271/11,071 contain both hands; 4,800 contain only one (237 left-only, 4,563 right-only). Both-hand strata cover 14,579/14,851 (98.2%) left-opponent observations and 78,743/97,652 (80.6%) right-opponent observations. 5,608 both-hand strata have fewer than five observations in at least one group (insufficient for a useful distribution comparison, not necessarily no possible comparison). 1,091 both-hand strata have no pair satisfying both rank calipers. A shared season is a diagnostic restriction, not proof of identical playing conditions.

A same-stratum counterpart within a factor of 1.5 on **both** focal and opponent rank exists for 11,660/14,851 (78.5%) left-opponent and 31,356/97,652 (32.1%) right-opponent observations. These are candidate counts before competition for matches without replacement; ranges alone were not used to declare overlap.

Historical rank distributions (median and quartiles; complete quantiles and focal-hand/surface/season breakdowns are linked below):

| opponent_hand | measure | nonmissing | q25 | q50 | q75 |
| --- | --- | --- | --- | --- | --- |
| L | player_rank | 14851 | 22.00 | 49.00 | 83.00 |
| L | opponent_rank | 14851 | 33.00 | 57.00 | 95.00 |
| L | log_rank_advantage | 14851 | -0.62 | 0.21 | 1.09 |
| R | player_rank | 97652 | 22.00 | 47.00 | 80.00 |
| R | opponent_rank | 97652 | 22.00 | 51.00 | 88.00 |
| R | log_rank_advantage | 97652 | -0.85 | 0.10 | 1.02 |

Among strata with at least five observations per hand, the table below gives equally weighted stratum diagnostics. ECDF distance is the largest gap between normalized cumulative distributions (0 means identical empirical distributions; 1 means fully separated). These descriptive distances can be noisy in small strata and are not significance tests. Overlapping middle halves alone do not establish comparability.

| measure | strata_with_at_least_5_per_hand | strata_with_overlapping_middle_50_percent | median_within_stratum_ECDF_distance | median_absolute_within_stratum_median_difference |
| --- | --- | --- | --- | --- |
| player_rank | 663 | 645 | 0.282 | 2.000 |
| opponent_rank | 663 | 626 | 0.378 | 16.500 |
| log_rank_advantage | 663 | 623 | 0.375 | 0.357 |

Coverage remains uncertain, so one sensitivity was run under the [rule recorded before fitting](protocol.json). It pairs left- and right-opponent observations for the same focal player, surface and calendar season; each absolute log-rank difference must be ≤ log(1.5). Candidates are chosen by the sum of the two differences, without replacement within a player, with stable match-ID traversal and ties. The factor 1.5 is pragmatic, not a universal standard. Outcomes do not select pairs, and no alternative calipers were searched. The original minimum of ten opportunities per hand is reapplied after matching.

| player_hand | opponent_hand | player_match_rows | original_player_match_rows | player_match_rows_retained_share | focal_players | unique_matches |
| --- | --- | --- | --- | --- | --- | --- |
| all | L | 10633 | 14851 | 0.716 | 330 | 10219 |
| all | R | 10633 | 97652 | 0.109 | 330 | 10151 |
| R | L | 9359 | 13001 | 0.720 | 290 | 9359 |
| R | R | 9359 | 85103 | 0.110 | 290 | 8877 |
| L | L | 1274 | 1850 | 0.689 | 40 | 860 |
| L | R | 1274 | 12549 | 0.102 | 40 | 1274 |

For right-handed focal players, the primary L-minus-R estimate is +1.11 pp (95% interval -0.86 to +3.08 pp); the matched sensitivity is +0.62 pp (95% interval -1.18 to +2.42 pp). The point estimates have the same direction. The matched interval is narrower. The matched interval includes zero.

For left-handed focal players, the primary L-minus-R estimate is +0.99 pp (95% interval -0.63 to +2.62 pp); the matched sensitivity is -0.13 pp (95% interval -3.20 to +2.94 pp). The point estimate changes direction. The matched interval is wider. The matched interval includes zero.

Before/after balance (signed left-minus-right means; recent form is a prior win proportion):

| sample | measure | mean_L_minus_R | standardized_mean_difference |
| --- | --- | --- | --- |
| adjusted | recent_win_rate | -0.009 | -0.045 |
| adjusted | opponent_recent_win_rate | -0.024 | -0.121 |
| adjusted | log_player_rank | 0.040 | 0.036 |
| adjusted | log_opponent_rank | 0.163 | 0.144 |
| matched_analysis | recent_win_rate | -0.002 | -0.009 |
| matched_analysis | opponent_recent_win_rate | -0.008 | -0.044 |
| matched_analysis | log_player_rank | 0.001 | 0.001 |
| matched_analysis | log_opponent_rank | 0.000 | 0.000 |

This refits the existing Q3 specification and shared-player dyadic uncertainty calculation with original participant and match IDs. Selected observations remain dependent when they share either player. The sensitivity estimates describe a narrower selected sample; changes in size, direction and uncertainty should be considered alongside the retention table, rather than treating interval inclusion of zero as the only result.

Sensitivity uncertainty notes: Dyadic covariance is indefinite; nonpositive contrast variances are unavailable. Positive contrasts remain exploratory. Exploratory dyadic intervals assume no remaining dependence between disjoint participant pairs; restrictions select a narrower sample.

Rankings imperfectly measure strength; matching does not equalize injuries, tournament conditions or all prior form. Restrictions select a narrower sample, sparse strata remain uncertain, and this observational comparison is not causal. The primary Q1/Q2/Q3 numerical outputs are unchanged.

[Normalized rank distributions](rank_distributions.png) · [Within-player coverage plot](within_player_coverage.png) · [Compact summary](compact_summary.csv) · [Quantiles and breakdowns](distributions.csv) · [Within-stratum quartiles and ECDF distances](strata.csv.gz) · [Coverage by focal hand](coverage.csv) · [Retention](retention.csv) · [Rank/form balance by focal hand](balance.csv) · [Sample verification](summary.json) · [Separate validation manifest](manifest.json).
