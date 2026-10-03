"""Execute the submission notebook and persist real cell outputs."""
from pathlib import Path
import nbformat
from nbclient import NotebookClient
import time

path = Path('project_starter.ipynb')
notebook = nbformat.read(path, as_version=4)
client = NotebookClient(notebook, timeout=900, kernel_name='python3',
                        resources={'metadata': {'path': str(path.resolve().parent)}})

def save():
    temporary = path.with_suffix('.executing.tmp')
    for attempt in range(5):
        try:
            temporary.write_text(nbformat.writes(notebook), encoding='utf-8')
            temporary.replace(path)
            return
        except OSError:
            if attempt == 4:
                raise
            time.sleep(1)

try:
    with client.setup_kernel():
        for index, cell in enumerate(notebook.cells):
            if cell.cell_type == 'code':
                print(f'Executing cell {index + 1}...', flush=True)
                client.execute_cell(cell, index)
                save()
                print(f'Cell {index + 1}: complete ({len(cell.outputs)} outputs)', flush=True)
finally:
    save()

cells = [cell for cell in notebook.cells if cell.cell_type == 'code']
assert all(cell.execution_count is not None and cell.outputs for cell in cells)
assert not any(output.output_type == 'error' for cell in cells for output in cell.outputs)
print(f'Verified {len(cells)} executed code cells with visible outputs and no errors.')
