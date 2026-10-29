"""Reproducible asset bootstrap: pinned URLs + SHA-256, no package manager needed."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'vendor/manifest.json').read_text(encoding='utf-8'))
for item in manifest['files']:
    path=ROOT/item['path']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
        with urllib.request.urlopen(item['url'],timeout=90) as response: data=response.read()
        if hashlib.sha256(data).hexdigest()!=item['sha256']: raise RuntimeError('Checksum mismatch: '+item['path'])
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
    print('Verified '+item['path'])
