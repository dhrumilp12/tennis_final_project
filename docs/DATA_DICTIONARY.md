# Data dictionary

The original source dictionary is cached at
`data/raw/83733587353df8a41f2fd4f516147d5aa83f5a8d/atp__matches_data_dictionary.txt`.
Jeff Sackmann compiled the data; the Aneeshers archive supplies the pinned copy.
Definitions below distinguish upstream fields from this project's transformations.
Run-dependent counts and estimates belong in `outputs_final/`, not this dictionary.

## Units, records, and availability

One source annual-CSV row describes one recorded singles match. Exact duplicated
source rows are removed; conflicting rows sharing a physical key remain in the
audit but cannot supply a result. A resolved match yields two **dependent** player
views, identified by `(match_id, player_id)`. Q2 retains one deterministic view.
Q1's unit is an index loss plus follow-up window; windows may overlap. Q3's
regression uses player views and explicitly accounts for shared participants.

A **pre-match** field below is available before the current match under the
source's tournament-date/checked-round approximation. This is not independently
verified match-day chronology. **Current-result** fields can be outcomes and
quality checks, but never Q2 predictors. **Follow-up** fields are subsequently
observed; they are used only for Q1 outcomes and conditional context adjustment.

Missing numeric values are blank in CSV and read as `NaN`; unavailable JSON
estimates are `null`. A missing result/rate is never filled with zero. History
counts of zero mean no eligible prior result in the observed history window;
they do not prove the player had never competed professionally.

## Original source fields retained

| Fields | Meaning and units | Availability and cleaning |
|---|---|---|
| `tourney_id`, `tourney_name` | Source tournament identity/name | Tournament context. Missing IDs become empty strings and exclude the match. ID formatting is not used as match-day evidence. |
| `tourney_date` | Usually the Monday of the tournament week, source `YYYYMMDD` | Tournament context; parsed to a timestamp. Invalid dates become `NaT`. No match day is imputed. |
| `match_num` | Source match identifier, sometimes arbitrary | Identity only. Never used to infer within-tournament chronology. Missing values exclude the match. |
| `tourney_level` | `A`: other ATP tour events; `M`: Masters; `G`: majors, with other source codes retained | Tournament context; individual A/M/G scope only. Named team competitions are excluded even if their level otherwise qualifies. |
| `surface` | Hard, Clay, Grass, Carpet, or other recorded category | Pre-match context; missing values become `Unknown`, not Hard. |
| `round` | Knockout round label or unsupported format | Pre-match context; recognized round order is R128, R64, R32, R16, QF, SF, F. |
| `best_of` | Match format, number of sets: typically 3 or 5 | Pre-match; numeric conversion failures become missing. |
| `winner_id`, `loser_id` | Source participant IDs | Source roles are known after the result. Analysis reorients both identities; IDs must be positive distinct integers. A known participant can still be linked to an unresolved-event ledger if the other ID is invalid. |
| `winner_name`, `loser_name` | Recorded participant names | Display metadata; IDs, not names, link histories. |
| `winner_age`, `loser_age` | Age in years at tournament date | Pre-match; nonnumeric values and ages outside 12–65 become missing. Age remains separate from experience. |
| `winner_hand`, `loser_hand` | R, L, U; source describes serving hand for ambidextrous players | Pre-match metadata. Strip/uppercase; missing or unsupported values become U. Unknown is never recoded R. |
| `winner_rank`, `loser_rank` | Ranking at tournament date or latest earlier ranking | Pre-match strength proxy; nonpositive/nonnumeric values become missing. |
| `score` | Source result string | Current result; used only to screen completion. The screen excludes W/O, RET, DEF and other abandonment/unrecognized strings; it is not a complete reconstruction of tennis scoring. |
| `w_svpt`, `l_svpt` | Service points played | Current-result counts; used only for descriptive service outcomes. |
| `w_1stIn`, `l_1stIn` | First serves in | Current-result counts. |
| `w_1stWon`, `l_1stWon` | First-serve points won | Current-result counts. |
| `w_2ndWon`, `l_2ndWon` | Second-serve points won | Current-result counts. |
| `w_df`, `l_df`, `w_ace`, `l_ace` | Double faults and aces | Current-result counts; not prediction features. |
| `w_bpSaved`, `l_bpSaved`, `w_bpFaced`, `l_bpFaced` | Break-point counts | Current-result fields retained, not predictors or primary outcomes. |
| Other source columns | Examples: seed, entry, height, nationality, ranking points, draw size, duration, service games | Preserved in the audited source table; unused by the three primary models. Their presence is not a claim of complete coverage. |

## Derived audit and provenance fields

