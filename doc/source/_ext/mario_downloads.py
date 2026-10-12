"""Produce clean, source-attributed notebook downloads without cached data."""
from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import urljoin

DOCS = 'https://mario-suite.readthedocs.io/en/latest/'


def clean_notebook(path, srcdir):
    path, srcdir = Path(path), Path(srcdir)
    notebook = deepcopy(json.loads(path.read_text(encoding='utf-8')))
    docname = path.relative_to(srcdir).with_suffix('').as_posix()
    guide = DOCS + docname + '.html'
    licences = json.loads((srcdir / '_static/data/database_licences.json').read_text())
    catalogue = json.loads((srcdir / '_static/data/database_profiles.json').read_text())
    ids = [g['id'] for g in catalogue['guides'] if g['doc'] == docname]
    notices = [n for key in ids for n in licences['guides'].get(key, [])]
    note = ['### Running this notebook\n',
            f'Guide: [{guide}]({guide}). Install MARIO, then set the example paths to your own files.\n\n',
            'This download contains code and explanations. Cached results, execution history and machine-specific paths have been removed. Download any linked example files before running the corresponding cells.\n\n',
            'The example code is distributed with MARIO under [GPL-3.0](https://github.com/it-is-me-mario/MARIO/blob/main/LICENSE). Source databases keep their own licences; access through a parser does not grant redistribution rights.\n']
    if notices:
        note.append('\n**Source data terms**\n\n')
        for n in notices:
            title = f"[{n['label']}]({n['url']})" if n.get('url') else n['label']
            note.append(f"- {n.get('scope', 'Source')}: {title}. {n['note']}\n")
    else:
        note.append('\nExamples using `mario.load_test()` use the packaged demonstration tables. For external data, use the licence on the selected publisher release.\n')
    for cell in notebook['cells']:
        cell['metadata'] = {}
        text = ''.join(cell.get('source', []))
        if cell['cell_type'] == 'code':
            cell['outputs'], cell['execution_count'] = [], None
            # Only literal paths are replaced; code, options and scientific methods stay intact.
            text = re.sub(r'([\'"])/Users/[^\'"\n]+\1', lambda m: m[1] + '/path/to/database' + m[1], text)
        elif cell['cell_type'] == 'markdown':
            def absolute(match):
                label, link = match.groups()
                if link.startswith(('https://', 'http://', '#', 'mailto:')):
                    return match[0]
                target = DOCS + link.lstrip('/') if link.startswith('/') else urljoin(guide, link)
                return f'[{label}]({target})'
            text = re.sub(r'\[([^\]]+)\]\(([^ )]+)\)', absolute, text)
        cell['source'] = text.splitlines(keepends=True)
    at = next((i for i, cell in enumerate(notebook['cells']) if cell['cell_type'] == 'code'), len(notebook['cells']))
    notebook['cells'].insert(at, {'cell_type': 'markdown', 'id': 'mario-download-notes', 'metadata': {}, 'source': note})
    notebook['metadata'] = {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}}
    return notebook
