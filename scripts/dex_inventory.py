"""Read DEX tables without executing firmware code. Also supports modified ZIP CRCs."""
import json
from pathlib import Path
import re
import struct
import zipfile
import zlib


def uleb(b, o):
    v = s = 0
    while True:
        c = b[o]
        o += 1
        v |= (c & 127) << s
        if not c & 128:
            return v, o
        s += 7


def dex_tables(b):
    def pair(o):
        return struct.unpack_from('<II', b, o)
    ns, os = pair(56)
    strings = []
    for i in range(ns):
        o = struct.unpack_from('<I', b, os + i * 4)[0]
        _, o = uleb(b, o)
        strings.append(b[o:b.index(b'\0', o)].decode('utf-8', errors='replace'))
    nt, ot = pair(64)
    types = [strings[struct.unpack_from('<I', b, ot + i * 4)[0]] for i in range(nt)]
    np, op = pair(72)
    prototypes = []
    for i in range(np):
        shorty, result, params = struct.unpack_from('<III', b, op + i * 12)
        args = []
        if params:
            count = struct.unpack_from('<I', b, params)[0]
            args = [types[struct.unpack_from('<H', b, params + 4 + j * 2)[0]] for j in range(count)]
        prototypes.append('(' + ''.join(args) + ')' + types[result])
    nm, om = pair(88)
    methods = []
    signatures = []
    for i in range(nm):
        c, proto, name = struct.unpack_from('<HHI', b, om + i * 8)
        methods.append(types[c] + '->' + strings[name])
        signatures.append(methods[-1] + prototypes[proto])
    nc, oc = pair(96)
    classes, defined_methods, native_methods = [], [], []
    defined_signatures = []
    for i in range(nc):
        fields = struct.unpack_from('<8I', b, oc + i * 32)
        classes.append(types[fields[0]])
        o = fields[6]
        if not o:
            continue
        counts = []
        for _ in range(4):
            v, o = uleb(b, o)
            counts.append(v)
        for _ in range(counts[0] + counts[1]):
            _, o = uleb(b, o)
            _, o = uleb(b, o)
        for count in counts[2:]:
            index = 0
            for _ in range(count):
                delta, o = uleb(b, o)
                flags, o = uleb(b, o)
                code, o = uleb(b, o)
                index += delta
                defined_methods.append(methods[index])
                defined_signatures.append(signatures[index])
                if flags & 0x100:
                    native_methods.append(methods[index])
    return {'strings': strings, 'types': types, 'classes': classes,
            'method_refs': methods, 'method_signatures': signatures,
            'defined_methods': defined_methods, 'defined_signatures': defined_signatures,
            'native_methods': native_methods}


def scan_archive(p):
    raw = p.read_bytes()
    result = []
    with zipfile.ZipFile(p) as z:
        for x in z.infolist():
            if not re.fullmatch(r'classes\d*\.dex', x.filename):
                continue
            o = x.header_offset
            nl, xl = struct.unpack_from('<HH', raw, o + 26)
            start = o + 30 + nl + xl
            compressed = raw[start:start + x.compress_size]
            b = zlib.decompress(compressed, -15) if x.compress_type == 8 else compressed
            t = dex_tables(b)
            t['dex_entry'] = x.filename
            t['zip_crc_ok'] = zlib.crc32(b) == x.CRC
            result.append(t)
    return result


if __name__ == '__main__':
    import sys
    root = Path(sys.argv[1])
    output = Path(sys.argv[2])
    output.mkdir(exist_ok=True)
    summary = []
    seen_names = set()
    for p in sorted(root.rglob('*')):
        if p.suffix not in ('.apk', '.jar'):
            continue
        if p.name in seen_names:
            raise ValueError(f'Duplicate archive basename in input tree: {p.name}')
        seen_names.add(p.name)
        tables = scan_archive(p)
        if not tables:
            continue
        dest = output / (p.name + '.json')
        dest.write_text(json.dumps(tables, ensure_ascii=False))
        summary.append({'file': str(p.relative_to(root)), 'classes': sum(len(t['classes']) for t in tables),
                        'hct_classes': [c for t in tables for c in t['classes'] if re.search(r'microntek|hct|mtc|mcu', c, re.I)],
                        'crc_ok': all(t['zip_crc_ok'] for t in tables)})
    (output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print('Scanned', len(summary), 'DEX archives')