| Fields | Definition | Missing/exclusion rule |
|---|---|---|
| `source_file`, `source_csv_row` | Annual filename and data-record ordinal plus header (first data record = 2) | Never recomputed from the sorted analysis table. Together they identify the source evidence. |
| `match_id` | `tourney_id + ':' + match_num` with trailing numeric `.0` normalized | Physical-key proxy, not an ordering variable. Conflict copies do not become multiple physical matches. |
| `season` | Year of parsed tournament date | Missing if date is invalid. |
| `round_order` | R128=1, R64=2, R32=3, R16=4, QF=5, SF=6, F=7 | Missing for unsupported rounds; entire affected event excluded from chronological histories. |
| `identity_ok`, `conflicting_key` | Valid distinct IDs; nonidentical records share tournament/match key | False identity or true conflict prevents model/history contribution. |
| `completed`, `in_scope` | Completion screen and individual A/M/G scope | Both must be true. |
| `same_date_multiple_events`, `repeated_player_round` | Known player appears in multiple tournaments with the same start date, or multiple records in a tournament round | Source-supported ambiguity flags. They overlap other exclusions. |
| `unsupported_round_event`, `missing_tournament_date` | Event contains unrecognized round; missing/invalid tournament date | Chronology ambiguity flags. |
| `order_reliable` | Passes the implemented source-supported ordering checks | Does not certify exact match days or resolve every different-start overlapping event. |
| `within_history_window`, `in_analysis_period` | Within configured history period; within configured main study period | Defaults 1990–2024 and 2000–2024, respectively. |
| `eligible` | Valid IDs/key, no conflict, complete, in scope/history, and passes ordering checks | Excluded records stay in audit; counts of flags are not additive attrition. |
| `exclusion_reasons` | Semicolon-separated overlapping reasons | Empty for eligible rows. Mutually exclusive flow tables use separately stated precedence. |
| Manifest `sha256`, `bytes`, `origin`, `retrieved_at_utc`, `checked_at_utc` | File integrity/provenance metadata | Hash agreement detects local changes. `local_unverified` does not establish upstream authenticity. The cache inventory is separate from each run's actual input list. |

## Derived player views and pre-match histories

Let `a` be the focal player, `b` their opponent, `N` earlier eligible matches,
`M` earlier eligible meetings between this pair, and `W` focal wins in those
meetings. History starts in 1990 by default and includes warm-up years.

| Fields | Formula/meaning | Timing and missing rule |
|---|---|---|
| `player_*`, `opponent_*` | Source fields mapped to focal and opposite participant in each view | Pre-match attributes retain their source missingness; no winner-coded predictor is passed to Q2. |
| `won` | 1 in winner view, 0 in loser view | Current result, exclusively an outcome/history update. |
| `prior_matches`, `prior_wins` | Eligible earlier observed matches/wins for focal player | Pre-match counts; begin at zero, not full-career totals. |
| `recent_win_rate`, `recent_match_count` | Mean and count of at most the 10 preceding eligible observed results | Pre-match; rate missing if no earlier match. Ineligible records do not update history. |
| `opponent_prior_matches`, `opponent_recent_win_rate` | Same quantities for opponent | Pre-match; same rules. |
| `prior_h2h_meetings`, `prior_h2h_wins` | `M`, `W` for ordered focal-opponent pair | Pre-match; zero if no eligible meeting. Both views have the same M. |
| `prior_h2h_last_won` | Focal result in most recent eligible previous pair meeting | Pre-match; missing if no meeting. |
| `prior_surface_h2h_meetings`, `prior_surface_h2h_wins` | M and W restricted to current surface | Pre-match; zero without an eligible same-surface meeting. |
| `rank_gap` | `opponent_rank − player_rank`, ranking places | Positive means opponent is lower ranked. Missing if either rank missing. |
| `log_rank_advantage` | `log(opponent_rank / player_rank)` | Natural logarithm; positive favors focal player by ranking. Missing without valid ranks. |
| `age_difference` | `player_age − opponent_age`, years | Pre-match; missing without both ages. |
| `log_experience_difference` | `log(1+prior_matches) − log(1+opponent_prior_matches)` | Pre-match; observed-history contrast. |
| `recent_form_difference` | `recent_win_rate − opponent_recent_win_rate` | Pre-match; missing if either rate unavailable. |
| `log_prior_h2h_meetings` | `log(1+M)` | Symmetric between players; does not inherently favor either one. |
| `h2h_smoothed_advantage` | `(2W−M)/(M+2)` | Pre-match, bounded signed summary; zero without meetings. The denominator implements one pseudo-win and one pseudo-loss. |
| `surface_h2h_smoothed_advantage` | Same formula for same-surface pair history | Pre-match; zero without same-surface meetings. |
| `is_player_a` | `player_id < opponent_id` | Fixed, outcome-independent orientation used by Q2. |
| `pair_id` | Smaller ID followed by larger ID | Undirected pair cluster identifier. |

Within each shared `(tourney_date, round_order)` block, all features are read
before any result in that block enters history. Dates/rounds determine order;
match number/CSV position never resolves a contested sequence.

## Service outcomes

