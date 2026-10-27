#!/usr/bin/env python3
"""Reconstruct ATP match histories for three observational research questions.

Run: python tennis_project.py
Notebook: Tennis_Project.ipynb
Data source: https://github.com/Aneeshers/tennis-sackmann-archive
The archive's ATP dictionary defines the original columns. See README.md for
our analysis definitions, scope, chronology assumptions, and limitations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import re
import sys
import tempfile
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPOSITORY = "Aneeshers/tennis-sackmann-archive"
# Verified archive commit, not the moving main branch.
REVISION = "83733587353df8a41f2fd4f516147d5aa83f5a8d"
BASE_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}"
ROUND_ORDER = {"R128": 1, "R64": 2, "R32": 3, "R16": 4, "QF": 5, "SF": 6, "F": 7}
REQUIRED = ["tourney_id", "tourney_name", "tourney_date", "tourney_level", "round",
            "match_num", "surface", "best_of", "score", "winner_id", "loser_id",
            "winner_name", "loser_name", "winner_age", "loser_age", "winner_hand",
            "loser_hand", "winner_rank", "loser_rank"]
STATS = ["svpt", "1stIn", "1stWon", "2ndWon", "df", "ace", "bpSaved", "bpFaced"]
LOG = logging.getLogger("tennis")


@dataclass
class Config:
    output_dir: str = "outputs"
    raw_dir: str = "data/raw"
    history_start: int = 1990  # Warm-up: earlier history, not primary analysis rows.
    analysis_start: int = 2000
    end_year: int = 2024
    test_start: int = 2020
    upset_max_rank: int = 50
    upset_rank_gap: int = 30
    recent_matches: int = 10
    min_hand_matches: int = 10
    bootstrap_samples: int = 500
    random_seed: int = 42
    offline: bool = False
    make_plots: bool = True

    def validate(self) -> None:
        if not 1968 <= self.history_start <= self.analysis_start <= self.end_year:
            raise ValueError("Require 1968 <= history_start <= analysis_start <= end_year.")
        if self.upset_max_rank < 1 or self.upset_rank_gap < 1:
            raise ValueError("Upset thresholds must be positive.")
        if self.recent_matches < 1 or self.min_hand_matches < 1:
            raise ValueError("History length and handedness minimum must be positive.")
        if self.bootstrap_samples < 1:
            raise ValueError("bootstrap_samples must be positive.")


def write_json(path: Path, obj: Any) -> None:
    """Atomically replace a valid JSON document, retaining the previous on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, indent=2, default=str, allow_nan=False)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_data(cfg: Config) -> list[Path]:
    """Download pinned yearly CSVs; cache, hash, and fail rather than skip a year.

    The cache is isolated by repository revision. When working offline, manually
    placed files are accepted but explicitly marked as local/unverified copies.
    """
    root = Path(cfg.raw_dir) / REVISION
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    previous = {}
    if manifest_path.exists():
        previous = {x["filename"]: x for x in json.loads(manifest_path.read_text())["files"]}
    session = requests.Session()
    session.headers["User-Agent"] = "Tennis-Class-Research/1.0"
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    files, records = [], previous.copy()
    relative_paths = ["LICENSE", "README.md", "atp/UPSTREAM_README.md", "atp/matches_data_dictionary.txt"]
    relative_paths += [f"atp/atp_matches_{y}.csv" for y in range(cfg.history_start, cfg.end_year + 1)]
    try:
        for relative in relative_paths:
            filename = relative.replace("/", "__") if not relative.endswith(".csv") else Path(relative).name
            target = root / filename
            url = f"{BASE_URL}/{relative}"
            old = previous.get(filename)
            now = datetime.now(timezone.utc).isoformat()
            if target.exists():
                current_hash = digest(target)
                if old and current_hash != old["sha256"]:
                    raise ValueError(f"Cached file changed: {target}. Restore it or use a new raw directory.")
                origin = old.get("origin", "local_unverified") if old else "local_unverified"
                retrieved = old.get("retrieved_at_utc") if old else None
            elif cfg.offline:
                if relative.endswith(".csv"):
                    raise FileNotFoundError(f"Offline file missing: {target}")
                continue
            else:
                LOG.info("Downloading %s", relative)
                try:
                    response = session.get(url, timeout=(10, 90))
                    response.raise_for_status()
                except requests.RequestException as exc:
                    raise RuntimeError(f"Could not download {relative}. Check your internet connection. "
                                       "No missing year has been silently skipped.") from exc
                body = response.content
                if relative.endswith(".csv") and b"winner_id" not in body.splitlines()[0]:
                    raise ValueError(f"Unexpected CSV header from {url}")
                temp = target.with_suffix(target.suffix + ".partial")
                temp.write_bytes(body)
                temp.replace(target)
                current_hash, origin, retrieved = digest(target), "downloaded_pinned_url", now
            records[filename] = {**(old or {}), "filename": filename, "source_path": relative, "source_url": url,
                            "revision": REVISION, "sha256": current_hash, "bytes": target.stat().st_size,
                            "origin": origin, "retrieved_at_utc": retrieved, "checked_at_utc": now}
            # Save after each file so interrupted runs retain provenance.
            write_json(manifest_path, {"repository": REPOSITORY, "revision": REVISION,
                                      "files": [records[key] for key in sorted(records)]})
            if relative.endswith(".csv"):
                files.append(target)
    finally:
        session.close()
    return files


