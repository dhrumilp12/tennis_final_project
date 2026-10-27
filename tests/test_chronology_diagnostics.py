"""Synthetic tests of the diagnostic screen, not claims of physical overlap."""
import pandas as pd
from tennis_project import Config, clean_matches
from tennis_chronology import cross_start_candidates, write_chronology_diagnostics
from test_pipeline import row


def screen(rows):
    cfg = Config()
    matches, _, _ = clean_matches(pd.DataFrame(rows), cfg)
    return matches, cross_start_candidates(matches, cfg)


def test_short_gap_is_diagnostic_not_an_automatic_exclusion():
    matches, candidates = screen([row(1, 20240101, 1, 2), row(2, 20240106, 1, 3)])
    assert matches.eligible.all()
    assert len(candidates) == 1
    assert candidates.observed_start_gap_days.iloc[0] == 5
    assert candidates.resolution_status.iloc[0] == 'potential_overlap_unresolved_without_match_dates'
    assert candidates.earlier_source_references.iloc[0] == 'SYNTHETIC:2'


def test_major_screen_does_not_invent_actual_end_date():
    _, candidates = screen([row(1, 20240101, 1, 2, tourney_level='G'), row(2, 20240112, 1, 3)])
    assert len(candidates) == 1
    assert candidates.screening_reason.iloc[0] == 'later_event_start_7_to_13_days_after_G_start'
    assert not any('end_date' in col or 'match_day' in col for col in candidates.columns)


def test_adjacent_ordinary_weeks_and_same_event_are_not_candidates():
    _, candidates = screen([row(1, 20240101, 1, 2), row(2, 20240108, 1, 3),
                            row(3, 20240109, 1, 4, tourney_id='2024-T2')])
    assert candidates.empty


def test_same_start_date_is_checked_elsewhere():
    matches, candidates = screen([row(1, 20240101, 1, 2), row(2, 20240101, 1, 3)])
    assert candidates.empty
    assert matches.same_date_multiple_events.all()


def test_gap_summary_has_explicit_zero_counts(tmp_path):
    matches, _ = screen([row()])
    result = write_chronology_diagnostics(matches, Config(), tmp_path)
    assert result['candidate_event_pairs_all_history'] == 0
    counts = pd.read_csv(tmp_path / 'chronology_start_gap_counts.csv')
    assert len(counts) == 39
    assert counts.candidate_event_pairs.eq(0).all()
