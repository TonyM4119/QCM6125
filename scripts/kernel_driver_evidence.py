"""Read narrow driver evidence from an original kernel and recovered symbol ELF.

No kernel code or relocation is executed. The recovered ELF is used as a symbol
index only. Relative pointer addends are read from the original image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile


def collect(kernel, recovered):
    raw = kernel.read_bytes()
    with recovered.open('rb') as handle:
        elf = ELFFile(handle)
        if elf.elfclass != 64 or elf['e_machine'] != 'EM_AARCH64':
            raise ValueError('Expected recovered AArch64 ELF64')
        table = elf.get_section_by_name('.symtab')
        if table is None:
            raise ValueError('Recovered symbol table missing')
        entries = list(table.iter_symbols())
        symbols = {s.name: s for s in entries}
    base = symbols['_text']['st_value']

    def at(address, length):
        offset = address - base
        if offset < 0 or offset + length > len(raw):
            raise ValueError('Address outside original kernel image')
        return raw[offset:offset + length]

    anchors = []
    for name, expected in [('linux_banner', b'Linux version '),
                           ('__kstrtab_mtc_dev_register', b'mtc_dev_register\0')]:
        address = symbols[name]['st_value']
        if at(address, len(expected)) != expected:
            raise ValueError('Recovered address mapping failed anchor: ' + name)
        anchors.append({'symbol': name, 'virtual_address': address,
                        'original_file_offset': address - base, 'bytes_match': True})

    def relative_pointer(target):
        needle = struct.pack('<Q', target)
        start, matches = 0, []
        while True:
            offset = raw.find(needle, start)
            if offset < 0:
                break
            if offset + 24 <= len(raw):
                where, info, addend = struct.unpack_from('<QQQ', raw, offset)
                if info == 1027:  # R_AARCH64_RELATIVE with symbol index zero.
                    matches.append({'target': where, 'addend': addend,
                                    'relocation_file_offset': offset})
            start = offset + 8
        if len(matches) != 1:
            raise ValueError('Expected exactly one relative pointer relocation')
        return matches[0]

    misc = symbols['car_misc_device']['st_value']
    fops = symbols['car_fops']['st_value']
    name_pointer = relative_pointer(misc + 8)
    device_name = at(name_pointer['addend'], 32).split(b'\0', 1)[0].decode('ascii')
    fops_pointer = relative_pointer(misc + 16)
    ioctl_pointer = relative_pointer(fops + 72)
    if device_name != 'mtc-car' or fops_pointer['addend'] != fops or ioctl_pointer['addend'] != symbols['car_ioctl']['st_value']:
        raise ValueError('Device name/file-operations/handler binding did not match')
    serial_names = []
    for offset in (8, 16):
        pointer = relative_pointer(symbols['vs_uart_driver']['st_value'] + offset)
        serial_names.append(at(pointer['addend'], 32).split(b'\0', 1)[0].decode('ascii'))
    names = {s['st_value']: s.name for s in entries if s['st_info']['type'] == 'STT_FUNC'}

    def instructions(start_name, end_name):
        start, end = symbols[start_name]['st_value'], symbols[end_name]['st_value']
        if end <= start or end - start > 65536:
            raise ValueError('Unexpected function extent')
        return list(Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN).disasm(at(start, end - start), start))

    ioctl = instructions('car_ioctl', 'car_open')
    sender = instructions('vs_send_func', 'vs_send_raw_func')
    windows = []
    for index, instruction in enumerate(ioctl):
        chosen = (instruction.mnemonic == 'cmp' and any(x in instruction.op_str for x in ('#0xbfe', '#0xf01')) or
                  instruction.mnemonic == 'tbnz' and '#0x10,' in instruction.op_str)
        if chosen:
            windows.append([{'address': i.address, 'instruction': i.mnemonic + ' ' + i.op_str}
                            for i in ioctl[max(0, index - 2):index + 3]])
    if len(windows) != 3:
        raise ValueError('Expected request limit, query flag and response limit evidence')
    sender_header = []
    start = next((n for n, i in enumerate(sender) if i.mnemonic == 'mov' and '#0xfa' in i.op_str), None)
    if start is None:
        raise ValueError('Virtual event marker construction not found')
    for i in sender[start:start + 8]:
        sender_header.append({'address': i.address, 'instruction': i.mnemonic + ' ' + i.op_str})
    selected = {}
    for name in ['car_ioctl', 'mtc_ioctl', 'mtc_send', 'vs_send_func', 'vs_send_raw_func',
                 'mtc_wakeup', 'mtc_pre_sleep', 'mtc_camera_probe']:
        if name in symbols:
            selected[name] = symbols[name]['st_value']
    calls = []
    for instruction in ioctl:
        if instruction.mnemonic == 'bl':
            target = int(instruction.op_str.lstrip('#'), 16)
            name = names.get(target)
            if name in ['strrchr', 'mtc_ioctl', '__arch_copy_from_user', '__arch_copy_to_user']:
                calls.append({'address': instruction.address, 'callee': name})
    return {'source_kernel_sha256': hashlib.sha256(raw).hexdigest(),
            'recovered_elf_sha256': hashlib.sha256(recovered.read_bytes()).hexdigest(),
            'recovered_base': base, 'symbol_table_entries': len(entries),
            'address_anchors': anchors, 'device_name': device_name,
            'pointer_relocations': {'misc_name': name_pointer, 'misc_fops': fops_pointer, 'unlocked_ioctl': ioctl_pointer},
            'serial_driver_names': serial_names, 'selected_symbols': selected,
            'ioctl_instruction_windows': windows, 'selected_calls': calls,
            'virtual_event_header_instructions': sender_header,
            'limits': ['Exact reviewed kernel/layout only; alternative structures or instruction layouts are rejected.',
                       'Recovered ELF is an analysis artifact, not original source or a replacement boot image.',
                       'No current January 2025 kernel or runtime device operation was tested.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('recovered_elf', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    evidence = collect(args.kernel, args.recovered_elf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + '\n')
    print('Validated symbol anchors and mtc-car handler binding; collected kernel evidence offline')
