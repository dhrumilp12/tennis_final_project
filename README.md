# Digital Archeology of ATP Match Histories

**Team:** Phouvadeth Vathana, Joseph Bronyah, Dhrumil Patel

The project lives in **[Dhrumil/](Dhrumil/)**, including its code, data, tests, reports and executed notebook.

- [Project guide and commands](Dhrumil/README.md)
- [Final report](Dhrumil/reports/FINAL_REPORT.md) and [results summary](Dhrumil/reports/RESULTS.md)
- [Executed notebook](Dhrumil/Tennis_Project.ipynb)
- [Authoritative results](Dhrumil/outputs_final/) and [verification record](Dhrumil/TEST_RESULTS.md)

From this repository root:

```bash
python3 -m venv .venv       # First-time setup; keep an existing environment.
source .venv/bin/activate
cd Dhrumil
python -m pip install -r requirements.txt
python -m pytest -q
```

If the environment already exists, start with activation. On Windows, activate with `.venv\Scripts\activate` before `cd Dhrumil`.

Git metadata, CI configuration and the local environment remain at the repository root. Run project commands from `Dhrumil/`; CI uses that same working directory. The original analysis run and saved notebook are preserved.

Code: [MIT license](Dhrumil/LICENSE). Data: [source attribution](Dhrumil/SOURCES.md) and [separate data license](Dhrumil/DATA_LICENSE.txt).
