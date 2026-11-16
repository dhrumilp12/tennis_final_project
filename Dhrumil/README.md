# Digital Archeology of ATP Match Histories

**Team:** Phouvadeth Vathana, Joseph Bronyah, Dhrumil Patel

We reconstruct tennis match histories to study performance after ranking upsets, previous meetings, and opponent handedness. Start with the [final report](reports/FINAL_REPORT.md), [results summary](reports/RESULTS.md), or [executed notebook](Tennis_Project.ipynb). **`outputs_final/` contains the authoritative results.**

## Questions and findings

<!-- GENERATED_FINDINGS_START -->
Analysis run: `20261027T121134Z-20f069d1`; **63,784 eligible study matches**.

**Historical primary analysis.** The overview below reports the preserved original models; the supplemental Q1/Q2 checks follow separately.

**1. Does performance after a ranking upset vary with age or experience?** We did not find clear evidence that the upset-related difference varied with age or prior recorded match experience. This does not show that all players recover identically. The overall adjusted next-three-match difference from ordinary losses was -1.37 pp (95% interval -2.24 to -0.51 pp) (18,471 loss events, 341 players).

**2. Do previous meetings help predict the next match?** Meeting count alone gave no clear improvement. Previous head-to-head results lowered prediction error. Meeting count alone: Brier improvement -0.000021 (95% interval -0.000091 to +0.000039). Including previous head-to-head results: +0.000586 (95% interval +0.000095 to +0.001019) (11,340 held-out matches). Positive improvement means lower prediction error.

**3. Does performance differ by opponent handedness?** We found no clear evidence of an adjusted difference against left- versus right-handed opponents in either focal-hand group. Adjusted left-minus-right differences: +1.11 pp (95% interval -0.86 to +3.08 pp) for right-handed focal players; +0.99 pp (95% interval -0.63 to +2.62 pp) for left-handed focal players.

Source rows: [`q1_adjusted_contrasts.csv`](outputs_final/q1_adjusted_contrasts.csv), primary average and age/experience interactions; [`q2_paired_improvements.csv`](outputs_final/q2_paired_improvements.csv), baseline Brier comparisons; [`q3_adjusted_contrasts.csv`](outputs_final/q3_adjusted_contrasts.csv), both focal hands.

**Supplemental Q1/Q2 validation.**

**Q1 direct post-upset associations:** next-three-match age slope -1.43 pp (95% interval -1.81 to -1.04 pp) per year; experience slope +7.73 pp (95% interval +5.95 to +9.51 pp) per log(1 + prior eligible recorded matches) unit. These conditional slopes answer a different question from modification of the upset-versus-ordinary difference. [Direct slopes and separate interactions](validation/q1_q2_checks/q1_post_upset_contrasts.csv).

**Q2 dependence and repeat encounters:** ALL, Baseline → count: both methods leave the direction uncertain. ALL, Baseline → H2H results: both methods support lower prediction error. REPEAT, Baseline → count: both methods leave the direction uncertain. REPEAT, Baseline → H2H results: both methods support lower prediction error. Brier remains primary; these are prediction-error differences, not increases in winning probability or causal effects. [Paired estimates under both methods](validation/q1_q2_checks/q2_comparisons.csv) and [support, retention and limitations](validation/q1_q2_checks/REPORT.md).
<!-- GENERATED_FINDINGS_END -->

“Percentage points” (pp) means an absolute difference between probabilities: 60% versus 59% is one percentage point. Brier score measures prediction error; lower is better. Its improvement is **not** an increase in a player's chance of winning. The reported 95% intervals describe uncertainty under the stated models and dependence assumptions.

## Data and definitions

The study covers **2000–2024 ATP singles**, with **1990–1999** used to build earlier history. We include individual A/M/G knockout events using the documented completion and chronology filters. Original annual files come from the pinned tennis-sackmann archive revision recorded in [SOURCES.md](SOURCES.md); cached files are hash-checked before reuse.

A **ranking upset** is a top-50 player losing to someone ranked at least 30 places lower. Age is measured in years; **observed experience** counts earlier eligible matches recorded since 1990, not a complete career. They are different measures. “Recovery” means subsequent recorded match performance, **not psychological recovery**. Comparisons are observational.

