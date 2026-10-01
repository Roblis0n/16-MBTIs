import argparse
import json
from .export import export_standalone, export_claude
p=argparse.ArgumentParser(description='Experimental offline export of a verified core package; no installation')
p.add_argument('host',choices=['standalone','claude']); p.add_argument('package'); p.add_argument('destination')
a=p.parse_args()
try:
    result={'standalone':export_standalone,'claude':export_claude}[a.host](a.package,a.destination)
    print(json.dumps({'status':result['status'],'host':a.host,'file_count':len(result['files'])}))
except (ValueError,OSError) as exc:
    print(json.dumps({'status':'error','message':str(exc)})); raise SystemExit(2)
