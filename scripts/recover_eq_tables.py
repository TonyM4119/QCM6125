"""Recover only the three preset arrays used by reviewed CarService.setEQ."""
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

WIDTHS = {'music_stytle_data': 3, 'music_stytle_data15': 15, 'music_stytle_data31': 31}


def evaluate(method):
    registers, tables = {}, {}
    instructions = dict(method.get_instructions_idx())
    for offset, ins in instructions.items():
        name, output = ins.get_name(), ins.get_output()
        if name == 'return-void':
            break
        operands = ins.get_operands()
        if name in {'const/4', 'const/16'}:
            registers[operands[0][1]] = operands[1][1]
        elif name == 'new-array':
            count = registers[operands[1][1]]
            if not isinstance(count, int) or not 0 <= count <= 64:
                raise ValueError('Unexpected array length')
            registers[operands[0][1]] = [None] * count
        elif name == 'fill-array-data':
            payload = instructions[offset + ins.get_ref_off() * 2]
            raw = payload.get_data()
            target = registers[operands[0][1]]
            if payload.element_width != 4 or len(raw) != len(target) * 4:
                raise ValueError('Unexpected preset element width/count')
            target[:] = struct.unpack('<' + 'i' * len(target), raw)
        elif name == 'aput-object':
            value, array, index = (registers[operand[1]] for operand in operands[:3])
            if not isinstance(index, int) or not 0 <= index < len(array):
                raise ValueError('Unexpected preset row index')
            array[index] = value
        elif name == 'sput-object':
            match = re.search(r'->(\w+) \[\[I$', output)
            if not match:
                raise ValueError('Unexpected static field')
            if match[1] in WIDTHS:
                # Copy now, before later instructions can reuse registers/arrays.
                tables[match[1]] = [list(row) for row in registers[operands[0][1]]]
        else:
            raise ValueError('Unsupported initializer instruction: ' + name)
    if set(tables) != set(WIDTHS):
        raise ValueError('Selected preset arrays missing')
    for name, rows in tables.items():
        if len(rows) != 6 or any(len(row) != WIDTHS[name] or
                                 any(type(value) is not int for value in row) for row in rows):
            raise ValueError('Preset dimensions or values changed')
    return tables


def recover(path):
    raw = path.read_bytes()
    records, crcs = [], []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not re.fullmatch(r'classes\d*\.dex', info.filename):
                continue
            name_size, extra_size = struct.unpack_from('<HH', raw, info.header_offset + 26)
            start = info.header_offset + 30 + name_size + extra_size
            stored = raw[start:start + info.compress_size]
            if info.compress_type == zipfile.ZIP_DEFLATED:
                original = zlib.decompress(stored, -15)
            elif info.compress_type == zipfile.ZIP_STORED:
                original = stored
            else:
                raise ValueError('Unsupported ZIP compression')
            crcs.append({'entry': info.filename, 'zip_crc_ok': zlib.crc32(original) == info.CRC})
            for cls in DEX(analysis_copy(original)).get_classes():
                if cls.get_name() != 'Landroid/microntek/MTCData;':
                    continue
                for method in cls.get_methods():
                    if method.get_name() == '<clinit>':
                        records.append(evaluate(method))
    if len(records) != 1:
        raise ValueError('Expected one MTCData initializer')
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'dex_crc_checks': crcs,
            'tables': records[0],
            'limits': ['Static numeric preset data only; hardware response is untested.',
                       'Stale ZIP CRC is reported rather than silently repaired.',
                       'Analysis omits hidden-API metadata in memory; originals unchanged.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jar', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(recover(args.jar), indent=2) + '\n')
