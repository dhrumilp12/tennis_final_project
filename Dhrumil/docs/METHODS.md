# Methods and interpretation

This document specifies the implemented analyses; numerical findings and their
run ID are generated in `reports/RESULTS.md` and `reports/FINAL_REPORT.md` from
`outputs_final/`. The study is observational. “Recovery” means subsequent
recorded match performance, not a psychological state or a causal response.

## Scope, acquisition, and chronology

The main study covers 2000–2024 ATP individual A/M/G knockout matches, with
1990–1999 history warm-up. Source bytes come from Jeff Sackmann's ATP data as
preserved by the Aneeshers archive at revision
`83733587353df8a41f2fd4f516147d5aa83f5a8d`. The cache manifest records URLs,
retrieval times, SHA-256 checks and provenance status; runs record their actual
annual inputs separately. Subset requests merge inventory entries, and atomic
manifest writes retain completed-file provenance after an interruption. A local
hash does not authenticate a previously unverified local file.

Source-record identity and filtering precede model construction. Exact duplicate
records are removed. Nonidentical records with the same tournament/match key,
invalid identities, missing dates, ambiguous same-player ordering, unsupported
round events, incomplete/unrecognized results, team events and out-of-scope
levels do not contribute model outcomes or history updates. Invalid service
counts mask service outcomes without automatically excluding usable results.
Overlapping exclusion flags must not be summed as an attrition flow.

`tourney_date` is a tournament-level date, usually the tournament week's Monday.
Recognized round order is R128, R64, R32, R16, QF, SF, F. Match numbers and CSV
positions are not chronological evidence. Same-start multiple events for one
player, repeated player-rounds, unsupported formats and missing dates are
explicit flags. Different-start overlapping or rescheduled events cannot always
be resolved from this source. No exact match-day or days-to-recovery claim is
made. Source-supported ordering is an approximation; entirely omitted matches
or unrecognized source errors remain possible.

Pre-match histories read every row in a shared date/round block before updating
from any result in that block. Only eligible prior results update counts, recent
form and pair histories. Experience therefore measures earlier **eligible
observed matches since 1990**, excluding other tours, team events and incomplete
results; it is not complete career experience. Warm-up reduces but does not
eliminate left-boundary truncation. Regression tests change future outcomes and
verify that earlier/current pre-match features are unchanged.

A separate ledger retains unresolved events that cannot become valid player
views. A key with two conflicting copies contributes one unresolved event per
known affected player, with both source references. An agreed date and round
can occupy a sequence slot with missing outcome. If date/round placement is
uncertain, the code blocks candidate windows that could cross the source date
bounds; an entirely missing date conservatively affects all known-player
windows in the loaded data. Known focal identity plus invalid opponent identity
is retained this way. Unknown identities remain explicit unlinked uncertainty.
No outcome or exact date is invented to complete a window.

## Q1: performance following ranking upsets

An index event is an eligible study-period loss. A **ranking upset** is a loss
by a player ranked at most 50 to an opponent at least 30 ranking places lower.
Both ranks must be known. The descriptive comparison and adjustment use the
same top-50, known-rank loss population; ordinary losses are its remaining
ranked losses. Counts for broader eligible losses are retained in audit outputs.
Predeclared gap checks at 20, 30 and 50 are all reported descriptively, including
ordinary-loss comparison groups at each threshold. No threshold is selected
because of the resulting estimate.

The two outcomes are the result in the next recorded match and the win rate in
the next three recorded matches. Excluded or unresolved recorded events are
not skipped. The three-match rate requires three eligible unblocked events;
end-of-file censoring, excluded follow-up and unresolved events produce missing
outcomes. Follow-up missingness may reflect retirement, participation patterns,
injury, source coverage or the study boundary, so complete-window selection is
itself a limitation.

Age and experience are shown separately (age <23, 23–29, 30+; prior-match counts
<100, 100–299, 300+). Tables give index losses, players, usable next matches,
complete three-match windows, unavailable windows, means/medians of age and
experience, and rates with focal-player-clustered intervals when at least 20
players contribute. The descriptive mean variance is
`G/(G−1) × sum_g[sum_i∈g(y_i−mean(y))]^2 / n^2`, with a `t(G−1)` critical value.
Repeated windows are not treated as independent Bernoulli observations.

The adjusted linear models include continuous centered age (`age−25`),
`log(1+prior_matches)`, upset status and its interactions with both age and
experience, initial recent win rate, log initial player rank, initial surface
and season. Next-match adjustment adds next-match log rank advantage, surface
and format. Next-three adjustment adds mean follow-up log rank advantage,
follow-up surface shares and best-of-five share; constant share terms are
omitted. Complete covariates are required. The fitted formula and attrition are
saved separately for every outcome/sample. A design-rank failure withholds
adjusted inference instead of treating a pseudoinverse as identification.

