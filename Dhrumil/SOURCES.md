# Sources checked for this implementation

## Dataset

- Archive: https://github.com/Aneeshers/tennis-sackmann-archive
- Pinned revision: `83733587353df8a41f2fd4f516147d5aa83f5a8d`
- Original project: https://github.com/JeffSackmann/tennis_atp
- Field definitions: https://github.com/Aneeshers/tennis-sackmann-archive/blob/83733587353df8a41f2fd4f516147d5aa83f5a8d/atp/matches_data_dictionary.txt
- Upstream documentation: https://github.com/Aneeshers/tennis-sackmann-archive/blob/83733587353df8a41f2fd4f516147d5aa83f5a8d/atp/UPSTREAM_README.md
- Actual sampled file: https://github.com/Aneeshers/tennis-sackmann-archive/blob/83733587353df8a41f2fd4f516147d5aa83f5a8d/atp/atp_matches_2024.csv
- Archive license: https://github.com/Aneeshers/tennis-sackmann-archive/blob/83733587353df8a41f2fd4f516147d5aa83f5a8d/LICENSE

The source dictionary documents tournament-week dates, age/rank at tournament
time, winner/loser identities, handedness (`R`, `L`, `U`), and service counts.
The age bands, upset cutoff, eligibility scope, experience features, temporal
split, model choices, and reporting thresholds are choices made in this code,
not definitions supplied or endorsed by the dataset compiler.

## Primary software documentation

- Logistic regression: https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html
- Probability-error metric: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.brier_score_loss.html
- Statsmodels regression API: https://www.statsmodels.org/stable/regression.html
- Statsmodels clustered covariance: https://www.statsmodels.org/stable/generated/statsmodels.stats.sandwich_covariance.cov_cluster_2groups.html

Installed and tested versions are recorded in `TEST_RESULTS.md` and each run's
`run_summary.json`. No claims of statistical significance are hard-coded.

## Inference and current verification

- Aronow, P. M., Samii, C., and Assenova, V. A. (2015). *Cluster-Robust Variance Estimation for Dyadic Data*. Political Analysis 23(4), 564–577. Author manuscript: https://arxiv.org/abs/1312.3398 . The Q3 implementation aggregates repeat directed views by unordered player pair, then accounts for score dependence through either participant.
- NumPy matrix-rank documentation: https://numpy.org/doc/stable/reference/generated/numpy.linalg.matrix_rank.html .

The pinned source dictionary and archive license were inspected from their cached
files in `data/raw/<revision>/`. The full study is now executed from that cache;
`reports/DATA_QUALITY.md` and `TEST_RESULTS.md` identify the actual final run and
checks. Internal spot checks compare local source rows and reconstructed histories;
no independent external match-day verification or human review is claimed.

Code is MIT-licensed (`LICENSE`); source/derived data have separate CC BY-NC-SA
4.0 attribution (`DATA_LICENSE.txt`). Current results use annual match data only.
