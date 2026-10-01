#!/usr/bin/env python3
"""Initialize an honest catalog matrix; merge only explicit, inspectable receipts.
No filename, fixture presence, mock, or exit-zero-only inference grants catalog pass.
"""
import argparse
import hashlib
import json
from pathlib import Path


def make_matrix(plan):
    catalog = json.loads((plan / '05_tests/test_catalog.json').read_text())
    wps = json.loads((plan / '00_governance/work_packages.json').read_text())
    trace = json.loads((plan / '00_governance/traceability.json').read_text())
    ids = [r['id'] for r in catalog]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate authoritative test ID')
    by_wp = {w['id']: w for w in wps}
    return {'schema_version': '1.0.0', 'catalog_sha256': hashlib.sha256((plan / '05_tests/test_catalog.json').read_bytes()).hexdigest(),
            'catalog_count': len(catalog), 'work_package_count': len(wps),
            'policy': 'Only reviewed full-layer receipts can pass. Implementation candidates are pointers, not evidence.',
            'tests': [{**t, 'original_status': t['status'], 'status': 'not_run', 'implementation_paths': by_wp[t['work_package']]['paths'],
                       'requirement_ids': [r['requirement_id'] for r in trace if t['id'] in r['tests']],
                       'command_or_host_receipt': None, 'exit_code': None, 'evidence_refs': [], 'assertions': [],
                       'not_run_reason': 'Pending explicit execution evidence and full-layer review'} for t in catalog]}


def merge_receipts(matrix, receipts, root):
    indexed = {t['id']: t for t in matrix['tests']}
    for receipt in receipts:
        tid = receipt['id']
        if tid not in indexed:
            raise ValueError('Unknown catalog ID: ' + tid)
        if receipt.get('status') not in {'pass', 'partial', 'failed', 'blocked', 'not_run', 'skipped'}:
            raise ValueError('Invalid status: ' + tid)
        if receipt['status'] == 'pass':
            needed = ['command_or_host_receipt', 'environment', 'actual_output', 'assertions', 'evidence_refs', 'review_reason', 'executed_at']
            if any(not receipt.get(k) for k in needed) or not (receipt.get('exit_code') == 0 or (receipt.get('execution_kind') == 'native_model' and receipt.get('actual_host_status') == 'completed' and receipt.get('exit_code') is None)):
                raise ValueError('Incomplete pass receipt: ' + tid)
            if receipt.get('covers_full_catalog_layer') is not True:
                raise ValueError('Partial-layer receipt cannot pass: ' + tid)
            for ref in receipt['evidence_refs']:
                p = (root / ref).resolve()
                if not p.is_relative_to(root.resolve()) or not p.is_file():
                    raise ValueError('Evidence missing/outside root: ' + ref)
        if receipt['status'] == 'not_run' and not receipt.get('not_run_reason'):
            raise ValueError('Missing not_run reason: ' + tid)
        # Never allow a receipt to replace the source test specification.
        protected = {'id', 'work_package', 'stage', 'layer', 'given', 'when', 'then', 'required_evidence', 'original_status', 'implementation_paths', 'requirement_ids'}
        previous_refs = indexed[tid].get('evidence_refs', [])
        history = indexed[tid].setdefault('receipt_history', [])
        history.append({k: v for k, v in receipt.items() if k not in protected})
        indexed[tid].update({k: v for k, v in receipt.items() if k not in protected})
        indexed[tid]['evidence_refs'] = sorted(set(previous_refs + receipt.get('evidence_refs', [])))
    return matrix


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--receipts', type=Path)
    p.add_argument('--evidence-root', type=Path, default=Path.cwd())
    a = p.parse_args()
    matrix = make_matrix(a.plan)
    if a.receipts:
        matrix = merge_receipts(matrix, json.loads(a.receipts.read_text()), a.evidence_root)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'catalog_count': matrix['catalog_count'], 'status_counts': {s: sum(t['status'] == s for t in matrix['tests']) for s in sorted(set(t['status'] for t in matrix['tests']))}}))

if __name__ == '__main__':
    main()