A valid core service record has integer `svpt > 0`,
`0 ≤ 1stIn ≤ svpt`, `0 ≤ 1stWon ≤ 1stIn`, and
`0 ≤ 2ndWon ≤ svpt−1stIn`. These checks set `valid_service_stats`.
`service_points_won = 1stWon + 2ndWon`;
`service_points_observed = svpt`;
`service_win_rate = service_points_won / service_points_observed`.
Invalid/missing components make all three derived service quantities missing,
without automatically excluding the match outcome. Aggregates divide summed
valid won points by summed valid observed points, rather than averaging rates.
`double_fault_rate = df/svpt` is retained where `svpt > 0` and `0 ≤ df ≤ svpt`;
it is not a primary modeled outcome or predictor.

## Recovery windows and blocker ledger

| Fields | Definition and timing | Missing rule |
|---|---|---|
| `ranking_upset` | Eligible index loss by a focal top-50 player to an opponent at least 30 ranking places lower | Current index result; both ranks required. Thresholds configurable and 20/30/50 checks retained. |
| `loss_type` | ranking_upset, other_ranked_loss, unknown_rank | Main descriptive/model comparisons retain only known ranks and the same focal-rank cutoff. |
| `age_group`, `experience_group` | Age: <23, 23–<30, ≥30; experience: <100, 100–299, ≥300 prior matches | Age missing stays missing; experience uses observed eligible history. |
| `next1_*`, `next2_*`, `next3_*` | Shifted record IDs, outcomes, eligibility, strength/context and blocker flags for the same focal player | Follow-up variables, prohibited in Q2. Ineligible/blocking events are not skipped to find later outcomes. |
| `next1_usable`, `next1_win` | Next recorded event eligible and without unresolved blocker; then its 0/1 outcome | Missing outcome otherwise, never zero-filled. |
| `followup_complete`, `next3_win_rate` | All three next recorded events present, eligible, and unblocked; mean of three 0/1 results | Incomplete/unusable/unresolved windows have missing rate. |
| `followup_status` | Complete, fewer than three recorded follow-ups, excluded/ambiguous match, unresolved record | Explicit distinction among censoring/unusable windows; unresolved status has precedence. |
| `followup_mean_log_rank_advantage` | Mean of three future rank advantages, requiring all three values | Conditional adjustment after follow-up; not an index-time prediction feature. |
| `followup_*_share` | Fractions of three follow-ups on Clay/Grass/Carpet/Unknown, or best-of-five | Conditional follow-up context; missing for incomplete windows. Hard is reference surface. |
| `recorded_event_position`, shifted positions | Ordinal in each player's source-supported event sequence, including placeable blockers | Not a match date or elapsed recovery time. |
| Ledger `event_key`, `player_id`, `source_references`, `source_record_count` | One unresolved key per known affected player with all source references/copy count | Two conflicting copies represent one unresolved key, not two physical events. Entirely unknown identities remain unlinked. |
| Ledger `placement_status`, `earliest_claimed_date`, `latest_claimed_date` | Date/round agreement or uncertainty in source records | Only agreed date/round permits a slot; source date bounds are not imputed dates. Missing chronology conservatively blocks potentially affected known-player windows. |
| `next1_unresolved_record`, `followup_unresolved_record`, `followup_blocker_keys` | Known unresolved event can affect the candidate window | Outcomes masked; blocker identity/reasons preserved for audit. |

## Analysis tables and uncertainty units

Q1 `estimate_pp` is 100 times a probability-unit linear contrast. For
`average_upset_minus_ordinary`, interactions are averaged over the model sample's
age/experience distribution (or named subgroup). Interaction rows are per year
or per one-unit increase in `log(1+prior_matches)`. In this table `players`
counts clusters in the fitted model, including subgroup-standardized rows;
`events` counts the standardization subgroup. Detailed subgroup opportunities
are in the descriptive tables. `sample=nonoverlapping` is the separately fitted
sensitivity sample. Coefficient tables remain in probability units.

Q2 Brier score is mean `(y−p)^2`; log loss is mean
`−y log(p)−(1−y)log(1−p)`; accuracy is the fraction correct at `p ≥ .5`.
`mean_improvement` is first-minus-second error, or second-minus-first accuracy:
positive always favors `second_model`. Calibration uses fixed probability bins,
not outcome-selected bins. Meeting groups are 0, 1, 2–4 and 5+ earlier meetings.

Q3 `difference_pp` is 100 times the adjusted opponent-L-minus-R contrast.
For focal R it is `β_opponent_left`; for focal L it is
`β_opponent_left + β_interaction`. `variance` uses the full covariance matrix.
Unavailable inference is explicitly labeled; blank limits are not null effects.
Unadjusted paired service differences require the minimum number of **valid
service matches** against each hand, separately from match-result opportunities.
See [METHODS.md](METHODS.md) for dependence assumptions and sensitivity analyses.

`q1_adjusted_contrasts.csv/players` is the number of clusters in the fitted model; `subgroup_players` is the actual distinct-player count in the standardization subgroup. They coincide for all-sample contrasts.
