# Executed verification

Authoritative full-study run: `20261027T121134Z-20f069d1`. Base git revision: `27f3cdca880281396badef197949aaa75008313f`; the working tree was dirty because this implementation was uncommitted. Actual source hashes and dirty-state details are in `outputs_final/run_summary.json`. No changes were pushed.

## Checks actually executed

| Check | Actual result | Evidence |
| --- | --- | --- |
| Initial existing test suite, before modifications | 26 passed; 1,504 warnings in 4.11 s | `docs/WORK_PLAN.md`; initial terminal execution |
| Final `.venv/bin/python -m pytest -q` | 74 passed, 1504 warnings in 5.98s | `validation/tests_final.txt` |
| `.venv/bin/python tennis_project.py --demo --output-dir validation/demo` | 31 real Brisbane source records; 29 eligible matches; all insufficient model paths explicitly reported | `validation/demo_final.log`, `validation/demo/run_summary.json` |
| `.venv/bin/python tennis_project.py --offline --output-dir outputs_final` | Successful full-data CLI run `20261027T120759Z-38f79f29`; 112,056 raw records and 63,784 eligible study matches | `validation/full_cli.log`; retained prior-run backup |
| `.venv/bin/python execute_notebook.py` | Full-study rerun, fresh kernel; 11/11 code cells executed; 0 execution errors; 36.99 s | `validation/notebook.log`, `validation/notebook_execution.json`, saved notebook |
| CLI versus final notebook numerical outputs | 26 Q1/Q2/Q3 CSV tables equal within 1e-10 tolerance | `validation/final_checks.json` |
| Input/output integrity | 35 annual input hashes and 56 generated artifact hashes verified; all 24 original output files unchanged | `validation/final_checks.json` |
| Actual module/requirement hashes and notebook hash | Match final provenance/execution record | `validation/final_checks.json` |
| `python -m pip check` | No broken requirements found | `validation/environment_check.txt` |
| `git diff --check` | Passed | Executed after edits |

The shell did not have unqualified `python` until environment activation, so actual terminal commands used `.venv/bin/python`. These are equivalent to the documented commands after `source .venv/bin/activate`.

## Synthetic regressions versus research evidence

The original January follow-up bug was reproduced using explicitly synthetic records: a January 1 loss, two conflicting copies on January 8, and later matches on January 15/22/29. Before the fix it produced a complete window; afterward one unresolved blocker occupies the event slot and the outcome is missing. Known focal players with invalid opponents, unknown dates, conflicting date ranges, unsupported identities and serialized ledgers are covered. The real run has zero conflicting keys and no identity/date blockers; this edge case does not show corruption of the original real findings. Evidence: `validation/recovery_regression.json` and `tests/test_recovery_blockers.py`.

The subset-cache bug was reproduced with mocked network responses: caching 2023–2024, requesting 2024 only, and returning to the full range lost 2023 provenance and marked it `local_unverified` before the fix. New tests check preserved inventory/retrieval information, atomic failed replacement, interrupted requests and subsequent full offline reuse. Evidence: `validation/baseline_audit.json` and `tests/test_provenance.py`. No mock download is used in research outputs.

Existing synthetic multi-season tests still exercise all model paths. New tests cover exact dyadic score covariance enumeration, the left-handed coefficient sum including cross covariance, negative-variance unavailability, subgroup support, common-rank Q1 population, greedy non-overlap, training-only preprocessing, fixed orientation, no-current/future-outcome history features, calibration accounting, missing follow-up, integer service counts, chronology screens, staged failure preservation, and report numerical/run consistency. The demo remains a real-data parsing/execution check, not a substitute for the full study.

## Full-study audit

The final study contains 63,784 eligible unique matches, unchanged from the preserved baseline. Q1 has 24,021 top-50 known-rank index losses; the primary next-three adjusted model uses 18,471 events from 341 players. Q2 trains on 52,444 and evaluates all three frozen models on the same 11,340 matches. Q3 adjusts 112,503 player views of 61,412 unique matches from 420 focal players. Source: final `run_summary.json/q1`, `/q2`, `/q3`; physical matches and player views are deliberately separate.

The Q3 within design has rank 34/34. The original player-by-match covariance's negative interaction variance is reproduced and retained with unavailable coefficient uncertainty. Primary shared-player dyadic covariance has 0 negative coefficient variance terms; both full-covariance subgroup contrasts have available exploratory intervals, each spanning zero. Sensitivity checks retain the original method, tournament-only and single-view methods, plus removal of high-exposure players in either role. Available intervals do not make the scientific question definitively resolved.

Automated internal spot checks passed 27 comparisons using source-row references, histories, upset windows and opponent pairs. A separate assistant review recomputed both Q3 contrasts from saved covariance and visually inspected all six chart types; `validation/report_review/review.json` records that scope. This is not external source verification or human review.

## Environment actually used

| component | version |
| --- | --- |
| python | 3.13.7 |
| platform | macOS-26.6.2-arm64-arm-64bit-Mach-O |
| numpy | 2.5.4 |
| pandas | 2.3.3 |
| scipy | 1.18.1 |
| scikit_learn | 1.9.1 |
| statsmodels | 0.14.6 |
| matplotlib | 3.11.2 |
| requests | 2.34.2 |
| pytest | 9.1.1 |
| nbformat | 5.11.1 |
| nbclient | 0.11.0 |
| ipykernel | 7.4.0 |
| jupyterlab | 4.6.4 |

`requirements.txt` contains compatible ranges; `requirements-lock.txt` is the actual `pip freeze`. The added GitHub Actions workflow runs offline tests and the real-data demo; it has **not** been remotely executed in this session and does not download annual seasons.

## Warnings and remaining limits

- The final tests emit 1,504 NumPy/pandas timedelta deprecation warnings, mostly from the existing synthetic fixture. The final full run records one such runtime warning. They are recorded rather than presented as test failures.
- Jupyter initially could not bind its local kernel ports under the sandbox. The permitted local-kernel retry succeeded; the saved notebook is actually executed. Its launcher logs a local TCP transport warning. No remote data download was performed by the notebook.
- An early plot run reported unavailable system font metadata and an unwritable default matplotlib cache. The plotting function now uses a writable temporary cache and all six chart types rendered and were inspected.
- The cache inventory contains 39 entries, including source documentation; this run actually reads 35 annual files. Original pinned retrieval provenance is preserved; hashes detect changes but do not independently establish source truth.
- Coarse tournament-week chronology cannot establish exact match-day order. The bounded screen flags 2,029 potential study-period individual-event overlaps involving 319 players, not confirmed collisions. Early exits and ordinary scheduling changes can explain them; no fake dates or speculative exclusions were introduced.
- Experience is observed eligible history since 1990. Exclusions, missingness, residual network/event dependence, limited left-handed support and unmeasured conditions constrain inference. Q1 post-index adjustment is conditional, Q2's small predictive improvement needs independent replication, and Q3 does not establish a universal effect. No causal or psychological claim is made.

No execution blocker remains. The submission files are `reports/FINAL_REPORT.md`, `reports/RESULTS.md`, `reports/DATA_QUALITY.md`, `docs/DATA_DICTIONARY.md`, the executed `Tennis_Project.ipynb`, and the supporting `outputs_final/` tables/charts/summary, README, sources, licenses and this verification record.
