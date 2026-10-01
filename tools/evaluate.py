#!/usr/bin/env python3
"""Validate an offline evaluation plan. This command cannot invoke models."""
import argparse
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.protocol import evaluate

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol',type=Path,default=Path(__file__).resolve().parents[1]/'evaluation/protocol.json')
    p.add_argument('--tasks',type=Path,default=Path(__file__).resolve().parents[1]/'evaluation/tasks/development.json')
    p.add_argument('--budget',type=float,default=0)
    a=p.parse_args()
    try: result=evaluate(json.loads(a.protocol.read_text()),a.budget,json.loads(a.tasks.read_text()))
    except (ValueError,OSError) as exc:
        print(json.dumps({'status':'error','message':str(exc)})); return 2
    print(json.dumps(result,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
