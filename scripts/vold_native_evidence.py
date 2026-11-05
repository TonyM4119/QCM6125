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
        dispatch, dispatch_hash = function(0xd3268)
        by_address = {ins.address: ins for ins in dispatch}
        expected_switch = {
            0xd3298: ('sub', 'w8, w1, #1'),
            0xd329c: ('cmp', 'w8, #0x4d'),
            0xd32a8: ('adrp', 'x9, #0x1a000'),
            0xd32ac: ('add', 'x9, x9, #0x53c'),
            0xd32b0: ('adr', 'x10, #0xd32c0'),
            0xd32b4: ('ldrh', 'w11, [x9, x8, lsl #1]'),
            0xd32b8: ('add', 'x10, x10, x11, lsl #2'),
            0xd32bc: ('br', 'x10'),
        }
        for address, expected in expected_switch.items():
            ins = by_address[address]
            if (ins.mnemonic, ins.op_str) != expected:
                raise ValueError('Reviewed dispatch switch changed')
        rodata = elf.get_section_by_name('.rodata')
        table = struct.unpack_from('<78H', rodata.data(), 0x1a53c - rodata['sh_addr'])
        targets = [0xd32c0 + entry * 4 for entry in table]
        if any(target not in by_address or by_address[target].mnemonic != 'bti' for target in targets):
            raise ValueError('Jump target does not identify a reviewed dispatch block')
        cases = []
        address_point = None
        for code in range(1, 7):
            start = targets[code - 1]
            block, at = [], start
            for _ in range(64):
                ins = by_address[at]
                block.append(ins)
                if ins.mnemonic == 'b':
                    break
                at += ins.size
            else:
                raise ValueError('Reviewed case did not reach its shared tail')
            loads = [ins for ins in block if ins.mnemonic == 'ldr' and ins.op_str.startswith('x9, [x8, #')]
            if len(loads) != 1:
                raise ValueError('Ambiguous reviewed vtable load')
            slot_offset = loads[0].operands[1].mem.disp
            if code == 1:
                address_point = slots[0]['slot_address'] - slot_offset
            slot_address = address_point + slot_offset
            if slot_address not in relative_offsets:
                raise ValueError('Dispatch slot lacks relative relocation')
            target = struct.unpack_from('<Q', data.data(), slot_address - data['sh_addr'])[0]
            target_instructions, _ = function(target)
            imported_calls = [imports[ins.operands[0].imm] for ins in block
                              if ins.mnemonic == 'bl' and ins.operands[0].imm in imports]
            cases.append({'code': code, 'case_address': start, 'vtable_slot_offset': slot_offset,
                          'slot_address': slot_address, 'target': target,
                          'trace_labels': trace_labels(target_instructions),
                          'imported_calls_before_shared_tail': imported_calls,
                          'shared_tail_address': block[-1].operands[0].imm})
        if cases[3]['trace_labels'] != ['exreset'] or cases[4]['trace_labels'] != ['reset']:
            raise ValueError('Native dispatch does not match the reviewed anchors')
        tail = [by_address[address] for address in range(0xd56c0, 0xd56ec, 4)]
        if by_address[0xd56cc].mnemonic != 'blr' or by_address[0xd56cc].op_str != 'x9':
            raise ValueError('Shared virtual invocation changed')
        write_status = by_address[0xd56d8]
        if write_status.mnemonic != 'bl' or imports.get(write_status.operands[0].imm) != '_ZNK7android6binder6Status13writeToParcelEPNS_6ParcelE':
            raise ValueError('Shared status reply path changed')
        dispatch_evidence = {
            'function_address': 0xd3268, 'fde_size': ranges[0xd3268],
            'instruction_sha256': dispatch_hash, 'jump_table_address': 0x1a53c,
            'relative_target_base': 0xd32c0, 'entry_count': len(targets),
            'all_targets_are_in_function_bti_entries': True,
            'inferred_primary_address_point': address_point, 'reviewed_cases': cases,
            'case4_shared_tail': [{'address': ins.address, 'mnemonic': ins.mnemonic,
                                   'operands': ins.op_str,
                                   'import': imports.get(ins.operands[0].imm) if ins.mnemonic == 'bl' else None}
                                  for ins in tail],
            'limit': 'Six cases statically traced; address point inferred from the setListener anchor. Object construction and other cases not fully reviewed.'}
    return {'sha256': digest, 'plt_stride': stride, 'validated_plt_entries': len(imports),
            'aps2_relocation_count': len(packed), 'relr_relocation_count': len(relative_offsets),
            'reviewed_vtable_slots': slots, 'functions': facts, 'native_dispatch': dispatch_evidence,
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
