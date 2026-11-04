"""Locate CarService JNI entries and selected ARM64 transport evidence offline.

Dependencies: capstone==5.0.9, pyelftools==0.33. Does not load or execute the ELF.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_MEM
from elftools.elf.elffile import ELFFile


def recover(path):
    with path.open('rb') as f:
        elf = ELFFile(f)
        if elf.elfclass != 64 or not elf.little_endian or elf['e_machine'] != 'EM_AARCH64':
            raise ValueError('Expected little-endian AArch64 ELF64')
        sections = [s for s in elf.iter_sections() if s['sh_type'] != 'SHT_NOBITS' and s['sh_size']]

        def at(address, count):
            for section in sections:
                offset = address - section['sh_addr']
                if 0 <= offset < section['sh_size']:
                    return section.data()[offset:offset + count]
            return b''

        def cstring(address):
            return at(address, 512).split(b'\0', 1)[0].decode('ascii', errors='replace')

        symbol_table = elf.get_section_by_name('.dynsym')
        symbols = list(symbol_table.iter_symbols())
        registrations = [{'symbol': s.name, 'address': s['st_value'], 'size': s['st_size']}
                         for s in symbols if 'register_android_server_microntek_CarService' in s.name]
        plt = elf.get_section_by_name('.plt')
        relocations = elf.get_section_by_name('.rela.plt')
        calls = {}
        if plt is not None and relocations is not None:
            syms = elf.get_section(relocations['sh_link'])
            calls = {r['r_offset']: syms.get_symbol(r['r_info_sym']).name
                     for r in relocations.iter_relocations()}

        def call_name(target):
            # Resolve the GOT load in the actual stub instead of assuming a PLT
            # stride. The references use both 16-byte and 24-byte PLT entries.
            if plt is None or not plt['sh_addr'] <= target < plt['sh_addr'] + plt['sh_size']:
                return None
            decoder = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
            decoder.detail = True
            registers = {}
            for instruction in decoder.disasm(at(target, 32), target):
                operands = instruction.operands
                if instruction.mnemonic == 'adrp' and len(operands) == 2 and operands[1].type == ARM64_OP_IMM:
                    registers[operands[0].reg] = operands[1].imm
                elif instruction.mnemonic == 'ldr' and len(operands) == 2 and operands[1].type == ARM64_OP_MEM:
                    memory = operands[1].mem
                    if memory.base in registers and not memory.index:
                        name = calls.get(registers[memory.base] + memory.disp)
                        if name:
                            return name
                elif instruction.mnemonic in ('br', 'ret'):
                    break
            return None
        targets = {
            'native_setParameters': '(Ljava/lang/String;)I',
            'native_getParameters': '(Ljava/lang/String;)Ljava/lang/String;',
        }
        addresses = {}
        for section in sections:
            if not section['sh_flags'] & 2:
                continue
            data = section.data()
            for name in targets:
                start = 0
                while True:
                    offset = data.find(name.encode() + b'\0', start)
                    if offset < 0:
                        break
                    addresses[section['sh_addr'] + offset] = name
                    start = offset + 1
        entries = []
        for section in sections:
            if not section['sh_flags'] & 2 or section['sh_flags'] & 4:
                continue
            data = section.data()
            for offset in range(0, len(data) - 23, 8):
                name_address, signature_address, function = struct.unpack_from('<QQQ', data, offset)
                name = addresses.get(name_address)
                if not name or cstring(signature_address) != targets[name]:
                    continue
                executable = any(s['sh_flags'] & 4 and s['sh_addr'] <= function < s['sh_addr'] + s['sh_size'] for s in sections)
                if not executable:
                    continue
                instructions = []
                for ins in Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN).disasm(at(function, 512), function):
                    instructions.append(ins)
                    if ins.mnemonic == 'ret':
                        break
                sites = []
                for i, ins in enumerate(instructions):
                    if ins.mnemonic != 'bl':
                        continue
                    name_at_call = call_name(int(ins.op_str.lstrip('#'), 16))
                    if name_at_call not in ('ioctl', '__open_2', 'strlen', '__memcpy_chk', 'close'):
                        continue
                    sites.append({'callee': name_at_call, 'call_address': ins.address,
                                  'preceding_instructions': [{'address': x.address, 'instruction': x.mnemonic + ' ' + x.op_str}
                                                             for x in instructions[max(0, i - 4):i]]})
                entries.append({'method': name, 'signature': targets[name],
                                'jni_table_entry_address': section['sh_addr'] + offset,
                                'function_address': function, 'selected_call_sites': sites})
        if {entry['method'] for entry in entries} != set(targets):
            raise ValueError('Could not recover both expected JNI entries; unsupported ELF layout')
        for entry in entries:
            resolved = {site['callee'] for site in entry['selected_call_sites']}
            if not {'ioctl', 'strlen', 'close'}.issubset(resolved):
                raise ValueError(f'Incomplete transport call resolution for {entry["method"]}; review ELF manually')
        return {'file': path.name, 'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest(),
                'registration_symbols': registrations, 'entries': entries,
                'notes': ['Static evidence only; no firmware code executed.',
                          'PLT annotations resolve GOT loads against relocation records, without assuming stub stride.',
                          'Unrelocated or packed JNI pointer tables may require other tooling.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = recover(args.elf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'Recovered {len(result["entries"])} JNI entries without executing firmware')
