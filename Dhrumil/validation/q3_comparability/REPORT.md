Unequal counts do not automatically invalidate this comparison. Ranking and prior-form adjustment are already present, but do not guarantee comparable observations. This separate check reconstructs the exact adjusted sample: 11,071 player × surface × season strata, with 14,851 left-opponent and 97,652 right-opponent observations (61,412 physical matches; 420 focal players). Player-match observations, physical matches, focal players and distinct opponents are counted separately in the [detailed check](DETAILS.md); totals across groups overlap.

Left-opponent historical rank has median 57 (middle half 33–95), versus 51 (22–88) for right opponents; lower rank numbers indicate higher rankings. 6,271/11,071 strata contain both hands, covering 14,579/14,851 (98.2%) left and 78,743/97,652 (80.6%) right observations. 5,608 both-hand strata have fewer than five observations in at least one hand; 1,091 have no pair meeting both rank calipers. Sparse observations and absent comparable observations are different limitations. Only 78.5% of left and 32.1% of right observations have such a candidate. A shared season does not ensure identical conditions.

Coverage remained uncertain, so **one matched sensitivity** used the [outcome-blind recorded rule](protocol.json): same player, surface and season; both focal and opponent ranks within a factor of 1.5; nearest summed log-rank differences, without replacement, with stable-ID ties. The caliper is pragmatic, not universal. Original opportunity/support checks and shared-player dyadic uncertainty were retained. The refit retains 21,266 observations, 19,499 physical matches and 330 players: 71.6% of original left-opponent and 10.9% of right-opponent observations. See [retention by focal hand](retention.csv).

| Focal hand | Primary L-minus-R | Matched sensitivity |
| --- | --- | --- |
| R | +1.11 pp (95% interval -0.86 to +3.08 pp) | +0.62 pp (95% interval -1.18 to +2.42 pp) |
| L | +0.99 pp (95% interval -0.63 to +2.62 pp) | -0.13 pp (95% interval -3.20 to +2.94 pp) |

Right-handed: the point estimate keeps its direction; the interval is narrower and includes zero. Left-handed: the point estimate changes direction; the interval is wider and includes zero.

The mean log-opponent-rank gap (L-minus-R) falls from 0.163 to 0.000. Prior-form gaps fall from -0.009 to -0.002 for focal players and -0.024 to -0.008 for opponents. Form is a prior win proportion; see [full rank/form balance](balance.csv).

The matched covariance matrix is indefinite; both reported contrast variances are positive. Under the unchanged safeguards their intervals remain available but exploratory; no variance repair was applied.

Rankings imperfectly measure strength; restrictions select a narrower sample and do not remove all form or playing-condition differences. This remains observational, not causal. **Primary Q1/Q2/Q3 results are preserved.** [Normalized rank plot](rank_distributions.png) · [Within-player coverage](within_player_coverage.png) · [Summary table](compact_summary.csv) · [Detailed distributions and limitations](DETAILS.md) · [Validation provenance](manifest.json).
