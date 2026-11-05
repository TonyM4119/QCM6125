"""Cross-check reviewed native dispatch labels against both working Java tables."""
import argparse
import hashlib
import json
from pathlib import Path


def check(reference, native):
    if reference['native_vold']['sha256'] != native['sha256']:
        raise ValueError('Native reference SHA-256 differs')
    dispatch = native['native_dispatch']
    if not dispatch['all_targets_are_in_function_bti_entries'] or dispatch['entry_count'] != 78:
        raise ValueError('Native dispatch bounds not established')
    cases = dispatch['reviewed_cases']
    if len({case['code'] for case in cases}) != len(cases):
        raise ValueError('Duplicate native case code')
    labelled, unlabelled = [], []
    for case in cases:
        labels = set(case['trace_labels'])
        if len(labels) > 1:
            raise ValueError('Ambiguous native trace labels')
        if not labels:
            unlabelled.append(case['code'])
            continue
        labelled.append((case['code'], next(iter(labels))))
    if not {(4, 'exreset'), (5, 'reset')} <= set(labelled):
        raise ValueError('Required reset-case anchors missing')
    matches = []
    if {table['source_file'] for table in reference['vold_transaction_tables']} != {'services.jar', 'framework.jar'} or len(reference['vold_transaction_tables']) != 2:
        raise ValueError('Expected both working Java transaction tables')
    for table in reference['vold_transaction_tables']:
        mapping = {item['method']: item['code'] for item in table['transactions']}
        if len(mapping) != len(table['transactions']) or len(set(mapping.values())) != len(mapping):
            raise ValueError('Duplicate Java method/code')
        for code, label in labelled:
            if mapping.get(label) != code:
                raise ValueError(f"Native/Java transaction mismatch: {table['source_file']} {label}")
            matches.append({'source_file': table['source_file'], 'method': label, 'code': code})
    return {'labelled_case_count': len(labelled), 'java_table_count': len(reference['vold_transaction_tables']),
            'matches': matches, 'unlabelled_reviewed_codes': unlabelled,
            'limits': ['Only reviewed trace-labelled cases compared; other transaction meanings remain unverified.',
                       'No complete Parcel, object-construction, runtime or Android 17 compatibility proof.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--native', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    reference_raw, native_raw = args.reference.read_bytes(), args.native.read_bytes()
    result = check(json.loads(reference_raw), json.loads(native_raw))
    result['reference_sha256'] = hashlib.sha256(reference_raw).hexdigest()
    result['native_report_sha256'] = hashlib.sha256(native_raw).hexdigest()
    args.report.write_text(json.dumps(result, indent=2) + '\n')
