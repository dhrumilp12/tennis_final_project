"""Supplemental report/notebook integrity; fixtures are software tests only."""
import json
from pathlib import Path

import nbformat
import pytest

from tennis_reporting import (
    SUPPLEMENTAL_CELL_ID, canonical_cell_hash, findings, generate_reports,
    supplemental_validation, update_supplemental_notebook,
)
from tennis_repro import sha256, verify_output


def fixture_bundle(root, output, summary, notebook=False, q3=False):
    folder = root / 'validation' / ('q3_comparability' if q3 else 'q1_q2_checks')
    folder.mkdir(parents=True)
    (folder/'REPORT.md').write_text('Software test prose only. [Evidence](summary.json).\n')
    (folder/'summary.json').write_text('{"software_test_only": true}\n')
    if not q3:
        (folder/'README_FINDINGS.md').write_text(
            'Software test direct post-upset and dyadic summaries. [Evidence](summary.json).\n')
    historical_cells = None
    if notebook:
        original = nbformat.v4.new_notebook(cells=[
            nbformat.v4.new_markdown_cell('Historical software test note.'),
            nbformat.v4.new_code_cell('1 + 1', execution_count=1, outputs=[
                nbformat.v4.new_output('execute_result', data={'text/plain': '2'}, execution_count=1)])])
        nbformat.write(original, root/'Tennis_Project.ipynb')
        stored = json.loads((root/'Tennis_Project.ipynb').read_text())
        historical_cells = stored['cells']
        digest = sha256(root/'Tennis_Project.ipynb')
        (folder/'baseline.json').write_text(json.dumps({'notebook_sha256': digest}))
        (folder/'historical_notebook_cells.json').write_text(json.dumps({
            'source_notebook_sha256': digest,
            'historical_cell_count': len(historical_cells),
            'canonical_cell_hashes': [canonical_cell_hash(c) for c in historical_cells]}))
    manifest = dict(
        validation_id='software-test-q3' if q3 else 'software-test-q1-q2',
        source_run_id=summary['run_id'],
        source_run_summary_sha256=sha256(output/'run_summary.json'),
        artifacts={p.name: sha256(p) for p in folder.iterdir() if p.is_file()},
        code_hashes={'tennis_reporting.py': sha256('tennis_reporting.py')})
    (folder/'manifest.json').write_text(json.dumps(manifest))
    return folder, manifest, historical_cells


def dummy_source(root):
    output = root/'source'
    output.mkdir()
    summary = {'run_id': 'software-test-source'}
    (output/'run_summary.json').write_text(json.dumps(summary))
    return output, summary


def test_absent_supplement_has_no_effect(tmp_path):
    assert supplemental_validation(tmp_path, tmp_path, {}) == ('', None, '')
    update_supplemental_notebook(tmp_path, tmp_path, {})
    assert not (tmp_path/'Tennis_Project.ipynb').exists()


