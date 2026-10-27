"""Traceable chronology diagnostics; screening horizons are not invented match dates."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from tennis_project import Config


CANDIDATE_COLUMNS = [
    'player_id', 'player_name', 'earlier_tourney_id', 'later_tourney_id',
    'earlier_tourney_name', 'later_tourney_name', 'earlier_start', 'later_start',
    'observed_start_gap_days', 'screening_reason', 'earlier_level', 'later_level',
    'earlier_observed_rounds', 'later_observed_rounds', 'earlier_source_records',
    'later_source_records', 'earlier_source_keys', 'later_source_keys',
    'earlier_eligible_records', 'later_eligible_records', 'both_individual_scope',
    'later_start_in_study_period', 'study_individual_candidate',
    'earlier_source_references', 'later_source_references', 'resolution_status',
]


def cross_start_candidates(matches: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Find known-player event starts within chosen audit horizons.

    A 1–6-day start gap is screened for any event. A 7–13-day gap is screened
    when the earlier event is G. These are potential chronology ambiguities,
    not evidence that the player's matches overlap: early exits and ordinary
    calendar differences can explain them. No outcomes or eligibility change.
    Same-date collisions have their own clean_matches flags and are not here.
    """
    views = []
    metadata = ['match_id', 'tourney_id', 'tourney_name', 'tourney_date', 'round',
                'tourney_level', 'in_scope', 'eligible', 'source_file', 'source_csv_row']
    for side in ['winner', 'loser']:
        known = matches[f'{side}_id'].gt(0) & matches[f'{side}_id'].mod(1).eq(0)
        view = matches.loc[known & matches.tourney_date.notna(),
                           metadata + [f'{side}_id', f'{side}_name']].copy()
        view = view.rename(columns={f'{side}_id': 'player_id', f'{side}_name': 'player_name'})
        views.append(view)
    rows = pd.concat(views, ignore_index=True)
    if rows.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    # Exact duplicate perspectives (e.g. invalid self-match) do not multiply
    # the source-reference count; unresolved source records remain traceable.
    rows = rows.drop_duplicates(['player_id', 'source_file', 'source_csv_row'])
    rows['source_reference'] = rows.source_file.astype(str) + ':' + rows.source_csv_row.astype(str)
    events = rows.groupby(['player_id', 'tourney_id', 'tourney_date'], dropna=False).agg(
        player_name=('player_name', 'first'), tourney_name=('tourney_name', 'first'),
        level=('tourney_level', lambda x: '|'.join(sorted(set(x)))),
        rounds=('round', lambda x: '|'.join(sorted(set(x)))),
        source_records=('match_id', 'size'), source_keys=('match_id', 'nunique'),
        eligible_records=('eligible', 'sum'), in_scope=('in_scope', 'all'),
        source_references=('source_reference', lambda x: '|'.join(sorted(set(x)))),
    ).reset_index().sort_values(['player_id', 'tourney_date', 'tourney_id'])
    candidates = []
    for player, group in events.groupby('player_id', sort=False):
        sequence = list(group.itertuples())
        for i, earlier in enumerate(sequence):
            for j in range(i + 1, len(sequence)):
                later = sequence[j]
                gap = (later.tourney_date - earlier.tourney_date).days
                if gap > 13:
                    break
                if gap <= 0 or earlier.tourney_id == later.tourney_id:
                    continue
                if gap < 7:
                    reason = 'distinct_event_starts_1_to_6_days_apart'
                elif 'G' in earlier.level.split('|'):
                    reason = 'later_event_start_7_to_13_days_after_G_start'
                else:
                    continue
                scope = bool(earlier.in_scope and later.in_scope)
                study = cfg.analysis_start <= later.tourney_date.year <= cfg.end_year
                candidates.append({
                    'player_id': int(player), 'player_name': earlier.player_name,
                    'earlier_tourney_id': earlier.tourney_id, 'later_tourney_id': later.tourney_id,
                    'earlier_tourney_name': earlier.tourney_name, 'later_tourney_name': later.tourney_name,
                    'earlier_start': earlier.tourney_date, 'later_start': later.tourney_date,
                    'observed_start_gap_days': gap, 'screening_reason': reason,
                    'earlier_level': earlier.level, 'later_level': later.level,
                    'earlier_observed_rounds': earlier.rounds, 'later_observed_rounds': later.rounds,
                    'earlier_source_records': earlier.source_records, 'later_source_records': later.source_records,
                    'earlier_source_keys': earlier.source_keys, 'later_source_keys': later.source_keys,
                    'earlier_eligible_records': earlier.eligible_records,
                    'later_eligible_records': later.eligible_records, 'both_individual_scope': scope,
                    'later_start_in_study_period': study, 'study_individual_candidate': bool(scope and study),
                    'earlier_source_references': earlier.source_references,
                    'later_source_references': later.source_references,
                    'resolution_status': 'potential_overlap_unresolved_without_match_dates',
                })
    return pd.DataFrame(candidates, columns=CANDIDATE_COLUMNS)


def write_chronology_diagnostics(matches: pd.DataFrame, cfg: Config, output: Path) -> dict:
    """Write auditable candidate events and return summary for run provenance."""
    candidates = cross_start_candidates(matches, cfg)
    candidates.to_csv(output / 'chronology_overlap_candidates.csv', index=False)
    subsets = {
        'all_loaded_history': candidates,
        'both_individual_events': candidates.loc[candidates.both_individual_scope.eq(True)],
        'study_individual_events': candidates.loc[candidates.study_individual_candidate.eq(True)],
    }
    summaries = []
    for population, data in subsets.items():
        for gap in range(1, 14):
            selected = data.loc[data.observed_start_gap_days.eq(gap)]
            summaries.append({'population': population, 'observed_start_gap_days': gap,
                              'candidate_event_pairs': len(selected),
                              'known_players': selected.player_id.nunique()})
    pd.DataFrame(summaries).to_csv(output / 'chronology_start_gap_counts.csv', index=False)
    study = subsets['study_individual_events']
    return {
        'candidate_event_pairs_all_history': len(candidates),
        'candidate_players_all_history': int(candidates.player_id.nunique()),
        'candidate_event_pairs_study_individual': len(study),
        'candidate_players_study_individual': int(study.player_id.nunique()),
        'study_individual_short_gap_pairs': int(study.observed_start_gap_days.le(6).sum()),
        'study_individual_G_screen_pairs': int(study.observed_start_gap_days.ge(7).sum()),
        'screening_rule': 'Distinct events for a known player: start gap 1–6 days, or 7–13 days after a G start.',
        'interpretation': 'Potential overlaps unresolved without match dates; early exits or ordinary calendar differences may explain candidates. No event end dates were imputed and this diagnostic does not change eligibility.',
    }
