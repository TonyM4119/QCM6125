"""Summarize selected board declarations from boot-v2 DTB and DTBO-v0 files.

Read-only parsing; does not apply overlays or modify any image/device. Requires
pyfdt 0.3. Output deliberately excludes arbitrary chosen/serial/MAC properties.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct

from pyfdt.pyfdt import FdtBlobParse, FdtNode, FdtPropertyStrings, FdtPropertyWords


def boot_dtb(image):
    if len(image) < 1660 or image[:8] != b'ANDROID!':
        raise ValueError('Invalid Android boot header')
    word = lambda offset: struct.unpack_from('<I', image, offset)[0]
    page, version = word(36), word(40)
    if version != 2 or page < 2048 or page > 65536 or page & (page - 1):
        raise ValueError('Only reviewed boot-v2 layout is supported')
    if word(1644) < 1660 or word(1644) > page:
        raise ValueError('Invalid boot-v2 header size')
    align = lambda value: (value + page - 1) // page * page
    before_recovery = page + align(word(8)) + align(word(16)) + align(word(24))
    recovery_size = word(1632)
    if recovery_size and struct.unpack_from('<Q', image, 1636)[0] != before_recovery:
        raise ValueError('Unsupported recovery DTBO placement')
    offset = before_recovery + align(recovery_size)
    size = word(1648)
    if size < 40 or offset + size > len(image):
        raise ValueError('Boot DTB extends outside image')
    return image[offset:offset + size], {'page_size': page, 'header_version': version,
                                       'dtb_offset': offset, 'dtb_size': size}


def overlay_entries(image):
    if len(image) < 32:
        raise ValueError('Truncated DTBO header')
    magic, total, header, entry_size, count, offset, page, version = struct.unpack_from('>8I', image)
    if magic != 0xd7b7ab1e or version != 0 or header < 32 or entry_size < 32:
        raise ValueError('Only DTBO-v0 layout is supported')
    table_end = offset + entry_size * count
    if total > len(image) or count > 1024 or offset < header or table_end > total:
        raise ValueError('DTBO table outside declared image bounds')
    result = []
    for index in range(count):
        size, start, identifier, revision, *custom = struct.unpack_from('>8I', image, offset + index * entry_size)
        if size < 40 or start < table_end or start + size > total:
            raise ValueError('DTBO entry outside declared data bounds')
        result.append((image[start:start + size], {'index': index, 'size': size,
                        'offset': start, 'id': identifier, 'revision': revision, 'custom': custom}))
    return result


def profile(blob):
    if len(blob) < 40:
        raise ValueError('Truncated flattened tree')
    magic, total = struct.unpack_from('>II', blob)
    if magic != 0xd00dfeed or not 40 <= total <= len(blob):
        raise ValueError('Invalid flattened tree bounds')
    if any(blob[total:]):
        raise ValueError('Concatenated/non-padding trailing DTB data needs separate review')
    root = FdtBlobParse(io.BytesIO(blob[:total])).to_fdt().get_rootnode()
    nodes = {'/': {}}
    for path, item in root.walk():
        if isinstance(item, FdtNode):
            nodes.setdefault(path, {})
            continue
        parent = path.rsplit('/', 1)[0] or '/'
        properties = nodes.setdefault(parent, {})
        if isinstance(item, FdtPropertyStrings):
            properties[item.get_name()] = item.strings
        elif isinstance(item, FdtPropertyWords):
            properties[item.get_name()] = item.words
        else:
            properties[item.get_name()] = True  # No arbitrary byte-property values exported.
    root_keys = ['model', 'compatible', 'qcom,msm-id', 'qcom,board-id', 'qcom,msm-name', 'qcom,pmic-name']
    allowed = {'compatible', 'status', 'reg', 'label', 'qcom,model',
               'qcom,mdss-dsi-panel-name', 'qcom,mdss-dsi-panel-width',
               'qcom,mdss-dsi-panel-height', 'qcom,mdss-dsi-panel-framerate',
               'mtc,icn6202_rst', 'mtc,icn6202_power', 'mtc,power_en', 'mtc,bl_en',
               'mtc,lcd_en', 'mtc,otg_drv', 'mtc,panel_io1', 'mtc,panel_io2',
               'mtc,camera_rst', 'mtc,camera_pwr', 'mtc,reg_en', 'mtc,dc_power',
               'mtc,hdmi_rst', 'mtc,hdmi_power', 'mtc,hdmi_det', 'mtc,hdmi_ack',
               'mtc,radio_rst', 'mtc,radio_scl', 'mtc,radio_sda', 'mtc,rst', 'mtc,en'}
    needles = ('mtc', 'hct', 'goodix', 'focaltech', 'himax', 'jadard', 'icn6202', 'td4330', 'snd-card')
    selected = []
    for path, props in nodes.items():
        if path.startswith('/__'):
            continue
        labels = [path]
        for key in ['compatible', 'label', 'qcom,model', 'qcom,mdss-dsi-panel-name']:
            labels.extend(v for v in props.get(key, []) if isinstance(v, str))
        if any(any(needle in label.lower() for needle in needles) for label in labels):
            selected.append({'path': path, 'properties': {k: v for k, v in props.items() if k in allowed},
                             'property_names': sorted(props)})
    return {'blob_sha256': hashlib.sha256(blob).hexdigest(), 'fdt_total_size': total,
            'node_count': len(nodes), 'root': {k: nodes['/'][k] for k in root_keys if k in nodes['/']},
            'selected_nodes': selected}


def base_profiles(data):
    result, offset = [], 0
    while offset < len(data):
        if not any(data[offset:]):
            break
        if len(result) >= 1024 or offset + 40 > len(data):
            raise ValueError('Truncated or excessive concatenated base trees')
        magic, size = struct.unpack_from('>II', data, offset)
        if magic != 0xd00dfeed or size < 40 or offset + size > len(data):
            raise ValueError('Invalid concatenated base tree bounds')
        result.append({'index': len(result), 'offset': offset,
                       'profile': profile(data[offset:offset + size])})
        offset += size
    if not result:
        raise ValueError('No base device tree found')
    return result


def inspect(boot, dtbo, label):
    boot_bytes, overlay_bytes = boot.read_bytes(), dtbo.read_bytes()
    tree, layout = boot_dtb(boot_bytes)
    overlays = [{'table': entry, 'profile': profile(data)} for data, entry in overlay_entries(overlay_bytes)]
    return {'label': label, 'boot_sha256': hashlib.sha256(boot_bytes).hexdigest(),
            'dtbo_sha256': hashlib.sha256(overlay_bytes).hexdigest(),
            'boot_layout': layout, 'base_trees': base_profiles(tree), 'overlays': overlays,
            'limits': ['Compiled declarations only; overlays were not applied and live bootloader changes are unknown.',
                       'Multiple declared touchscreen/peripheral nodes do not establish fitted or active hardware.',
                       'GPIO cells may contain unresolved overlay phandles, not direct physical pin instructions.',
                       'This does not diagnose the failed XTRONS update or validate another firmware.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot', type=Path, required=True)
    parser.add_argument('--dtbo', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.boot, args.dtbo, args.label)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('Read', len(result['base_trees']), 'base blobs and', len(result['overlays']), 'overlay entries without applying them')
