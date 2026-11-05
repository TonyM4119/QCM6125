"""Decode Android APS2 relocation metadata; never apply relocations or execute ELF."""


def sleb(data, offset):
    value, shift = 0, 0
    while True:
        if offset >= len(data) or shift >= 70:
            raise ValueError('Truncated or oversized SLEB128')
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        shift += 7
        if not byte & 128:
            if byte & 64:
                value -= 1 << shift
            if not -(2**63) <= value < 2**63:
                raise ValueError('SLEB128 outside signed 64-bit range')
            return value, offset


def decode_aps2(data):
    if data[:4] != b'APS2':
        raise ValueError('Expected Android APS2 header')
    position = 4

    def read():
        nonlocal position
        result, position = sleb(data, position)
        return result

    count, offset = read(), read()
    if not 0 <= count <= 1_000_000 or offset < 0:
        raise ValueError('Invalid relocation count/initial offset')
    result, addend = [], 0
    while len(result) < count:
        size, flags = read(), read()
        if size <= 0 or size > count - len(result) or flags < 0 or flags & ~15:
            raise ValueError('Invalid relocation group')
        if flags & 4 and not flags & 8:
            raise ValueError('Grouped addend requires addends')
        delta = read() if flags & 2 else None
        info = read() if flags & 1 else None
        addend_delta = read() if flags & 8 and flags & 4 else None
        for _ in range(size):
            offset += delta if delta is not None else read()
            current_info = info if info is not None else read()
            if flags & 8:
                addend += addend_delta if addend_delta is not None else read()
            else:
                addend = 0
            if not 0 <= offset < 2**64 or not 0 <= current_info < 2**64 or not -(2**63) <= addend < 2**63:
                raise ValueError('Relocation arithmetic outside supported range')
            result.append({'offset': offset, 'info': current_info, 'addend': addend})
    if position != len(data):
        raise ValueError('Unexpected bytes after relocation stream')
    return result
