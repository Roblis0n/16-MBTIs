#!/usr/bin/env python3
"""Local candidate packaging only. Does not publish, install, or approve release."""
from pathlib import Path, PurePosixPath
import argparse,hashlib,json,os,stat,sys,zipfile
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build import collect,verify_existing,digest,json_bytes,safe_tree

def zip_members(path, files, root_name):
    if path.exists(): raise FileExistsError('Refusing to overwrite existing delivery archive')
    manifest={name:digest(value) for name,value in sorted(files.items())}
    data={**files,'MANIFEST.json':json_bytes({'manifest_version':'1.0.0','files':manifest})}
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,value in sorted(data.items()):
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name:raise ValueError('Unsafe package member')
            i=zipfile.ZipInfo(root_name+'/'+name,(1980,1,1,0,0,0));i.create_system=3;i.external_attr=0o100644<<16;i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,value)
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise ValueError('CRC failed')
        for name,h in manifest.items():
            if digest(z.read(root_name+'/'+name))!=h:raise ValueError('Member hash mismatch')
    return {'file':path.name,'sha256':digest(path.read_bytes()),'bytes':path.stat().st_size,'members':len(data)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    output=Path(args.output).absolute();safe_tree(output)
    if output.exists() and any(output.iterdir()):raise FileExistsError('Use a new empty delivery directory')
    output.mkdir(parents=True,exist_ok=True)
    identity,files,inputs=collect(ROOT);verify_existing(ROOT/'plugins/16-minds')
    m=json.loads((ROOT/'plugins/16-minds/build-manifest.json').read_text())
    if inputs!=m['source_hashes'] or {k:digest(v) for k,v in files.items()}!=m['files']:raise ValueError('Run final core build first')
    artifacts=[]
    core=ROOT/'dist'/f"16-minds-{identity['version']}-static_candidate.zip"
    with zipfile.ZipFile(core) as z:
        if z.testzip():raise ValueError('Core CRC')
    dest=output/core.name
    with dest.open('xb') as f:f.write(core.read_bytes())
    artifacts.append({'file':dest.name,'sha256':digest(dest.read_bytes()),'bytes':dest.stat().st_size})
    for host in ('standalone','claude'):
        base=ROOT/'dist'/host
        manifest=json.loads((base/'export-manifest.json').read_text())
        if manifest['source_build_sha256']!=digest((ROOT/'plugins/16-minds/build-manifest.json').read_bytes()):raise ValueError('Stale export')
        export={p.relative_to(base).as_posix():p.read_bytes() for p in base.rglob('*') if p.is_file()}
        if set(export)!=(set(manifest['files'])|{'export-manifest.json'}):raise ValueError('Export inventory drift')
        for name,h in manifest['files'].items():
            safe_tree(base/name)
            if digest(export[name])!=h:raise ValueError('Export hash drift')
        artifacts.append(zip_members(output/f"16-minds-{identity['version']}-{host}-experimental.zip",export,'16-minds-'+host))
    (output/'runtime-artifacts.json').write_bytes(json_bytes(artifacts))
    print(json.dumps(artifacts,ensure_ascii=False))
if __name__=='__main__':main()
