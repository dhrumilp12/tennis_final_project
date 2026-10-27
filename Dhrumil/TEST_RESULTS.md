# Executed verification

The sections below record the original **pre-push analysis execution**. Post-push CI and later local cleanup checks are recorded separately at the end.

Authoritative full-study run: `20261027T121134Z-20f069d1`. Base git revision: `27f3cdca880281396badef197949aaa75008313f`; the working tree was dirty because this implementation was uncommitted. Actual source hashes and dirty-state details are in `outputs_final/run_summary.json`. No changes were pushed during that implementation session.

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

`requirements.txt` contains compatible ranges; `requirements-lock.txt` is the actual `pip freeze`. At the time this historical execution record was written, the added GitHub Actions workflow had not yet been remotely executed. It runs offline tests and the real-data demo, without downloading annual seasons; the later verified result is recorded below.

## Warnings and remaining limits

- The final tests emit 1,504 NumPy/pandas timedelta deprecation warnings, mostly from the existing synthetic fixture. The final full run records one such runtime warning. They are recorded rather than presented as test failures.
- Jupyter initially could not bind its local kernel ports under the sandbox. The permitted local-kernel retry succeeded; the saved notebook is actually executed. Its launcher logs a local TCP transport warning. No remote data download was performed by the notebook.
- An early plot run reported unavailable system font metadata and an unwritable default matplotlib cache. The plotting function now uses a writable temporary cache and all six chart types rendered and were inspected.
- The cache inventory contains 39 entries, including source documentation; this run actually reads 35 annual files. Original pinned retrieval provenance is preserved; hashes detect changes but do not independently establish source truth.
- Coarse tournament-week chronology cannot establish exact match-day order. The bounded screen flags 2,029 potential study-period individual-event overlaps involving 319 players, not confirmed collisions. Early exits and ordinary scheduling changes can explain them; no fake dates or speculative exclusions were introduced.
- Experience is observed eligible history since 1990. Exclusions, missingness, residual network/event dependence, limited left-handed support and unmeasured conditions constrain inference. Q1 post-index adjustment is conditional, Q2's small predictive improvement needs independent replication, and Q3 does not establish a universal effect. No causal or psychological claim is made.

No execution blocker remains. The submission files are `reports/FINAL_REPORT.md`, `reports/RESULTS.md`, `reports/DATA_QUALITY.md`, `docs/DATA_DICTIONARY.md`, the executed `Tennis_Project.ipynb`, and the supporting `outputs_final/` tables/charts/summary, README, sources, licenses and this verification record.


## Post-push verification — October 27, 2026

