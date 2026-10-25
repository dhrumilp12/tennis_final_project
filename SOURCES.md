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
