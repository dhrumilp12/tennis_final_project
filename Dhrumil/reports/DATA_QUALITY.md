# Data quality and reconstruction audit

Run ID: `20261027T121134Z-20f069d1`. Generated from verified outputs; all numerical claims below refer to this run.

The authoritative run contains 63,784 eligible unique study matches. No count target was enforced. Subgroup support and dependent observations still constrain inference. Source: [`run_summary.json`](../outputs_final/run_summary.json), `eligible_analysis_matches`. Historical baseline checks remain in `validation/baseline_audit.json` and `validation/final_checks.json`; they do not imply an `outputs/` directory is included in this clone.

## Attrition and units

| stage | count | unit | population | note |
| --- | --- | --- | --- | --- |
| raw_records | 112056 | source_rows | all_input_files | unavailable |
| exact_duplicates_removed | 0 | source_rows | all_input_files | unavailable |
| warmup_records | 37150 | deduplicated_source_rows | history | unavailable |
| study_period_records | 74906 | deduplicated_source_rows | study | unavailable |
| study_unique_match_keys | 74906 | distinct_source_match_keys | study | Conflicting keys are unresolved physical matches, counted once here. |
| study_resolved_unique_physical_matches | 74906 | physical_matches | study | unavailable |
| study_eligible_matches | 63784 | physical_matches | study | unavailable |
| study_player_perspective_rows | 149812 | player_views | study | Includes excluded records retained for follow-up; not independent matches. |
| study_eligible_player_perspective_rows | 127568 | player_views | study | unavailable |
| q1_all_eligible_index_losses | 63784 | loss_events | Q1 | unavailable |
| q1_rank_eligible_known_rank_losses | 24021 | loss_events | Q1 | unavailable |
| q1_complete_next3_windows | 18546 | loss_events | Q1 | unavailable |
| q1_model_events | 18471 | loss_events | q1 | unavailable |
| q2_training_matches | 52444 | physical_matches | q2 | unavailable |
| q2_test_matches | 11340 | physical_matches | q2 | unavailable |
| q3_unique_matches | 63719 | physical_matches | q3 | unavailable |
| q3_adjusted_unique_matches | 61412 | physical_matches | q3 | unavailable |
| q3_adjusted_player_match_rows | 112503 | player_views | q3 | unavailable |

Source: [`attrition.csv`](../outputs_final/attrition.csv), all rows; run `20261027T121134Z-20f069d1`.

Warm-up and study counts are partitions of deduplicated source rows. Distinct match keys can include unresolved conflicts; resolved physical matches require usable distinct identities and a nonconflicting key. Player views include excluded events retained to prevent skipped follow-up. Q1 windows overlap, and Q3 subgroup match totals cannot be added as independent observations.

The following first-reason flow is mutually exclusive within period. Reasons are applied in code order, so later overlapping flags do not create extra attrition:

| period | first_reason | records |
| --- | --- | --- |
| study | ambiguous_order | 938 |
| study | eligible | 63784 |
| study | outside_individual_AMG_scope | 7780 |
| study | unfinished_or_unrecognized_score | 2404 |
| warmup | ambiguous_order | 318 |
| warmup | eligible | 32717 |
| warmup | outside_individual_AMG_scope | 3327 |
| warmup | unfinished_or_unrecognized_score | 788 |

Source: [`exclusion_flow.csv`](../outputs_final/exclusion_flow.csv), all rows; run `20261027T121134Z-20f069d1`.

Overlapping flag counts are separately retained in `run_summary.json/exclusion_flag_counts_nonexclusive`; never add them to this flow.

## Coverage and missingness

| dimension | group | source_rows | unique_match_keys | eligible_matches | missing_date | missing_either_rank | unknown_either_hand | ambiguous_order |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| surface | Carpet | 7905 | 7905 | 6451 | 0 | 346 | 123 | 1295 |
| surface | Clay | 37213 | 37213 | 31624 | 0 | 1108 | 638 | 4569 |
| surface | Grass | 10842 | 10842 | 10092 | 0 | 160 | 33 | 438 |
| surface | Hard | 56043 | 56043 | 48334 | 0 | 1749 | 857 | 6030 |
| surface | Unknown | 53 | 53 | 0 | 0 | 17 | 9 | 53 |

Source: [`coverage_by_group.csv`](../outputs_final/coverage_by_group.csv), dimension=surface; includes warm-up; run `20261027T121134Z-20f069d1`.

Year-by-year raw/eligible counts and missing hands are in [`coverage_by_year.csv`](../outputs_final/coverage_by_year.csv). Expanded year, surface and level coverage is in [`coverage_by_group.csv`](../outputs_final/coverage_by_group.csv). Missingness is explicitly recorded by year, surface, focal hand, age and observed experience in [`missingness_by_group.csv`](../outputs_final/missingness_by_group.csv); its denominators are study-period player views, including excluded recorded events.

