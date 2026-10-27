# Prioritized implementation and verification plan

Historical implementation note, retained as evidence for the initial test outcome. This is not the current directory guide; see README.md.

1. Preserve baseline and reproduce regressions. Starting revision: `27f3cdca880281396badef197949aaa75008313f`; clean worktree. Initial `.venv/bin/python -m pytest -q`: **26 passed**, 1,504 dependency deprecation warnings, 4.11 seconds. The shell has no unqualified `python` until the virtual environment is activated. Saved run: 112,056 raw rows, 63,784 eligible study matches, all three models fitted, Q3 one negative covariance diagonal.
2. Repair unresolved follow-up handling and cache inventory merging/atomic writes, with synthetic regression cases. Keep original raw data and `outputs/` intact.
3. Review Q3 identification and dependence; provide subgroup contrasts with full covariance and explicit warnings. Improve Q1 common-population summaries, next-match inference and non-overlap sensitivity; add Q2 paired comparison/calibration outputs without tuning against test outcomes.
4. Add staged publication, run/code/input/environment provenance, attrition, grouped missingness and traceable internal spot checks. Generate numerical reports from verified tables.
5. Run tests, demo in `validation/demo`, cached offline full study in `outputs_final`, and a fresh-kernel full-study notebook. Verify output hashes and report/run consistency; record actual outcomes and remaining limitations.

Analyses remain observational. Age and observed history since 1990 are separate. Recovery means subsequent recorded match performance. No betting odds, point-level extension, dashboard, or deep learning is added.
