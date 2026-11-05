"""Inventory selected manager/storage/vold sleep dependencies without execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile
import zlib

from recover_binder_constants import analysis_copy
from androguard.core.dex import DEX

SELECTED = {
    'Lcom/android/server/StorageManagerService;': {'unmount', 'resetExDevice'},
    'Landroid/microntek/service/MicrontekServiceBase;': {'deviceunMountAndSleep', 'gotoSleep'},
    'Landroid/microntek/service/MicrontekServer;': {'s_onStatusChanged', 'DoCarPower', 'onCreate'},
    'Landroid/os/IVold$Stub$Proxy;': {'exreset'},
}
STRINGS = {'carpower', 'sleep', 'power_on', 'power_off', 'acc_off', 'CarPower', 'type',
           'hctall', 'rpt_media_safemounted=start', 'rpt_media_safemounted=end',
           'CarEvent,CarPower,KeyDown,CarApp,CarBox,Appinfo', 'rpt_power=true',
           'android.intent.action.SCREEN_ON', 'android.intent.action.SCREEN_OFF',
           'android.permission.MOUNT_UNMOUNT_FILESYSTEMS'}


def dexes(path):
    raw = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not re.fullmatch(r'classes\d*\.dex', info.filename):
                continue
            nl, xl = struct.unpack_from('<HH', raw, info.header_offset + 26)
            start = info.header_offset + 30 + nl + xl
            stored = raw[start:start + info.compress_size]
            if info.compress_type == zipfile.ZIP_DEFLATED:
                original = zlib.decompress(stored, -15)
            elif info.compress_type == zipfile.ZIP_STORED:
                original = stored
            else:
                raise ValueError('Unsupported ZIP compression')
            yield DEX(analysis_copy(original)), {'entry': info.filename, 'zip_crc_ok': zlib.crc32(original) == info.CRC}


def recover(paths, vold_path=None, upstream_aidl=None):
    sources, methods, constants, vold_tables = [], [], [], []
    for path in paths:
        checks = []
        for dex, check in dexes(path):
            checks.append(check)
            for cls in dex.get_classes():
                if cls.get_name() == 'Landroid/os/IVold$Stub;':
                    transactions = []
                    for field in cls.get_fields():
                        if field.get_name().startswith('TRANSACTION_'):
                            transactions.append({'method': field.get_name().removeprefix('TRANSACTION_'),
                                                 'code': field.get_init_value().get_value()})
                        if field.get_name() == 'TRANSACTION_exreset':
                            constants.append({'source_file': path.name, 'class': cls.get_name(), 'field': field.get_name(),
                                              'value': field.get_init_value().get_value()})
                    vold_tables.append({'source_file': path.name,
                                        'transactions': sorted(transactions, key=lambda t: t['code'])})
                if cls.get_name() not in SELECTED:
                    continue
                for method in cls.get_methods():
                    if method.get_name() not in SELECTED[cls.get_name()]:
                        continue
                    calls, strings, offset = [], [], 0
                    for ins in method.get_instructions():
                        name, output = ins.get_name(), ins.get_output()
                        if name.startswith('invoke-'):
                            match = re.search(r'(L[^ ]+;->.*)$', output)
                            if match:
                                calls.append({'offset': offset, 'reference': match.group(1)})
                        if name.startswith('const-string'):
                            value = output.split(', ', 1)[-1].strip('"')
                            if value in STRINGS:
                                strings.append({'offset': offset, 'value': value})
                        offset += ins.get_length()
                    methods.append({'source_file': path.name, 'class': cls.get_name(), 'method': method.get_name(),
                                    'descriptor': method.get_descriptor(), 'calls': calls,
                                    'reviewed_constants': strings})
        sources.append({'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'dex_crc_checks': checks})
    found = {(m['class'], m['method']) for m in methods}
    expected = {(cls, method) for cls, names in SELECTED.items() for method in names}
    if found != expected or len(constants) != 2 or len({c['value'] for c in constants}) != 1:
        raise ValueError('Selected sleep dependencies missing or changed')
    result = {'sources': sources, 'methods': methods, 'transaction_constants': constants,
            'vold_transaction_tables': vold_tables,
            'limits': ['Static references/constants only; branch semantics require separate review.',
                       'Native vold implementation and MCU acknowledgement semantics remain unverified.',
                       'No sleep, storage, power, Binder or firmware code was executed.',
                       'Only selected metadata published; originals remain unchanged.']}
    if vold_path is not None:
        from elftools.elf.elffile import ELFFile
        raw = vold_path.read_bytes()
        needed, symbols = [], []
        with vold_path.open('rb') as stream:
            elf = ELFFile(stream)
            if elf.elfclass != 64 or elf['e_machine'] != 'EM_AARCH64':
                raise ValueError('Expected ARM64 vold executable')
            for section in elf.iter_sections():
                if section.name == '.dynamic':
                    needed = [tag.needed for tag in section.iter_tags() if tag.entry.d_tag == 'DT_NEEDED']
                if section.name in {'.symtab', '.dynsym'}:
                    symbols.extend(symbol.name for symbol in section.iter_symbols() if 'exreset' in symbol.name)
        result['native_vold'] = {'sha256': hashlib.sha256(raw).hexdigest(), 'needed': needed,
                                 'contains_exreset_string': b'exreset' in raw,
                                 'exreset_named_symbols': symbols,
                                 'limit': 'Strings/dependencies only; no native implementation or Binder dispatch proven.'}
    if upstream_aidl is not None:
        raw = upstream_aidl.read_bytes()
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', raw.decode(), flags=re.S)
        names = re.findall(r'\b(\w+)\s*\([^;{}]*\)\s*;', text)
        if len(names) != len(set(names)) or not names:
            raise ValueError('AIDL declaration parser requires manual review')
        result['upstream_aidl_reference'] = {'sha256': hashlib.sha256(raw).hexdigest(),
                                             'declared_method_names': names,
                                             'contains_exreset': 'exreset' in names,
                                             'limit': 'Declaration names only; no upstream generated transaction codes verified.'}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('services_jar', type=Path)
    parser.add_argument('framework_jar', type=Path)
    parser.add_argument('manager_apk', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--vold', type=Path)
    parser.add_argument('--upstream-aidl', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(recover([args.services_jar, args.framework_jar, args.manager_apk],
                                             args.vold, args.upstream_aidl), indent=2) + '\n')
