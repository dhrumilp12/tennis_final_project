# Digital Archeology of ATP Match Histories

**Team:** Phouvadeth Vathana, Joseph Bronyah, Dhrumil Patel

A reproducible observational study of performance after ranking upsets, previous-opponent history, and opponent handedness. Study years: **2000–2024**; history warm-up: **1990–1999**. Individual ATP A/M/G knockout events only. Age and observed experience are separate. “Recovery” means subsequent recorded match performance, not psychological recovery.

## Authoritative findings

<!-- GENERATED_FINDINGS_START -->
Verified run: `20261027T121134Z-20f069d1`; **63,784 eligible unique study matches**.

**Q1:** Adjusted next-three performance after ranking upsets versus ordinary losses: -1.37 pp (95% interval -2.24 to -0.51 pp). See the report for separate age/experience interactions, next-match results, and non-overlap sensitivity.

**Q2:** Brier improvement from meeting count alone: -0.000021 (95% interval -0.000091 to +0.000039); with previous head-to-head results: +0.000586 (95% interval +0.000095 to +0.001019).

**Q3:** Adjusted opponent L-minus-R differences: +1.11 pp (95% interval -0.86 to +3.08 pp) for right-handed focal players; +0.99 pp (95% interval -0.63 to +2.62 pp) for left-handed focal players.

All are observational estimates with dependence and chronology limitations; see the report for sample sizes and interpretation.
<!-- GENERATED_FINDINGS_END -->

Read [RESULTS.md](reports/RESULTS.md) for plain-English answers and [FINAL_REPORT.md](reports/FINAL_REPORT.md) for the submission report. Every reported number points to a generated table and run ID. **`outputs_final/` is authoritative**; `outputs/` preserves the earlier saved run. Neither the small demo nor synthetic tests supplies research findings.

## Installation

