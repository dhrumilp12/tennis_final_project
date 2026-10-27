# Chronology and unresolved events

`tourney_date` is the source's tournament-level date. It is not an observed match
day. The project orders a player's records by that date and the checked knockout
round sequence `R128 → R64 → R32 → R16 → QF → SF → F`. `match_num` identifies a
record; it never supplies chronological evidence. No days-to-recovery estimate
is calculated. Recovery means subsequent recorded performance.

## What is checked

The audited match table exposes the following overlapping diagnostic flags.
Their current counts and the final run ID belong to the generated
[Data quality report](../reports/DATA_QUALITY.md) and
[run summary](../outputs_final/run_summary.json), rather than a copied count here.

| Field | Source-supported check |
|---|---|
| `same_date_multiple_events` | A known player is recorded at multiple tournaments with the same tournament date. All affected match IDs are marked unreliable. A known player still participates in this check when the opponent's identity is invalid. |
| `repeated_player_round` | A player appears more than once in the same tournament and round. These cannot be ordered using the supplied round. Conflicting copies can also trigger this flag. |
| `unsupported_round_event` | At least one record in the tournament has a round outside the checked knockout sequence. The entire event's order is unreliable. |
| `missing_tournament_date` | The tournament date cannot be parsed. No substitute date is assigned. |
| `order_reliable` | The above explicit checks have not found an ordering failure. This means the documented approximation is usable; it does not certify exact match-day order. |

These flags overlap with scope exclusions. For example, round-robin or team
records can fail both the individual-event scope and chronology screens. They
must not be added together as mutually exclusive attrition counts.

Results from a common date/round block are read before any result from the block
updates pre-match history. Only earlier eligible results contribute observed
experience, form, or head-to-head records. Experience refers to observed history
since 1990, not an entire career. Excluded events are not assigned estimated wins.

## Follow-up blockers

`unresolved_event_ledger.csv` preserves records that cannot become resolved
player views: conflicting physical-match keys, invalid player identities, and
missing tournament dates. It retains source-file/CSV-row references and every
known potentially affected player. Multiple versions of one conflicting key are
one unresolved event, never multiple physical matches. An event whose players
are both unknown is retained but cannot be attached to a specific player's
history. A missing physical key is retained by source reference rather than
merged with unrelated unkeyed records.

When all conflicting copies agree on tournament date and round, a blocker
occupies one slot in the player's recorded-event sequence. Its result is missing,
and it cannot enter experience or prediction histories. A January 8 blocker
therefore prevents the January 15, 22, and 29 matches from being called a complete
next-three window after a January 1 loss.

When the date or round is unresolved, the ledger retains the supplied bounds
without choosing a convenient date. Windows that can intersect a bounded date
conflict are flagged unresolved. A known-player record with a missing date
conservatively leaves all that player's windows uncertain within the loaded
history, because its position cannot be determined. Missing outcomes remain
missing, never zero wins. `followup_blocker_keys`, `next1_unresolved_record`, and
`followup_unresolved_record` link the recovery table to this evidence.

`recorded_event_position` and the corresponding next-event positions are ordinal
sequence indices, not dates or counts of independently verified match days.
They support the non-overlapping follow-up sensitivity rule.

The pipeline passes the ledger explicitly. In-memory callers may also use the
ledger attached by `make_player_rows()` and preserved by `add_history()`. Since
CSV files do not preserve DataFrame attributes, callers reconstructing recovery
from serialized tables should explicitly supply the saved ledger:

```python
import pandas as pd
from tennis_project import Config, build_recovery_events

players = pd.read_csv(
    'outputs_final/player_match_features.csv.gz', parse_dates=['tourney_date'])
ledger = pd.read_csv(
    'outputs_final/unresolved_event_ledger.csv',
    parse_dates=['tourney_date', 'earliest_claimed_date', 'latest_claimed_date'])
events = build_recovery_events(players, Config(), event_ledger=ledger)
```

The explicit synthetic regression and observed before/after behavior are recorded
in [recovery_regression.json](../validation/recovery_regression.json). The fixture
is a software check, not evidence that the saved real-data results were corrupted.

## What these checks cannot establish

The generated `chronology_overlap_candidates.csv` separately flags known-player
appearances at distinct events whose observed starts are 1–6 days apart, or
7–13 days apart when the earlier event is level G. These are explicit screening
horizons, not inferred tournament end dates. The table retains both source
reference lists, observed rounds, event scope, and eligible-record counts.
`chronology_start_gap_counts.csv` quantifies candidates by observed start gap
for all loaded history, individual events, and individual study-period events.
The final run summary's `chronology` entry gives the corresponding totals.

These candidates are labeled `potential_overlap_unresolved_without_match_dates`.
An early exit or ordinary Sunday/Monday calendar difference can explain a
short gap. Therefore a candidate flag does not change eligibility or assert
that the player's matches physically overlapped. This bounded screen is not an
exhaustive overlap detector, and it does not establish that later start gaps
are safe. In particular, the horizons do not specify every tournament's actual
duration. Candidate rates and source references support review of the ordering
approximation without manufacturing match days.

Tournaments with different start dates can still overlap, and rescheduled
matches can fall outside the expected sequence. The available source dates do
not identify those match days. Passing the checks does not prove absence of such
overlaps. This implementation does not manufacture tournament end dates and
blanket-exclude players who start their next event after an early loss. Exact
resolution requires additional match-date evidence. Entirely absent records and
unidentified players cannot be recovered merely by sorting the files.

Service-point summaries separately require complete, integer, nonnegative counts
with component bounds (`1stWon ≤ 1stIn ≤ svpt`, `2ndWon ≤ svpt − 1stIn`, and
`svpt > 0`). Invalid service counts are masked without discarding an otherwise
eligible match result. This validity rule does not verify every source entry
against an independent scorecard.
