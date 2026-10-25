# Real-data smoke-test fixture

`brisbane_2024_excerpt.csv` contains the 31 Brisbane matches in source CSV
lines 2–32 (plus the header) of:

https://github.com/Aneeshers/tennis-sackmann-archive/blob/83733587353df8a41f2fd4f516147d5aa83f5a8d/atp/atp_matches_2024.csv

Source file Git blob SHA: `c401319bc1dec4633dd2c730aa5a7a7376e176f8`.
That is the SHA of the full upstream annual file, NOT this extracted subset.
The fixture was transcribed from the GitHub file response and reviewed against
that response. It is only a parsing/cleaning demonstration, not a sample from
which to infer recovery, head-to-head, or handedness effects.

Expected checks: 31 raw rows, 29 completed eligible matches, one walkover and
one retirement excluded. Models are intentionally skipped for insufficient
historical data. See the root DATA_LICENSE.txt for attribution and licensing.
