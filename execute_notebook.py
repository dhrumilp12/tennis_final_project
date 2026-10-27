"""Execute the existing notebook in a fresh kernel from this Python environment."""
from pathlib import Path
import json
import hashlib
import os
import sys
import tempfile
import time
import nbformat
from nbclient import NotebookClient


def main():
    root = Path(__file__).resolve().parent
    notebook = root / 'Tennis_Project.ipynb'
    nb = nbformat.read(notebook, as_version=4)
    # Clear old output before execution. Never manufacture execution counts.
    for cell in nb.cells:
        if cell.cell_type == 'code':
            cell.outputs = []
            cell.execution_count = None
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='tennis-jupyter-') as temporary:
        temp = Path(temporary)
        kernel = temp / 'kernels' / 'tennis-project'
        kernel.mkdir(parents=True)
        (kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'], 'display_name':'Tennis project verification', 'language':'python'}))
        old = {k:os.environ.get(k) for k in ['JUPYTER_PATH','JUPYTER_CONFIG_DIR','JUPYTER_RUNTIME_DIR','IPYTHONDIR']}
        os.environ['JUPYTER_PATH'] = str(temp) + (os.pathsep+old['JUPYTER_PATH'] if old['JUPYTER_PATH'] else '')
        for key, name in [('JUPYTER_CONFIG_DIR','config'),('JUPYTER_RUNTIME_DIR','runtime'),('IPYTHONDIR','ipython')]:
            (temp/name).mkdir();os.environ[key]=str(temp/name)
        try:
            client=NotebookClient(nb, timeout=900, kernel_name='tennis-project',resources={'metadata':{'path':str(root)}})
            client.execute()
        except BaseException:
            nbformat.write(nb,root/'validation'/'notebook_failed.ipynb')
            raise
        finally:
            for key,value in old.items():
                if value is None: os.environ.pop(key,None)
                else: os.environ[key]=value
    errors=[o for c in nb.cells if c.cell_type=='code' for o in c.outputs if o.output_type=='error']
    if errors: raise RuntimeError(f'{len(errors)} notebook execution errors')
    # Restore portable kernel metadata, while retaining actual executed outputs.
    nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
    temp_notebook=notebook.with_suffix('.executed.tmp.ipynb')
    nbformat.write(nb,temp_notebook);temp_notebook.replace(notebook)
    summary=json.loads((root/'outputs_final'/'run_summary.json').read_text())
    record={'run_id':summary['run_id'],'python_executable':sys.executable,'fresh_kernel':True,
            'notebook':notebook.name,'code_cells':sum(c.cell_type=='code' for c in nb.cells),
            'executed_code_cells':sum(c.cell_type=='code' and c.execution_count is not None for c in nb.cells),
            'execution_errors':len(errors),'elapsed_seconds':time.monotonic()-started,
            'notebook_sha256':hashlib.sha256(notebook.read_bytes()).hexdigest()}
    (root/'validation').mkdir(exist_ok=True)
    (root/'validation'/'notebook_execution.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record,indent=2))


if __name__=='__main__': main()