def load_files(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        frame = pd.read_csv(path, low_memory=False)
        missing = set(REQUIRED) - set(frame.columns)
        if missing:
            raise ValueError(f"{path.name}: missing required columns: {sorted(missing)}")
        frame["source_file"] = path.name
        frame["source_csv_row"] = np.arange(2, len(frame) + 2)  # Header is CSV line 1.
        frames.append(frame)
    if not frames:
        raise ValueError("No input CSVs supplied.")
    return pd.concat(frames, ignore_index=True)


def clean_matches(raw: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Keep excluded records in the audit table instead of silently deleting them."""
    d = raw.copy()
    original_columns = [x for x in d.columns if not x.startswith("source_")]
    exact_duplicates = d.duplicated(original_columns, keep="first")
    duplicate_rows = d.loc[exact_duplicates].copy()
    d = d.loc[~exact_duplicates].copy()
    numeric = ["winner_id", "loser_id", "winner_age", "loser_age", "winner_rank", "loser_rank", "best_of"]
    numeric += [f"{side}_{stat}" for side in ["w", "l"] for stat in STATS]
    for col in numeric:
        if col not in d:
            d[col] = np.nan
        d[col] = pd.to_numeric(d[col], errors="coerce")
    for col in ["winner_rank", "loser_rank"]:
        d.loc[d[col] <= 0, col] = np.nan
    for col in ["winner_age", "loser_age"]:
        d.loc[~d[col].between(12, 65), col] = np.nan
    for col in ["winner_hand", "loser_hand"]:
        d[col] = d[col].fillna("U").astype(str).str.upper().str.strip()
        d.loc[~d[col].isin(["L", "R"]), col] = "U"
    d["surface"] = d["surface"].fillna("Unknown").astype(str)
    for col in ["tourney_id", "tourney_name", "round", "tourney_level"]:
        d[col] = d[col].fillna("").astype(str).str.strip()
    d["tourney_date"] = pd.to_datetime(d["tourney_date"].astype(str).str.replace(r"\.0$", "", regex=True),
                                          format="%Y%m%d", errors="coerce")
    d["season"] = d["tourney_date"].dt.year
    d["round_order"] = d["round"].map(ROUND_ORDER)
    # Source identifiers, NOT a chronological match-number assumption.
    d["match_id"] = d["tourney_id"] + ":" + d["match_num"].astype(str).str.replace(r"\.0$", "", regex=True)
    d["conflicting_key"] = d.duplicated(["tourney_id", "match_num"], keep=False)
    identity_ok = (d["winner_id"].notna() & d["loser_id"].notna() &
                   d["winner_id"].ne(d["loser_id"]) & d["winner_id"].gt(0) & d["loser_id"].gt(0) &
                   d["winner_id"].mod(1).eq(0) & d["loser_id"].mod(1).eq(0))
    d["identity_ok"] = identity_ok
    score = d["score"].fillna("").astype(str).str.upper().str.strip()
    # A completion screen, not a full score reconstruction/validation engine.
    unfinished = score.str.contains(r"W\s*/?\s*O|RET|DEF|ABD|ABN|CANC|BYE|UNFIN", regex=True)
    d["completed"] = score.str.contains(r"\d+-\d+", regex=True) & ~unfinished & ~score.str.contains(r"[A-Z?]")
    team = d["tourney_name"].str.contains(r"United Cup|ATP Cup|Davis Cup|Hopman|Laver Cup|World Team|Team Cup", case=False, regex=True)
    # A consistent, explicitly narrower scope: individual ATP/major knockout events.
    d["in_scope"] = d["tourney_level"].isin(["A", "M", "G"]) & ~team
    unsupported_events = d.loc[d["round_order"].isna(), "tourney_id"].unique()
    d["order_reliable"] = d["tourney_date"].notna() & ~d["tourney_id"].isin(unsupported_events)
    # Exclude ambiguous same-player ordering, rather than sort arbitrary match_num.
    views = []
    for side in ["winner", "loser"]:
        known = d[f"{side}_id"].gt(0) & d[f"{side}_id"].mod(1).eq(0)
        v = d.loc[known, ["match_id", "tourney_id", "tourney_date", "round", f"{side}_id"]].rename(columns={f"{side}_id": "player_id"})
        views.append(v)
    ids = pd.concat(views, ignore_index=True)
    simultaneous = ids.groupby(["player_id", "tourney_date"], dropna=False)["tourney_id"].transform("nunique").gt(1)
    same_round = ids.duplicated(["player_id", "tourney_id", "round"], keep=False)
    d["same_date_multiple_events"] = d["match_id"].isin(ids.loc[simultaneous, "match_id"])
    d["repeated_player_round"] = d["match_id"].isin(ids.loc[same_round, "match_id"])
    d["unsupported_round_event"] = d["tourney_id"].isin(unsupported_events)
    d["missing_tournament_date"] = d["tourney_date"].isna()
    bad_matches = set(ids.loc[simultaneous | same_round, "match_id"])
    d.loc[d["match_id"].isin(bad_matches), "order_reliable"] = False
    d["within_history_window"] = d["season"].between(cfg.history_start, cfg.end_year)
    d["eligible"] = (identity_ok & ~d["conflicting_key"] & d["in_scope"] & d["within_history_window"] &
                      d["completed"] & d["order_reliable"] & d["tourney_id"].ne("") & d["match_num"].notna())
    flags = [(~identity_ok, "invalid_player_ids"), (d["conflicting_key"], "conflicting_match_key"),
             (~d["in_scope"], "outside_individual_AMG_scope"), (~d["completed"], "unfinished_or_unrecognized_score"),
             (~d["order_reliable"], "ambiguous_order"), (~d["within_history_window"], "outside_history_window"),
             (d["tourney_id"].eq("") | d["match_num"].isna(), "missing_match_key")]
    d["exclusion_reasons"] = ""
    for mask, label in flags:
        d.loc[mask, "exclusion_reasons"] += label + ";"
    d["in_analysis_period"] = d["season"].between(cfg.analysis_start, cfg.end_year)
    d = d.sort_values(["tourney_date", "round_order", "tourney_id", "match_id"], na_position="last").reset_index(drop=True)
    audit = {"raw_match_rows": len(raw), "exact_duplicates_removed": len(duplicate_rows),
             "unique_source_rows": len(d), "eligible_history_matches": int(d["eligible"].sum()),
             "eligible_analysis_matches": int((d["eligible"] & d["in_analysis_period"]).sum()),
             "exclusion_flag_counts_nonexclusive": {label: int(mask.sum()) for mask, label in flags}}
    return d, duplicate_rows, audit


def build_event_ledger(matches: pd.DataFrame) -> pd.DataFrame:
    """One unresolved record group per known player, never one per conflicting copy.

    These records cannot supply an outcome or enter pre-match history. A date is
    supplied only when all copies agree. Date bounds describe conflicting source
    claims, not imputed match days. A missing date leaves chronology unbounded.
    Unknown players are retained in the ledger but cannot be linked to histories.
    """
    columns = ["event_key", "match_id", "player_id", "tourney_id", "tourney_date",
               "earliest_claimed_date", "latest_claimed_date", "round_order",
               "placement_status", "blocker_reason", "source_record_count", "source_references"]
    missing_from_views = (~matches["identity_ok"] | matches["conflicting_key"] |
                          matches["tourney_date"].isna())
    unresolved = matches.loc[missing_from_views].copy()
    if unresolved.empty:
        return pd.DataFrame(columns=columns)
    # A missing physical key cannot justify combining unrelated source rows.
    unresolved["event_key"] = unresolved["match_id"]
    no_key = unresolved["tourney_id"].eq("") | unresolved["match_num"].isna()
    unresolved.loc[no_key, "event_key"] = [
        f"unkeyed:{r.source_file}:{r.source_csv_row}" for r in unresolved.loc[no_key].itertuples()]
    records = []
    for key, group in unresolved.groupby("event_key", sort=True):
        identifiers = pd.concat([group["winner_id"], group["loser_id"]])
        identifiers = identifiers.loc[identifiers.gt(0) & identifiers.mod(1).eq(0)].dropna().unique()
        known_players = sorted(int(x) for x in identifiers) or [np.nan]
        date_known = group["tourney_date"].notna().all()
        one_date = date_known and group["tourney_date"].nunique() == 1
        one_round = group["round_order"].notna().all() and group["round_order"].nunique() == 1
        placement = ("dated_round_resolved" if one_date and one_round else
                     "dated_round_unknown" if one_date else
                     "date_range_conflict" if date_known else "date_unknown")
        reasons = []
        if group["conflicting_key"].any():
            reasons.append("conflicting_match_key")
        if (~group["identity_ok"]).any():
            reasons.append("invalid_player_identity")
        if not date_known:
            reasons.append("missing_date")
        if not one_date and date_known:
            reasons.append("conflicting_dates")
        if not one_round:
            reasons.append("unresolved_round")
        source_refs = "|".join(sorted({f"{r.source_file}:{r.source_csv_row}" for r in group.itertuples()}))
        for player in known_players:
            records.append({"event_key": key, "match_id": group["match_id"].iloc[0],
                            "player_id": player, "tourney_id": group["tourney_id"].iloc[0],
                            "tourney_date": group["tourney_date"].iloc[0] if one_date else pd.NaT,
                            "earliest_claimed_date": group["tourney_date"].min() if date_known else pd.NaT,
                            "latest_claimed_date": group["tourney_date"].max() if date_known else pd.NaT,
                            "round_order": group["round_order"].iloc[0] if one_round else np.nan,
                            "placement_status": placement, "blocker_reason": ";".join(reasons),
                            "source_record_count": len(group), "source_references": source_refs})
    return pd.DataFrame(records, columns=columns)


def make_player_rows(matches: pd.DataFrame) -> pd.DataFrame:
    """Two views of a resolved physical match, with a separate blocker ledger.

    The ledger is preserved in attrs through history construction and consumed
    by build_recovery_events; excluded identities never acquire invented wins.
    """
    valid = matches["identity_ok"] & ~matches["conflicting_key"] & matches["tourney_date"].notna()
    m = matches.loc[valid].copy()
    metadata = ["match_id", "source_file", "source_csv_row", "tourney_id", "tourney_name", "tourney_date",
                "season", "round", "round_order", "surface", "tourney_level", "best_of", "score",
                "eligible", "completed", "in_scope", "order_reliable", "in_analysis_period"]
    frames = []
    for side, opposite, stat_prefix, won in [("winner", "loser", "w", 1), ("loser", "winner", "l", 0)]:
        p = m[metadata].copy()
        for field in ["id", "name", "age", "hand", "rank"]:
            p[f"player_{field}"] = m[f"{side}_{field}"]
            p[f"opponent_{field}"] = m[f"{opposite}_{field}"]
        p["player_id"] = p["player_id"].astype("int64")
        p["opponent_id"] = p["opponent_id"].astype("int64")
        p["won"] = won
        for stat in STATS:
            p[stat] = m[f"{stat_prefix}_{stat}"]
        # Mask impossible/incomplete stat components, without removing match results.
        sw = p["1stWon"] + p["2ndWon"]
        valid_service = (p["svpt"].gt(0) & p["1stIn"].between(0, p["svpt"]) &
                         p["1stWon"].between(0, p["1stIn"]) &
                         p["2ndWon"].between(0, p["svpt"] - p["1stIn"]) &
                         p[["svpt", "1stIn", "1stWon", "2ndWon"]].mod(1).eq(0).all(axis=1))
        p["valid_service_stats"] = valid_service
        p["service_points_won"] = sw.where(valid_service)
        p["service_points_observed"] = p["svpt"].where(valid_service)
        p["service_win_rate"] = (sw / p["svpt"]).where(valid_service)
        p["double_fault_rate"] = (p["df"] / p["svpt"]).where(p["svpt"].gt(0) & p["df"].between(0, p["svpt"]))
        frames.append(p)
    result = pd.concat(frames, ignore_index=True)
    result.attrs["event_blocker_ledger"] = build_event_ledger(matches).to_dict("records")
    return result


def add_history(player_rows: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Only earlier eligible results enter pre-match features.

    Tournament-date + round order is an explicitly documented approximation of
    a player's sequence. Exact match dates are NOT invented. Shared time-block
    results are all read before any are added to history.
    """
    p = player_rows.sort_values(["tourney_date", "round_order", "tourney_id", "match_id", "player_id"], na_position="last").reset_index(drop=True).copy()
    counts, wins = defaultdict(int), defaultdict(int)
    recent = defaultdict(lambda: deque(maxlen=cfg.recent_matches))
    pairs = defaultdict(lambda: [0, 0])  # Ordered (player, opponent): meetings, wins.
    pair_surface = defaultdict(lambda: [0, 0])
    latest_pair = {}
    columns = ["prior_matches", "prior_wins", "recent_win_rate", "recent_match_count", "opponent_prior_matches",
               "opponent_recent_win_rate", "prior_h2h_meetings", "prior_h2h_wins", "prior_h2h_last_won",
               "prior_surface_h2h_meetings", "prior_surface_h2h_wins"]
    values = np.full((len(p), len(columns)), np.nan)
    for _, block in p.groupby(["tourney_date", "round_order"], sort=False, dropna=False):
        for r in block.itertuples():
            a, b = r.player_id, r.opponent_id
            n, w = pairs[(a, b)]
            sn, sw = pair_surface[(a, b, r.surface)]
            values[r.Index] = [counts[a], wins[a], np.mean(recent[a]) if recent[a] else np.nan,
                               len(recent[a]), counts[b], np.mean(recent[b]) if recent[b] else np.nan,
                               n, w, latest_pair.get((a, b), np.nan), sn, sw]
        for r in block.itertuples():
            if not r.eligible:
                continue
            a, b = r.player_id, r.opponent_id
            counts[a] += 1
            wins[a] += r.won
            recent[a].append(r.won)
            pairs[(a, b)][0] += 1
            pairs[(a, b)][1] += r.won
            pair_surface[(a, b, r.surface)][0] += 1
            pair_surface[(a, b, r.surface)][1] += r.won
            latest_pair[(a, b)] = r.won
    p[columns] = values
    p["rank_gap"] = p["opponent_rank"] - p["player_rank"]
    p["log_rank_advantage"] = np.log(p["opponent_rank"] / p["player_rank"])
    p["age_difference"] = p["player_age"] - p["opponent_age"]
    p["log_experience_difference"] = np.log1p(p["prior_matches"]) - np.log1p(p["opponent_prior_matches"])
    p["recent_form_difference"] = p["recent_win_rate"] - p["opponent_recent_win_rate"]
    p["log_prior_h2h_meetings"] = np.log1p(p["prior_h2h_meetings"])
    p["h2h_smoothed_advantage"] = (2 * p["prior_h2h_wins"] - p["prior_h2h_meetings"]) / (p["prior_h2h_meetings"] + 2)
    p["surface_h2h_smoothed_advantage"] = (2 * p["prior_surface_h2h_wins"] - p["prior_surface_h2h_meetings"]) / (p["prior_surface_h2h_meetings"] + 2)
    # Smaller ID is Player A regardless of outcome: exactly one row per match for Q2.
    p["is_player_a"] = p["player_id"] < p["opponent_id"]
    p["pair_id"] = [f"{min(a,b)}:{max(a,b)}" for a,b in zip(p["player_id"], p["opponent_id"])]
    p.attrs["event_blocker_ledger"] = player_rows.attrs.get("event_blocker_ledger", [])
    return p


def build_recovery_events(players: pd.DataFrame, cfg: Config,
                          event_ledger: pd.DataFrame | None = None) -> pd.DataFrame:
    """Loss-level records with transparent censoring of incomplete follow-up.

    We inspect the next three *recorded* matches. We do not skip a retirement,
    an out-of-scope match, or an ambiguous event to make follow-up look complete.
    Completely absent source matches cannot be detected by this code.
    """
    ledger = event_ledger.copy() if event_ledger is not None else pd.DataFrame(players.attrs.get("event_blocker_ledger", []))
    p = players.copy()
    p.attrs = {}
    p["recovery_blocker"] = False
    p["blocker_reason"] = ""
    # Only source-agreed dates and rounds may occupy a particular sequence slot.
    # Each conflicting key appears once for each potentially affected player.
    if not ledger.empty:
        placeable = ledger.loc[ledger["placement_status"].eq("dated_round_resolved") &
                               ledger["player_id"].notna()].copy()
        if not placeable.empty:
            extra = pd.DataFrame({col: pd.Series(
                False if pd.api.types.is_bool_dtype(dtype) else
                pd.NaT if pd.api.types.is_datetime64_any_dtype(dtype) else
                np.nan if pd.api.types.is_numeric_dtype(dtype) else None,
                index=placeable.index,
                dtype=bool if pd.api.types.is_bool_dtype(dtype) else
                dtype if pd.api.types.is_datetime64_any_dtype(dtype) else
                float if pd.api.types.is_numeric_dtype(dtype) else object)
                for col, dtype in p.dtypes.items()})
            for col in ["match_id", "player_id", "tourney_id", "tourney_date", "round_order", "blocker_reason"]:
                extra[col] = placeable[col]
            extra["recovery_blocker"] = True
            extra["eligible"] = False
            extra["order_reliable"] = False
            extra["in_analysis_period"] = False
            p = pd.concat([p, extra], ignore_index=True)
    p = p.sort_values(["player_id", "tourney_date", "round_order", "tourney_id", "match_id"],
                      na_position="last").reset_index(drop=True)
    # Position includes resolved blockers; it is an ordinal, never a match date.
    p["recorded_event_position"] = p.groupby("player_id").cumcount()
    grouped = p.groupby("player_id", sort=False)
    for k in [1, 2, 3]:
        for col in ["match_id", "won", "eligible", "log_rank_advantage", "surface", "best_of", "order_reliable",
                    "tourney_date", "recovery_blocker", "blocker_reason", "recorded_event_position"]:
            p[f"next{k}_{col}"] = grouped[col].shift(-k)
    p["next1_unresolved_record"] = p["next1_recovery_blocker"].eq(True)
    p["followup_unresolved_record"] = p[[f"next{k}_recovery_blocker" for k in [1, 2, 3]]].eq(True).any(axis=1)
    p["followup_blocker_keys"] = ""
    if not ledger.empty:
        uncertain = ledger.loc[~ledger["placement_status"].eq("dated_round_resolved") & ledger["player_id"].notna()]
        # An unplaceable known-player event can lie between recorded candidates.
        # Bound conflicting-date claims where possible; missing-date uncertainty
        # conservatively affects all windows for that player in the loaded data.
        for blocker in uncertain.itertuples():
            focal = p["player_id"].eq(blocker.player_id)
            if pd.notna(blocker.earliest_claimed_date) and pd.notna(blocker.latest_claimed_date):
                after_index = p["tourney_date"].le(blocker.latest_claimed_date)
                next1_before = p["next1_tourney_date"].isna() | p["next1_tourney_date"].ge(blocker.earliest_claimed_date)
                next3_before = p["next3_tourney_date"].isna() | p["next3_tourney_date"].ge(blocker.earliest_claimed_date)
                affects_one = focal & after_index & next1_before
                affects_three = focal & after_index & next3_before
            else:
                affects_one = affects_three = focal
            p.loc[affects_one, "next1_unresolved_record"] = True
            p.loc[affects_three, "followup_unresolved_record"] = True
            p.loc[affects_three, "followup_blocker_keys"] += str(blocker.event_key) + ";"
        for k in [1, 2, 3]:
            mask = p[f"next{k}_recovery_blocker"].eq(True)
            p.loc[mask, "followup_blocker_keys"] += p.loc[mask, f"next{k}_match_id"].astype(str) + ";"
    ranked = p["player_rank"].notna() & p["opponent_rank"].notna()
    p["ranking_upset"] = (ranked & p["won"].eq(0) & p["player_rank"].le(cfg.upset_max_rank) & p["rank_gap"].ge(cfg.upset_rank_gap))
    p["loss_type"] = np.where(~ranked, "unknown_rank", np.where(p["ranking_upset"], "ranking_upset", "other_ranked_loss"))
    p["age_group"] = pd.cut(p["player_age"], [-np.inf, 23, 30, np.inf], right=False, labels=["under_23", "23_to_29", "30_plus"])
    p["experience_group"] = pd.cut(p["prior_matches"], [-1, 100, 300, np.inf], right=False, labels=["under_100", "100_to_299", "300_plus"])
    p["next1_usable"] = p["next1_eligible"].eq(True) & ~p["next1_unresolved_record"]
    p["next1_win"] = p["next1_won"].where(p["next1_usable"])
    all_three_present = p[[f"next{k}_match_id" for k in [1, 2, 3]]].notna().all(axis=1)
    all_three_eligible = p[[f"next{k}_eligible" for k in [1, 2, 3]]].eq(True).all(axis=1)
    p["followup_complete"] = all_three_present & all_three_eligible & ~p["followup_unresolved_record"]
    p["followup_status"] = np.select([p["followup_unresolved_record"], ~all_three_present, ~all_three_eligible],
                                      ["followup_contains_unresolved_record", "fewer_than_three_recorded_followups",
                                       "followup_contains_excluded_or_ambiguous_match"], default="complete")
    p["next3_win_rate"] = p[[f"next{k}_won" for k in [1, 2, 3]]].mean(axis=1, skipna=False).where(p["followup_complete"])
    p["followup_mean_log_rank_advantage"] = p[[f"next{k}_log_rank_advantage" for k in [1, 2, 3]]].mean(axis=1, skipna=False).where(p["followup_complete"])
    for label in ["Clay", "Grass", "Carpet", "Unknown"]:
        p[f"followup_{label.lower()}_share"] = (sum(p[f"next{k}_surface"].eq(label).astype(float) for k in [1, 2, 3]) / 3).where(p["followup_complete"])
    p["followup_best_of_5_share"] = (sum(p[f"next{k}_best_of"].eq(5).astype(float) for k in [1, 2, 3]) / 3).where(p["followup_complete"])
    # A study-period loss is an index event. Warm-up losses are not study events.
    return p.loc[p["won"].eq(0) & p["eligible"] & p["in_analysis_period"]].reset_index(drop=True)


def save_quality_tables(matches: pd.DataFrame, players: pd.DataFrame, output: Path) -> None:
    cols = [c for c in REQUIRED + ["w_svpt", "l_svpt"] if c in matches]
    missing = pd.DataFrame({"field": cols, "missing_count": [int(matches[c].isna().sum()) for c in cols],
                            "missing_percent": [float(matches[c].isna().mean() * 100) for c in cols]})
    missing.to_csv(output / "missing_values.csv", index=False)
    coverage = matches.groupby("season", dropna=False).agg(source_matches=("match_id", "size"), eligible_matches=("eligible", "sum"),
                       unknown_winner_hands=("winner_hand", lambda x: x.eq("U").sum()), unknown_loser_hands=("loser_hand", lambda x: x.eq("U").sum()))
    coverage.to_csv(output / "coverage_by_year.csv")
    pd.DataFrame({"flag": ["unknown_player_hand_rows", "missing_player_rank_rows", "invalid_or_missing_service_stat_rows"],
                  "count": [int(players["player_hand"].eq("U").sum()), int(players["player_rank"].isna().sum()), int((~players["valid_service_stats"]).sum())]}).to_csv(output / "player_row_quality.csv", index=False)


def run_project(cfg: Config | None = None, input_files: list[Path] | None = None) -> dict:
    """Build and verify a complete staged run, then replace the output directory.

    Previous runs remain in a sibling backup. A failed run cannot leave a new
    successful summary or a mixture of old and new generated tables.
    """
    import shutil
    import uuid
    from collections import Counter
    import warnings
    from tennis_repro import (code_provenance, environment, input_records, quality_extensions,
                              spot_checks, output_inventory, verify_output)
    cfg = cfg or Config()
    cfg.validate()
    output = Path(cfg.output_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    code = code_provenance()
    files = input_files if input_files is not None else download_data(cfg)
    files = [Path(f) for f in files]
    # Never replace a directory holding input files.
    if any(output.resolve() == f.resolve() or output.resolve() in f.resolve().parents for f in files):
        raise ValueError("Output directory must not contain an input file.")
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    backup = output.with_name(f".{output.name}.previous-{run_id}")
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            raw = load_files(files)
            LOG.info("Loaded %s raw match rows from %s file(s).", len(raw), len(files))
            matches, duplicates, audit = clean_matches(raw, cfg)
            players = add_history(make_player_rows(matches), cfg)
            events = build_recovery_events(players, cfg, event_ledger=build_event_ledger(matches))
            matches.to_csv(stage / "matches_audited.csv.gz", index=False)
            duplicates.to_csv(stage / "exact_duplicate_rows.csv", index=False)
            matches.loc[~matches["eligible"]].to_csv(stage / "excluded_matches.csv.gz", index=False)
            if "build_event_ledger" in globals():
                build_event_ledger(matches).to_csv(stage / "unresolved_event_ledger.csv", index=False)
            study_players = players.loc[players["in_analysis_period"]].copy()
            study_players.to_csv(stage / "player_match_features.csv.gz", index=False)
            events.to_csv(stage / "q1_recovery_events.csv.gz", index=False)
            save_quality_tables(matches, players, stage)
            from tennis_analyses import analyze_recovery, analyze_head_to_head, analyze_handedness, make_charts
            q1 = analyze_recovery(events, cfg, stage)
            q2 = analyze_head_to_head(study_players, cfg, stage)
            q3 = analyze_handedness(study_players, cfg, stage)
            if cfg.make_plots:
                make_charts(stage)
            quality = quality_extensions(raw, matches, players, events, cfg, stage, {'q1':q1,'q2':q2,'q3':q3})
            from tennis_chronology import write_chronology_diagnostics
            chronology = write_chronology_diagnostics(matches, cfg, stage)
            checks = spot_checks(matches, players, events, stage)
        warning_counts = Counter((w.category.__name__, str(w.message)) for w in captured)
        run_warnings = [{"category":c,"message":m,"count":n} for (c,m),n in warning_counts.items()]
        for name, result in [('q1', q1), ('q2', q2), ('q3', q3)]:
            result.setdefault('warnings', [])
            result.setdefault('status_code', 'fitted_with_limitations' if 'fitted' in result['status'] and 'not fitted' not in result['status'] else 'insufficient_or_unavailable')
        audit.update({"run_id":run_id,"started_at_utc":started.isoformat(),
                      "completed_at_utc":datetime.now(timezone.utc).isoformat(),
                      "publication_status":"verified", "configuration":asdict(cfg),
                      "source_repository":REPOSITORY,"source_revision":REVISION,
                      "inputs":input_records(files),"cache_inventory_is_separate":True,
                      "input_mode":"provided_local_files" if input_files is not None else "pinned_download_or_cached_files",
                      "test_data_warning":"Provided files may be partial or synthetic; not full-study findings." if input_files is not None else None,
                      "q1":q1,"q2":q2,"q3":q3,"quality":quality,"chronology":chronology,"spot_checks":checks,
                      "runtime":environment(),"code":code,"runtime_warnings":run_warnings})
        warning_text = [f"{q.upper()}: {w}" for q in ['q1','q2','q3'] for w in audit[q]['warnings']]
        lines = ["# Run summary", "", f"Run ID: `{run_id}`", "",
                 f"Raw match rows: {audit['raw_match_rows']:,}",
                 f"Eligible study matches: {audit['eligible_analysis_matches']:,}", "",
                 "Q1: " + q1["status"], "Q2: " + q2["status"], "Q3: " + q3["status"], "", *warning_text, "",
                 "Observational associations, not causal or psychological conclusions.",
                 "See generated reports, configuration, input/code hashes, and output inventory in run_summary.json."]
        (stage / "RUN_SUMMARY.md").write_text("\n".join(lines),encoding="utf-8")
        audit['output_inventory'] = output_inventory(stage)
        audit['inventory_note'] = 'Hashes cover generated artifacts except this self-referential JSON summary; unrelated preserved user files are not run artifacts.'
        write_json(stage / 'run_summary.json', audit)
        verify_output(stage, audit)
        # Preserve unrelated user files. Known results from older runs are retired.
        if output.exists():
            previous_inventory = set()
            prior = output / 'run_summary.json'
            if prior.exists():
                previous_inventory = {r['path'] for r in json.loads(prior.read_text()).get('output_inventory', [])}
            known = {'run_summary.json','RUN_SUMMARY.md','matches_audited.csv.gz','exact_duplicate_rows.csv',
                     'excluded_matches.csv.gz','player_match_features.csv.gz','missing_values.csv',
                     'coverage_by_year.csv','player_row_quality.csv'}
            for old in output.rglob('*'):
                relative = old.relative_to(output)
                generated = (str(relative) in previous_inventory or str(relative) in known or
                             old.name.startswith(('q1_', 'q2_', 'q3_')) or relative.parts[0]=='charts')
                target = stage / relative
                if old.is_file() and not generated and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(old, target)
            output.rename(backup)
        try:
            stage.rename(output)
        except BaseException:
            if backup.exists() and not output.exists(): backup.rename(output)
            raise
        LOG.info("Verified run %s saved in %s", run_id, output.resolve())
        return audit
    except BaseException:
        # Keep failed-stage evidence separate and explicitly unsuccessful.
        if stage.exists():
            write_json(stage / 'FAILED_RUN.json', {'run_id':run_id,'status':'failed','output_target':str(output)})
            (stage / 'run_summary.json').unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--history-start", type=int, default=1990)
    parser.add_argument("--analysis-start", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--test-start", type=int, default=2020)
    parser.add_argument("--upset-max-rank", type=int, default=50)
    parser.add_argument("--upset-rank-gap", type=int, default=30)
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--demo", action="store_true", help="Run the bundled 31-match real-data fixture, not the full study.")
    args = parser.parse_args()
    demo, no_plots = args.demo, args.no_plots
    del args.demo, args.no_plots
    cfg = Config(**vars(args), make_plots=not no_plots)
    files = None
    if demo:
        cfg.history_start = cfg.analysis_start = cfg.end_year = 2024
        cfg.output_dir = "demo_outputs" if cfg.output_dir == "outputs" else cfg.output_dir
        files = [Path(__file__).parent / "tests" / "fixtures" / "brisbane_2024_excerpt.csv"]
    try:
        run_project(cfg, files)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        LOG.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
