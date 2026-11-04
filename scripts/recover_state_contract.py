"""Inventory selected HCT state-method references without executing firmware."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

from recover_binder_constants import analysis_copy
from androguard.core.dex import DEX


METHODS = {
    'getBooleanState', 'getByteState', 'getIntState', 'getStringState',
    'getByteArrayState', 'getIntArrayState', 'getStringArrayState',
    'putBooleanState', 'putByteState', 'putIntState', 'putStringState',
    'putByteArraryState', 'putIntArraryState', 'putStringArraryState',
    'putDataChanage', 'setParameters',
}
CONSTANTS = {'navi_package', 'av_gps_package=', 'CarData', 'type', 'value',
             'av_channel', 'sys', 'av_channel_enter=', 'av_channel_exit='}


def recover(path):
    records = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith('.dex'):
                continue
            dex = DEX(analysis_copy(archive.read(name)))
            for cls in dex.get_classes():
                if cls.get_name() != 'Lcom/android/server/microntek/CarService;':
                    continue
                for method in cls.get_methods():
                    if method.get_name() not in METHODS:
                        continue
                    references, constants = set(), set()
                    for instruction in method.get_instructions():
                        output = instruction.get_output()
                        if instruction.get_name().startswith('invoke-'):
                            reference = re.search(r'(L[^ ]+;->.*)$', output)
                            if reference:
                                references.add(reference.group(1))
                        if instruction.get_name().startswith('const-string'):
                            value = output.split(', ', 1)[-1].strip('"')
                            if value in CONSTANTS:
                                constants.add(value)
                    records.append({'method': method.get_name(),
                                    'descriptor': method.get_descriptor(),
                                    'calls': sorted(references),
                                    'reviewed_constants': sorted(constants)})
    if {record['method'] for record in records} != METHODS:
        raise ValueError('Expected state-method inventory is incomplete or changed')
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'class': 'com.android.server.microntek.CarService',
            'methods': sorted(records, key=lambda item: item['method']),
            'limits': ['Static reference inventory, not control-flow or runtime proof.',
                       'Only selected constants are retained; no full disassembly is published.',
                       'Hidden-API metadata is omitted in an in-memory analysis copy only.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jar', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(recover(args.jar), indent=2) + '\n')
