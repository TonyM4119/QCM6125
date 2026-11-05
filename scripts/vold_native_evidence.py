"""Read narrow native-reset evidence from the reviewed working vold; never execute it."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile
from android_packed_relocations import decode_aps2

EXPECTED_SHA256 = '5b7e13fac3ab33272462cee42f2635696cf132fa6e8c059290ef025737d5c215'


def profile(path):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError('Address-based review applies only to the identified working vold')
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        if elf.elfclass != 64 or elf['e_machine'] != 'EM_AARCH64':
            raise ValueError('Expected ARM64 ELF')
        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        md.detail = True
        text = elf.get_section_by_name('.text')
        ranges = {entry['initial_location']: entry['address_range']
                  for entry in elf.get_dwarf_info().EH_CFI_entries()
                  if hasattr(entry, 'header') and 'initial_location' in entry.header}

        def function(address):
            size = ranges[address]
            offset = address - text['sh_addr']
            data = text.data()[offset:offset + size]
            instructions = list(md.disasm(data, address))
            if sum(ins.size for ins in instructions) != size:
                raise ValueError('Incomplete function decoding')
            return instructions, hashlib.sha256(data).hexdigest()

        # This binary uses 24-byte PLT entries, not the commonly assumed 16.
        # Validate each entry against its relocation's GOT address.
        plt = elf.get_section_by_name('.plt')
        relocation_section = elf.get_section_by_name('.rela.plt')
        relocations = list(relocation_section.iter_relocations())
        symbols = elf.get_section(relocation_section['sh_link'])
        if (plt['sh_size'] - 32) % len(relocations):
            raise ValueError('Unexpected PLT layout')
        stride = (plt['sh_size'] - 32) // len(relocations)
        imports = {}
        for index, relocation in enumerate(relocations):
            offset = 32 + index * stride
            instructions = list(md.disasm(plt.data()[offset:offset + stride], plt['sh_addr'] + offset))
            if instructions[0].mnemonic != 'adrp' or instructions[1].mnemonic != 'ldr':
                raise ValueError('Unexpected PLT instructions')
            got = instructions[0].operands[1].imm + instructions[1].operands[1].mem.disp
            if got != relocation['r_offset']:
                raise ValueError('PLT/GOT relocation mismatch')
            imports[plt['sh_addr'] + offset] = symbols.get_symbol(relocation['r_info_sym']).name

        def cstring(address):
            for segment in elf.iter_segments():
                if segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= address < segment['p_vaddr'] + segment['p_filesz']:
                    offset = address - segment['p_vaddr'] + segment['p_offset']
                    end = raw.find(b'\0', offset, min(len(raw), offset + 256))
                    if end < 0:
                        raise ValueError('Unterminated reviewed string')
                    return raw[offset:end].decode('ascii')
            raise ValueError('String outside mapped ELF data')

        def trace_labels(instructions):
            labels = []
            for index, ins in enumerate(instructions):
                if ins.mnemonic != 'bl' or imports.get(ins.operands[0].imm) != 'atrace_begin_body':
                    continue
                a, b = instructions[index - 2:index]
                if a.mnemonic == 'adrp' and b.mnemonic == 'add' and a.op_str.startswith('x0,') and b.op_str.startswith('x0, x0,'):
                    labels.append(cstring(a.operands[1].imm + b.operands[2].imm))
            return labels

        relative_offsets = {relocation['r_offset'] for relocation in elf.get_section_by_name('.relr.dyn').iter_relocations()}
        packed = decode_aps2(elf.get_section_by_name('.rela.dyn').data())
        data = elf.get_section_by_name('.data.rel.ro')
        slots = []
        for address in range(0xdd810, 0xdd840, 8):
            if address not in relative_offsets:
                raise ValueError('Reviewed vtable slot lacks a relative relocation')
            target = struct.unpack_from('<Q', data.data(), address - data['sh_addr'])[0]
            instructions, code_hash = function(target)
            slots.append({'slot_address': address, 'target': target,
                          'trace_labels': trace_labels(instructions), 'instruction_sha256': code_hash})
        if slots[3]['target'] != 0x57150 or slots[3]['trace_labels'] != ['exreset']:
            raise ValueError('Native exreset anchor changed')

        roles = {0x57150: 'exreset_trace_wrapper', 0x8e1a4: 'calling_uid_guard',
                 0x93238: 'filtered_disk_loop', 0x9a2e4: 'destroy_candidate',
                 0x98b3c: 'create_candidate'}
        facts = []
        selected_addresses = {0x57160, 0x5716c, 0x571ac, 0x8e1d4, 0x8e1d8, 0x8e1e4,
                              0x93278, 0x9327c, 0x93288, 0x93290, 0x932c8,
                              0x9a310, 0x9a37c, 0x98b64, 0x98b70}
        for address, role in roles.items():
            instructions, code_hash = function(address)
            calls, checkpoints = [], []
            for ins in instructions:
                if ins.mnemonic in {'bl', 'b'} and ins.operands[0].type == 2:
                    target = ins.operands[0].imm
                    calls.append({'address': ins.address, 'target': target,
                                  'import': imports.get(target)})
                if ins.address in selected_addresses:
                    checkpoints.append({'address': ins.address, 'mnemonic': ins.mnemonic, 'operands': ins.op_str})
            facts.append({'role': role, 'address': address, 'fde_size': ranges[address],
                          'instruction_sha256': code_hash, 'direct_calls': calls, 'checkpoints': checkpoints})
    return {'sha256': digest, 'plt_stride': stride, 'validated_plt_entries': len(imports),
            'aps2_relocation_count': len(packed), 'relr_relocation_count': len(relative_offsets),
            'reviewed_vtable_slots': slots, 'functions': facts,
            'limits': ['Known-binary static review, not a general function-name recovery tool.',
                       'create/destroy names are source-correlated candidates, not recovered ELF symbols.',
                       'C++ vtable evidence does not prove complete native Binder transaction dispatch.',
                       'No native routine, device, storage or power operation executed; no full disassembly published.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vold', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(profile(args.vold), indent=2) + '\n')
