# Tennis Match History Project

**Team:** Phouvadeth Vathana, Joseph Bronyah, Dhrumil Patel

This project builds historical player records and provides a first analysis of:

1. Performance after a **ranking upset**, separately by age and prior recorded experience.
2. Whether previous meetings help predict a pair's next result.
3. Performance against left-handed versus right-handed opponents.

This is runnable research code, not a completed research finding. Read the
choices and limitations below before interpreting results.

## Start here

Use Python 3.10–3.13. The code was tested with Python 3.13.5.
Extract the ZIP and keep its files together. Open a terminal in this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m jupyterlab Tennis_Project.ipynb
```

On Windows, use `.venv\Scripts\activate` instead of the `source` command.
In the notebook, run the cells from top to bottom. `RUN_FULL_STUDY = True`
uses the annual data downloads. Set it to `False` for the small offline demo.

For a terminal-only run:

```bash
python tennis_project.py
```

For an offline smoke test, without downloading the annual data:

```bash
python tennis_project.py --demo
python -m pytest -q
```

The demo contains **31 real Brisbane 2024 source records**, of which **29**
pass the completion/scope checks. The small sample cannot answer the research
questions; the model functions deliberately skip insufficient samples.
Do not present demo results or synthetic test records as research findings.

## Default settings — research choices, not universal definitions

| Setting | Default |
|---|---|
| Main analysis | 2000–2024 |
| History warm-up | 1990–1999 |
| Source files | Annual ATP singles match CSVs from a fixed archive revision |
| Eligible events | Individual knockout events with ATP levels A, M, or G |
| Ranking upset | A top-50 player loses to an opponent ranked at least 30 places lower |
| Recovery outcomes | Next recorded match; next three recorded matches when all three are eligible |
| Age display groups | Under 23; 23–29; 30+ |
| Experience display groups | Under 100; 100–299; 300+ prior eligible recorded matches |
| Recent form | Up to 10 earlier eligible recorded matches |
| Head-to-head training | Eligible study matches before 2020, with a 21-day boundary gap |
| Head-to-head evaluation | 2020–2024, with frozen model parameters |
| Handedness paired comparison | At least 10 eligible observations against each opponent hand |
| Bootstrap | 500 opponent-pair cluster resamples, reproducible random seed |

Change the upset definition or dates from the command line:

```bash
python tennis_project.py --upset-max-rank 50 --upset-rank-gap 50 --output-dir outputs_gap50
python tennis_project.py --history-start 1990 --analysis-start 2005 --end-year 2024 --test-start 2020 --output-dir outputs_2005
```

Use a different output directory for each configuration you want to compare.
Rerunning into the same directory replaces the program's known generated files
and removes stale model outputs. Other files are not intentionally removed.

From Python or Jupyter:

```python
from tennis_project import Config, run_project