## Install and get started

Use Python 3.10–3.13. Keep the virtual environment at the repository root, then work inside `Dhrumil/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
cd Dhrumil
python -m pip install -r requirements.txt
python -m jupyterlab Tennis_Project.ipynb
```

On Windows, activate with `.venv\Scripts\activate` before entering `Dhrumil/`. All commands below run from `Dhrumil/`. The preserved notebook calls this its “repository root”; that refers to the project directory before this move. The supplied notebook is already executed; you can read its saved results without rerunning it. [requirements-lock.txt](requirements-lock.txt) records the original execution environment; [TEST_RESULTS.md](TEST_RESULTS.md) separates historical execution, remote CI, and later local checks.

To reproduce the full study in a separate results directory, choose either command:

```bash
# Reuse cached inputs; download only missing files from the pinned source.
python tennis_project.py --output-dir validation/full-study
# Require all inputs to be cached; make no network requests.
python tennis_project.py --offline --output-dir validation/full-study
```

To regenerate the written findings from existing authoritative tables, without refitting:

```bash
python tennis_reporting.py --output-dir outputs_final
```

To regenerate the separate [Q3 opponent-comparability validation](validation/q3_comparability/REPORT.md) from saved data and include it in the reports, run the commands below. This checks the adjusted Q3 sample and fits its single matched-sample sensitivity; it leaves the primary models and `outputs_final/` unchanged. The validation has its own [provenance manifest](validation/q3_comparability/manifest.json).

```bash
python tennis_q3_comparability.py
python tennis_reporting.py --output-dir outputs_final
```

The separate [supplemental Q1/Q2 validation](validation/q1_q2_checks/REPORT.md) checks performance after upsets and uncertainty for the saved Q2 predictions. Regenerate it from saved data with the commands below. Historical primary outputs and Q3 validation remain intact; reporting adds the supplement to the reports, README and one Markdown-only notebook cell without rerunning notebook code.

```bash
python tennis_q1_q2_checks.py
python tennis_reporting.py --output-dir outputs_final
```

For fresh-kernel notebook execution, run this **in a separate copy of the repository** when preserving the supplied run:

```bash
python execute_notebook.py
```

That helper reruns the study and replaces `outputs_final/`, reports, README findings, and notebook execution evidence in that copy. It is not needed just to read the project.

Run tests and check the installed dependencies:

```bash
python -m pytest -q
python -m pip check
```

<details>
<summary>Optional quick demo</summary>

```bash
python tennis_project.py --demo --output-dir validation/demo-run
```

This uses the small real Brisbane fixture and explicitly reports insufficient samples for models. Synthetic tests and demo results are software checks, not research findings.
</details>

## Where things live

| Location | Purpose |
| --- | --- |
| `Tennis_Project.ipynb`, `execute_notebook.py` | Executed study and execution helper |
| `tennis_*.py` | Pipeline, analyses, reporting and integrity checks |
| `reports/` | Final report, short results, data-quality report and claim provenance |
| `outputs_final/` | Complete authoritative tables, charts and run inventory |
| `docs/` | Data dictionary, methods, chronology and historical baseline note |
| `data/raw/` | Original inputs, cache manifest and source documents |
| `tests/`, `../.github/workflows/` | Tests, fixtures and offline-test/demo CI |
| `validation/` | Retained execution and regression evidence |

## Limitations and attribution

Tournament-week dates approximate sequence; exact match days and recovery durations are unavailable. Missing follow-up stays missing. Selection, unmeasured playing conditions, residual dependence and smaller handedness subgroups limit inference. Q1 adjustment includes subsequent context and is not causal. Details are in [methods](docs/METHODS.md), [chronology](docs/CHRONOLOGY.md), [data quality](reports/DATA_QUALITY.md), and the [data dictionary](docs/DATA_DICTIONARY.md).

Data were compiled by **Jeff Sackmann** and archived by **Aneeshers**. Code is [MIT-licensed](LICENSE); source and derived data have separate [CC BY-NC-SA 4.0 attribution](DATA_LICENSE.txt).
