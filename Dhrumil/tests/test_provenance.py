"""Mocked cache transactions and staged-run integrity; no network downloads."""
import json
from pathlib import Path
import pytest
import requests
from tennis_project import Config, REVISION, download_data, write_json, run_project


def fake_network(monkeypatch, fail_year=None):
    calls = []
    body = Path('tests/fixtures/brisbane_2024_excerpt.csv').read_bytes()
    class Response:
        def __init__(self, content): self.content = content
        def raise_for_status(self): pass
    def get(self, url, timeout):
        calls.append(url)
        if fail_year and url.endswith(f'{fail_year}.csv'):
            raise requests.ConnectionError('SYNTHETIC interruption')
        return Response(body if url.endswith('.csv') else b'MOCK DOCUMENT')
    monkeypatch.setattr(requests.Session, 'get', get)
    return calls


def inventory(raw):
    return {r['filename']: r for r in json.loads((raw / REVISION / 'manifest.json').read_text())['files']}


def test_subset_preserves_inventory_retrieval_and_full_reuse(tmp_path, monkeypatch):
    calls = fake_network(monkeypatch)
    cfg = Config(raw_dir=str(tmp_path), history_start=2023, analysis_start=2023, end_year=2024)
    assert len(download_data(cfg)) == 2
    first = inventory(tmp_path)
    cfg.history_start = cfg.analysis_start = 2024
    assert len(download_data(cfg)) == 1  # Actual run inputs separate from cache inventory.
    assert inventory(tmp_path)['atp_matches_2023.csv'] == first['atp_matches_2023.csv']
    cfg.history_start = cfg.analysis_start = 2023
    cfg.offline = True
    assert len(download_data(cfg)) == 2
    for year in (2023, 2024):
        after = inventory(tmp_path)[f'atp_matches_{year}.csv']
        assert after['origin'] == 'downloaded_pinned_url'
        assert after['retrieved_at_utc'] == first[f'atp_matches_{year}.csv']['retrieved_at_utc']
        assert after['sha256'] == first[f'atp_matches_{year}.csv']['sha256']
    assert len(calls) == 6


def test_interrupted_download_retains_prior_inventory_and_completed_new_files(tmp_path, monkeypatch):
    fake_network(monkeypatch)
    cfg = Config(raw_dir=str(tmp_path), history_start=2023, analysis_start=2023, end_year=2024)
    download_data(cfg)
    before = inventory(tmp_path)
    fake_network(monkeypatch, fail_year=2026)
    cfg.history_start = cfg.analysis_start = 2025
    cfg.end_year = 2026
    with pytest.raises(RuntimeError, match='No missing year'):
        download_data(cfg)
    after = inventory(tmp_path)
    assert after['atp_matches_2023.csv'] == before['atp_matches_2023.csv']
    assert after['atp_matches_2025.csv']['origin'] == 'downloaded_pinned_url'
    assert 'atp_matches_2026.csv' not in after
    cfg.history_start = cfg.analysis_start = 2023
    cfg.end_year = 2025
    cfg.offline = True
    assert len(download_data(cfg)) == 3
    assert all(inventory(tmp_path)[f'atp_matches_{y}.csv']['origin'] == 'downloaded_pinned_url' for y in (2023, 2024, 2025))


def test_failed_atomic_manifest_replace_keeps_valid_original(tmp_path, monkeypatch):
    import tennis_project
    target = tmp_path / 'manifest.json'
    write_json(target, {'files': ['original']})
    def fail(*args): raise OSError('SYNTHETIC disk failure')
    monkeypatch.setattr(tennis_project.os, 'replace', fail)
    with pytest.raises(OSError, match='disk failure'):
        write_json(target, {'files': ['new']})
    assert json.loads(target.read_text()) == {'files': ['original']}
    assert not list(tmp_path.glob('.*.tmp'))


def test_invalid_json_never_replaces_previous_manifest(tmp_path):
    target = tmp_path / 'manifest.json'
    write_json(target, {'value': None})
    with pytest.raises(ValueError): write_json(target, {'value': float('nan')})
    assert json.loads(target.read_text()) == {'value': None}


def test_failed_run_retains_verified_directory_and_user_files(tmp_path, monkeypatch):
    import tennis_analyses
    output = tmp_path / 'results'
    cfg = Config(output_dir=str(output), history_start=2024, analysis_start=2024, end_year=2024, make_plots=False)
    fixture = [Path('tests/fixtures/brisbane_2024_excerpt.csv')]
    original = run_project(cfg, fixture)
    (output / 'team_notes.txt').write_text('keep this user file')
    old_summary = (output / 'run_summary.json').read_bytes()
    def fail(*args): raise RuntimeError('SYNTHETIC analysis failure')
    monkeypatch.setattr(tennis_analyses, 'analyze_head_to_head', fail)
    with pytest.raises(RuntimeError, match='analysis failure'): run_project(cfg, fixture)
    assert (output / 'run_summary.json').read_bytes() == old_summary
    assert (output / 'team_notes.txt').read_text() == 'keep this user file'
    failed = list(tmp_path.glob('.results.staging-*/FAILED_RUN.json'))
    assert len(failed) == 1
    assert not (failed[0].parent / 'run_summary.json').exists()


def test_successful_rerun_preserves_unrelated_user_file(tmp_path):
    output = tmp_path / 'results'
    output.mkdir()
    (output / 'team_notes.txt').write_text('keep this user file')
    cfg = Config(output_dir=str(output), history_start=2024, analysis_start=2024, end_year=2024, make_plots=False)
    run_project(cfg, [Path('tests/fixtures/brisbane_2024_excerpt.csv')])
    assert (output / 'team_notes.txt').read_text() == 'keep this user file'
    from tennis_repro import verify_output
    verify_output(output)
