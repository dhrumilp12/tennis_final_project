"""Separate, outcome-blind overlap audit of the saved adjusted Q3 sample.

Run from Dhrumil/: python tennis_q3_comparability.py [--diagnostics-only].
Never writes to the source run or changes its analysis specification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from tennis_repro import code_provenance, environment, sha256, verify_output
from tennis_q3_sample import reconstruct_adjusted_sample, verify_adjusted_sample

STRATA = ['player_id', 'surface', 'season']
MEASURES = ['player_rank', 'opponent_rank', 'log_rank_advantage',
            'recent_win_rate', 'opponent_recent_win_rate']
CALIPER = float(np.log(1.5))
SETTINGS = {
    'strata': STRATA, 'rank_ratio_caliper': 1.5, 'absolute_log_rank_caliper': CALIPER,
    'floating_point_boundary_tolerance': 1e-12,
    'distribution_minimum_per_hand_in_stratum': 5,
    'quantiles': [.05, .10, .25, .50, .75, .90, .95],
    'sensitivity_trigger': 'Either hand has <90% with a same-stratum dual-rank candidate, '
                           'or <80% in strata with >=5 observations per hand.',
    'trigger_note': 'Conservative descriptive coverage thresholds, not statistical tests or universal standards.',
    'matching_rule': 'Same focal player, surface, calendar season; traverse left rows by stable '
                     'match_id within sorted strata; nearest available right row by sum of absolute '
                     'log focal-rank and log opponent-rank differences, each <=log(1.5); '
                     'tie by right match_id; no reuse within focal player; no outcomes used.',
    'opportunity_rule': 'Reapply original minimum per opponent hand after matching; no rematching.',
    'inference': 'Existing Q3 within-player specification and shared-player dyadic sandwich; '
                 'retain original IDs, support, identification, residual-df and variance safeguards.',
}


def counts(d):
    return {'player_match_rows': len(d), 'unique_matches': int(d.match_id.nunique()),
            'focal_players': int(d.player_id.nunique()), 'distinct_opponents': int(d.opponent_id.nunique())}


def overlap_diagnostics(d):
    """Candidate coverage is many-to-many feasibility, not selected matching.

    No range-only overlap assertion: report central quartiles, empirical CDF
    distances and simultaneous rank-caliper feasibility within each focal player.
    Sparse strata are not called well supported merely because they have both hands.
    """
    rows = []
    for key, g in d.groupby(STRATA, sort=True, dropna=False):
        left, right = [g.loc[g.opponent_hand.eq(hand)] for hand in ['L', 'R']]
        row = dict(zip(STRATA, key))
        row.update(player_hand=g.player_hand.iloc[0], n_L=len(left), n_R=len(right))
        logs = []
        for x in [left, right]:
            ranks = x[['player_rank', 'opponent_rank']].to_numpy(float)
            valid = np.isfinite(ranks) & (ranks > 0)
            logs.append(np.log(np.where(valid, ranks, np.nan)))
        lr, rr = logs
        # The tiny tolerance only absorbs floating-point representation at 1.5.
        edges = (np.abs(lr[:, None, :] - rr[None, :, :]) <= CALIPER + 1e-12).all(axis=2)
        row.update(with_rank_candidate_L=int(edges.any(axis=1).sum()),
                   with_rank_candidate_R=int(edges.any(axis=0).sum()))
        if not len(left) or not len(right):
            status = 'one_hand_only'
        elif not edges.any():
            status = 'no_rank_candidates'
        elif min(len(left), len(right)) < 5:
            status = 'insufficient_observations'
        else:
            status = 'assessable'
        row['status'] = status
        for field in MEASURES:
            a, b = [x[field].dropna().to_numpy(float) for x in [left, right]]
            for hand, values in [('L', a), ('R', b)]:
                for label, q in [('q25', .25), ('median', .5), ('q75', .75)]:
                    row[f'{field}_{hand}_{label}'] = float(np.quantile(values, q)) if len(values) else np.nan
            if len(a) and len(b):
                grid = np.sort(np.concatenate([a, b]))
                row[f'{field}_ecdf_distance'] = float(np.max(np.abs(
                    np.searchsorted(np.sort(a), grid, side='right') / len(a) -
                    np.searchsorted(np.sort(b), grid, side='right') / len(b))))
                row[f'{field}_median_L_minus_R'] = float(np.median(a) - np.median(b))
            else:
                row[f'{field}_ecdf_distance'] = np.nan
                row[f'{field}_median_L_minus_R'] = np.nan
        rows.append(row)
    strata = pd.DataFrame(rows)
    if strata.empty:
        columns = STRATA + ['player_hand', 'n_L', 'n_R', 'with_rank_candidate_L', 'with_rank_candidate_R', 'status']
        columns += [f'{field}_{hand}_{q}' for field in MEASURES for hand in ['L', 'R'] for q in ['q25', 'median', 'q75']]
        columns += [f'{field}_{stat}' for field in MEASURES for stat in ['ecdf_distance', 'median_L_minus_R']]
        strata = pd.DataFrame(columns=columns)
    coverage = []
    for own in ['all', 'R', 'L']:
        s = strata if own == 'all' else strata.loc[strata.player_hand.eq(own)]
        both = s.n_L.gt(0) & s.n_R.gt(0)
        adequate = s.n_L.ge(5) & s.n_R.ge(5)
        for hand in ['L', 'R']:
            n = int(s[f'n_{hand}'].sum())
            coverage.append({'player_hand': own, 'opponent_hand': hand,
                             'player_match_rows': n, 'strata': len(s), 'both_hand_strata': int(both.sum()),
                             'one_hand_strata': int((~both).sum()),
                             'no_rank_candidate_strata': int(s.status.eq('no_rank_candidates').sum()),
                             'sparse_both_hand_strata': int((both & ~adequate).sum()),
                             'both_hand_rows': int(s.loc[both, f'n_{hand}'].sum()),
                             'adequately_observed_rows': int(s.loc[adequate, f'n_{hand}'].sum()),
                             'rank_candidate_rows': int(s[f'with_rank_candidate_{hand}'].sum())})
    coverage = pd.DataFrame(coverage)
    for label in ['both_hand', 'adequately_observed', 'rank_candidate']:
        coverage[f'{label}_share'] = coverage[f'{label}_rows'] / coverage.player_match_rows.replace(0, np.nan)
    return strata, coverage


def distribution_summary(d, sample):
    rows = []
    for dimension in ['overall', 'player_hand', 'surface', 'season']:
        groups = [('all', d)] if dimension == 'overall' else d.groupby(dimension, sort=True, dropna=False)
        for group, part in groups:
            for hand in ['L', 'R']:
                g = part.loc[part.opponent_hand.eq(hand)]
                for field in MEASURES:
                    v = g[field].dropna()
                    row = dict(sample=sample, dimension=dimension, group=group,
                               opponent_hand=hand, measure=field, **counts(g), nonmissing=len(v))
                    row.update({f'q{int(q*100):02d}': float(v.quantile(q)) if len(v) else np.nan for q in SETTINGS['quantiles']})
                    row['iqr'] = row['q75'] - row['q25']
                    rows.append(row)
    return pd.DataFrame(rows)


def balance_summary(d, sample):
    """Signed L-minus-R descriptive differences; no hypothesis tests."""
    rows = []
    for own in ['all', 'R', 'L']:
        g = d if own == 'all' else d.loc[d.player_hand.eq(own)]
        for field in MEASURES + ['log_player_rank', 'log_opponent_rank']:
            source = field.removeprefix('log_') if field in ['log_player_rank', 'log_opponent_rank'] else field
            a, b = [g.loc[g.opponent_hand.eq(h), source].dropna() for h in ['L', 'R']]
            if field in ['log_player_rank', 'log_opponent_rank']:
                a, b = np.log(a), np.log(b)
            scale = np.sqrt((a.var() + b.var()) / 2)
            rows.append(dict(sample=sample, player_hand=own, measure=field, n_L=len(a), n_R=len(b),
                             mean_L=a.mean(), mean_R=b.mean(), mean_L_minus_R=a.mean()-b.mean(),
                             median_L_minus_R=a.median()-b.median(),
                             standardized_mean_difference=(a.mean()-b.mean())/scale if scale > 0 else np.nan))
    return pd.DataFrame(rows)


def retention_table(original, samples):
    rows = []
    for name, d in samples.items():
        for own in ['all', 'R', 'L']:
            for hand in ['L', 'R']:
                mask = original.opponent_hand.eq(hand)
                chosen = d.opponent_hand.eq(hand)
                if own != 'all':
                    mask &= original.player_hand.eq(own)
                    chosen &= d.player_hand.eq(own)
                before, after = counts(original.loc[mask]), counts(d.loc[chosen])
                row = dict(sample=name, player_hand=own, opponent_hand=hand, **after)
                for unit in before:
                    row[f'original_{unit}'] = before[unit]
                    row[f'{unit}_retained_share'] = after[unit]/before[unit] if before[unit] else np.nan
                rows.append(row)
    return pd.DataFrame(rows)


def make_plots(samples, coverage, output):
    os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'tennis-project-matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    labels = ['Focal historical rank', 'Opponent historical rank', 'log(opponent rank / focal rank)']
    fig, axes = plt.subplots(len(samples), 3, figsize=(13, 3.6*len(samples)), squeeze=False)
    for row, (name, d) in enumerate(samples.items()):
        for col, field in enumerate(MEASURES[:3]):
            ax = axes[row, col]
            for hand, color in [('L', '#bf5934'), ('R', '#246b91')]:
                v = np.sort(d.loc[d.opponent_hand.eq(hand), field].dropna())
                if len(v):
                    ax.step(v, np.arange(1, len(v)+1)/len(v), where='post', color=color,
                            label=f'Opponent {hand}: n={len(v):,}')
            if col < 2:
                ax.set_xscale('log')
            ax.set(title=f'{name}\n{labels[col]}', ylabel='Within-group cumulative proportion', ylim=(0, 1.02))
            ax.legend(fontsize=8, loc='lower right')
            ax.grid(alpha=.18)
    fig.suptitle('Historical rankings in the adjusted Q3 sample and selected sensitivity\nEach opponent-hand distribution is normalized separately', fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, .94))
    fig.savefig(output/'rank_distributions.png', dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    c = coverage.loc[coverage.player_hand.eq('all')].set_index('opponent_hand').loc[['L', 'R']]
    x = np.arange(3)
    for offset, (hand, color) in enumerate([('L', '#bf5934'), ('R', '#246b91')]):
        heights = c.loc[hand, ['both_hand_share', 'adequately_observed_share', 'rank_candidate_share']].to_numpy(float)
        bars = ax.bar(x+(offset-.5)*.35, 100*heights, .35, color=color,
                      label=f'Opponent {hand}, denominator n={int(c.loc[hand, "player_match_rows"]):,}')
        ax.bar_label(bars, fmt='%.1f%%', padding=3)
    ax.set(xticks=x, xticklabels=['Both opponent hands\nin same stratum', 'At least 5 observations\nper hand in stratum', 'At least one dual-rank\ncaliper candidate'],
           ylabel='Percent of original adjusted observations', ylim=(0, 112),
           title='Within focal player × surface × season coverage')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.17), ncols=2)
    fig.tight_layout()
    fig.savefig(output/'within_player_coverage.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')


def run_validation(source=Path('outputs_final'), output=Path('validation/q3_comparability'), diagnostics_only=False):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError('Validation must be separate from source run.')
    output.mkdir(parents=True, exist_ok=True)
    historical = verify_output(source)
    before = {str(p.relative_to(source)): sha256(p) for p in sorted(source.rglob('*')) if p.is_file()}
    baseline = output/'baseline_hashes.json'
    if baseline.exists():
        if json.loads(baseline.read_text())['outputs_final'] != before:
            raise ValueError('Source run differs from recorded validation baseline.')
    else:
        write_json(baseline, {'source_run_id': historical['run_id'], 'outputs_final': before})
    # This file is written before diagnostics, matching, or sensitivity outcomes.
    write_json(output/'protocol.json', SETTINGS)
    players = pd.read_csv(source/'player_match_features.csv.gz')
    minimum = historical['configuration']['min_hand_matches']
    d = reconstruct_adjusted_sample(players, minimum)
    checks = verify_adjusted_sample(players, d, historical, source)
    d[['player_id', 'match_id', 'opponent_id']].to_csv(output/'adjusted_sample_ids.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    strata, coverage = overlap_diagnostics(d)
    strata.to_csv(output/'strata.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    coverage.to_csv(output/'coverage.csv', index=False)
    both_keys = strata.loc[strata.n_L.gt(0) & strata.n_R.gt(0), STRATA]
    both = d.merge(both_keys, on=STRATA, how='inner', validate='many_to_one')
    overall = coverage.loc[coverage.player_hand.eq('all')]
    needed = bool((overall.rank_candidate_share < .9).any() or (overall.adequately_observed_share < .8).any())
    decision = {'sensitivity_needed': needed, 'outcomes_examined_for_decision': False,
                'reason': 'Within-player coverage remains uncertain under the recorded descriptive thresholds.' if needed else 'Both hands meet recorded candidate and distribution coverage thresholds.',
                'coverage': json.loads(overall.to_json(orient='records'))}
    write_json(output/'decision.json', decision)
    print(json.dumps({'adjusted': counts(d), 'decision': decision}, indent=2), flush=True)
    distributions = [distribution_summary(d, 'adjusted'), distribution_summary(both, 'both_hand_strata')]
    samples = {'adjusted': d}
    info = {'status': 'not_needed' if not needed else 'pending_diagnostics_only'}
    if needed and not diagnostics_only:
        from tennis_q3_matching import match_observations, refit_matched
        selected, pairs = match_observations(d, CALIPER)
        pairs.to_csv(output/'matched_pairs.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
        contrasts, info, analyzed = refit_matched(selected, minimum)
        contrasts.to_csv(output/'matched_contrasts.csv', index=False)
        analyzed[['player_id', 'match_id', 'opponent_id']].to_csv(output/'matched_analysis_ids.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
        write_json(output/'matched_model.json', info)
        samples.update(matched_selected=selected, matched_analysis=analyzed)
        distributions.append(distribution_summary(analyzed, 'matched_analysis'))
    pd.concat(distributions, ignore_index=True).to_csv(output/'distributions.csv', index=False)
    balance = pd.concat([balance_summary(x, name) for name, x in samples.items()], ignore_index=True)
    balance.to_csv(output/'balance.csv', index=False)
    retention = retention_table(d, samples)
    retention.to_csv(output/'retention.csv', index=False)
    compact = pd.concat(distributions, ignore_index=True)
    compact = compact.loc[compact.dimension.eq('overall'), ['sample', 'opponent_hand', 'measure', 'nonmissing', 'q10', 'q25', 'q50', 'q75', 'q90', 'iqr']]
    compact.to_csv(output/'compact_summary.csv', index=False)
    plot_samples = {'Adjusted': d}
    if 'matched_analysis' in samples:
        plot_samples['Matched sensitivity'] = samples['matched_analysis']
    make_plots(plot_samples, coverage, output)
    after = {str(p.relative_to(source)): sha256(p) for p in sorted(source.rglob('*')) if p.is_file()}
    if before != after:
        raise AssertionError('Historical output files changed.')
    checks['all_historical_output_hashes_unchanged'] = True
    summary = {'source_run_id': historical['run_id'], 'adjusted_sample': counts(d),
               'minimum_opportunities_per_hand': minimum, 'sensitivity_needed': needed,
               'sensitivity_executed': needed and not diagnostics_only,
               'sensitivity_sample': counts(samples['matched_analysis']) if 'matched_analysis' in samples else None,
               'checks_executed': checks}
    write_json(output/'summary.json', summary)
    if not diagnostics_only:
        write_report(source, output, historical, strata, coverage, compact, balance, retention, summary)
        provenance = code_provenance()
        artifacts = {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file() and p.name not in ['manifest.json', 'tests.txt', 'verification.json']}
        write_json(output/'manifest.json', {
            'validation_id': 'q3-comparability-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
            'source_run_id': historical['run_id'], 'source_run_summary_sha256': sha256(source/'run_summary.json'),
            'created_at_utc': datetime.now(timezone.utc).isoformat(), 'code_version': provenance,
            'code_hashes': provenance['source_hashes'], 'runtime': environment(), 'settings': SETTINGS,
            'input_hashes': {str(source/name): before[name] for name in ['run_summary.json', 'player_match_features.csv.gz', 'q3_adjusted_contrasts.csv', 'q3_subgroup_support.csv', 'q3_player_exposure.csv']},
            'artifacts': artifacts, 'checks_executed': checks,
            'note': 'Separate later validation of saved data. Historical run manifest is unchanged. Tests recorded separately in verification.json.'})
    return summary


def write_report(source, output, historical, strata, coverage, compact, balance, retention, summary):
    """Generate ordinary-English findings only from executed diagnostics."""
    from tennis_reporting import markdown_table, interval
    c = coverage.loc[coverage.player_hand.eq('all')].set_index('opponent_hand')
    both = strata.n_L.gt(0) & strata.n_R.gt(0)
    sparse = both & (strata.n_L.lt(5) | strata.n_R.lt(5))
    lines = [
        f'This separate validation uses the exact adjusted Q3 sample from run `{historical["run_id"]}`: '
        f'{summary["adjusted_sample"]["player_match_rows"]:,} player-match observations, '
        f'{summary["adjusted_sample"]["unique_matches"]:,} physical matches and '
        f'{summary["adjusted_sample"]["focal_players"]:,} focal players. Two views of a match are dependent; '
        'match/player/opponent totals across groups can overlap and must not be added as independent observations.',
        'Unequal group sizes are not automatically a problem. The primary model already adjusts for rank advantage '
        'and both players’ prior recent form, but adjustment does not ensure comparable opponents. '
        'Only saved historical rankings are used; missing ranks are not invented.',
    ]
    tab = retention.loc[retention['sample'].eq('adjusted') & retention.player_hand.eq('all'),
                        ['opponent_hand', 'player_match_rows', 'unique_matches', 'focal_players', 'distinct_opponents']]
    lines += [markdown_table(tab),
              f'Within focal-player × surface × calendar-season strata, {int(both.sum()):,}/{len(strata):,} contain both hands; '
              f'{int((~both).sum()):,} contain only one ({int((strata.n_R.eq(0)).sum()):,} left-only, '
              f'{int((strata.n_L.eq(0)).sum()):,} right-only). '
              f'Both-hand strata cover {int(c.loc["L", "both_hand_rows"]):,}/{int(c.loc["L", "player_match_rows"]):,} '
              f'({100*c.loc["L", "both_hand_share"]:.1f}%) left-opponent observations and '
              f'{int(c.loc["R", "both_hand_rows"]):,}/{int(c.loc["R", "player_match_rows"]):,} '
              f'({100*c.loc["R", "both_hand_share"]:.1f}%) right-opponent observations. '
              f'{int(sparse.sum()):,} both-hand strata have fewer than five observations in at least one group '
              '(insufficient for a useful distribution comparison, not necessarily no possible comparison). '
              f'{int(strata.status.eq("no_rank_candidates").sum()):,} both-hand strata have no pair satisfying both rank calipers. '
              'A shared season is a diagnostic restriction, not proof of identical playing conditions.',
              f'A same-stratum counterpart within a factor of 1.5 on **both** focal and opponent rank exists for '
              f'{int(c.loc["L", "rank_candidate_rows"]):,}/{int(c.loc["L", "player_match_rows"]):,} '
              f'({100*c.loc["L", "rank_candidate_share"]:.1f}%) left-opponent and '
              f'{int(c.loc["R", "rank_candidate_rows"]):,}/{int(c.loc["R", "player_match_rows"]):,} '
              f'({100*c.loc["R", "rank_candidate_share"]:.1f}%) right-opponent observations. '
              'These are candidate counts before competition for matches without replacement; ranges alone were not used to declare overlap.',
              'Historical rank distributions (median and quartiles; complete quantiles and focal-hand/surface/season breakdowns are linked below):']
    ranks = compact.loc[compact['sample'].eq('adjusted') & compact.measure.isin(MEASURES[:3]),
                        ['opponent_hand', 'measure', 'nonmissing', 'q25', 'q50', 'q75']]
    lines += [markdown_table(ranks, digits=2)]
    supported = strata.loc[strata.n_L.ge(5) & strata.n_R.ge(5)]
    within_rows = []
    for field in MEASURES[:3]:
        q_overlap = (supported[[f'{field}_L_q25', f'{field}_R_q25']].max(axis=1) <=
                     supported[[f'{field}_L_q75', f'{field}_R_q75']].min(axis=1))
        within_rows.append({'measure': field, 'strata_with_at_least_5_per_hand': len(supported),
                            'strata_with_overlapping_middle_50_percent': int(q_overlap.sum()),
                            'median_within_stratum_ECDF_distance': supported[f'{field}_ecdf_distance'].median(),
                            'median_absolute_within_stratum_median_difference': supported[f'{field}_median_L_minus_R'].abs().median()})
    pd.DataFrame(within_rows).to_csv(output/'within_stratum_summary.csv', index=False)
    lines += ['Among strata with at least five observations per hand, the table below gives equally weighted '
              'stratum diagnostics. ECDF distance is the largest gap between normalized cumulative distributions '
              '(0 means identical empirical distributions; 1 means fully separated). These descriptive distances '
              'can be noisy in small strata and are not significance tests. Overlapping middle halves alone do not establish comparability.',
              markdown_table(pd.DataFrame(within_rows), digits=3)]
    if summary['sensitivity_executed']:
        contrasts = pd.read_csv(output/'matched_contrasts.csv')
        primary = pd.read_csv(source/'q3_adjusted_contrasts.csv')
        lines += ['Coverage remains uncertain, so one sensitivity was run under the [rule recorded before fitting](protocol.json). '
                  'It pairs left- and right-opponent observations for the same focal player, surface and calendar season; '
                  'each absolute log-rank difference must be ≤ log(1.5). Candidates are chosen by the sum of the two differences, '
                  'without replacement within a player, with stable match-ID traversal and ties. The factor 1.5 is pragmatic, '
                  'not a universal standard. Outcomes do not select pairs, and no alternative calipers were searched. '
                  'The original minimum of ten opportunities per hand is reapplied after matching.',
                  markdown_table(retention.loc[retention['sample'].eq('matched_analysis'),
                      ['player_hand', 'opponent_hand', 'player_match_rows', 'original_player_match_rows',
                       'player_match_rows_retained_share', 'focal_players', 'unique_matches']], digits=3)]
        for hand, name in [('R', 'right-handed'), ('L', 'left-handed')]:
            a = primary.loc[primary.player_hand.eq(hand)].iloc[0]
            b = contrasts.loc[contrasts.player_hand.eq(hand)].iloc[0]
            lines.append(f'For {name} focal players, the primary L-minus-R estimate is {interval(a, "difference_pp")}; '
                         f'the matched sensitivity is {interval(b, "difference_pp")}. '
                         + ('The point estimate changes direction. ' if a.difference_pp*b.difference_pp < 0 else 'The point estimates have the same direction. ')
                         + ('The matched interval is wider. ' if b.get('ci95_upper_pp', np.nan)-b.get('ci95_lower_pp', np.nan) > a.ci95_upper_pp-a.ci95_lower_pp else
                            'The matched interval is narrower. ' if b.get('inference_status') == 'available' else '')
                         + ('The matched interval includes zero.' if b.get('inference_status') == 'available' and b.ci95_lower_pp <= 0 <= b.ci95_upper_pp else
                            'The matched interval excludes zero.' if b.get('inference_status') == 'available' else 'Matched inference is unavailable under the original safeguards.'))
        b = balance.loc[balance.player_hand.eq('all') & balance['sample'].isin(['adjusted', 'matched_analysis']) &
                        balance.measure.isin(['log_player_rank', 'log_opponent_rank', 'recent_win_rate', 'opponent_recent_win_rate'])]
        lines += ['Before/after balance (signed left-minus-right means; recent form is a prior win proportion):',
                  markdown_table(b[['sample', 'measure', 'mean_L_minus_R', 'standardized_mean_difference']], digits=3),
                  'This refits the existing Q3 specification and shared-player dyadic uncertainty calculation with original participant and match IDs. '
                  'Selected observations remain dependent when they share either player. The sensitivity estimates describe a narrower selected sample; '
                  'changes in size, direction and uncertainty should be considered alongside the retention table, rather than treating interval inclusion of zero as the only result.']
    else:
        lines += ['The recorded coverage thresholds support keeping the primary analysis without a matched sensitivity; '
                  'this is descriptive support, not a nonsignificance argument or proof of identical groups.']
    lines += ['Rankings imperfectly measure strength; matching does not equalize injuries, tournament conditions or all prior form. '
              'Restrictions select a narrower sample, sparse strata remain uncertain, and this observational comparison is not causal. '
              'The primary Q1/Q2/Q3 numerical outputs are unchanged.',
              '[Normalized rank distributions](rank_distributions.png) · [Within-player coverage plot](within_player_coverage.png) · '
              '[Compact summary](compact_summary.csv) · [Quantiles and breakdowns](distributions.csv) · '
              '[Within-stratum quartiles and ECDF distances](strata.csv.gz) · [Coverage by focal hand](coverage.csv) · '
              '[Retention](retention.csv) · [Rank/form balance by focal hand](balance.csv) · '
              '[Sample verification](summary.json) · [Separate validation manifest](manifest.json).']
    model_path = output/'matched_model.json'
    warnings = json.loads(model_path.read_text()).get('warnings', []) if summary['sensitivity_executed'] else []
    if warnings:
        lines.insert(-2, 'Sensitivity uncertainty notes: ' + ' '.join(warnings))
    (output/'DETAILS.md').write_text('\n\n'.join(lines)+'\n')
    # Keep the existing reports concise; detailed diagnostics stay in this folder.
    rank = compact.loc[compact['sample'].eq('adjusted') & compact.measure.eq('opponent_rank')].set_index('opponent_hand')
    brief = [
        'Unequal counts do not automatically invalidate this comparison. Ranking and prior-form adjustment are already '
        'present, but do not guarantee comparable observations. This separate check reconstructs the exact adjusted '
        f'sample: {len(strata):,} player × surface × season strata, with {int(c.loc["L", "player_match_rows"]):,} '
        f'left-opponent and {int(c.loc["R", "player_match_rows"]):,} right-opponent observations '
        f'({summary["adjusted_sample"]["unique_matches"]:,} physical matches; {summary["adjusted_sample"]["focal_players"]:,} focal players). '
        'Player-match observations, physical matches, focal players and distinct opponents are counted separately in the '
        '[detailed check](DETAILS.md); totals across groups overlap.',
        f'Left-opponent historical rank has median {rank.loc["L", "q50"]:.0f} '
        f'(middle half {rank.loc["L", "q25"]:.0f}–{rank.loc["L", "q75"]:.0f}), versus '
        f'{rank.loc["R", "q50"]:.0f} ({rank.loc["R", "q25"]:.0f}–{rank.loc["R", "q75"]:.0f}) for right opponents; '
        'lower rank numbers indicate higher rankings. '
        f'{int(both.sum()):,}/{len(strata):,} strata contain both hands, covering '
        f'{int(c.loc["L", "both_hand_rows"]):,}/{int(c.loc["L", "player_match_rows"]):,} '
        f'({100*c.loc["L", "both_hand_share"]:.1f}%) left and '
        f'{int(c.loc["R", "both_hand_rows"]):,}/{int(c.loc["R", "player_match_rows"]):,} '
        f'({100*c.loc["R", "both_hand_share"]:.1f}%) right observations. '
        f'{int(sparse.sum()):,} both-hand strata have fewer than five observations in at least one hand; '
        f'{int(strata.status.eq("no_rank_candidates").sum()):,} have no pair meeting both rank calipers. '
        'Sparse observations and absent comparable observations are different limitations. '
        f'Only {100*c.loc["L", "rank_candidate_share"]:.1f}% of left and {100*c.loc["R", "rank_candidate_share"]:.1f}% '
        'of right observations have such a candidate. A shared season does not ensure identical conditions.'
    ]
    if summary['sensitivity_executed']:
        retain = retention.loc[retention['sample'].eq('matched_analysis') & retention.player_hand.eq('all')].set_index('opponent_hand')
        brief += ['Coverage remained uncertain, so **one matched sensitivity** used the [outcome-blind recorded rule](protocol.json): '
                  'same player, surface and season; both focal and opponent ranks within a factor of 1.5; nearest summed '
                  'log-rank differences, without replacement, with stable-ID ties. The caliper is pragmatic, not universal. '
                  'Original opportunity/support checks and shared-player dyadic uncertainty were retained. '
                  f'The refit retains {summary["sensitivity_sample"]["player_match_rows"]:,} observations, '
                  f'{summary["sensitivity_sample"]["unique_matches"]:,} physical matches and '
                  f'{summary["sensitivity_sample"]["focal_players"]:,} players: '
                  f'{100*retain.loc["L", "player_match_rows_retained_share"]:.1f}% of original left-opponent and '
                  f'{100*retain.loc["R", "player_match_rows_retained_share"]:.1f}% of right-opponent observations. '
                  'See [retention by focal hand](retention.csv).']
        comparison = []
        for hand in ['R', 'L']:
            a = primary.loc[primary.player_hand.eq(hand)].iloc[0]
            b = contrasts.loc[contrasts.player_hand.eq(hand)].iloc[0]
            comparison.append({'Focal hand': hand, 'Primary L-minus-R': interval(a, 'difference_pp'),
                               'Matched sensitivity': interval(b, 'difference_pp')})
        changes = []
        for hand, label in [('R', 'Right-handed'), ('L', 'Left-handed')]:
            a = primary.loc[primary.player_hand.eq(hand)].iloc[0]
            b = contrasts.loc[contrasts.player_hand.eq(hand)].iloc[0]
            direction = 'changes direction' if a.difference_pp*b.difference_pp < 0 else 'keeps its direction'
            if b.inference_status == 'available':
                width = 'wider' if b.ci95_upper_pp-b.ci95_lower_pp > a.ci95_upper_pp-a.ci95_lower_pp else 'narrower'
                zero = 'includes' if b.ci95_lower_pp <= 0 <= b.ci95_upper_pp else 'excludes'
                changes.append(f'{label}: the point estimate {direction}; the interval is {width} and {zero} zero.')
            else:
                changes.append(f'{label}: matched inference is unavailable under the original safeguards.')
        brief += [markdown_table(pd.DataFrame(comparison)), ' '.join(changes)]
        form = balance.loc[balance.player_hand.eq('all')].set_index(['sample', 'measure'])
        brief += [f'The mean log-opponent-rank gap (L-minus-R) falls from '
                  f'{form.loc[("adjusted", "log_opponent_rank"), "mean_L_minus_R"]:.3f} to '
                  f'{form.loc[("matched_analysis", "log_opponent_rank"), "mean_L_minus_R"]:.3f}. '
                  f'Prior-form gaps fall from {form.loc[("adjusted", "recent_win_rate"), "mean_L_minus_R"]:.3f} to '
                  f'{form.loc[("matched_analysis", "recent_win_rate"), "mean_L_minus_R"]:.3f} for focal players and '
                  f'{form.loc[("adjusted", "opponent_recent_win_rate"), "mean_L_minus_R"]:.3f} to '
                  f'{form.loc[("matched_analysis", "opponent_recent_win_rate"), "mean_L_minus_R"]:.3f} for opponents. '
                  'Form is a prior win proportion; see [full rank/form balance](balance.csv).']
        if any('indefinite' in note for note in warnings):
            brief += ['The matched covariance matrix is indefinite; both reported contrast variances are positive. '
                      'Under the unchanged safeguards their intervals remain available but exploratory; no variance repair was applied.']
    else:
        brief += ['Measured coverage meets the recorded diagnostic thresholds, so matching was not needed. '
                  'This decision does not rely on a nonsignificant statistical test.']
    brief += ['Rankings imperfectly measure strength; restrictions select a narrower sample and do not remove all form or playing-condition differences. '
              'This remains observational, not causal. **Primary Q1/Q2/Q3 results are preserved.** '
              '[Normalized rank plot](rank_distributions.png) · [Within-player coverage](within_player_coverage.png) · '
              '[Summary table](compact_summary.csv) · [Detailed distributions and limitations](DETAILS.md) · '
              '[Validation provenance](manifest.json).']
    (output/'REPORT.md').write_text('\n\n'.join(brief)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('outputs_final'))
    parser.add_argument('--output', type=Path, default=Path('validation/q3_comparability'))
    parser.add_argument('--diagnostics-only', action='store_true')
    args = parser.parse_args()
    run_validation(args.source, args.output, args.diagnostics_only)
