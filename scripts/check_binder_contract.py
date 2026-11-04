"""Generate Java from reconstructed AIDL and compare its wire operations.

Requires a local AIDL compiler supporting --min_sdk_version=33. Generated Java
is inspected, not compiled to bytecode or executed. Parser scope is deliberately
limited to the conventional Java output used by the tested compiler.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def block(text, opening):
    depth = 0
    for at in range(opening, len(text)):
        if text[at] == '{':
            depth += 1
        elif text[at] == '}':
            depth -= 1
            if depth == 0:
                return text[opening + 1:at]
    raise ValueError('Unbalanced generated block')


def descriptor(java_type):
    prefix = ''
    while java_type.endswith('[]'):
        prefix += '['
        java_type = java_type[:-2]
    primitives = {'void': 'V', 'boolean': 'Z', 'byte': 'B', 'int': 'I'}
    return prefix + (primitives[java_type] if java_type in primitives
                     else 'L' + java_type.replace('.', '/') + ';')


def generated_contract(source):
    ids = {name: int(offset) + 1 for name, offset in re.findall(
        r'static final int TRANSACTION_(\w+)\s*=\s*\(android\.os\.IBinder\.FIRST_CALL_TRANSACTION\s*\+\s*(\d+)\)', source)}
    token = re.search(r'DESCRIPTOR\s*=\s*"([^"]+)"', source)[1]
    proxy = source[source.index('private static class Proxy'):]
    pattern = re.compile(r'public\s+([\w.\[\]]+)\s+(\w+)\(([^)]*)\)\s+throws android\.os\.RemoteException\s*\{')
    methods = {}
    for match in pattern.finditer(proxy):
        result, name, args = match.groups()
        body = block(proxy, match.end() - 1)
        call = re.search(r'mRemote\.transact\(Stub\.TRANSACTION_(\w+),\s*_data,\s*(_reply|null),\s*([^)]*)\)', body)
        if not call:
            continue
        if call[1] != name:
            raise ValueError('Method and transaction name differ')
        flags = {'0': 0, 'android.os.IBinder.FLAG_ONEWAY': 1}[call[3].strip()]
        types = [arg.strip().rsplit(' ', 1)[0] for arg in args.split(',')] if args.strip() else []
        methods[name] = {'code': ids[name], 'flags': flags,
                         'signature': '(' + ''.join(descriptor(t) for t in types) + ')' + descriptor(result),
                         'request_parcel_operations': re.findall(r'_data\.(write\w+)\(', body),
                         'reply_parcel_operations': re.findall(r'_reply\.((?:read|create)\w+)\(', body),
                         'null_reply': call[2] == 'null'}
    cases = {}
    for match in re.finditer(r'case TRANSACTION_(\w+):\s*\{', source):
        name = match[1]
        body = block(source, match.end() - 1)
        cases[name] = {'code': ids[name],
                       'request_reads': re.findall(r'\bdata\.((?:read|create)\w+)\(', body),
                       'reply_writes': re.findall(r'\breply\.(write\w+)\(', body),
                       'enforce_no_data_avail': 'data.enforceNoDataAvail()' in body}
    return token, methods, cases


def verify(generated, reference):
    expected = {}
    expected_cases = {}
    for item in reference['methods']:
        name = item['proxy_class'].removeprefix('L').removesuffix('$Stub$Proxy;').replace('/', '.')
        expected.setdefault(name, {})[item['method']] = item
    for item in reference['stub_cases']:
        name = item['stub_class'].removeprefix('L').removesuffix('$Stub;').replace('/', '.')
        expected_cases.setdefault(name, {})[item['method']] = item
    checked = []
    for interface, methods in expected.items():
        path = generated / (interface.replace('.', '/') + '.java')
        token, actual, cases = generated_contract(path.read_text())
        if token != interface or set(actual) != set(methods) or set(cases) != set(expected_cases[interface]):
            raise ValueError('Descriptor or method coverage differs: ' + interface)
        for name, original in methods.items():
            current = actual[name]
            for key in ['code', 'flags', 'request_parcel_operations', 'reply_parcel_operations']:
                if current[key] != original[key]:
                    raise ValueError(f'{interface}.{name}: {key} differs')
            if current['signature'] != original['signature'].replace(' ', ''):
                raise ValueError(f'{interface}.{name}: Java signature differs')
            if current['null_reply'] != (original['flags'] == 1):
                raise ValueError(f'{interface}.{name}: reply direction differs')
            for key in ['code', 'request_reads', 'reply_writes', 'enforce_no_data_avail']:
                if cases[name][key] != expected_cases[interface][name][key]:
                    raise ValueError(f'{interface}.{name}: server {key} differs')
            checked.append({'interface': interface, 'method': name, 'code': current['code'],
                            'flags': current['flags'], 'signature_and_parcel_checks': 'match'})
    return checked


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aidl', default='aidl')
    parser.add_argument('--compiler-label', default='user-supplied AIDL compiler')
    parser.add_argument('--output', type=Path, default=Path('work/binder-check'))
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    inputs = [root / 'interfaces/android/microntek' / (name + '.aidl')
              for name in ['ICarService', 'ICarManageCallback']]
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.run([args.aidl, '--lang=java', '--min_sdk_version=33', '-I' + str(root / 'interfaces'),
                    '-p' + str(root / 'interfaces/test-support/framework-types.aidl'),
                    '--out=' + str(args.output), *map(str, inputs)], check=True)
    checked = verify(args.output, json.loads(args.reference.read_text()))
    report = {'check_kind': 'AIDL Java generation and static generated-source comparison',
              'compiler_label': args.compiler_label, 'min_sdk_version': 33,
              'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
              'input_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
              'checked_methods': checked,
              'limits': ['Generated Java was not compiled to bytecode or executed.',
                         'Bundle schemas, concrete service overrides, Android 17 integration and hardware remain untested.']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(f'AIDL declarations match {len(checked)} reference proxy/Stub methods')
