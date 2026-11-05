"""Compare generated upstream IVold transaction IDs with recovered HCT constants."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def generated_constants(source):
    declarations = re.findall(r'static final int TRANSACTION_(\w+)\s*=\s*([^;]+);', source)
    if not declarations:
        raise ValueError('No generated transaction constants')
    result = {}
    for name, expression in declarations:
        match = re.fullmatch(r'\(android\.os\.IBinder\.FIRST_CALL_TRANSACTION \+ (\d+)\)', expression.strip())
        if not match or name in result:
            raise ValueError('Unsupported or duplicate generated constant')
        result[name] = 1 + int(match[1])
    if len(set(result.values())) != len(result):
        raise ValueError('Generated transaction codes are not unique')
    return result


def compare(generated_path, reference_path, source_path, compiler_label):
    generated = generated_path.read_bytes()
    upstream = generated_constants(generated.decode())
    reference_raw = reference_path.read_bytes()
    tables = json.loads(reference_raw)['vold_transaction_tables']
    comparisons = []
    for table in tables:
        hct = {item['method']: item['code'] for item in table['transactions']}
        if len(hct) != len(table['transactions']) or len(set(hct.values())) != len(hct):
            raise ValueError('Duplicate recovered transaction names/codes')
        mismatches = [{'method': name, 'upstream_code': upstream[name], 'hct_code': hct[name]}
                      for name in sorted(upstream.keys() & hct.keys()) if upstream[name] != hct[name]]
        comparisons.append({'source_file': table['source_file'], 'hct_method_count': len(hct),
                            'shared_method_count': len(upstream.keys() & hct.keys()),
                            'hct_only_methods': sorted(hct.keys() - upstream.keys()),
                            'upstream_only_methods': sorted(upstream.keys() - hct.keys()),
                            'shared_code_mismatches': mismatches,
                            'names_and_codes_match': upstream == hct})
    return {'check_kind': 'Static comparison with Java generated from upstream Android 13 IVold AIDL',
            'compiler_label': compiler_label,
            'upstream_aidl_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
            'generated_java_sha256': hashlib.sha256(generated).hexdigest(),
            'reference_sha256': hashlib.sha256(reference_raw).hexdigest(),
            'upstream_method_count': len(upstream), 'comparisons': comparisons,
            'limits': ['Names/codes only; full Parcel layouts and native vold dispatch remain unverified.',
                       'AIDL generation only; no Java compilation, Android runtime or device operation.',
                       'Android 13 source comparison does not establish any Android 17 ABI.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated', required=True, type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--compiler-label', required=True)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    args.report.write_text(json.dumps(compare(args.generated, args.reference, args.source,
                                             args.compiler_label), indent=2) + '\n')