Read-only inspection of GitHub Actions verified that the latest run is [Offline tests #1](https://github.com/dhrumilp12/tennis_final_project/actions/runs/40504267984), triggered by a push of commit `7c9569d6a25780506285faa7a7f587d9154b9223`. It ran on October 27, 2026, **08:30:19–08:31:34 EDT** (12:30:19–12:31:34 UTC) and concluded **success**. The `test` job succeeded, including dependency installation, `python -m pytest -q`, and `python tennis_project.py --demo --output-dir validation/ci-demo`. The API listed one run at inspection time, and that commit matched remote `main`. Run/job/step details and inspection time are retained under `remote_ci` in the [cleanup verification record](validation/cleanup_verification.json).

This workflow checks tests and the demo, **not a fresh full historical analysis**. Its success applies to that committed revision, not subsequent local cleanup edits. No commit, push or workflow trigger was performed during this cleanup.

## Reporting and cleanup provenance

`outputs_final/` remains authoritative. The historical `outputs/` directory was removed in the already-pushed `ae573c4` commit; it is not part of the current clone and is absent on this machine. Historical statements above about preserving its files describe the original implementation checks, recorded in `validation/baseline_audit.json` and `validation/final_checks.json`. Optional local `.outputs_final.previous-*` backups are not required clone contents.

The original run summary, input/output inventories, notebook bytes and execution record are preserved. Its source hashes describe code at analysis time, not later reporting edits. All original source/requirement hashes were checked against immutable commit `7c9569d6a25780506285faa7a7f587d9154b9223`; only `tennis_reporting.py` intentionally changes among those files. The separate `validation/cleanup_verification.json` records its old/new hashes and before-cleanup hashes of every authoritative artifact. The tests enforce that boundary rather than rewriting historical hashes.

Removed 34 unreferenced intermediate files: repeated chronology/Q1/Q3 audit tables, header-only empty-sample outputs, two superseded test logs and an obsolete worktree-status snapshot. Numerical sensitivity results remain in `outputs_final/`. The short `docs/WORK_PLAN.md` remains because it substantiates the initial 26-test result. The complete historical demo, baseline/regression/final-integrity records and chart-review record remain. The review record describes an intermediate run inspected at that time; its optional local working directory is not promised in a fresh clone. Three small historical logs cited above are now explicitly retained alongside their JSON records.


## Local cleanup checks — October 27, 2026

These checks exercised the proposed, uncommitted documentation/reporting cleanup; the earlier GitHub Actions run did not test it. No new authoritative analysis was published.

| Check | Actual outcome |
| --- | --- |
| Existing suite before cleanup | 74 passed, 1504 warnings in 5.85s |
| `.venv/bin/python -m pytest -q` after cleanup | 96 passed, 1504 warnings in 7.78s — [full log](validation/cleanup_tests.txt) |
| Required demo command (`--demo --output-dir validation/cleanup-demo`) | 31 records, 29 eligible; models explicitly insufficient |
| `.venv/bin/python -m pip check` | No broken requirements found; existing environment retained |
| `git diff --check` | Passed |
| Isolated report regeneration | README and reports idempotent; sections outside generated markers preserved |
| Isolated fresh-kernel notebook | 11/11 code cells executed; zero errors; 37.87 seconds |
| Isolated numerical comparison | 48 CSV/CSV.gz tables agree with authoritative tables within 1e-10 |
| Links and inclusion | 85 local Markdown links checked; no broken links; required targets tracked or present as unignored proposed additions |
| Preserved artifacts | All 57 original final artifacts and the saved notebook remain byte-identical; numerical claim tables unchanged |

The extra 22 focused tests cover both primary Q1 outcomes, changed future interaction evidence, missing/unavailable estimates, unrounded interval boundaries, detailed narrative consistency, and isolated README/report regeneration. Existing scientific tests and warnings remain intact. The original notebook's saved wording already reports age and experience intervals spanning zero; its evidence is preserved rather than replacing its outputs with newly written text. The temporary-copy execution exercised the updated shared explanation in the notebook without touching the submitted notebook.

The separate [cleanup verification record](validation/cleanup_verification.json) contains the remote CI inspection, historical/current reporting hashes, protected artifact hashes, exact removed-file list and isolated notebook result. Temporary copies and disposable cleanup-demo output are not required in a clone. Retained notebook, final-integrity and regression records remain available. Existing NumPy/pandas deprecation warnings persist; the local Jupyter launcher also reports its localhost TCP transport warning. No model, data filter, threshold, dependency version or numerical result was changed.


## Directory relocation — October 27, 2026

The project now lives in `Dhrumil/`; Git metadata, CI, ignore/attribute rules, the short entry README and the existing `.venv` remain at the repository root. All project-relative data, output, report and test paths keep their meaning when commands run from `Dhrumil/`. Activate the root environment before entering that directory, or use `../.venv/bin/python` there. Historical `.venv/bin/python` commands and the notebook's “repository root” wording refer to the layout at their original execution time. Optional local `.outputs_final.previous-*` backups remain at the repository root.

No analysis source, dependency, raw input, final output, report numerical claim or saved notebook was changed. The original run `20261027T121134Z-20f069d1` and its hashes remain authoritative. The CI workflow now uses `Dhrumil` as its working directory and `Dhrumil/requirements.txt` for dependency caching; these edits have not been committed, pushed or remotely tested in this relocation session.

Local checks after the move: **96 passed, 1504 warnings in 7.38s** ([log](validation/relocation_tests.txt)); demo completed with 31 records and 29 eligible matches, with insufficient model samples explicitly reported; `pip check` found no broken requirements. Input/output integrity verification passed. An isolated full-study notebook execution in a temporary copy with the same nested layout completed 11/11 cells with zero errors in 37.06 seconds. All 48 numerical tables agree with the authoritative outputs within `1e-10`. The submitted notebook was not re-executed or overwritten. README/report regeneration is covered by the passing tests; `git diff --check` passed. Existing deprecation and local Jupyter transport warnings remain.

The separate [relocation check record](validation/relocation_checks.json) preserves these checks without modifying historical execution records. Local links and inclusion of the moved files were checked before handoff.
