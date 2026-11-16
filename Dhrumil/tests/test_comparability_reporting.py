"""Reporting provenance checks; temporary prose is explicitly software test data."""
import json
from pathlib import Path

import pytest

from tennis_reporting import comparability_validation, generate_reports
from tennis_repro import sha256, verify_output


def validation_fixture(root, output, summary):
    folder = root / 'validation' / 'q3_comparability'
    folder.mkdir(parents=True)
    (folder / 'summary.json').write_text('{"software_test_only": true}\n')
    (folder / 'REPORT.md').write_text(
        'Software test evidence, not research findings. [Summary](summary.json).\n')
    manifest = dict(
        source_run_id=summary['run_id'], validation_id='software-test-validation',
        source_run_summary_sha256=sha256(output / 'run_summary.json'),
        artifacts={p.name: sha256(p) for p in folder.iterdir()},
        code_hashes={'tennis_reporting.py': sha256('tennis_reporting.py')})
    (folder / 'manifest.json').write_text(json.dumps(manifest))
    return folder, manifest


def test_absent_comparability_validation_has_no_section(tmp_path):
    assert comparability_validation(tmp_path, tmp_path, {'run_id': 'test'}) == ('', None)


@pytest.mark.parametrize('change', ['source_id', 'source_hash', 'artifact', 'missing_artifact', 'escape'])
def test_comparability_rejects_wrong_source_or_unverified_evidence(tmp_path, change):
    output = tmp_path / 'source'
    output.mkdir()
    summary = {'run_id': 'test-source'}
    (output / 'run_summary.json').write_text(json.dumps(summary))
    folder, manifest = validation_fixture(tmp_path, output, summary)
    if change == 'source_id':
        manifest['source_run_id'] = 'different-source'
    elif change == 'source_hash':
        manifest['source_run_summary_sha256'] = '0' * 64
    elif change == 'artifact':
        (folder / 'REPORT.md').write_text('Unverified changed finding.\n')
    elif change == 'missing_artifact':
        del manifest['artifacts']['summary.json']
    else:
        manifest['artifacts']['../../outside.txt'] = '0' * 64
    (folder / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Q3 comparability'):
        comparability_validation(output, tmp_path, summary)


@pytest.mark.parametrize('destination', ['missing.csv', 'unlisted.csv'])
def test_comparability_rejects_broken_or_uninventoried_report_links(tmp_path, destination):
    output = tmp_path / 'source'
    output.mkdir()
    summary = {'run_id': 'test-source'}
    (output / 'run_summary.json').write_text(json.dumps(summary))
    folder, manifest = validation_fixture(tmp_path, output, summary)
    if destination == 'unlisted.csv':
        (folder / destination).write_text('test data\n')
    (folder / 'REPORT.md').write_text(f'[Evidence]({destination})\n')
    manifest['artifacts']['REPORT.md'] = sha256(folder / 'REPORT.md')
    (folder / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Q3 comparability report link'):
        comparability_validation(output, tmp_path, summary)


def test_comparability_regeneration_is_separate_idempotent_and_linked(tmp_path):
    output = Path('outputs_final')
    if not (output / 'run_summary.json').exists():
        pytest.skip('Saved research run unavailable; provenance unit tests still run.')
    summary = verify_output(output)
    original = {str(p): sha256(p) for p in output.rglob('*') if p.is_file()}
    folder, manifest = validation_fixture(tmp_path, output, summary)
    generate_reports(output, tmp_path)
    hashes = {p.name: sha256(p) for p in (tmp_path / 'reports').iterdir()}
    generate_reports(output, tmp_path)
    assert {p.name: sha256(p) for p in (tmp_path / 'reports').iterdir()} == hashes
    for name in ['RESULTS.md', 'FINAL_REPORT.md']:
        report = (tmp_path / 'reports' / name).read_text()
        assert report.count('### Opponent comparability') == 1
        assert 'Software test evidence, not research findings.' in report
        assert '**Primary analysis.**' in report
        assert '[Summary](../validation/q3_comparability/summary.json)' in report
        assert 'separately labeled opponent-comparability validation was produced later' in report
    for name in ['report_claims.json', 'report_manifest.json']:
        record = json.loads((tmp_path / 'reports' / name).read_text())
        ref = record['separate_validations']['q3_comparability']
        assert ref['source_run_id'] == summary['run_id']
        assert ref['validation_id'] == manifest['validation_id']
        assert ref['manifest_sha256'] == sha256(folder / 'manifest.json')
    assert {name: sha256(name) for name in original} == original
