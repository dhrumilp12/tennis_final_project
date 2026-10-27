"""Generate report numbers directly from a verified run; no embedded findings."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from tennis_repro import verify_output, sha256

TEAM = 'Phouvadeth Vathana, Joseph Bronyah, Dhrumil Patel'


def markdown_table(frame, columns=None, digits=3):
    frame = frame if columns is None else frame[columns]
    def value(v):
        if pd.isna(v): return 'unavailable'
        if isinstance(v, (float, np.floating)): return f'{v:,.{digits}f}'
        return str(v).replace('|', '/')
    return '\n'.join(['| ' + ' | '.join(frame.columns) + ' |',
                     '| ' + ' | '.join(['---']*len(frame.columns)) + ' |'] +
                    ['| ' + ' | '.join(value(v) for v in row) + ' |' for row in frame.itertuples(index=False, name=None)])


def one(frame, **selectors):
    d = frame
    for k,v in selectors.items(): d = d.loc[d[k].eq(v)]
    if len(d)!=1: raise ValueError(f'Expected exactly one source row: {selectors}; found {len(d)}')
    return d.iloc[0]


def interval(row, estimate='estimate_pp', lower='ci95_lower_pp', upper='ci95_upper_pp', digits=2, unit=' pp'):
    if pd.isna(row[estimate]): return 'unavailable'
    if pd.isna(row[lower]) or pd.isna(row[upper]): return f'{row[estimate]:+.{digits}f}{unit}; inference unavailable'
    return f'{row[estimate]:+.{digits}f}{unit} (95% interval {row[lower]:+.{digits}f} to {row[upper]:+.{digits}f}{unit})'


def direction(row, lower='ci95_lower_pp', upper='ci95_upper_pp'):
    if pd.isna(row[lower]) or pd.isna(row[upper]): return 'inference is unavailable'
    if row[lower] <= 0 <= row[upper]: return 'the interval includes zero'
    return 'the interval is above zero' if row[lower]>0 else 'the interval is below zero'


def findings(output):
    """Shared by README, notebook and reports; selectors are claim provenance."""
    output=Path(output); s=verify_output(output)
    read=lambda n: pd.read_csv(output/f'{n}.csv')
    q1=read('q1_adjusted_contrasts'); q2=read('q2_paired_improvements'); q3=read('q3_adjusted_contrasts')
    a=one(q1,outcome='next3_win_rate',sample='all_windows',contrast='average_upset_minus_ordinary',subgroup='all')
    b=one(q1,outcome='next1_win',sample='all_windows',contrast='average_upset_minus_ordinary',subgroup='all')
    age=one(q1,outcome='next3_win_rate',sample='all_windows',contrast='age_interaction_per_year',subgroup='all')
    exp=one(q1,outcome='next3_win_rate',sample='all_windows',contrast='experience_interaction_log_unit',subgroup='all')
    count=one(q2,first_model='baseline',second_model='plus_meeting_count',metric='brier')
    h2h=one(q2,first_model='baseline',second_model='plus_h2h_results',metric='brier')
    r=one(q3,player_hand='R'); l=one(q3,player_hand='L')
    q1text=(f'After a ranking upset, adjusted next-three-match performance differed from ordinary losses by {interval(a)} '
            f'across {int(a.events):,} complete, covariate-usable loss events from {int(a.players):,} players. '
            f'The next-match difference was {interval(b)}. '
            f'Age modification was {interval(age)} per year; experience modification was {interval(exp)} per unit of log(1 + prior matches). '
            f'For age, {direction(age)}; for experience, {direction(exp)}. '
            'Interpret the joint age and experience interactions using their intervals, rather than treating descriptive age bands as experience groups. '
            'Adjustment includes subsequent playing context, so this is a conditional association, not a causal recovery effect.')
    q2text=(f'On {s["q2"]["test_matches"]:,} held-out matches, meeting count alone changed Brier performance by '
            f'{interval(count,"mean_improvement","ci95_lower","ci95_upper",6,"")}; {direction(count,"ci95_lower","ci95_upper")}. '
            f'Adding previous head-to-head results changed Brier performance by '
            f'{interval(h2h,"mean_improvement","ci95_lower","ci95_upper",6,"")}. '
            f'Positive improvement means lower prediction error; for previous results, {direction(h2h,"ci95_lower","ci95_upper")}. Meeting count and previous outcomes answer different questions. '
            'Pair-cluster intervals leave shared-player dependence across pairs unresolved.')
    q3text=(f'Adjusted opponent-left-minus-right win-probability differences were {interval(r,"difference_pp")} '
            f'for {int(r.players):,} right-handed focal players and {interval(l,"difference_pp")} for {int(l.players):,} left-handed focal players. '
            f'For right-handed players, {direction(r)}; for left-handed players, {direction(l)}. '
            'The results do not establish a uniform handedness advantage. Dyadic intervals account for matches sharing either participant; '
            'the smaller left-handed subgroup and remaining event/network dependence warrant caution.')
    return s, [q1text,q2text,q3text]


def incomplete_reports(output, root, summary):
    """Explicitly report unavailable models; never fabricate final estimates."""
    reports=root/'reports';reports.mkdir(parents=True,exist_ok=True)
    answers=[f'{q.upper()}: {summary[q]["status"]} See descriptive tables; no missing adjusted estimate is interpreted as zero.' for q in ['q1','q2','q3']]
    text=(f'# Analysis availability report\n\nTeam: {TEAM}\n\nRun ID: `{summary["run_id"]}`.\n\n'
          'At least one required model/contrast is unavailable. This is an incomplete research report, not evidence that all questions were answered.\n\n'+
          '\n\n'.join(answers)+'\n\n'+str(summary.get('test_data_warning') or 'No synthetic substitute was used.'))
    tables={}
    for name in ['attrition','q1_summary_overall','q1_model_samples','q3_subgroup_support']:
        path=output/f'{name}.csv'
        if path.exists():
            frame=pd.read_csv(path)
            text+=f'\n\nSource: `{path}`.\n\n'+markdown_table(frame)
            tables[name]=json.loads(frame.to_json(orient='records',double_precision=15))
    for name in ['RESULTS.md','FINAL_REPORT.md','DATA_QUALITY.md']:
        (reports/name).write_text(text+'\n')
    (reports/'report_claims.json').write_text(json.dumps({'run_id':summary['run_id'],'answers':answers,'tables':tables},indent=2,allow_nan=False))
    (reports/'report_manifest.json').write_text(json.dumps({'run_id':summary['run_id'],'outputs_summary_sha256':sha256(output/'run_summary.json'),'files':{p.name:sha256(p) for p in sorted(reports.iterdir()) if p.is_file() and p.name!='report_manifest.json'}},indent=2))
    return summary,answers


def generate_reports(output='outputs_final', root='.'):
    output,root=Path(output),Path(root)
    availability=verify_output(output)
    required=['q1_adjusted_contrasts','q2_paired_improvements','q3_adjusted_contrasts']
    if any(not (output/f'{name}.csv').exists() or pd.read_csv(output/f'{name}.csv').empty for name in required):
        return incomplete_reports(output,root,availability)
    s,answers=findings(output); rid=s['run_id']
    reports=root/'reports';reports.mkdir(parents=True,exist_ok=True)
    read=lambda n: pd.read_csv(output/f'{n}.csv')
    # Relative links keep the project portable as a submission directory.
    import os
    prefix=os.path.relpath(output,reports)
    def source(name, selector='all rows'):
        return f'Source: [`{name}.csv`]({prefix}/{name}.csv), {selector}; run `{rid}`.'
    banner=f'Run ID: `{rid}`. Generated from verified outputs; all numerical claims below refer to this run.\n'
    q1=read('q1_adjusted_contrasts');q1overall=read('q1_summary_overall');q2=read('q2_model_metrics');q3=read('q3_adjusted_contrasts')
    primary=q1.loc[q1['subgroup'].eq('all')]
    metrics=q2.loc[q2.meeting_group.eq('all')]
    desc=read('q3_descriptive_contrasts')
    results=f'''# Results: ATP match histories, 2000–2024

**Team:** {TEAM}

{banner}
The study uses **{s['eligible_analysis_matches']:,} eligible physical matches** from **{s['raw_match_rows']:,} input records**, with 1990–1999 as history warm-up. Two player views are not two independent matches. Source: [`attrition.csv`]({prefix}/attrition.csv), `study_eligible_matches` and `raw_records`.

## 1. Performance after ranking upsets

{answers[0]}

{source('q1_adjusted_contrasts','sample=all_windows, subgroup=all; average and age/experience interaction rows')}

The descriptive comparison uses the same top-50, both-ranks-known loss population as adjustment. Counts of complete and unusable windows are:

{markdown_table(q1overall,['loss_type','index_losses','unique_players','usable_next_matches','complete_three_match_windows','incomplete_or_unusable_windows'],0)}

{source('q1_summary_overall')}

Age and experience are separately described in [`q1_summary_age.csv`]({prefix}/q1_summary_age.csv) and [`q1_summary_experience.csv`]({prefix}/q1_summary_experience.csv). Their raw patterns mix differences in strength, exposure and playing conditions. The continuous interactions above are the appropriate joint adjusted comparison. Experience is observed eligible history since 1990, not a complete career.

The non-overlapping-window check greedily retains the earliest available complete windows in sequence for each player, forbidding reuse of its index or follow-up matches. All primary and sensitivity contrasts are shown below; intervals cluster by player, accounting for repeated and overlapping windows within that player.

{markdown_table(primary,['outcome','sample','contrast','events','players','estimate_pp','ci95_lower_pp','ci95_upper_pp'],3)}

{source('q1_adjusted_contrasts','subgroup=all')}

## 2. Do previous meetings improve prediction?

{answers[1]}

{source('q2_paired_improvements','metric=brier; first_model=baseline')}

{markdown_table(metrics,['model','test_matches','brier_score','log_loss','accuracy'],6)}

{source('q2_model_metrics','meeting_group=all')}

Training used {s['q2']['training_matches']:,} matches, with a 21-day exclusion gap before 2020; test seasons were 2020–2024. Parameters and preprocessing remain frozen. Earlier test-period results update later pre-match histories. Meeting count is shared by both players and does not inherently favor either one. No test-driven tuning was performed. Source: [`run_summary.json`]({prefix}/run_summary.json), `q2`.

The same generated table contains results by zero, one, two-to-four and five-plus prior meetings. [`q2_paired_improvements.csv`]({prefix}/q2_paired_improvements.csv) includes paired Brier, log-loss and accuracy intervals for all three model comparisons. [`q2_calibration.csv`]({prefix}/q2_calibration.csv) gives fixed-bin denominators and observed versus predicted rates.

## 3. Does opponent handedness matter?

{answers[2]}

{source('q3_adjusted_contrasts','method=dyadic_primary; player_hand=R and L')}

The adjusted sample has {s['q3']['adjusted_unique_matches']:,} unique physical matches and {s['q3']['adjusted_player_match_rows']:,} focal-player rows from {s['q3']['adjusted_players']:,} players. Subgroup match counts overlap when both views of a match qualify. Source: [`run_summary.json`]({prefix}/run_summary.json), `q3`.

These equal-player service and match summaries are **unadjusted**, not evidence of a controlled handedness effect:

{markdown_table(desc,['player_hand','players','mean_player_win_difference_pp','service_eligible_players','mean_player_service_difference_pp','service_points_vs_L','service_points_vs_R'],3)}

{source('q3_descriptive_contrasts')}

The original player-by-match covariance still has {s['q3']['legacy_two_way_negative_variance_terms']} negative coefficient variance term(s). It is retained as a sensitivity with unavailable affected intervals, never replaced by zero or an absolute value. The primary dyadic method uses dependence through either player and includes absorbed fixed-effect degrees of freedom. Left-handed contrasts use the coefficient sum and **the full covariance including its cross term**. See [`q3_inference_sensitivity.csv`]({prefix}/q3_inference_sensitivity.csv), [`q3_subgroup_support.csv`]({prefix}/q3_subgroup_support.csv), and [`q3_player_influence.csv`]({prefix}/q3_player_influence.csv).

## Interpretation limits

These are exploratory observational results. Ranking upsets are a ranking-based operational definition, not a measure of surprise or psychological recovery. Tournament-week dates and checked rounds approximate chronology; exact match days and recovery durations are unavailable. Missing follow-up is missing, never zero wins. Player and pair intervals do not remove every source of dependence, selection bias or unmeasured confounding. All thresholds, including rank gaps 20, 30 and 50, are reported rather than selected for a preferred finding.
'''
    (reports/'RESULTS.md').write_text(results)
    quality=read('attrition');flow=read('exclusion_flow');chron=read('chronology_checks');cov=read('coverage_by_group');miss=read('missingness_by_group')
    ledger=pd.read_csv(output/'unresolved_event_ledger.csv')
    checks=read('spotcheck_evidence')
    baseline_path=root/'validation'/'baseline_audit.json'
    baseline=json.loads(baseline_path.read_text()) if baseline_path.exists() else None
    previous_summary=root/'outputs'/'run_summary.json'
    previous=json.loads(previous_summary.read_text()) if previous_summary.exists() else None
    change=(f'The preserved saved run had {previous["eligible_analysis_matches"]:,} eligible study matches; this run has {s["eligible_analysis_matches"]:,}, a change of {s["eligible_analysis_matches"]-previous["eligible_analysis_matches"]:+,}. '
            'Legitimate exclusions were retained; no count target was enforced.' if previous else 'No earlier run count is available for comparison.')
    overlap = s.get('chronology', {})
    dq=f'''# Data quality and reconstruction audit

{banner}
{change} The eligible unique-match count is substantial for these class questions; subgroup support and dependent observations still constrain inference. Source: current and preserved `run_summary.json`, `eligible_analysis_matches`.

## Attrition and units

{markdown_table(quality)}

{source('attrition')}

Warm-up and study counts are partitions of deduplicated source rows. Distinct match keys can include unresolved conflicts; resolved physical matches require usable distinct identities and a nonconflicting key. Player views include excluded events retained to prevent skipped follow-up. Q1 windows overlap, and Q3 subgroup match totals cannot be added as independent observations.

The following first-reason flow is mutually exclusive within period. Reasons are applied in code order, so later overlapping flags do not create extra attrition:

{markdown_table(flow)}

{source('exclusion_flow')}

Overlapping flag counts are separately retained in `run_summary.json/exclusion_flag_counts_nonexclusive`; never add them to this flow.

## Coverage and missingness

{markdown_table(cov.loc[cov.dimension.eq('surface')])}

{source('coverage_by_group','dimension=surface; includes warm-up')}

Year-by-year raw/eligible counts and missing hands are in [`coverage_by_year.csv`]({prefix}/coverage_by_year.csv). Expanded year, surface and level coverage is in [`coverage_by_group.csv`]({prefix}/coverage_by_group.csv). Missingness is explicitly recorded by year, surface, focal hand, age and observed experience in [`missingness_by_group.csv`]({prefix}/missingness_by_group.csv); its denominators are study-period player views, including excluded recorded events.

{markdown_table(miss.loc[miss.dimension.eq('player_hand')],digits=2)}

{source('missingness_by_group','dimension=player_hand')}

Ranks at or below zero and implausible ages are masked. Unknown hand stays unknown. Service totals require integer, nonnegative component counts and valid first-/second-serve bounds. Invalid service statistics do not invalidate an otherwise eligible match result. Hand-specific opportunities are in [`q3_subgroup_support.csv`]({prefix}/q3_subgroup_support.csv) and [`q3_by_player_and_hand.csv`]({prefix}/q3_by_player_and_hand.csv).

## Unresolved records and chronology

{markdown_table(chron)}

{source('chronology_checks','overlapping diagnostics; entire history window')}

The unresolved identity/date/conflict ledger contains {len(ledger):,} player-event records. Source: [`unresolved_event_ledger.csv`]({prefix}/unresolved_event_ledger.csv). A conflicting key is one unresolved physical event, not two matches. A known focal player with an invalid opponent retains a blocker. Source-agreed dates/rounds allow a blocker to occupy one sequence slot without a fake outcome. Unknown dates or conflicting ranges conservatively flag affected follow-up as unresolved; no date is imputed. Records with no known identity remain auditable but cannot be linked to a player.

The synthetic January 1/8/15/22/29 regression demonstrates a software edge case, not corruption of this real-data run. The saved baseline had zero conflicting keys. `validation/recovery_regression.json` and the regression tests record the checks actually made.

`tourney_date` is usually the tournament-week start. `match_num` and CSV row order are identifiers, never chronology. Checked knockout order is R128, R64, R32, R16, QF, SF, F. Unsupported-round events, repeated player rounds and same-start appearances in multiple tournaments are flagged. The bounded cross-start screen flagged {overlap.get('candidate_event_pairs_study_individual', 'unavailable')} study-period individual-event candidate pairs involving {overlap.get('candidate_players_study_individual', 'unavailable')} players. Source: [`run_summary.json`]({prefix}/run_summary.json), `chronology`, and [`chronology_start_gap_counts.csv`]({prefix}/chronology_start_gap_counts.csv). Distinct starts 1–6 days apart, or 7–13 days after a G start, are screened; source references and unresolved statuses appear in [`chronology_overlap_candidates.csv`]({prefix}/chronology_overlap_candidates.csv). These are potential overlaps, not confirmed collisions: early exits and ordinary scheduling shifts can explain them. No event end date is invented or speculative exclusion imposed. Different-start overlaps cannot always be resolved from these fields. No exact days-to-recovery claim is supported. See [chronology details](../docs/CHRONOLOGY.md).

## Traceable internal spot checks

The deterministic sample selects high-exposure player histories, ranking-upset windows by follow-up status, and opponent pairs with the most observed meetings. It includes original annual filenames and 1-based CSV rows (header is row 1). {len(checks):,} automated comparisons were performed; {int(checks.passed.sum()):,} passed. These check local source outcomes, strictly earlier history counts, pair meetings and complete-window means. They are **not independent external verification or human review**.

{markdown_table(checks)}

{source('spotcheck_evidence')}

The inspectable evidence is in [`spotcheck_player_histories.csv`]({prefix}/spotcheck_player_histories.csv), [`spotcheck_recovery_windows.csv`]({prefix}/spotcheck_recovery_windows.csv), and [`spotcheck_opponent_pairs.csv`]({prefix}/spotcheck_opponent_pairs.csv). Entirely absent source matches, wrong source identities and unreported historical errors cannot be recovered from this audit.

## Acquisition and run integrity

The pinned cache inventory is separate from this run's actual input list. Every required annual file was hash-checked before reuse; original retrieval timestamps and pinned URLs remain in the inventory. Subset/interrupted-run tests use mocked responses, never invented research observations. Each run is built and verified in a sibling staging directory, then published as a unit; an existing target is retained in a backup. Failed stages carry `FAILED_RUN.json` and no successful summary. Input hashes, working-code hashes, base revision/dirty state, package versions, analysis warnings and generated output hashes appear in [`run_summary.json`]({prefix}/run_summary.json).
'''
    (reports/'DATA_QUALITY.md').write_text(dq)
    support=read('q3_subgroup_support');influence=read('q3_player_influence');sens=read('q3_inference_sensitivity')
    influence_range=influence.groupby('player_hand').difference_pp.agg(['min','max']).reset_index()
    warnings='\n'.join(f'- **{q.upper()}**: {w}' for q in ['q1','q2','q3'] for w in s[q]['warnings'])
    final=f'''# Digital Archeology of ATP Match Histories

**Team:** {TEAM}

{banner}
## Objectives and motivation

Historical sports records allow us to reconstruct the information available before successive matches. We ask whether performance after ranking upsets varies with age and observed experience; whether previous meetings add predictive information beyond strength, form and surface; and whether within-player results differ against left- and right-handed opponents. These are observational and predictive questions, not measurements of psychological recovery or causal effects.

## Data and acquisition

Annual ATP singles files cover the 2000–2024 study period and a 1990–1999 warm-up. Jeff Sackmann compiled the data; the Aneeshers archival mirror supplies revision `{s['source_revision']}`. The run read {len(s['inputs'])} annual files, {s['raw_match_rows']:,} raw records and {s['eligible_analysis_matches']:,} eligible study matches. The cache preserves source bytes, pinned URLs, SHA-256 hashes and retrieval records. This run used existing cached files offline. Source: [`run_summary.json`]({prefix}/run_summary.json), `inputs`, `configuration.offline`, and raw/eligible counts.

The code is MIT-licensed under `LICENSE`; the data and derived data retain the separate CC BY-NC-SA 4.0 attribution in `DATA_LICENSE.txt`. The project uses match-level annual ATP data. No betting odds, point-level charting data, dashboard or deep-learning model is used. See [SOURCES.md](../SOURCES.md).

## Cleaning and history reconstruction

We preserve source-file/row references, remove exact duplicate records, and exclude conflicting keys, invalid identities, missing dates, unrecognized or unfinished scores, unsupported ordering, and events outside individual A/M/G knockout scope. Retirement, walkover and team-event exclusions remain in the event sequence when identities/dates are usable. Invalid service totals are masked independently of match eligibility. The completion screen is not a full tennis-score validator.

Tournament dates describe tournament weeks, not match days. Checked round order and synchronous feature updates avoid using arbitrary match numbers or CSV positions. Unresolved records are retained in a blocker ledger so later matches cannot silently substitute for the next recorded matches. Same-date and unsupported-round ambiguity is flagged; uncertain cross-event overlap remains a limitation. [DATA_QUALITY.md](DATA_QUALITY.md) contains mutually exclusive attrition, overlapping flags, coverage, missingness and traceable spot checks.

Two player perspectives preserve each side's pre-match history. Experience counts earlier eligible recorded matches since 1990, with up to ten earlier results for form. Head-to-head history includes only previous eligible meetings. Q2 retains exactly one outcome-independent orientation: the lower numeric player ID is Player A. Both views used in Q3 are dependent observations, accounted for explicitly in inference. See [DATA_DICTIONARY.md](../docs/DATA_DICTIONARY.md).

## Methods

**Q1.** A ranking upset is a top-50 player losing to an opponent at least 30 ranking places lower. Upset and ordinary losses are compared within the same top-50, known-ranks population. Outcomes are the next recorded match result and the mean win indicator over the next three recorded matches when all are eligible and resolved. Missing or unusable follow-up stays missing. Age and experience have separate descriptive groupings, and both enter the adjusted model continuously with upset interactions. Controls include initial rank, recent form, initial surface/season, and following-opponent strength, surface and match format. OLS estimates probability-point differences; focal-player cluster covariance and t critical values account for repeated/overlapping windows within players. Full-covariance standardized contrasts average each fitted upset difference over the stated sample. Subsequent-context adjustment changes the estimand to a conditional association.

**Q2.** Three prespecified logistic models use strength, age/experience differences, recent form, surface, round, format, level and both hands: baseline; baseline plus shared meeting count; and baseline plus count and previous head-to-head results. Median imputation, scaling and category encoding fit training data only. A chronological split uses training before 2020 with a 21-day boundary gap, and the same 2020–2024 test matches for all models. Current scores, service statistics, winner labels and follow-up outcomes are excluded from predictors. Earlier test results can update later histories while fitted parameters stay frozen. Brier score and log loss assess probability predictions; accuracy is secondary. Paired opponent-pair bootstrap intervals use {s['configuration']['bootstrap_samples']} seeded resamples, with remaining cross-pair shared-player dependence acknowledged. No repeated tuning on inspected test performance was performed.

**Q3.** Known-hand player views are compared within player. The descriptive minimum is ten opportunities against each opponent hand; service differences independently require ten valid service-stat matches per hand. Adjustment requires complete strength/age/form covariates and the opportunity minimum after filtering. A within-player linear probability model absorbs player intercepts and adjusts rank advantage, age, experience, each side's form, surface and season, including opponent-hand × focal-hand interaction. The within design has rank {s['q3']['within_design_rank']} of {s['q3']['within_design_columns']} columns, with {s['q3']['absorbed_player_intercepts']} absorbed player intercepts. Source: [`run_summary.json`]({prefix}/run_summary.json), `q3`.

The original focal-player × physical-match covariance omitted cross-role/shared-opponent dependence and produced a negative interaction variance with the design rank reported above. Primary inference now uses the [shared-player dyadic sandwich of Aronow, Samii and Assenova](https://arxiv.org/abs/1312.3398): sum score vectors per unordered pair, sum incident pair scores per player, and subtract pair outer products from node outer products to remove double counting. Repeat meetings and complementary views remain in the same dyads. The finite-sample factor includes absorbed player intercepts. This covariance change addresses dependence structure; it was not selected to obtain significance. No negative variance is clipped, absolutized or replaced with zero. Right-handed contrast is the opponent-left coefficient; left-handed contrast adds the interaction using the full covariance. These remain exploratory normal intervals under assumptions about disjoint dyads.

## Findings

### Performance following ranking upsets

{answers[0]}

{source('q1_adjusted_contrasts','sample=all_windows, subgroup=all')}

### Previous meetings and prediction

{answers[1]}

{source('q2_paired_improvements','metric=brier, first_model=baseline')}

{markdown_table(metrics,['model','test_matches','brier_score','log_loss','accuracy'],6)}

{source('q2_model_metrics','meeting_group=all')}

### Opponent handedness

{answers[2]}

{source('q3_adjusted_contrasts','method=dyadic_primary')}

Unadjusted service comparisons use valid point totals and equal-player differences, separately from adjusted match-result estimates:

{markdown_table(desc,['player_hand','players','matches_vs_L','matches_vs_R','service_eligible_players','mean_player_service_difference_pp','service_points_vs_L','service_points_vs_R'],3)}

{source('q3_descriptive_contrasts')}

## Sensitivity checks

Q1 retains rank-gap thresholds 20, 30 and 50 in [`q1_threshold_sensitivity.csv`]({prefix}/q1_threshold_sensitivity.csv), with both loss types and age groups; these are descriptive checks, not a threshold search. Non-overlap sensitivity greedily selects the earliest available complete windows in sequence for each focal player without using its wins, forbids reuse of all index/follow-up IDs, and then applies covariate exclusions. Selection changes the sample. Estimates for both outcomes and their age/experience interactions are:

{markdown_table(primary,['outcome','sample','contrast','events','estimate_pp','ci95_lower_pp','ci95_upper_pp'],3)}

{source('q1_adjusted_contrasts','subgroup=all')}

Q2 reports paired metrics and fixed calibration bins for all models, and metrics by previous-meeting group, without further parameter selection. See [RESULTS.md](RESULTS.md) and the generated calibration plot.

Q3 retains the original covariance, a tournament-only covariance, and a deterministic outcome-independent single-view/focal-player-cluster model as sensitivities. Tournament clustering alone misses serial player dependence; single-view clustering misses shared-opponent dependence and changes the sample.

{markdown_table(sens,['method','player_hand','players','difference_pp','ci95_lower_pp','ci95_upper_pp','inference_status'],3)}

{source('q3_inference_sensitivity')}

To examine concentration, the five most exposed focal players of each hand are selected by exposure, not outcomes. Each is removed in either participant role, opportunity minima are reapplied, and fixed effects are refitted. The resulting point-estimate ranges are:

{markdown_table(influence_range,digits=3)}

{source('q3_player_influence','grouped by player_hand, min/max difference_pp; point estimates only, no deletion confidence intervals')}

Subgroup support and concentration are explicit:

{markdown_table(support.loc[support['sample'].eq('adjusted')],digits=3)}

{source('q3_subgroup_support','sample=adjusted')}

The deletion ranges show how high-exposure participants can affect the magnitude; they are not confidence intervals or evidence of a universal effect. The smaller left-handed group has fewer players and larger exposure concentration. Neither a handful of prominent players nor these average associations establishes a universal handedness effect.

## Limitations and warnings

{warnings}

Additional limitations include source incompleteness/errors, selected ATP scope, left-truncated history, nonrandom follow-up/covariate missingness, coarse chronology, a ranking-based upset definition, and unmeasured conditions or injuries. The models are exploratory; multiple contrasts are not multiplicity-adjusted. Q1's post-index controls preclude a simple causal interpretation. A linear probability model can predict outside zero to one and is used for conditional mean contrasts. Q2 uses an already inspected holdout and its small gain needs future independent replication. Dyadic Q3 inference assumes no remaining dependence between disjoint player pairs; tournament-wide shocks and indirect network dependence can violate that assumption. Available uncertainty is not proof that every analysis is definitive.

## Reproducibility and sources

Use the commands in [README.md](../README.md). [`run_summary.json`]({prefix}/run_summary.json) records run ID/timestamps, configuration, actual inputs, source revision, code hashes, git base/dirty state, package versions, analysis warnings and output hashes. Results were staged and hash-verified before publication; the original saved `outputs/` remain intact. The actual environment is also frozen in `requirements-lock.txt`. [TEST_RESULTS.md](../TEST_RESULTS.md) distinguishes full-data execution, real-demo smoke testing and explicitly synthetic regressions. The executed [Tennis_Project.ipynb](../Tennis_Project.ipynb) uses the same modules and final output directory; its displayed findings are read from the same tables. [SOURCES.md](../SOURCES.md), [DATA_LICENSE.txt](../DATA_LICENSE.txt), [METHODS.md](../docs/METHODS.md), and [DATA_QUALITY.md](DATA_QUALITY.md) provide the source, method and audit details.
'''
    (reports/'FINAL_REPORT.md').write_text(final)
    claims={'run_id':rid,'output_directory':str(output),'answers':answers,
            'tables':{n:json.loads(read(n).to_json(orient='records',double_precision=15)) for n in ['q1_summary_overall','q1_adjusted_contrasts','q2_model_metrics','q2_paired_improvements','q3_adjusted_contrasts','q3_descriptive_contrasts']}}
    (reports/'report_claims.json').write_text(json.dumps(claims,indent=2,allow_nan=False))
    (reports/'report_manifest.json').write_text(json.dumps({'run_id':rid,'outputs_summary_sha256':sha256(output/'run_summary.json'),'files':{p.name:sha256(p) for p in sorted(reports.iterdir()) if p.is_file() and p.name!='report_manifest.json'}},indent=2))
    readme=root/'README.md'
    if readme.exists():
        content=readme.read_text()
        start,end='<!-- GENERATED_FINDINGS_START -->','<!-- GENERATED_FINDINGS_END -->'
        if start in content and end in content:
            import re
            first=one(q1,outcome='next3_win_rate',sample='all_windows',contrast='average_upset_minus_ordinary',subgroup='all')
            comparisons=read('q2_paired_improvements')
            count=one(comparisons,first_model='baseline',second_model='plus_meeting_count',metric='brier')
            history=one(comparisons,first_model='baseline',second_model='plus_h2h_results',metric='brier')
            brief=(f'**Q1:** Adjusted next-three performance after ranking upsets versus ordinary losses: {interval(first)}. '
                   'See the report for separate age/experience interactions, next-match results, and non-overlap sensitivity.\n\n'
                   f'**Q2:** Brier improvement from meeting count alone: {interval(count,"mean_improvement","ci95_lower","ci95_upper",6,"")}; '
                   f'with previous head-to-head results: {interval(history,"mean_improvement","ci95_lower","ci95_upper",6,"")}.\n\n'
                   f'**Q3:** Adjusted opponent L-minus-R differences: {interval(one(q3,player_hand="R"),"difference_pp")} for right-handed focal players; '
                   f'{interval(one(q3,player_hand="L"),"difference_pp")} for left-handed focal players.\n\n'
                   'All are observational estimates with dependence and chronology limitations; see the report for sample sizes and interpretation.')
            generated=f'{start}\nVerified run: `{rid}`; **{s["eligible_analysis_matches"]:,} eligible unique study matches**.\n\n{brief}\n{end}'
            readme.write_text(re.sub(re.escape(start)+r'.*?'+re.escape(end),lambda _:generated,content,flags=re.S))
    return s,answers


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',default='outputs_final')
    parser.add_argument('--root',default='.')
    args=parser.parse_args()
    summary,_=generate_reports(args.output_dir,args.root)
    print(f'Reports generated from verified run {summary["run_id"]}')