| dimension | group | field | player_views | missing | missing_percent |
| --- | --- | --- | --- | --- | --- |
| player_hand | L | player_rank | 19119 | 169 | 0.88 |
| player_hand | L | opponent_rank | 19119 | 181 | 0.95 |
| player_hand | L | player_age | 19119 | 0 | 0.00 |
| player_hand | L | recent_win_rate | 19119 | 586 | 3.07 |
| player_hand | L | service_win_rate | 19119 | 1273 | 6.66 |
| player_hand | L | player_hand | 19119 | 0 | 0.00 |
| player_hand | L | opponent_hand | 19119 | 90 | 0.47 |
| player_hand | R | player_rank | 129629 | 1269 | 0.98 |
| player_hand | R | opponent_rank | 129629 | 1547 | 1.19 |
| player_hand | R | player_age | 129629 | 0 | 0.00 |
| player_hand | R | recent_win_rate | 129629 | 5308 | 4.09 |
| player_hand | R | service_win_rate | 129629 | 10860 | 8.38 |
| player_hand | R | player_hand | 129629 | 0 | 0.00 |
| player_hand | R | opponent_hand | 129629 | 784 | 0.60 |
| player_hand | U | player_rank | 1064 | 603 | 56.67 |
| player_hand | U | opponent_rank | 1064 | 313 | 29.42 |
| player_hand | U | player_age | 1064 | 8 | 0.75 |
| player_hand | U | recent_win_rate | 1064 | 1014 | 95.30 |
| player_hand | U | service_win_rate | 1064 | 917 | 86.18 |
| player_hand | U | player_hand | 1064 | 1064 | 100.00 |
| player_hand | U | opponent_hand | 1064 | 190 | 17.86 |

Source: [`missingness_by_group.csv`](../outputs_final/missingness_by_group.csv), dimension=player_hand; run `20261027T121134Z-20f069d1`.

Ranks at or below zero and implausible ages are masked. Unknown hand stays unknown. Service totals require integer, nonnegative component counts and valid first-/second-serve bounds. Invalid service statistics do not invalidate an otherwise eligible match result. Hand-specific opportunities are in [`q3_subgroup_support.csv`](../outputs_final/q3_subgroup_support.csv) and [`q3_by_player_and_hand.csv`](../outputs_final/q3_by_player_and_hand.csv).

## Unresolved records and chronology

| check | records_or_keys |
| --- | --- |
| unreliable_order_records | 12385 |
| invalid_identity_records | 0 |
| missing_dates | 0 |
| conflicting_source_rows | 0 |
| conflicting_match_keys | 0 |
| same_date_multiple_events | 4 |
| repeated_player_round | 9804 |
| unsupported_round_event | 12384 |
| missing_tournament_date | 0 |

Source: [`chronology_checks.csv`](../outputs_final/chronology_checks.csv), overlapping diagnostics; entire history window; run `20261027T121134Z-20f069d1`.

The unresolved identity/date/conflict ledger contains 0 player-event records. Source: [`unresolved_event_ledger.csv`](../outputs_final/unresolved_event_ledger.csv). A conflicting key is one unresolved physical event, not two matches. A known focal player with an invalid opponent retains a blocker. Source-agreed dates/rounds allow a blocker to occupy one sequence slot without a fake outcome. Unknown dates or conflicting ranges conservatively flag affected follow-up as unresolved; no date is imputed. Records with no known identity remain auditable but cannot be linked to a player.

The synthetic January 1/8/15/22/29 regression demonstrates a software edge case, not corruption of this real-data run. The saved baseline had zero conflicting keys. `validation/recovery_regression.json` and the regression tests record the checks actually made.

`tourney_date` is usually the tournament-week start. `match_num` and CSV row order are identifiers, never chronology. Checked knockout order is R128, R64, R32, R16, QF, SF, F. Unsupported-round events, repeated player rounds and same-start appearances in multiple tournaments are flagged. The bounded cross-start screen flagged 2029 study-period individual-event candidate pairs involving 319 players. Source: [`run_summary.json`](../outputs_final/run_summary.json), `chronology`, and [`chronology_start_gap_counts.csv`](../outputs_final/chronology_start_gap_counts.csv). Distinct starts 1–6 days apart, or 7–13 days after a G start, are screened; source references and unresolved statuses appear in [`chronology_overlap_candidates.csv`](../outputs_final/chronology_overlap_candidates.csv). These are potential overlaps, not confirmed collisions: early exits and ordinary scheduling shifts can explain them. No event end date is invented or speculative exclusion imposed. Different-start overlaps cannot always be resolved from these fields. No exact days-to-recovery claim is supported. See [chronology details](../docs/CHRONOLOGY.md).

## Traceable internal spot checks

The deterministic sample selects high-exposure player histories, ranking-upset windows by follow-up status, and opponent pairs with the most observed meetings. It includes original annual filenames and 1-based CSV rows (header is row 1). 27 automated comparisons were performed; 27 passed. These check local source outcomes, strictly earlier history counts, pair meetings and complete-window means. They are **not independent external verification or human review**.

