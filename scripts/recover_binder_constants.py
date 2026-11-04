"""Read HCT Stub transaction constants from a local framework JAR; no execution."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

from loguru import logger
logger.disable('androguard')
from androguard.core.dex import DEX


def analysis_copy(original):
    # Androguard 4.1.4 rejects some factory hidden-API domain flag values. Omit
    # only that metadata from an in-memory copy; original files stay untouched.
    data = bytearray(original)
    offset = struct.unpack_from('<I', data, 52)[0]
    count = struct.unpack_from('<I', data, offset)[0]
    entries = [data[offset + 4 + i * 12:offset + 16 + i * 12] for i in range(count)]
    keep = [entry for entry in entries if struct.unpack_from('<H', entry)[0] != 0xf000]
    struct.pack_into('<I', data, offset, len(keep))
    data[offset + 4:offset + 4 + len(keep) * 12] = b''.join(keep)
    data[12:32] = hashlib.sha1(data[32:]).digest()
    struct.pack_into('<I', data, 8, zlib.adler32(data[12:]))
    return bytes(data)


def recover(path):
    raw = path.read_bytes()
    records, crcs = [], []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.filename.endswith('.dex'):
                continue
            offset = info.header_offset
            name_size, extra_size = struct.unpack_from('<HH', raw, offset + 26)
            start = offset + 30 + name_size + extra_size
            stored = raw[start:start + info.compress_size]
            if info.compress_type == zipfile.ZIP_DEFLATED:
                original = zlib.decompress(stored, -15)
            elif info.compress_type == zipfile.ZIP_STORED:
                original = stored
            else:
                raise ValueError('Unsupported ZIP compression')
            crcs.append({'entry': info.filename, 'zip_crc_ok': zlib.crc32(original) == info.CRC})
            dex = DEX(analysis_copy(original))
            for cls in dex.get_classes():
                name = cls.get_name()
                if not name.startswith('Landroid/microntek/') or not name.endswith('$Stub;'):
                    continue
                fields = []
                for field in cls.get_fields():
                    if not field.get_name().startswith('TRANSACTION_'):
                        continue
                    initial = field.get_init_value()
                    fields.append({'method': field.get_name().removeprefix('TRANSACTION_'),
                                   'code': initial.get_value() if initial else None})
                records.append({'class': name, 'transactions': sorted(fields, key=lambda x: x['code'])})
    return {'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
            'dex_crc_checks': crcs, 'interfaces': records,
            'limits': ['Constants only; onTransact/Proxy parcel layout and one-way flags still require verification.',
                       'Hidden-API metadata omitted only in an analysis copy; originals not modified.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jar', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = recover(args.jar)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('Recovered constants for', len(result['interfaces']), 'HCT interfaces')