@pytest.mark.parametrize('change', ['run_id', 'source_hash', 'readme_content', 'missing_readme'])
def test_supplement_rejects_unverified_evidence(tmp_path, change):
    output, summary = dummy_source(tmp_path)
    folder, manifest, _ = fixture_bundle(tmp_path, output, summary)
    if change == 'run_id':
        manifest['source_run_id'] = 'wrong'
    elif change == 'source_hash':
        manifest['source_run_summary_sha256'] = '0' * 64
    elif change == 'readme_content':
        (folder/'README_FINDINGS.md').write_text('Changed unverified prose.')
    else:
        del manifest['artifacts']['README_FINDINGS.md']
    (folder/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Q1/Q2 supplemental'):
        supplemental_validation(output, tmp_path, summary)


@pytest.mark.parametrize('prose', [
    'Software fixture: Q1 +2.50 pp; Q2 -0.003 improvement. Directions disagree.',
    'Software fixture: Q1 -1.25 pp; Q2 +0.002 improvement with an interval spanning zero.',
    'Software fixture: point estimate +0.001; inference unavailable because variance is nonpositive.',
])
def test_report_layer_keeps_verified_values_directions_and_unavailable_inference(tmp_path, prose):
    output, summary = dummy_source(tmp_path)
    folder, manifest, _ = fixture_bundle(tmp_path, output, summary)
    (folder/'REPORT.md').write_text(prose)
    (folder/'README_FINDINGS.md').write_text(prose)
    for name in ['REPORT.md', 'README_FINDINGS.md']:
        manifest['artifacts'][name] = sha256(folder/name)
    (folder/'manifest.json').write_text(json.dumps(manifest))
    section, _, brief = supplemental_validation(output, tmp_path, summary)
    assert prose in section and brief == prose
    assert 'no clear difference' not in section


def test_notebook_append_is_markdown_only_preserves_cells_and_is_idempotent(tmp_path):
    output, summary = dummy_source(tmp_path)
    _, _, historical = fixture_bundle(tmp_path, output, summary, notebook=True)
    update_supplemental_notebook(output, tmp_path, summary)
    path = tmp_path/'Tennis_Project.ipynb'
    first = path.read_bytes()
    actual = json.loads(first)
    assert actual['cells'][:-1] == historical
    assert actual['cells'][-1]['cell_type'] == 'markdown'
    assert actual['cells'][-1]['id'] == SUPPLEMENTAL_CELL_ID
    assert 'validation/q1_q2_checks/summary.json' in ''.join(actual['cells'][-1]['source'])
    assert len([c for c in actual['cells'] if c['cell_type'] == 'code']) == 1
    nbformat.validate(nbformat.read(path, as_version=4))
    update_supplemental_notebook(output, tmp_path, summary)
    assert path.read_bytes() == first


def test_notebook_refuses_modified_historical_cells(tmp_path):
    output, summary = dummy_source(tmp_path)
    fixture_bundle(tmp_path, output, summary, notebook=True)
    path = tmp_path/'Tennis_Project.ipynb'
    content = json.loads(path.read_text())
    content['cells'][1]['outputs'][0]['data']['text/plain'] = ['3']
    path.write_text(json.dumps(content))
    before = path.read_bytes()
    with pytest.raises(ValueError, match='Historical notebook cells changed'):
        update_supplemental_notebook(output, tmp_path, summary)
    assert path.read_bytes() == before


def test_notebook_refuses_to_replace_supplemental_code_cell(tmp_path):
    output, summary = dummy_source(tmp_path)
    fixture_bundle(tmp_path, output, summary, notebook=True)
    path = tmp_path/'Tennis_Project.ipynb'
    content = json.loads(path.read_text())
    content['cells'].append(dict(nbformat.v4.new_code_cell('raise RuntimeError()', id=SUPPLEMENTAL_CELL_ID)))
    path.write_text(json.dumps(content))
    with pytest.raises(ValueError, match='must remain Markdown'):
        update_supplemental_notebook(output, tmp_path, summary)


def test_regeneration_preserves_both_validation_claims_and_historical_results(tmp_path):
    output = Path('outputs_final')
    if not (output/'run_summary.json').exists():
        pytest.skip('Saved research run absent; synthetic integrity checks still run.')
    summary = verify_output(output)
    _, original_answers = findings(output)
    protected = {str(p): sha256(p) for p in output.rglob('*') if p.is_file()}
    fixture_bundle(tmp_path, output, summary, q3=True)
    _, _, historical = fixture_bundle(tmp_path, output, summary, notebook=True)
    (tmp_path/'README.md').write_text('Before\n<!-- GENERATED_FINDINGS_START -->\nold\n<!-- GENERATED_FINDINGS_END -->\nAfter\n')
    generate_reports(output, tmp_path)
    first = {str(p.relative_to(tmp_path)): sha256(p) for p in tmp_path.rglob('*') if p.is_file()}
    generate_reports(output, tmp_path)
    assert {str(p.relative_to(tmp_path)): sha256(p) for p in tmp_path.rglob('*') if p.is_file()} == first
    for name in ['RESULTS.md', 'FINAL_REPORT.md']:
        text = (tmp_path/'reports'/name).read_text()
        assert text.count('### Supplemental Q1/Q2 validation') == 1
        assert text.count('### Opponent comparability') == 1
        assert text.count('**Historical primary analysis.**') == 2
    for name in ['report_claims.json', 'report_manifest.json']:
        record = json.loads((tmp_path/'reports'/name).read_text())
        assert set(record['separate_validations']) == {'q3_comparability', 'q1_q2_checks'}
    claims = json.loads((tmp_path/'reports'/'report_claims.json').read_text())
    assert claims['answers'] == original_answers
    readme = (tmp_path/'README.md').read_text()
    assert '**Historical primary analysis.**' in readme
    assert readme.count('**Supplemental Q1/Q2 validation.**') == 1
    assert '[Evidence](validation/q1_q2_checks/summary.json)' in readme
    assert readme.startswith('Before\n') and readme.endswith('After\n')
    notebook = json.loads((tmp_path/'Tennis_Project.ipynb').read_text())
    assert notebook['cells'][:-1] == historical
    assert {path: sha256(path) for path in protected} == protected
