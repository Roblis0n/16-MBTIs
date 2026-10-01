"""Offline export only. Never installs, registers, overwrites, or claims host support."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from tools.build import safe_tree, verify_existing, digest, json_bytes

VERSION='1.0.0'

def _export(package, destination, host):
    package,destination=Path(package).absolute(),Path(destination).absolute()
    safe_tree(package); safe_tree(destination)
    manifest=json.loads((package/'build-manifest.json').read_text())
    for rel in manifest.get('files', {}):
        path=PurePosixPath(rel)
        if path.is_absolute() or '..' in path.parts or '\\' in rel: raise ValueError('Unsafe core manifest path')
    verify_existing(package)
    if not manifest.get('source_hashes') or not manifest.get('files'): raise ValueError('Missing core build provenance')
    if destination.exists():
        existing=sorted(p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file())
        raise FileExistsError('Export name conflict; refusing all overwrite. Existing files: '+', '.join(existing[:20]))
    files={}
    for rel in manifest['files']:
        path=PurePosixPath(rel)
        if path.is_absolute() or '..' in path.parts: raise ValueError('Unsafe core manifest path')
        if rel.startswith('skills/') or rel in {'LICENSE','ATTRIBUTION.md','persona-provenance.json'}:
            files[rel]=(package/rel).read_bytes()
    skills=sorted({PurePosixPath(rel).parts[1] for rel in files if rel.startswith('skills/')})
    if len(skills)!=8: raise ValueError('Expected eight core skills')
    for name in skills:
        skill_path='skills/'+name+'/SKILL.md'
        if skill_path not in files: raise ValueError('Missing skill entry')
        for target in re.findall(r'\]\(([^)]+)\)',files[skill_path].decode()):
            if '://' in target: continue
            if '..' in PurePosixPath(target).parts or target.startswith('/') or 'skills/'+name+'/'+target not in files:
                raise ValueError('Skill reference is not self contained')
        # A copied single directory retains license, provenance, resources and runtime.
        for asset in ('LICENSE','ATTRIBUTION.md','persona-provenance.json'):
            files['skills/'+name+'/'+asset]=files[asset]
    identity=json.loads((package/'plugin.json').read_text())
    if host=='claude':
        files['.claude-plugin/plugin.json']=json_bytes({k:identity[k] for k in ('name','version','description')})
    export_manifest={'exporter_version':VERSION,'host':host,'status':'experimental_exporter',
      'source_build_sha256':digest((package/'build-manifest.json').read_bytes()),
      'source_hashes':manifest['source_hashes'],'files':{p:digest(b) for p,b in sorted(files.items())},
      'host_version':None,'install':'not_run','eight_entry_smoke':'not_run',
      'limitations':['Target host not supplied or tested','Tool permissions and native delegation are host-specific',
                      'No global registration; copied runtime is generated from the core build']}
    files['export-manifest.json']=json_bytes(export_manifest)
    # Exclusive creation prevents overwrite even if another process races preflight.
    destination.mkdir(parents=True,exist_ok=False)
    for rel,content in sorted(files.items()):
        target=destination/rel; safe_tree(target); target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream: stream.write(content)
    return export_manifest

def export_standalone(package,destination): return _export(package,destination,'standalone')
def export_claude(package,destination): return _export(package,destination,'claude')
