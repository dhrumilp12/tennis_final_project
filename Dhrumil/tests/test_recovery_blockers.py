"""Explicitly synthetic regression cases; none are research observations."""
import numpy as np
import pandas as pd
import pytest

from tennis_project import Config, clean_matches, make_player_rows, add_history, build_recovery_events
from test_pipeline import row


def process(rows):
    cfg = Config(history_start=2000, analysis_start=2000, end_year=2024, make_plots=False)
    matches, _, _ = clean_matches(pd.DataFrame(rows), cfg)
    players = add_history(make_player_rows(matches), cfg)
    return matches, players, build_recovery_events(players, cfg)


def january_rows():
    rows = [row(1, 20240101, 2, 1, winner_rank=90, loser_rank=10),
            row(2, 20240108, 1, 3), row(2, 20240108, 1, 3, score='6-0 6-0'),
            row(3, 20240115, 1, 4), row(4, 20240122, 1, 5), row(5, 20240129, 1, 6)]
    for line, record in enumerate(rows, start=2):
        record['source_csv_row'] = line
    return rows


def first_event(events):
    return events.loc[events.match_id.eq('2024-T1:1')].iloc[0]


def test_conflicting_january_event_blocks_three_match_followup():
    _, _, events = process(january_rows())
    first = first_event(events)
    assert not first.followup_complete
    assert pd.isna(first.next3_win_rate)
    assert not first.next1_usable
    assert 'unresolved' in first.followup_status


def test_two_conflicting_copies_are_one_blocker_not_two_physical_matches():
    from tennis_project import build_event_ledger
    matches, players, events = process(january_rows())
    ledger = build_event_ledger(matches)
    focal = ledger.loc[ledger.player_id.eq(1)]
    assert len(focal) == 1
    assert focal.source_record_count.iloc[0] == 2
    first = first_event(events)
    assert first.next1_match_id == '2024-T2:2'
    assert first.next2_match_id == '2024-T3:3'
    assert first.next3_match_id == '2024-T4:4'
    assert pd.isna(first.next1_won)
    assert '2024-T2:2' in first.followup_blocker_keys
    # Unresolved copies contribute neither experience nor head-to-head outcomes.
    jan15 = players.loc[players.player_id.eq(1) & players.match_id.eq('2024-T3:3')].iloc[0]
    assert jan15.prior_matches == 1


@pytest.mark.parametrize('unknown', [np.nan, -1, 1.5])
def test_known_focal_player_invalid_opponent_still_blocks_followup(unknown):
    rows = january_rows()
    rows[1] = row(2, 20240108, 1, unknown)
    del rows[2]
    _, _, events = process(rows)
    first = first_event(events)
    assert not first.followup_complete
    assert pd.isna(first.next1_win)
    assert 'unresolved' in first.followup_status


def test_missing_date_is_not_filled_and_uncertainty_is_explicit():
    from tennis_project import build_event_ledger
    rows = january_rows()
    rows[1] = row(2, np.nan, 1, 3)
    del rows[2]
    matches, _, events = process(rows)
    ledger = build_event_ledger(matches)
    focal = ledger.loc[ledger.player_id.eq(1)].iloc[0]
    assert pd.isna(focal.tourney_date)
    assert pd.isna(focal.earliest_claimed_date)
    assert focal.placement_status == 'date_unknown'
    first = first_event(events)
    assert first.followup_unresolved_record
    assert not first.next1_usable
    assert pd.isna(first.next3_win_rate)


def test_conflicting_dates_are_bounded_claims_not_a_chosen_date():
    from tennis_project import build_event_ledger
    rows = january_rows()
    rows[2]['tourney_date'] = 20240122
    matches, _, events = process(rows)
    focal = build_event_ledger(matches).query('player_id == 1').iloc[0]
    assert focal.placement_status == 'date_range_conflict'
    assert pd.isna(focal.tourney_date)
    assert focal.earliest_claimed_date == pd.Timestamp('2024-01-08')
    assert focal.latest_claimed_date == pd.Timestamp('2024-01-22')
    assert not first_event(events).followup_complete


def test_future_dated_blocker_does_not_invalidate_an_earlier_complete_window():
    rows = [row(1, 20240101, 2, 1), row(2, 20240108, 1, 3), row(3, 20240115, 1, 4),
            row(4, 20240122, 1, 5), row(5, 20240129, 1, 6), row(5, 20240129, 1, 6, score='6-0 6-0')]
    _, _, events = process(rows)
    assert first_event(events).followup_complete
    assert first_event(events).next3_win_rate == 1


def test_unidentifiable_record_is_retained_without_invented_player():
    from tennis_project import build_event_ledger
    matches, _, _ = process([row(1, 20240101, np.nan, np.nan)])
    ledger = build_event_ledger(matches)
    assert len(ledger) == 1
    assert ledger.player_id.isna().all()
    assert ledger.source_references.iloc[0] == 'SYNTHETIC:2'


def test_within_tournament_round_order_is_independent_of_match_number():
    rows = [row(99, winner=1, loser=3, tourney_id='same-event', round='SF'),
            row(1, winner=2, loser=1, tourney_id='same-event', round='F')]
    _, players, _ = process(rows[::-1])
    focal = players.loc[players.player_id.eq(1)]
    assert focal['round'].tolist() == ['SF', 'F']
    assert focal.prior_matches.tolist() == [0, 1]
    assert focal.recent_win_rate.iloc[1] == 1


def test_known_player_invalid_opponent_does_not_hide_same_date_overlap():
    matches, _, events = process([row(1, 20240101, 2, 1), row(2, 20240101, 1, np.nan)])
    assert matches.same_date_multiple_events.all()
    assert not matches.order_reliable.any()
    assert events.empty


@pytest.mark.parametrize('field', ['w_svpt', 'w_1stIn', 'w_1stWon', 'w_2ndWon'])
def test_fractional_service_point_counts_are_invalid(field):
    matches, players, _ = process([row(**{field: 10.5})])
    assert matches.eligible.iloc[0]
    winner = players.loc[players.won.eq(1)].iloc[0]
    assert not winner.valid_service_stats
    assert pd.isna(winner.service_points_observed)
    assert pd.isna(winner.service_points_won)


def test_explicit_ledger_supports_player_tables_without_dataframe_attrs():
    from tennis_project import build_event_ledger
    matches, players, _ = process(january_rows())
    players.attrs = {}
    events = build_recovery_events(players, Config(), event_ledger=build_event_ledger(matches))
    assert not first_event(events).followup_complete