OLS estimates conditional differences in probability units. Standard errors
cluster by focal player with the finite-sample correction supplied by
statsmodels and `t(G−1)` inference. Thus repeated and overlapping windows for a
player may be arbitrarily correlated within that cluster. Shared-opponent
and broader network dependence can remain. A linear model may predict outside
[0,1]; this project reports contrasts, not calibrated Q1 probability forecasts.

The average adjusted upset-minus-ordinary contrast is
`β_upset + mean(age−25)β_upset×age + mean(log(1+experience))β_upset×experience`.
Named age/experience subgroups average the same fitted expression over their
observed model rows. Every uncertainty calculation uses `c' V c`, including
cross-covariances. Interactions describe change in the upset-versus-ordinary
contrast per additional year and per natural-log experience unit, respectively;
they do not conflate age with experience. These subgroup estimates are
exploratory, with no multiplicity-adjusted claim of discovery.

Subsequent opponent strength, surface and format are observed **after** the
index loss. Adjusting for them estimates a conditional association among
observed follow-ups. It does not identify a causal effect of an upset, nor a
psychological recovery effect; conditioning on subsequent circumstances may
also induce selection bias.

The non-overlapping sensitivity greedily retains the earliest complete window
for each focal player, then rejects any candidate reusing an index or follow-up
match from an already selected window. Selection uses chronology and outcome
availability, not wins; it occurs before covariate exclusion. The rule is applied
separately to next-match and next-three outcomes. The same adjusted model is
refitted to each selected sample, and the chosen window IDs are saved. This
reduces within-player window overlap but changes the sample and does not remove
all shared-opponent dependence. Missing outcomes are never treated as losses.

## Q2: incremental prediction from previous meetings

One view per physical match is retained: Player A has the smaller numerical
player ID. This rule is fixed independently of the winner; source winner/loser
roles are mapped into Player A attributes before prediction. No current score,
service statistic, winner label or follow-up outcome enters a predictor.

Training includes eligible study matches earlier than 21 days before January 1,
2020. Testing includes 2020–2024 matches. The gap reduces tournament-week
ambiguity at the boundary; it does not reconstruct exact dates. All three models
train/test on identical matches, retaining missing predictors through training-
fitted preprocessing. Numeric medians, missing indicators and standardization,
and categorical imputation/vocabulary, are fitted only on training data.
Unseen test categories are ignored by the encoder.

The three prespecified logistic regressions use the existing fixed `C=1.0` and
maximum 2,500 iterations, with no held-out hyperparameter search:

1. **Baseline:** log rank advantage, age difference, log observed-experience
   difference, recent-form difference; surface, round, best-of format, event
   level, focal hand and opponent hand.
2. **Baseline + meeting count:** adds `log(1+prior_h2h_meetings)`.
3. **Baseline + head-to-head results:** adds meeting count, smoothed prior pair
   advantage `(2W−M)/(M+2)`, most recent prior meeting result, and analogous
   same-surface pair advantage.

This is an **as-of-match** evaluation. Earlier eligible held-out outcomes can
update later held-out histories; fitted coefficients and preprocessing stay
frozen. It is not one forecast of all future matches issued on January 1, 2020.
Pre-match status is conditional on the documented source chronology.

Meeting count is shared by both players and has no intrinsic direction. A
coefficient in the fixed-ID orientation can exploit associations with that
orientation or interactions represented elsewhere; it must not be interpreted
as both players gaining an advantage over one another through more meetings.
Previous outcomes are directional and conceptually different from count alone.

Brier score (mean squared probability error) and log loss are lower-is-better;
accuracy at probability 0.5 is secondary and higher-is-better. Each is reported
over all test matches and prior-meeting groups 0, 1, 2–4 and 5+. Fixed probability
deciles show mean predicted versus observed win rates with bin denominators.
These calibration summaries are descriptive, not independent-bin hypothesis
tests or a reason to refit on the held-out outcomes.

For each of count-versus-baseline, full-versus-baseline and full-versus-count,
paired per-match improvements are aggregated by unordered opponent pair.
Five hundred bootstrap resamples of pairs (seed 42) retain all matches within a
sampled pair and calculate a match-weighted mean improvement. Percentile
2.5/97.5% limits describe uncertainty. Positive values always favor the second
model: first-minus-second Brier/log loss or second-minus-first accuracy.
Opponent-pair resampling handles repeat pair meetings but not all shared-player
dependence across different pairs. Consequently small differences and intervals
are exploratory, not evidence of causality or uniformly improved performance.
The model uses scikit-learn's [LogisticRegression implementation](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html).

## Q3: within-player comparisons by opponent hand