config = Config(
    history_start=1990,
    analysis_start=2000,
    end_year=2024,
    test_start=2020,
    upset_max_rank=50,
    upset_rank_gap=30,
    output_dir="outputs",
)
summary = run_project(config)
print(summary["eligible_analysis_matches"])
```

## What the program does

### 1. Obtain and preserve original files

The downloader uses archive commit
`83733587353df8a41f2fd4f516147d5aa83f5a8d`, not the moving `main` branch.
It downloads only annual singles CSVs plus source documentation and license
information. It does **not** clone the entire archive or download MCP.

Original bytes are kept in `data/raw/<revision>/`. A manifest records source
URLs, hashes, sizes, and retrieval times. Existing downloads are reused after
hash checks. Network errors stop the run rather than silently omit a season.
After a successful download, `--offline` reuses the cache.

Manually placed cache files without a download manifest are marked
`local_unverified`. A locally computed hash is a change detector, not proof that
an unverified local copy matches the upstream source.

### 2. Audit before analysis

The pipeline checks required columns, player IDs, duplicate match keys,
missing ranks, missing/unknown handedness, impossible service statistics,
completion markers, and ordering problems.

Walkovers, retirements, unrecognized score strings, team events, unsupported
round formats, and unresolved ordering conflicts are excluded from the main
analysis. Finals/round-robin events outside A/M/G are outside the chosen scope.
The score check screens for completion; it does not validate every set against
tennis scoring rules. Bad service statistics are masked without automatically
throwing out an otherwise usable match result.

Excluded rows and their reasons are saved. Exclusion-flag counts overlap and
should not be added together as though they were mutually exclusive.

### 3. Construct pre-match histories

The source's winner/loser rows become two player-perspective rows. The fields
`player_*` and `opponent_*` are assigned correctly in both views.

Prior experience, recent form, previous meetings, previous head-to-head wins,
and surface-specific head-to-head statistics are computed **before** each
result enters history. Results within a shared date/round block are all read
before that block updates history. Tests verify that changing a future result
does not alter earlier features.

For prediction, exactly one player view is retained per physical match:
Player A has the smaller numerical player ID. Player A is not automatically
the winner. Two player views are **not two independent match observations**.

### 4. Analyze the three questions

**Question 1 — performance after ranking upsets.**

A ranking upset is not a betting-market surprise, and subsequent results are
not a measure of emotional recovery. The code produces age and experience
tables separately, complete-follow-up counts, and descriptive sensitivity
checks for rank-gap thresholds of 20, 30, and 50 (plus a custom threshold).

For a qualifying initial loss, the next three *recorded* matches are inspected.
A retirement, out-of-scope event, or ambiguity in that window is not skipped to
find a more convenient later match. The three-match rate is missing if the
window is incomplete or unusable. No follow-up is not the same as zero wins.

The optional adjusted analysis is an exploratory regression of the next-three
win rate. It compares ranking upsets with other losses in the same rank-eligible
population (top 50 by default). It includes continuous age and experience,
interactions with upset status, initial rank and recent form, follow-up opponent
strength, follow-up surfaces/format, initial surface, and season. Uncertainty is
clustered by the focal player. This does not fully handle every shared-opponent
or match-network dependence. The response is a rate; this is not a causal
recovery model. Overlapping windows for one player are retained and documented.

**Question 2 — repeated meetings.**

Three pre-specified logistic models are compared on the same held-out matches:

- Baseline: rankings, age difference, prior experience, recent form, surface,
  format, round, level, and both players' hands.
- Baseline plus the number of earlier meetings.
- Baseline plus meeting count, prior head-to-head results, most recent earlier
  result, and same-surface head-to-head history.

Imputation, encoding, and scaling are fitted only on training data. Current
match statistics and future recovery outcomes never enter the predictors.
The test period is chronological, not a random row split. During evaluation,
results of earlier test matches may update the features of later test matches;
the trained model parameters stay fixed. This is an as-of-match evaluation,
not a single forecast made for every future match on January 1, 2020.

Brier score and log loss evaluate probability predictions; lower is better.
Accuracy is included as a secondary measure. A paired opponent-pair cluster
bootstrap describes uncertainty in the Brier improvement. Shared players
across different pairs can still create dependence, so this interval is
exploratory. Meeting-history features may improve prediction without proving
that repeated exposure causes improvement. No hyperparameter search is performed.

**Question 3 — left-handed opponents.**

The program makes within-player L-versus-R comparisons, shows opportunity
counts, and calculates service-point success from integer source counts.
Unknown hands are excluded, not recoded as right-handed. Service aggregates
use only valid point totals and are descriptive, not opponent-adjusted.

The adjusted match-result analysis uses a within-player linear probability
model. It accounts for observed rank advantage, form, age, experience, surface,
and season, plus an interaction with the focal player's own hand. Demeaning
removes time-invariant player differences. Standard errors are clustered by
focal player and physical match. Other shared-opponent dependence can remain.

The `opponent_left` coefficient is the adjusted L-minus-R contrast for a
right-handed focal player. Add `opponent_left_x_player_left` for the corresponding
left-handed focal-player contrast. Coefficients are probability units: 0.02
means approximately two percentage points. Confidence intervals are exploratory
large-sample approximations, not causal estimates. Insufficient data causes
models to be skipped explicitly rather than replaced with invented results.

## Chronology and coverage: important limitations

`tourney_date` is usually the start of the tournament week, not the exact match
day. The code orders a player's records by tournament date and knockout round.
It does not use CSV row order or arbitrary match numbers as dates. Repeated
same-round appearances, unsupported formats, and same-date appearances in
multiple tournaments are flagged.

This is a documented chronological approximation, not independently verified
match-day chronology. Unusual overlapping or rescheduled events can still need
manual review. Do not report exact days to recovery using this dataset alone.
Historical source errors or entirely absent matches cannot be detected merely
by sorting available records.

Prior experience and previous meetings refer to **earlier eligible matches
observed since the history-start year**, not complete career totals. The warm-up
reduces left-boundary truncation but does not eliminate it. Excluded retirements,
team events, round-robin events, and lower tours are not included in those
history counts. Near the end of the dataset, follow-up is censored and reported
as missing. Missing-data and exclusion patterns may create selection bias.

All three analyses describe associations or predictive value. They do not
establish psychological states or prove cause and effect. Do not select upset
thresholds or reporting subgroups because they give the strongest result.

## Main output files

All are inside the selected output directory. pandas reads `.csv.gz` directly.

| File | What it contains |
|---|---|
| `run_summary.json` / `RUN_SUMMARY.md` | Exact settings, counts, model status, versions, and input hashes |
| `matches_audited.csv.gz` | Match-level audit with eligibility and reason flags |
| `excluded_matches.csv.gz` | Excluded source records and reasons |
| `coverage_by_year.csv` | Source and eligible counts by year |
| `missing_values.csv` / `player_row_quality.csv` | Missing data and validity checks |
| `player_match_features.csv.gz` | Study-period player views and pre-match history fields |
| `q1_recovery_events.csv.gz` | Initial losses, following records, recovery rates, censoring |
| `q1_summary_age.csv` / `q1_summary_experience.csv` | Descriptive recovery comparisons |
| `q1_threshold_sensitivity.csv` | Alternative ranking-gap summaries |
| `q1_adjusted_coefficients.csv` | Adjusted recovery-rate model, when estimable |
| `q2_model_metrics.csv` | Held-out probability errors for the three prediction models |
| `q2_test_predictions.csv.gz` | One prediction record per test match |
| `q3_by_player_and_hand.csv` | Win and service rates by player and opponent hand |
| `q3_paired_player_comparison.csv` | L-minus-R differences for players meeting opportunity minima |
| `q3_adjusted_coefficients.csv` | Within-player adjusted match-result model, when estimable |
| `charts/` | Separate exploratory charts, where data are sufficient |

```python
import pandas as pd
features = pd.read_csv("outputs/player_match_features.csv.gz")
metrics = pd.read_csv("outputs/q2_model_metrics.csv")
```

Models can legitimately produce no clear difference. Read the sample counts
and uncertainty before interpreting a point estimate.

## What has actually been tested

The included tests cover chronological features, exclusion decisions, missing
follow-up, outcome-independent orientation, unknown handedness, bad statistics,
cache integrity, stale output removal, and model execution.

The three models were exercised with explicitly synthetic multi-season test
data. A 31-row real-data excerpt was processed end to end. The full 1990–2024
bulk download could not be executed in the authoring environment because
outbound networking was unavailable. Therefore **full-study counts, coverage,
performance, and findings are not claimed**. Run the full study on an
internet-connected computer and inspect its quality reports.

## Source and attribution

Data compiled by Jeff Sackmann; archival mirror maintained by Aneeshers.
The data license is CC BY-NC-SA 4.0. See `DATA_LICENSE.txt` and `SOURCES.md`.
No MCP data are required or downloaded in this version. MCP can be a later
point-level extension, not a prerequisite for these match-history questions.
