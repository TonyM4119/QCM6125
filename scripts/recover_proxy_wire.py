"""Recover selected HCT Proxy Parcel operations and constant transact flags.

This is a narrow static check for the observed straight-line proxy setup. It
rejects unresolved arguments; it is not a general DEX control-flow analyser.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile
import zlib

from loguru import logger
logger.disable('androguard')
from androguard.core.dex import DEX
from recover_binder_constants import analysis_copy


def stub_cases(cls):
    result = []
    for method in cls.get_methods():
        if method.get_name() != 'onTransact' or not method.get_code():
            continue
        instructions = dict(method.get_instructions_idx())
        for offset, instruction in instructions.items():
            if instruction.get_name() not in ('packed-switch', 'sparse-switch'):
                continue
            payload = instructions[offset + instruction.get_ref_off() * 2]
            for code, target in zip(payload.get_keys(), payload.get_targets()):
                if not 1 <= code <= 26:
                    continue
                start = offset + target * 2
                reads, writes, calls, enforce = [], [], [], False
                for at, ins in instructions.items():
                    if at < start:
                        continue
                    name, output = ins.get_name(), ins.get_output()
                    if name.startswith(('goto', 'return')):
                        break
                    if name.startswith('if-'):
                        raise ValueError('Conditional Stub case needs manual control-flow review')
                    parcel = re.search(r'Landroid/os/Parcel;->(\w+)', output)
                    if parcel:
                        operation = parcel[1]
                        if operation.startswith(('read', 'create')):
                            reads.append(operation)
                        elif operation.startswith('write'):
                            writes.append(operation)
                        elif operation == 'enforceNoDataAvail':
                            enforce = True
                    call = re.search(re.escape(cls.get_name()) + r'->(\w+)\(', output)
                    if call:
                        calls.append(call[1])
                if len(calls) != 1:
                    raise ValueError('Unexpected Stub dispatch shape')
                result.append({'stub_class': cls.get_name(), 'method': calls[0], 'code': code,
                               'request_reads': reads, 'reply_writes': writes,
                               'enforce_no_data_avail': enforce})
    return result


def recover(path):
    raw = path.read_bytes()
    records, checks, server = [], [], []
    selected = {'Landroid/microntek/ICarService$Stub$Proxy;',
                'Landroid/microntek/ICarManageCallback$Stub$Proxy;'}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not re.fullmatch(r'classes\d*\.dex', info.filename):
                continue
            offset = info.header_offset
            nl, xl = struct.unpack_from('<HH', raw, offset + 26)
            start = offset + 30 + nl + xl
            stored = raw[start:start + info.compress_size]
            if info.compress_type == zipfile.ZIP_DEFLATED:
                data = zlib.decompress(stored, -15)
            elif info.compress_type == zipfile.ZIP_STORED:
                data = stored
            else:
                raise ValueError('Unsupported ZIP compression')
            checks.append({'entry': info.filename, 'zip_crc_ok': zlib.crc32(data) == info.CRC})
            dex = DEX(analysis_copy(data))
            for cls in dex.get_classes():
                if cls.get_name() in {'Landroid/microntek/ICarService$Stub;',
                                      'Landroid/microntek/ICarManageCallback$Stub;'}:
                    server.extend(stub_cases(cls))
                if cls.get_name() not in selected:
                    continue
                for method in cls.get_methods():
                    if not method.get_code():
                        continue
                    constants, writes, reads, transactions = {}, [], [], []
                    for instruction in method.get_instructions():
                        name, output = instruction.get_name(), instruction.get_output()
                        if not transactions and (name.startswith('if-') or name in ('goto', 'goto/16', 'goto/32', 'packed-switch', 'sparse-switch')):
                            raise ValueError('Branch before transact requires manual control-flow review')
                        match = re.fullmatch(r'v(\d+), (-?(?:0x[0-9a-f]+|\d+))', output)
                        if name in ('const/4', 'const/16', 'const') and match:
                            constants[int(match[1])] = int(match[2], 0)
                        elif name in ('move', 'move/from16', 'move/16'):
                            regs = re.findall(r'v(\d+)', output)
                            if int(regs[1]) in constants:
                                constants[int(regs[0])] = constants[int(regs[1])]
                            else:
                                constants.pop(int(regs[0]), None)
                        elif not name.startswith(('invoke', 'return', 'if-', 'goto', 'iput', 'sput', 'aput', 'monitor', 'throw', 'nop')):
                            destination = re.match(r'v(\d+)', output)
                            if destination:
                                constants.pop(int(destination[1]), None)
                        parcel = re.search(r'Landroid/os/Parcel;->(\w+)', output)
                        if parcel:
                            operation = parcel[1]
                            if not transactions and operation.startswith('write'):
                                writes.append(operation)
                            if transactions and operation.startswith(('read', 'create')):
                                reads.append(operation)
                        if 'Landroid/os/IBinder;->transact(' not in output:
                            continue
                        regs = [int(r) for r in re.findall(r'v(\d+)', output.split('Landroid/os/IBinder;')[0])]
                        if len(regs) != 5 or regs[1] not in constants or regs[4] not in constants:
                            raise ValueError('Unresolved transact code/flags; inspect method manually')
                        transactions.append({'code': constants[regs[1]], 'flags': constants[regs[4]]})
                    if transactions:
                        if len(transactions) != 1:
                            raise ValueError('Multiple transact paths require manual analysis')
                        records.append({'proxy_class': cls.get_name(), 'method': method.get_name(),
                                        'signature': method.get_descriptor(), **transactions[0],
                                        'request_parcel_operations': writes, 'reply_parcel_operations': reads})
    return {'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'dex_crc_checks': checks,
            'methods': records, 'stub_cases': server,
            'limits': ['Straight-line proxy/Stub evidence only; Bundle schemas, custom concrete-service overrides and runtime behaviour need separate review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jar', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = recover(args.jar)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('Recovered', len(result['methods']), 'proxy method records')