Use Python 3.10–3.13 (the verified environment uses Python 3.13.7):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate`. `requirements.txt` declares compatible ranges; `requirements-lock.txt` records the actual full environment used, including transitive packages. For exact versions, install with `python -m pip install -r requirements-lock.txt` on a compatible Python/platform. Actual executed versions are recorded in the final summary and [TEST_RESULTS.md](TEST_RESULTS.md).

## Exact commands

Run these from the repository root with the environment activated.

Full study (reuses hash-checked cached files; downloads only missing inputs from the pinned revision):

```bash
python tennis_project.py --output-dir outputs_final
python tennis_reporting.py --output-dir outputs_final
```

Full study without network access:

```bash
python tennis_project.py --offline --output-dir outputs_final
python tennis_reporting.py --output-dir outputs_final
```

Real-data demo and offline tests:

```bash
python tennis_project.py --demo --output-dir validation/demo
python -m pytest -q
```

The demo is 31 real Brisbane 2024 source records, with 29 eligible matches. It checks execution and explicitly skips insufficient models. Tests use that excerpt and clearly labeled synthetic fixtures; mocked network tests never download the annual study.

Execute the full-study notebook in a fresh kernel using the active Python environment:

```bash
python execute_notebook.py
```

This reruns the offline full study into `outputs_final`, generates reports/README findings from that run, verifies artifacts, and saves **actually executed** `Tennis_Project.ipynb`. It also records `validation/notebook_execution.json`. To explore interactively: `python -m jupyterlab Tennis_Project.ipynb`. The notebook's `RUN_FULL_STUDY = False` branch uses a separate demo directory and never publishes demo findings as final results.

Recheck final artifact hashes and report consistency:

```bash
python -c "from tennis_repro import verify_output; print(verify_output('outputs_final')['run_id'])"
python -m pytest -q tests/test_reporting.py
```

Use a separate output directory for alternative configurations:

```bash
python tennis_project.py --offline --upset-rank-gap 50 --output-dir validation/gap50
```

Thresholds 20, 30 and 50 are always retained in the descriptive sensitivity table. They are not selected based on significance.

## Definitions and interpretation

A **ranking upset** is a top-50 player losing to someone ranked at least 30 places lower. Q1 compares upset and ordinary losses within that same rank-eligible population. Next-match and next-three-match outcomes are missing when unresolved or unusable; the pipeline never skips a known problematic event to obtain a clean window. Models jointly include age and observed history, their upset interactions, strength, form, surface and following-match context. Player clustering handles repeated/overlapping windows within each player; a sensitivity using greedily selected non-overlapping windows is provided. Post-index context adjustment estimates a conditional association, not a causal recovery effect.

Q2 uses one outcome-independent orientation per physical match (lower player ID first), training before 2020 with a 21-day gap, and identical 2020–2024 held-out matches. Three fixed logistic models distinguish meeting count from earlier head-to-head results. Preprocessing is fitted on training only; test-period histories update as earlier results become available, while model parameters stay frozen. Brier/log-loss/accuracy comparisons, paired intervals, calibration and prior-meeting subgroups are reported. Shared meeting count does not automatically favor either player.

Q3 compares opponents within player, excludes unknown hands, and requires at least ten observations per opponent hand. Service-point differences are unadjusted and require separate valid-service opportunities. Adjusted match-result contrasts use a shared-player dyadic covariance that retains both dependent match views. Separate right- and left-handed focal-player contrasts include full covariance. Legacy negative variances remain explicitly unavailable in sensitivity output; no variance is clipped or absolutized. Small-subgroup and player-deletion diagnostics accompany the results.

`tourney_date` is a tournament-week date. Checked knockout round order, not match number or CSV position, approximates sequence. Exact match-day order and days to recovery are not claimed. Experience means eligible observed history since 1990, not full careers. [CHRONOLOGY.md](docs/CHRONOLOGY.md), [METHODS.md](docs/METHODS.md), and [DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) detail these choices.

## Project structure

| File/directory | Purpose |
| --- | --- |
| `tennis_project.py` | Pinned cache, cleaning, event blockers, histories, staged CLI/notebook runs |
| `tennis_analyses.py` | Q1/Q2 estimation and labeled charts |
| `tennis_handedness.py` | Q3 within-player inference and sensitivities |
| `tennis_repro.py` | Provenance, attrition, internal spot checks and artifact verification |
| `tennis_reporting.py` | Numerical reports generated from verified tables |
| `Tennis_Project.ipynb`, `execute_notebook.py` | Executed full-study presentation and fresh-kernel execution |
| `reports/` | Results, final report, data quality, machine-readable claim provenance |
| `docs/` | Dictionary, methods, chronology and initial work plan |
| `outputs_final/` | Authoritative tables, charts and `run_summary.json` |
| `outputs/` | Preserved earlier saved results |
| `data/raw/<revision>/` | Original annual source files, source documents and cache manifest |
| `tests/` | Offline fixtures, regression and consistency tests |
| `validation/` | Actual execution logs and regression evidence |

Each run uses a fresh staging directory, verifies files, and publishes the directory as a unit. Existing targets are retained in `.NAME.previous-RUN_ID` backups; failed staging directories carry `FAILED_RUN.json` and no success summary. Unrelated user files are preserved. The run summary records timestamp, configuration, input hashes, actual package versions, base git revision/dirty state, actual source-code hashes, per-analysis warnings and output inventory. Cache inventory includes files outside the current request; the run input list includes only files actually read.

## Sources and licenses

Data compiled by **Jeff Sackmann**, archived by **Aneeshers**, pinned at `83733587353df8a41f2fd4f516147d5aa83f5a8d`. See [SOURCES.md](SOURCES.md). The code is MIT-licensed ([LICENSE](LICENSE)); the source and derived data have separate **CC BY-NC-SA 4.0** terms and attribution ([DATA_LICENSE.txt](DATA_LICENSE.txt)). No betting odds, point-level charting data, dashboard, or deep learning is used.