Both hands must be known R/L. Unadjusted tables compare each player's win rate
against left and right-handed opponents. The minimum opportunity rule requires
at least 10 eligible matches against **each** hand. Service rates separately
require at least 10 matches with valid core service counts against each hand;
points won are summed and divided by total valid service points. Equal-player
mean L-minus-R differences and all denominators are descriptive. They are not
opponent-strength-adjusted service estimates.

Adjustment requires complete rank advantage, focal age, both recent-form rates
and observed experience, then reapplies the per-hand match minimum. Players
with changing recorded focal hand are excluded from adjustment; metadata
inconsistency is reported. Both perspectives can remain, and their row count is
not a count of independent matches.

The linear probability model has focal-player fixed intercepts, opponent-left
indicator, opponent-left × focal-left interaction, log rank advantage, focal
age, focal and opponent recent win rates, log observed experience, surface and
season. Demeaning response and every predictor within focal player absorbs the
intercepts. Constant demeaned nuisance columns are omitted; both scientific hand
terms remain for identification checks. Rank and condition number are recorded.
A rank-deficient design withholds contrast inference. Effective residual degrees
of freedom subtract both absorbed intercepts and within-design rank.

For focal right-handers the adjusted contrast is `β_left`. For focal left-handers
it is `β_left + β_left×focal_left`, with variance
`V_left,left + V_interaction,interaction + 2V_left,interaction`. Results multiply
probability differences and interval limits by 100 to express **percentage
points**, not relative percent changes. At least 20 focal players and 20 distinct
opponents in a focal-hand group are required to report its interval; these
explicit minima do not guarantee reliable asymptotics.

The primary covariance recognizes that observations sharing either participant
can be dependent, including repeat meetings and complementary views. The
dyadic sandwich follows the shared-member approach of
[Aronow, Samii and Assenova (2015)](https://arxiv.org/abs/1312.3398).
Implemented score contributions are summed by unordered player pair. Summing
outer products of incident-pair scores over players, then subtracting pair
outer products, counts within-pair dependence once and covariance across pairs
sharing a player once. Sandwich bread uses the within-model inverse cross-product;
finite-sample scaling is `(n−1)/(n−absorbed_intercepts−within_rank)`. Normal 95%
intervals remain exploratory and assume no residual dependence among disjoint
pairs. Indirect network effects or tournament-wide shocks can violate that
assumption.

The earlier focal-player × physical-match two-way covariance is retained as a
sensitivity, using [statsmodels' documented two-group sandwich](https://www.statsmodels.org/stable/generated/statsmodels.stats.sandwich_covariance.cov_cluster_2groups.html)
and correcting for absorbed intercepts. It does not capture all dependence
through the opponent role. Inclusion–exclusion covariance estimates can be
indefinite in finite samples. Negative or zero contrast variance is never
clipped, absolutized or replaced with zero; the estimate may remain, but its
uncertainty is marked unavailable. Eigenvalue and negative-diagonal diagnostics
are reported, and any positive-variance contrasts from an indefinite covariance
are explicitly exploratory.

Additional sensitivities use tournament-only covariance and one reproducible,
outcome-independent SHA-256-selected view per match with focal-player clustering.
Tournament clustering does not capture serial player dependence; the single-view
analysis removes complementary outcomes but changes the qualifying sample. No
covariance method is chosen to obtain statistical significance.

Exposure diagnostics report each subgroup's rows, players, opponents, pairs,
tournaments and shares contributed by the largest and five largest focal
players. A deletion sensitivity selects the five most exposed focal players in
each hand group by match count, removes all matches involving each selected
player in either role, reapplies minimum opportunities and refits. These are
point-estimate robustness checks, not new inferential intervals or proof that
all players behave similarly. Smaller left-handed subgroups and player/network
heterogeneity constrain generalization.

## Reproducibility and evidentiary boundaries

The CLI and notebook use the same analysis modules/configuration. Runs stage
outputs in a fresh directory and verify the staged inventory before replacing a
requested output directory; previous results remain separately recoverable.
Run metadata records a unique ID, timestamps, configuration, actual inputs and
hashes, source revision, code revision/dirty state, runtime packages, model
statuses/warnings and output inventory. Missing estimates remain explicit and
JSON is written without nonstandard NaN tokens.

Synthetic regression fixtures test failure modes, not tennis hypotheses. The
bundled Brisbane excerpt is a real small parsing/smoke fixture, not the study.
Spot-check records trace selected histories/windows/pairs back to cached source
rows and recompute specified features. They are an internal reproducibility
check, not independent external verification or human review. See
`reports/DATA_QUALITY.md` for evidence and unresolved limitations, and
`TEST_RESULTS.md` for checks actually executed.
