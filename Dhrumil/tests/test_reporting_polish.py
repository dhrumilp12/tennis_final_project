"""Focused reporting regressions; synthetic intervals are not research results."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from tennis_reporting import (
    contrast_evidence, generate_reports, q1_age_experience_conclusion,
)
from tennis_repro import sha256


NO_CLEAR_INTERACTION = (
    'We did not find clear evidence that the upset-related difference varied '
    'with age or prior recorded match experience.'
)


def interaction_rows():
    return pd.DataFrame([
        dict(outcome=outcome, sample='all_windows', subgroup='all',
             contrast=contrast, estimate_pp=.1, ci95_lower_pp=-.2,
             ci95_upper_pp=.4, inference_status='available')
        for outcome in ['next1_win', 'next3_win_rate']
        for contrast in ['age_interaction_per_year', 'experience_interaction_log_unit']
    ])


def test_q1_answers_age_and_experience_when_both_outcomes_are_uncertain():
    answer = q1_age_experience_conclusion(interaction_rows())
    assert NO_CLEAR_INTERACTION in answer


@pytest.mark.parametrize('row_number', range(4))
def test_later_clear_interaction_does_not_repeat_no_clear_evidence(row_number):
    rows = interaction_rows()
    rows.loc[row_number, ['estimate_pp', 'ci95_lower_pp', 'ci95_upper_pp']] = [.2, .01, .4]
    answer = q1_age_experience_conclusion(rows)
    assert NO_CLEAR_INTERACTION not in answer
    assert 'age' in answer.lower() or 'experience' in answer.lower()


@pytest.mark.parametrize('column,value', [
    ('estimate_pp', np.nan), ('estimate_pp', np.inf),
    ('ci95_lower_pp', np.nan), ('ci95_upper_pp', np.inf),
    ('inference_status', 'unavailable'),
])
def test_missing_or_unavailable_interaction_is_not_interpreted_as_no_difference(column, value):
    rows = interaction_rows()
    rows.loc[0, column] = value
    answer = q1_age_experience_conclusion(rows)
    assert NO_CLEAR_INTERACTION not in answer
    assert 'unavailable' in answer.lower()


def test_missing_interaction_row_is_explicitly_unavailable():
    answer = q1_age_experience_conclusion(interaction_rows().iloc[1:])
    assert NO_CLEAR_INTERACTION not in answer
    assert 'unavailable' in answer.lower()


def test_duplicate_interaction_rows_are_not_silently_selected():
    rows = interaction_rows()
    with pytest.raises(ValueError):
        q1_age_experience_conclusion(pd.concat([rows, rows.iloc[[0]]], ignore_index=True))


@pytest.mark.parametrize('lower,estimate,upper,expected', [
    (1e-8, .1, .2, 'positive'),
    (-.2, -.1, -1e-8, 'negative'),
    (0., .1, .2, 'uncertain'),
    (-.2, -.1, 0., 'uncertain'),
])
def test_interpretation_uses_unrounded_limits(lower, estimate, upper, expected):
    row = pd.Series(dict(estimate_pp=estimate, ci95_lower_pp=lower,
                         ci95_upper_pp=upper, inference_status='available'))
    assert contrast_evidence(row) == expected


def test_reversed_interval_is_unavailable():
    row = pd.Series(dict(estimate_pp=.1, ci95_lower_pp=.2,
                         ci95_upper_pp=-.2, inference_status='available'))
    assert contrast_evidence(row) == 'unavailable'


def test_subgroup_and_sensitivity_rows_do_not_replace_primary_interactions():
    primary = interaction_rows()
    sensitivity = primary.assign(sample='nonoverlapping', ci95_lower_pp=.01)
    subgroup = primary.assign(subgroup='age_group:under_23', ci95_lower_pp=.01)
    assert NO_CLEAR_INTERACTION in q1_age_experience_conclusion(pd.concat([primary, sensitivity, subgroup]))


def test_report_regeneration_keeps_readme_interpretation_and_is_idempotent(tmp_path):
    output = Path('outputs_final')
    if not (output / 'run_summary.json').exists():
        pytest.skip('Authoritative outputs absent; synthetic reporting tests still run.')
    # Regenerate prose in isolation; never publish, fit models or alter outputs.
    originals = {str(p): sha256(p) for p in output.rglob('*') if p.is_file()}
    readme = tmp_path / 'README.md'
    original = Path('README.md').read_text()
    readme.write_text(original)
    generate_reports(output, tmp_path)
    first = readme.read_text()
    expected = q1_age_experience_conclusion(pd.read_csv(output / 'q1_adjusted_contrasts.csv'))
    assert expected in first
    begin, end = '<!-- GENERATED_FINDINGS_START -->', '<!-- GENERATED_FINDINGS_END -->'
    assert first.split(begin)[0] == original.split(begin)[0]
    assert first.split(end)[1] == original.split(end)[1]
    report_hashes = {p.name: sha256(p) for p in (tmp_path / 'reports').iterdir() if p.is_file()}
    generate_reports(output, tmp_path)
    assert readme.read_text() == first
    assert {p.name: sha256(p) for p in (tmp_path / 'reports').iterdir() if p.is_file()} == report_hashes
    assert {name: sha256(name) for name in originals} == originals


@pytest.mark.parametrize('estimate', [np.nan, np.inf, 2.])
def test_detailed_report_direction_does_not_interpret_missing_or_invalid_estimate(estimate):
    from tennis_reporting import direction
    row = pd.Series(dict(estimate_pp=estimate, ci95_lower_pp=-.2,
                         ci95_upper_pp=.4, inference_status='available'))
    assert direction(row, estimate='estimate_pp') == 'inference is unavailable'
