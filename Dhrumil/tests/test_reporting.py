"""Checks of numerical provenance, without downloading research inputs."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from tennis_reporting import findings, generate_reports, interval, direction
from tennis_repro import verify_output, sha256


def test_intervals_preserve_unavailable_uncertainty():
    row = pd.Series({'estimate_pp':1.2,'ci95_lower_pp':np.nan,'ci95_upper_pp':np.nan})
    assert 'unavailable' in interval(row)
    assert direction(row) == 'inference is unavailable'


def test_interval_direction_is_data_driven():
    assert direction(pd.Series({'ci95_lower_pp':-2.,'ci95_upper_pp':1.})) == 'the interval includes zero'
    assert direction(pd.Series({'ci95_lower_pp':-2.,'ci95_upper_pp':-.1})) == 'the interval is below zero'


def final_output():
    output = Path('outputs_final')
    if not (output/'run_summary.json').exists():
        pytest.skip('Authoritative full study not present; offline unit/fixture tests still run.')
    return output


def test_final_reports_numerical_claims_and_run_id_match_generated_outputs():
    output=final_output(); summary=verify_output(output)
    claims=json.loads(Path('reports/report_claims.json').read_text())
    assert claims['run_id']==summary['run_id']
    for name, records in claims['tables'].items():
        actual=pd.read_csv(output/f'{name}.csv')
        reported=pd.DataFrame(records)
        pd.testing.assert_frame_equal(actual,reported,check_dtype=False,atol=1e-8,rtol=1e-8)
    for name in ['RESULTS.md','FINAL_REPORT.md','DATA_QUALITY.md']:
        assert summary['run_id'] in (Path('reports')/name).read_text()
    assert summary['run_id'] in Path('README.md').read_text()
    manifest=json.loads(Path('reports/report_manifest.json').read_text())
    assert manifest['outputs_summary_sha256']==sha256(output/'run_summary.json')
    for name,digest in manifest['files'].items(): assert sha256(Path('reports')/name)==digest


def test_final_contrasts_use_full_covariance_and_physical_counts():
    output=final_output(); summary=verify_output(output)
    covariance=pd.read_csv(output/'q3_adjusted_covariance.csv',index_col=0)
    coef=pd.read_csv(output/'q3_adjusted_coefficients.csv').set_index('term')
    contrasts=pd.read_csv(output/'q3_adjusted_contrasts.csv').set_index('player_hand')
    for hand in ['R','L']:
        names=['opponent_left']+(['opponent_left_x_player_left'] if hand=='L' else [])
        assert contrasts.loc[hand,'difference_pp']==pytest.approx(100*coef.loc[names,'coefficient'].sum())
        assert contrasts.loc[hand,'standard_error_pp']==pytest.approx(100*np.sqrt(covariance.loc[names,names].to_numpy().sum()))
    matches=pd.read_csv(output/'matches_audited.csv.gz',usecols=['match_id','eligible','in_analysis_period'])
    assert matches.loc[matches.eligible & matches.in_analysis_period,'match_id'].nunique()==summary['eligible_analysis_matches']


def test_final_nonoverlapping_windows_reuse_no_match_per_player():
    output=final_output()
    windows=pd.read_csv(output/'q1_model_windows.csv.gz')
    for (_,_,_),g in windows.loc[windows['sample'].eq('nonoverlapping')].groupby(['sample','outcome','player_id']):
        ids=g[['match_id','next1_match_id','next2_match_id','next3_match_id']].to_numpy().ravel()
        ids=[x for x in ids if pd.notna(x)]
        assert len(ids)==len(set(ids))


def test_final_notebook_executed_same_run_and_source_hashes_match():
    output=final_output();summary=verify_output(output)
    notebook=json.loads(Path('Tennis_Project.ipynb').read_text())
    cells=[c for c in notebook['cells'] if c['cell_type']=='code']
    assert all(c['execution_count'] is not None for c in cells)
    assert not any(o.get('output_type')=='error' for c in cells for o in c.get('outputs',[]))
    evidence=json.loads(Path('validation/notebook_execution.json').read_text())
    assert evidence['run_id']==summary['run_id']
    assert evidence['execution_errors']==0 and evidence['fresh_kernel']
    assert evidence['executed_code_cells']==len(cells)
    # The saved notebook is an execution artifact, not newly manufactured output.
    assert sha256('Tennis_Project.ipynb') == evidence['notebook_sha256']
    source_hashes = summary['code']['source_hashes']
    changed = {name for name, digest in source_hashes.items() if sha256(name) != digest}
    if changed:
        # Reporting-only maintenance can follow an analysis without pretending
        # that the new prose generator executed that historical run. All other
        # executable analysis sources and requirements remain hash-identical.
        assert changed == {'tennis_reporting.py'}
        cleanup = json.loads(Path('validation/cleanup_verification.json').read_text())
        assert cleanup['analysis_run_id'] == summary['run_id']
        revision = cleanup['historical_source_revision']
        assert len(revision) == 40 and set(revision) <= set('0123456789abcdef')
        declared = cleanup['reporting_only_source_changes']
        assert set(declared) == changed
        for name, hashes in declared.items():
            assert hashes['analysis_sha256'] == source_hashes[name]
            assert hashes['cleanup_sha256'] == sha256(name)
        protected = cleanup['authoritative_outputs_sha256']
        expected = {str(output / r['path']) for r in summary['output_inventory']}
        expected.add(str(output / 'run_summary.json'))
        assert set(protected) == expected
        for name, digest in protected.items():
            assert sha256(name) == digest
        assert cleanup['preserved_notebook_sha256'] == evidence['notebook_sha256']
    for name, digest in source_hashes.items():
        if name not in changed:
            assert sha256(name) == digest


def test_demo_report_labels_inference_unavailable_instead_of_inventing_results(tmp_path):
    from tennis_project import Config,run_project
    output=tmp_path/'demo'
    cfg=Config(output_dir=str(output),history_start=2024,analysis_start=2024,end_year=2024,make_plots=False)
    run_project(cfg,[Path('tests/fixtures/brisbane_2024_excerpt.csv')])
    summary,answers=generate_reports(output,tmp_path)
    text=(tmp_path/'reports'/'FINAL_REPORT.md').read_text()
    assert summary['run_id'] in text
    assert 'incomplete research report' in text
    assert 'insufficient' in text