| kind | player_id | match_id | evidence | expected | observed | passed |
| --- | --- | --- | --- | --- | --- | --- |
| history_count | 103819 | 1998-314:2 | atp_matches_1998.csv: CSV row 2032 | 0.000 | 0.000 | True |
| source_outcome | 103819 | 1998-314:2 | atp_matches_1998.csv: CSV row 2032 | 0.000 | 0.000 | True |
| history_count | 103819 | 2009-451:16 | atp_matches_2009.csv: CSV row 1562 | 678.000 | 678.000 | True |
| source_outcome | 103819 | 2009-451:16 | atp_matches_2009.csv: CSV row 1562 | 1.000 | 1.000 | True |
| history_count | 103819 | 2021-540:223 | atp_matches_2021.csv: CSV row 1677 | 1,356.000 | 1,356.000 | True |
| source_outcome | 103819 | 2021-540:223 | atp_matches_2021.csv: CSV row 1677 | 0.000 | 0.000 | True |
| history_count | 104745 | 2002-573:6 | atp_matches_2002.csv: CSV row 2502 | 0.000 | 0.000 | True |
| source_outcome | 104745 | 2002-573:6 | atp_matches_2002.csv: CSV row 2502 | 1.000 | 1.000 | True |
| history_count | 104745 | 2012-451:1 | atp_matches_2012.csv: CSV row 60 | 589.000 | 589.000 | True |
| source_outcome | 104745 | 2012-451:1 | atp_matches_2012.csv: CSV row 60 | 1.000 | 1.000 | True |
| history_count | 104745 | 2024-M-DC-2024-FLS-M-NED-ESP-01:1 | atp_matches_2024.csv: CSV row 2876 | 1,181.000 | 1,181.000 | True |
| source_outcome | 104745 | 2024-M-DC-2024-FLS-M-NED-ESP-01:1 | atp_matches_2024.csv: CSV row 2876 | 0.000 | 0.000 | True |
| history_count | 104925 | 2004-D045:5 | atp_matches_2004.csv: CSV row 3135 | 0.000 | 0.000 | True |
| source_outcome | 104925 | 2004-D045:5 | atp_matches_2004.csv: CSV row 3135 | 1.000 | 1.000 | True |
| history_count | 104925 | 2014-580:96 | atp_matches_2014.csv: CSV row 236 | 572.000 | 572.000 | True |
| source_outcome | 104925 | 2014-580:96 | atp_matches_2014.csv: CSV row 236 | 1.000 | 1.000 | True |
| history_count | 104925 | 2024-5014:369 | atp_matches_2024.csv: CSV row 2441 | 1,145.000 | 1,145.000 | True |
| source_outcome | 104925 | 2024-5014:369 | atp_matches_2024.csv: CSV row 2441 | 0.000 | 0.000 | True |
| window_mean | 102271 | 2000-451:9 | 2000-338:6; 2000-338:19; 2000-580:14 | 0.667 | 0.667 | True |
| window_mean | 102338 | 2000-891:1 | 2000-580:64; 2000-580:96; 2000-580:112 | 1.000 | 1.000 | True |
| window_mean | 102434 | 2000-339:8 | 2000-338:4; 2000-580:34; 2000-402:21 | 0.000 | 0.000 | True |
| prior_meetings | 104745 | 2022-520:220 | atp_matches_2022.csv: CSV row 1369; pair 104745:104925 | 48.000 | 48.000 | True |
| prior_meetings | 104745 | 2024-0096:133 | atp_matches_2024.csv: CSV row 2000; pair 104745:104925 | 49.000 | 49.000 | True |
| prior_meetings | 103819 | 2019-0605:291 | atp_matches_2019.csv: CSV row 2606; pair 103819:104925 | 41.000 | 41.000 | True |
| prior_meetings | 103819 | 2020-580:225 | atp_matches_2020.csv: CSV row 294; pair 103819:104925 | 41.000 | 41.000 | True |
| prior_meetings | 103819 | 2019-520:1602 | atp_matches_2019.csv: CSV row 1332; pair 103819:104745 | 33.000 | 33.000 | True |
| prior_meetings | 103819 | 2019-540:225 | atp_matches_2019.csv: CSV row 1629; pair 103819:104745 | 34.000 | 34.000 | True |

Source: [`spotcheck_evidence.csv`](../outputs_final/spotcheck_evidence.csv), all rows; run `20261027T121134Z-20f069d1`.

The inspectable evidence is in [`spotcheck_player_histories.csv`](../outputs_final/spotcheck_player_histories.csv), [`spotcheck_recovery_windows.csv`](../outputs_final/spotcheck_recovery_windows.csv), and [`spotcheck_opponent_pairs.csv`](../outputs_final/spotcheck_opponent_pairs.csv). Entirely absent source matches, wrong source identities and unreported historical errors cannot be recovered from this audit.

## Acquisition and run integrity

The pinned cache inventory is separate from this run's actual input list. Every required annual file was hash-checked before reuse; original retrieval timestamps and pinned URLs remain in the inventory. Subset/interrupted-run tests use mocked responses, never invented research observations. Each run is built and verified in a sibling staging directory, then published as a unit; an existing target is retained in a backup. Failed stages carry `FAILED_RUN.json` and no successful summary. Input hashes, working-code hashes, base revision/dirty state, package versions, analysis warnings and generated output hashes appear in [`run_summary.json`](../outputs_final/run_summary.json).
