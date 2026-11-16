"""Supplemental Q1 interpretation and Q2 uncertainty from the saved study.

Run from Dhrumil/: python tennis_q1_q2_checks.py
No downloads, primary-run writes, Q2 refits, or changed model definitions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from tennis_repro import code_provenance, environment, sha256, verify_output


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def chronology_views(matches, candidates):
    """Trace existing candidate player/event IDs; do not infer match dates."""
    keys = set()
    for row in candidates.itertuples():
        keys.add((row.player_id, row.earlier_tourney_id))
        keys.add((row.player_id, row.later_tourney_id))
    parts = []
    for side, other in [('winner', 'loser'), ('loser', 'winner')]:
        d = matches[['match_id', 'tourney_id', 'tourney_date', 'round_order', 'eligible',
                     f'{side}_id', f'{other}_id']].rename(columns={f'{side}_id': 'player_id', f'{other}_id': 'opponent_id'}).copy()
        d = d.loc[d.player_id.notna()]
        d['candidate_event'] = [(pid, event) in keys for pid, event in zip(d.player_id, d.tourney_id)]
        parts.append(d)
    return pd.concat(parts, ignore_index=True).drop_duplicates(['player_id', 'match_id'])


def prior_candidate_counts(history, query):
    """Strictly earlier tournament-start/round blocks, matching saved history policy.

    Counts are exposures to screening candidates, not proven corrupted features.
    The last-ten screen follows the original recent-form history length.
    """
    result = query[['match_id', 'player_id']].copy()
    result['prior_candidate_records'] = 0
    result['recent_candidate_records'] = 0
    result['prior_eligible_records'] = 0
    used = set()
    for player, indices in query.groupby('player_id').groups.items():
        h = history.loc[history.player_id.eq(player)].sort_values(['tourney_date', 'round_order', 'match_id'])
        if h.empty:
            continue
        # Multiplying day numbers by 16 makes checked round order the minor key.
        hk = (pd.to_datetime(h.tourney_date).astype('int64').to_numpy() // 86400000000000) * 16 + h.round_order.to_numpy()
        q = query.loc[indices]
        qk = (pd.to_datetime(q.tourney_date).astype('int64').to_numpy() // 86400000000000) * 16 + q.round_order.to_numpy()
        positions = np.searchsorted(hk, qk, side='left')
        prefix = np.r_[0, h.candidate_event.astype(int).to_numpy().cumsum()]
        result.loc[indices, 'prior_candidate_records'] = prefix[positions]
        result.loc[indices, 'recent_candidate_records'] = prefix[positions] - prefix[np.maximum(positions-10, 0)]
        result.loc[indices, 'prior_eligible_records'] = positions
        if len(positions):
            used.update(zip(h.iloc[:positions.max()].loc[lambda x: x.candidate_event, 'player_id'],
                            h.iloc[:positions.max()].loc[lambda x: x.candidate_event, 'match_id']))
    return result, used


def run_chronology(source, output, summary):
    candidates = pd.read_csv(source/'chronology_overlap_candidates.csv')
    matches = pd.read_csv(source/'matches_audited.csv.gz', usecols=[
        'match_id', 'tourney_id', 'tourney_date', 'round_order', 'eligible', 'winner_id', 'loser_id'])
    views = chronology_views(matches, candidates)
    marked = set(zip(views.loc[views.candidate_event, 'player_id'], views.loc[views.candidate_event, 'match_id']))
    physical = set(views.loc[views.candidate_event, 'match_id'])
    windows = pd.read_csv(source/'q1_model_windows.csv.gz')
    events = pd.read_csv(source/'q1_recovery_events.csv.gz')
    common = events.loc[events.player_rank.le(summary['configuration']['upset_max_rank']) & events.opponent_rank.notna()]
    common_ids = []
    for outcome in ['next3_win_rate', 'next1_win']:
        piece = common[['player_id', 'match_id', 'next1_match_id', 'next2_match_id', 'next3_match_id']].copy()
        piece['outcome'], piece['sample'] = outcome, 'common_rank_eligible_population'
        common_ids.append(piece)
    windows = pd.concat([windows, *common_ids], ignore_index=True)
    window_flags = []
    counts = []
    for (outcome, sample), group in windows.groupby(['outcome', 'sample'], sort=True):
        k = 3 if outcome == 'next3_win_rate' else 1
        flag_rows = []
        for r in group.itertuples():
            ids = [r.match_id] + [getattr(r, f'next{i}_match_id') for i in range(1, k+1)]
            flag_rows.append({'outcome': outcome, 'sample': sample, 'player_id': r.player_id, 'match_id': r.match_id,
                              'index_in_candidate_event_for_focal': (r.player_id, r.match_id) in marked,
                              'window_includes_candidate_event_for_focal': any((r.player_id, m) in marked for m in ids),
                              'window_includes_candidate_event_either_participant': any(m in physical for m in ids)})
        flags = pd.DataFrame(flag_rows)
        window_flags.append(flags)
        for check in ['index_in_candidate_event_for_focal', 'window_includes_candidate_event_for_focal', 'window_includes_candidate_event_either_participant']:
            selected = flags.loc[flags[check]]
            counts.append(dict(question='Q1', sample=sample, outcome=outcome, check=check,
                               denominator=len(flags), unit='index_events_or_windows', flagged_records=len(selected),
                               flagged_players=selected.player_id.nunique(), flagged_unique_matches=selected.match_id.nunique()))
    pd.concat(window_flags, ignore_index=True).to_csv(output/'chronology_q1_windows.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    pred = pd.read_csv(source/'q2_test_predictions.csv.gz')
    # Exact physical-match metadata; no synthetic dates or removed observations.
    metadata = matches.loc[matches.eligible].drop_duplicates('match_id')[['match_id', 'round_order']]
    pred = pred.merge(metadata, on='match_id', how='left', validate='one_to_one')
    if pred.round_order.isna().any():
        raise ValueError('Cannot trace a Q2 prediction to eligible source chronology.')
    eligible = views.loc[views.eligible].copy()
    q2 = pred[['match_id', 'player_id', 'opponent_id', 'prior_h2h_meetings']].copy()
    q2['evaluation_in_candidate_event'] = pred.match_id.isin(physical)
    used_records = set()
    feature_counts = pd.read_csv(source/'player_match_features.csv.gz', usecols=[
        'match_id', 'player_id', 'is_player_a', 'prior_matches', 'opponent_prior_matches'])
    feature_counts = feature_counts.loc[feature_counts.is_player_a].set_index('match_id').loc[pred.match_id]
    for role, participant in [('focal', 'player_id'), ('opponent', 'opponent_id')]:
        query = pred[['match_id', participant, 'tourney_date', 'round_order']].rename(columns={participant: 'player_id'})
        history, used = prior_candidate_counts(eligible, query)
        saved_column = 'prior_matches' if role == 'focal' else 'opponent_prior_matches'
        np.testing.assert_array_equal(history.prior_eligible_records.to_numpy(), feature_counts[saved_column].to_numpy())
        used_records |= used
        q2[f'{role}_earlier_candidate_records'] = history.prior_candidate_records.to_numpy()
        q2[f'{role}_recent_candidate_records'] = history.recent_candidate_records.to_numpy()
    q2['either_player_has_earlier_candidate_history'] = q2[['focal_earlier_candidate_records', 'opponent_earlier_candidate_records']].gt(0).any(axis=1)
    q2['either_player_recent10_includes_candidate_history'] = q2[['focal_recent_candidate_records', 'opponent_recent_candidate_records']].gt(0).any(axis=1)
    q2.to_csv(output/'chronology_q2_records.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    for sample, mask in [('all', np.ones(len(q2), bool)), ('repeat', q2.prior_h2h_meetings.ge(1)), ('first', q2.prior_h2h_meetings.eq(0))]:
        g = q2.loc[mask]
        for check in ['evaluation_in_candidate_event', 'either_player_has_earlier_candidate_history', 'either_player_recent10_includes_candidate_history']:
            flagged = g.loc[g[check]]
            counts.append(dict(question='Q2', sample=sample, outcome='saved_test_predictions', check=check,
                               denominator=len(g), unit='physical_test_matches', flagged_records=len(flagged),
                               flagged_players=pd.unique(flagged[['player_id', 'opponent_id']].to_numpy().ravel()).size,
                               flagged_unique_matches=flagged.match_id.nunique()))
    table = pd.DataFrame(counts)
    table['flagged_share'] = table.flagged_records / table.denominator
    table.to_csv(output/'chronology_summary.csv', index=False)
    pd.DataFrame(sorted(used_records), columns=['player_id', 'match_id']).to_csv(output/'chronology_prior_candidate_ids.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    return {'candidate_event_pairs_all_history': len(candidates),
            'prior_eligible_record_counts_equal_saved_focal_and_opponent': True,
            'candidate_event_pairs_study_individual': int(candidates.study_individual_candidate.sum()),
            'candidate_history_player_records_prior_to_at_least_one_test_match': len(used_records),
            'candidate_history_unique_matches_prior_to_at_least_one_test_match': len({m for _, m in used_records}),
            'method': 'Join existing screened player/event IDs to original index/follow-up matches. Q2 history screens use strictly earlier tournament-start/round blocks and original last-ten eligible records.',
            'count_units': 'Q1 flagged_unique_matches counts distinct index-match IDs, not every follow-up match; Q2 counts physical evaluation matches. Window totals and history exposures overlap.',
            'limitation': 'Candidate event exposure is not a proven ordering error or proof that a fitted prediction changed. Histories include warm-up records. Cumulative exposure is broad; last-ten exposure is more specific to prior form. Actual match dates and unrecorded events remain unresolved.'}


def run_checks(source=Path('outputs_final'), output=Path('validation/q1_q2_checks')):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError('Supplement must be outside the historical source run.')
    output.mkdir(parents=True, exist_ok=True)
    summary = verify_output(source)
    if (output/'baseline.json').exists():
        baseline = json.loads((output/'baseline.json').read_text())
    else:
        baseline = {'source_run_id': summary['run_id'], 'configuration': summary['configuration'],
                    'outputs_final': {str(p): sha256(p) for p in sorted(source.rglob('*')) if p.is_file()},
                    'input_hashes': {r['path']: sha256(r['path']) for r in summary['inputs']}}
        write_json(output/'baseline.json', baseline)
    protected = {**baseline['outputs_final'], **baseline['input_hashes'], **baseline.get('preserved_q3_hashes', {})}
    for name, digest in protected.items():
        if sha256(name) != digest:
            raise ValueError(f'Baseline preservation mismatch: {name}')
    settings = {'source_run_id': summary['run_id'], 'configuration': summary['configuration'],
                'Q1': 'Reconstruct unchanged four original fits, exact event/window IDs and historical coefficients; post-upset sums with full original focal-player covariance and t(players-1); no new model or practical contrast.',
                'Q2': 'Use frozen saved predictions; all/repeat(prior>=1)/first(prior=0); original pair bootstrap alongside shared-player dyadic mean sandwich; Brier primary, log loss/accuracy secondary; no refits.',
                'chronology': 'Trace original candidate event screen without changing dates, eligibility, histories, or windows.'}
    write_json(output/'settings.json', settings)
    from tennis_q1_checks import run_q1
    from tennis_q2_checks import run_q2
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        q1 = run_q1(source, output, summary)
        print('Q1 exact-fit reconstruction and diagnostics completed.', flush=True)
        q2 = run_q2(source, output, summary)
        print('Q2 saved-prediction comparisons completed.', flush=True)
        chronology = run_chronology(source, output, summary)
    for name, digest in protected.items():
        if sha256(name) != digest:
            raise AssertionError(f'Protected file changed: {name}')
    result = {'source_run_id': summary['run_id'], 'q1': q1, 'q2': q2, 'chronology': chronology,
              'protected_files_unchanged': len(protected),
              'warnings': [{'category': w.category.__name__, 'message': str(w.message)} for w in caught]}
    write_json(output/'summary.json', result)
    write_report(source, output, summary, result)
    code = code_provenance()
    manifest = {'validation_id': 'q1-q2-checks-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                'created_at_utc': datetime.now(timezone.utc).isoformat(), 'source_run_id': summary['run_id'],
                'source_run_summary_sha256': sha256(source/'run_summary.json'), 'settings': settings,
                'code_version': code, 'code_hashes': code['source_hashes'], 'runtime': environment(),
                'input_hashes': {str(p): sha256(p) for p in sorted(source.iterdir()) if p.is_file()},
                'artifacts': {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file() and p.name not in ['manifest.json', 'tests.txt', 'verification.json']},
                'checks_executed': result, 'note': 'Later supplemental validation, not part of the historical analysis run. Tests are recorded separately.'}
    write_json(output/'manifest.json', manifest)
    return result


def write_report(source, output, summary, result):
    """Separate conditional slopes, interaction contrasts and predictive uncertainty."""
    from tennis_reporting import one, interval, markdown_table, contrast_evidence
    q1 = pd.read_csv(output/'q1_post_upset_contrasts.csv')
    q2 = pd.read_csv(output/'q2_comparisons.csv')
    scores = pd.read_csv(output/'q2_scores.csv')
    support = pd.read_csv(output/'q1_support.csv')
    retention = pd.read_csv(output/'q1_retention.csv')
    design = pd.read_csv(output/'q1_model_diagnostics.csv')
    distributions = pd.read_csv(output/'q1_distributions.csv')
    chronology = pd.read_csv(output/'chronology_summary.csv')
    historical_q1 = pd.read_csv(source/'q1_adjusted_contrasts.csv')
    average = one(historical_q1, outcome='next3_win_rate', sample='all_windows', subgroup='all', contrast='average_upset_minus_ordinary')
    q1rows, interpretations = [], []
    outcome_names = {'next3_win_rate': 'Next three (primary)', 'next1_win': 'Next match (secondary)'}
    for sample in ['all_windows', 'nonoverlapping']:
        for outcome in ['next3_win_rate', 'next1_win']:
            a = one(q1, outcome=outcome, sample=sample, contrast='age_post_upset_per_year')
            e = one(q1, outcome=outcome, sample=sample, contrast='experience_post_upset_log_unit')
            q1rows.append({'Outcome': outcome_names[outcome], 'Sample': sample,
                           'Events / players': f'{int(a.events):,} / {int(a.players):,}',
                           'Age, pp/year (95% interval)': interval(a),
                           'Experience, pp/log unit (95% interval)': interval(e)})
            if sample == 'all_windows':
                for label, row in [('age', a), ('prior experience', e)]:
                    state = contrast_evidence(row)
                    conclusion = {'positive': 'a positive conditional association', 'negative': 'a negative conditional association',
                                  'uncertain': 'an uncertain conditional association (interval includes zero)',
                                  'unavailable': 'unavailable inference'}[state]
                    interpretations.append(f'{outcome_names[outcome]}: {label} has {conclusion}.')
    q1compact = pd.DataFrame(q1rows)
    q1compact.to_csv(output/'q1_compact.csv', index=False)
    comparison_names = {('baseline', 'plus_meeting_count'): 'Baseline → count',
                        ('baseline', 'plus_h2h_results'): 'Baseline → H2H results',
                        ('plus_meeting_count', 'plus_h2h_results'): 'Count → H2H results'}
    q2rows = []
    for subset in ['ALL', 'REPEAT', 'FIRST']:
        for (first, second), label in comparison_names.items():
            selected = q2.loc[q2.subset.eq(subset) & q2.metric.eq('brier') & q2.first_model.eq(first) & q2.second_model.eq(second)]
            d = one(selected, method='shared_player_dyadic')
            b = one(selected, method='opponent_pair_bootstrap')
            def bounds(row):
                if contrast_evidence(row, 'mean_improvement', 'ci95_lower', 'ci95_upper') == 'unavailable':
                    return 'inference unavailable'
                return f'[{row.ci95_lower:+.6f}, {row.ci95_upper:+.6f}]'
            q2rows.append({'Subset': subset, 'Comparison': label, 'Matches / players / pairs': f'{int(d.n_matches):,} / {int(d.players):,} / {int(d.pairs):,}',
                           'Brier improvement': f'{d.mean_improvement:+.6f}',
                           'Pair bootstrap 95%': bounds(b), 'Shared-player dyadic 95%': bounds(d)})
    q2compact = pd.DataFrame(q2rows)
    q2compact.to_csv(output/'q2_compact.csv', index=False)
    primary_ret = retention.loc[retention.outcome.eq('next3_win_rate') & retention['sample'].eq('all_windows') & retention.dimension.eq('overall')]
    secondary_ret = retention.loc[retention.outcome.eq('next1_win') & retention['sample'].eq('all_windows') & retention.dimension.eq('overall')].set_index('loss_type')
    rrows = []
    for r in primary_ret.itertuples():
        rrows.append({'Loss type': r.loss_type, 'Index events / players': f'{r.denominator_events:,} / {r.denominator_players:,}',
                      'Usable next match': r.usable_next1_events, 'Complete next three': r.complete_next3_events,
                      'Adjusted next match': int(secondary_ret.loc[r.loss_type, 'model_events']), 'Adjusted next three': r.model_events})
    retention_compact = pd.DataFrame(rrows)
    retention_compact.to_csv(output/'q1_retention_compact.csv', index=False)
    primary_design = one(design, outcome='next3_win_rate', sample='all_windows')
    common_support = support.loc[support.population.eq('common_rank_eligible')]
    extreme = common_support.loc[common_support.age_group.eq('under_23') & common_support.experience_group.eq('300_plus')]
    older_low = common_support.loc[common_support.age_group.eq('30_plus') & common_support.experience_group.eq('under_100')]
    interactions = q1.loc[q1.outcome.eq('next3_win_rate') & q1['sample'].eq('all_windows') & q1.contrast_kind.eq('upset_minus_ordinary_interaction')]
    age_i = one(interactions, contrast='age_interaction_per_year')
    experience_i = one(interactions, contrast='experience_interaction_log_unit')
    q1_chron = one(chronology, question='Q1', sample='all_windows', outcome='next3_win_rate', check='window_includes_candidate_event_for_focal')
    q2_chron = one(chronology, question='Q2', sample='all', check='evaluation_in_candidate_event')
    q2_recent = one(chronology, question='Q2', sample='all', check='either_player_recent10_includes_candidate_history')
    q2_cumulative = one(chronology, question='Q2', sample='all', check='either_player_has_earlier_candidate_history')
    pre = result['q1']['common_population']
    selection = distributions.loc[distributions.population.eq('next3_win_rate/all_windows') & distributions.dimension.eq('overall') & distributions.loss_type.eq('all')]
    retained_rank = one(selection, retention_status='retained', measure='player_rank')['mean']
    omitted_rank = one(selection, retention_status='omitted', measure='player_rank')['mean']
    retained_form = one(selection, retention_status='retained', measure='recent_win_rate')['mean']
    omitted_form = one(selection, retention_status='omitted', measure='recent_win_rate')['mean']
    finer_link = Path(os.path.relpath(source/'q2_model_metrics.csv', output)).as_posix()
    lines = [f'Later validation of unchanged source run `{summary["run_id"]}`: exact Q1 samples/coefficients and original Q2 prediction results were reproduced. '
             '[Checks and settings](summary.json) · [Separate provenance](manifest.json).',
             '**Q1: separate the questions.** The primary overall upset-minus-ordinary difference remains '
             f'{interval(average)}. Interactions measure changes in that difference; post-upset slopes measure age/experience associations '
             'within upset cases. Uncertain interactions do not imply zero post-upset slopes.',
             'Post-upset slopes sum the existing main and upset-interaction coefficients, using `Vaa + Vbb + 2Vab`, original player-cluster covariance '
             'and t(players−1) intervals. Units are percentage points per age year or natural-log(1 + prior eligible recorded matches) unit, '
             'holding other predictors fixed. Counts below are model-wide; [full contrasts](q1_post_upset_contrasts.csv) include upset-only support, SEs and separate interaction rows:',
             markdown_table(q1compact), ' '.join(interpretations),
             f'The separate primary next-three interactions are {interval(age_i)} per age year and '
             f'{interval(experience_i)} per log-experience unit. The nonoverlapping rows use the existing sensitivity rule and model.',
             f'**Q1 support/selection.** Among {pre["events"]:,} common top-50, known-rank losses ({pre["players"]:,} players), '
             f'only {int(extreme.events.sum()):,} combine age under 23 with 300+ prior matches, and {int(older_low.events.sum()):,} combine age 30+ with fewer than 100. '
             f'The primary design is full rank ({int(primary_design.design_rank)}/{int(primary_design.design_columns)}), but age/log-experience correlation is '
             f'{primary_design.age_log_experience_correlation:.3f}; sparse combinations limit practical overlap. '
             '[Cross-tabulations](q1_support.csv) and [conditioning diagnostics](q1_model_diagnostics.csv) document this without an arbitrary failure cutoff.',
             markdown_table(retention_compact),
             f'For next-three windows, {int(primary_ret.end_of_recorded_data_unobserved_followup_events.sum()):,} events lack enough recorded follow-ups, '
             f'{int(primary_ret.unresolved_record_blocks_followup_events.sum()):,} are blocked by unresolved records, '
             f'{int(primary_ret.excluded_or_ambiguous_followup_events.sum()):,} contain excluded/ambiguous follow-ups, and '
             f'{int(primary_ret.missing_model_covariates_events.sum()):,} otherwise available windows lack model covariates. '
             'End of recorded history does not establish retirement or administrative study-end censoring. Missing outcomes stay missing. '
             f'Omitted cases have stronger mean pre-loss rankings ({omitted_rank:.2f} versus {retained_rank:.2f}; lower is better) and higher recent form '
             f'({omitted_form:.3f} versus {retained_form:.3f}). [Group retention denominators/reasons](q1_retention.csv) and '
             '[age/experience, rank and form distributions](q1_distributions.csv) therefore warrant caution about selection.',
             '**Q2: paired prediction-error differences.** Positive Brier improvement means lower prediction error for the second model, '
             'not a percentage-point rise in winning chances. REPEAT uses `prior_h2h_meetings >= 1`; FIRST uses zero prior meetings. '
             'Both methods use the same paired differences and frozen predictions, without subset refits:',
             markdown_table(q2compact),
             'The added dyadic sandwich accounts for either shared player and repeated pairs, with 1/n² mean scaling, no finite-sample multiplier and normal intervals. '
             'Insufficient support or invalid variance withholds inference. The original pair bootstrap uses 500 draws, seed 42. '
             '[Paired estimates/SEs/statuses](q2_comparisons.csv), [Brier and secondary scores](q2_scores.csv), and '
             f'[original finer groups]({finer_link}) are retained. First-meeting gains can reflect different global fitted coefficients, not benefits from nonexistent prior meetings.',
             f'**Chronology and remaining limits.** The existing screen flags candidate-event exposure in '
             f'{int(q1_chron.flagged_records):,}/{int(q1_chron.denominator):,} primary Q1 windows for their focal player, '
             f'{int(q2_chron.flagged_records):,}/{int(q2_chron.denominator):,} Q2 evaluation matches for either participant, and '
             f'{int(q2_recent.flagged_records):,}/{int(q2_recent.denominator):,} Q2 matches through either player’s last-ten eligible history. '
             '[Traceable counts](chronology_summary.csv) use tournament-week/round order, not verified match dates. These are candidate overlaps, not proven errors; '
             'no dates or replacement windows were invented.',
             'Q1 remains a complete-case conditional association. Focal-player clustering does not remove follow-up selection, persistent player-level '
             'confounding or all shared-opponent dependence; adjustment for subsequent context prevents a simple causal recovery interpretation. '
             'Match outcomes do not measure psychological recovery. Q2 dyadic intervals assume negligible dependence between disjoint pairs; tournament shocks may remain. '
             'Both Q2 methods condition on fitted models/period, omit training uncertainty, and do not establish causal or universal gains or performance in a new era. '
             'The existing primary results and Q3 validation are preserved.']
    # Derive the interpretation of Q2 directly from each method, including disagreement.
    def q2_conclusion(subset, first, second):
        messages = []
        for method, label in [('opponent_pair_bootstrap', 'pair bootstrap'), ('shared_player_dyadic', 'shared-player dyadic')]:
            row = one(q2, subset=subset, metric='brier', first_model=first, second_model=second, method=method)
            evidence = contrast_evidence(row, 'mean_improvement', 'ci95_lower', 'ci95_upper')
            text = {'positive': 'supports lower prediction error', 'negative': 'supports higher prediction error',
                    'uncertain': 'leaves the direction uncertain', 'unavailable': 'has unavailable inference'}[evidence]
            messages.append(f'{label} {text}')
        if messages[0].removeprefix('pair bootstrap ') == messages[1].removeprefix('shared-player dyadic '):
            return f'{subset}, {comparison_names[(first, second)]}: both methods ' + messages[0].removeprefix('pair bootstrap ').replace('supports', 'support').replace('leaves', 'leave').replace('has', 'have') + '.'
        return f'{subset}, {comparison_names[(first, second)]}: ' + '; '.join(messages) + '.'
    conclusions = ' '.join(q2_conclusion(s, 'baseline', m) for s in ['ALL', 'REPEAT'] for m in ['plus_meeting_count', 'plus_h2h_results'])
    lines.insert(-2, conclusions)
    (output/'REPORT.md').write_text('\n\n'.join(lines)+'\n')
    age = one(q1, outcome='next3_win_rate', sample='all_windows', contrast='age_post_upset_per_year')
    exp = one(q1, outcome='next3_win_rate', sample='all_windows', contrast='experience_post_upset_log_unit')
    readme = (f'**Q1 direct post-upset associations:** next-three-match age slope {interval(age)} per year; '
              f'experience slope {interval(exp)} per log(1 + prior eligible recorded matches) unit. '
              'These conditional slopes answer a different question from modification of the upset-versus-ordinary difference. '
              '[Direct slopes and separate interactions](q1_post_upset_contrasts.csv).\n\n'
              f'**Q2 dependence and repeat encounters:** {conclusions} '
              'Brier remains primary; these are prediction-error differences, not increases in winning probability or causal effects. '
              '[Paired estimates under both methods](q2_comparisons.csv) and [support, retention and limitations](REPORT.md).')
    (output/'README_FINDINGS.md').write_text(readme+'\n')
    write_json(output/'claim_references.json', {'source_run_id': summary['run_id'],
        'Q1_post_upset_and_interactions': {'table': 'q1_post_upset_contrasts.csv', 'selectors': ['outcome', 'sample', 'contrast'], 'method': 'original_focal_player_cluster_t'},
        'Q1_retention': {'table': 'q1_retention.csv', 'selectors': ['outcome', 'sample', 'dimension', 'group', 'loss_type']},
        'Q2': {'table': 'q2_comparisons.csv', 'selectors': ['subset', 'metric', 'first_model', 'second_model', 'method']},
        'chronology': {'table': 'chronology_summary.csv', 'selectors': ['question', 'sample', 'outcome', 'check']}})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('outputs_final'))
    parser.add_argument('--output', type=Path, default=Path('validation/q1_q2_checks'))
    args = parser.parse_args()
    run_checks(args.source, args.output)
