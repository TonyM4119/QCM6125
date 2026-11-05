"""Read selected control-method metadata from local HCT services.jar; no execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

from recover_binder_constants import analysis_copy
from androguard.core.dex import DEX

SERVICE = 'Lcom/android/server/microntek/CarService;'
SELECTED = {
    SERVICE: {'getEqIdx', 'setEqIdx', 'getLud', 'setLud', 'getVideoEnable',
              'setVideoOverSpeed', 'setEQ', 'setLUD', 'getInt', 'putInt',
              'isKGLCustomerSub', 'getParameters'},
    'Lcom/android/server/microntek/CarService$1;': {'handleMessage'},
}
STRINGS = {'KeyEQmode', 'KeyCTmode', 'KeyCustomEQ', 'KeyCustom1EQ',
           'KeyCustom2EQ', 'KeyCustom3EQ', 'KeyCustom4EQ', 'KeyCustom5EQ',
           'KeyCustom6EQ', 'KeyLudGain', 'key_Lud', 'DrivingVideoEN',
           'DrivingVideoOverSpeed', 'handbrake', 'ro.product.customer.sub',
           'HCT', 'KGLMMR', 'KGL1', 'av_eq=', 'av_dsp=0,', 'av_lud=on',
           'av_lud=off', 'av_dsp=1,1,', 'av_dsp=1,0,', '0,0',
           'CarData', 'CarEvent', 'type', 'value', 'EQ_MODE', 'LOUND_MODE'}


def recover(path):
    records = []
    with zipfile.ZipFile(path) as archive:
        for entry in sorted(archive.namelist()):
            if not entry.endswith('.dex'):
                continue
            for cls in DEX(analysis_copy(archive.read(entry))).get_classes():
                if cls.get_name() not in SELECTED:
                    continue
                for method in cls.get_methods():
                    if method.get_name() not in SELECTED[cls.get_name()]:
                        continue
                    calls, constants, offset = [], [], 0
                    instructions = list(method.get_instructions())
                    for instruction in instructions:
                        output = instruction.get_output()
                        if instruction.get_name().startswith('invoke-'):
                            match = re.search(r'(L[^ ]+;->.*)$', output)
                            if match:
                                calls.append({'offset': offset, 'reference': match.group(1)})
                        if instruction.get_name().startswith('const-string'):
                            value = output.split(', ', 1)[-1].strip('"')
                            if value in STRINGS:
                                constants.append({'offset': offset, 'value': value})
                        offset += instruction.get_length()
                    records.append({'class': cls.get_name(), 'method': method.get_name(),
                                    'descriptor': method.get_descriptor(),
                                    'instruction_sha256': hashlib.sha256(b''.join(
                                        instruction.get_raw() for instruction in instructions)).hexdigest(),
                                    'calls': calls, 'reviewed_constants': constants})
    expected = {(cls, method) for cls, methods in SELECTED.items() for method in methods}
    if {(r['class'], r['method']) for r in records} != expected or len(records) != len(expected):
        raise ValueError('Selected method inventory changed or is incomplete')
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'methods': sorted(records, key=lambda r: (r['class'], r['method'])),
            'limits': ['Static metadata only; branch semantics require separate instruction review.',
                       'Offsets are bytes within each method, not file offsets.',
                       'No full bytecode or disassembly retained; originals are unchanged.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jar', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(recover(args.jar), indent=2) + '\n')
