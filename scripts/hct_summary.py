"""Produce a narrowly scoped dependency summary from local DEX inventory JSON."""
import json
from pathlib import Path
import sys


def summarize(root):
    records = []
    for p in sorted(root.glob('*.json')):
        if p.name == 'summary.json':
            continue
        tables = json.loads(p.read_text())
        if not isinstance(tables, list):
            continue
        classes = {c for t in tables for c in t['classes']}
        core = p.name in ('framework.jar.json', 'services.jar.json')
        custom = sorted(c for c in classes if core and c.startswith(('Landroid/microntek/', 'Lcom/android/server/microntek/')))
        refs = sorted({m for t in tables for m in t.get('method_signatures', [])
                       if m.startswith('Landroid/microntek/') and m.split('->')[0] not in classes})
        native = sorted({m for t in tables for m in t['native_methods']
                         if m.startswith('Lcom/android/server/microntek/')})
        definitions = sorted({m for t in tables for m in t.get('defined_signatures', [])
                              if core and m.startswith(('Landroid/microntek/', 'Lcom/android/server/microntek/'))})
        if custom or refs or native:
            records.append({'archive': p.name.removesuffix('.json'),
                            'all_dex_zip_crcs_ok': all(t['zip_crc_ok'] for t in tables),
                            'framework_classes': custom, 'defined_signatures': definitions,
                            'external_framework_references': refs, 'native_methods': native})
    return records


if __name__ == '__main__':
    root, dest = map(Path, sys.argv[1:3])
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = summarize(root)
    dest.write_text(json.dumps(result, indent=2) + '\n')
    print(f'Wrote {len(result)} scoped archive records to {dest}')
