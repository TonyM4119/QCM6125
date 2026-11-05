import unittest
from android_packed_relocations import decode_aps2, sleb


def encode(value):
    result = bytearray()
    while True:
        byte = value & 127
        value >>= 7
        done = (value == 0 and not byte & 64) or (value == -1 and byte & 64)
        result.append(byte if done else byte | 128)
        if done:
            return bytes(result)


def stream(*values):
    return b'APS2' + b''.join(encode(value) for value in values)


class PackedChecks(unittest.TestCase):
    def test_signed_values(self):
        for value in [-(2**63), -65, -1, 0, 63, 64, 2**63 - 1]:
            self.assertEqual(sleb(encode(value), 0), (value, len(encode(value))))

    def test_grouped_delta_and_info(self):
        result = decode_aps2(stream(2, 0x1000, 2, 3, 8, 1027))
        self.assertEqual(result, [{'offset': 0x1008, 'info': 1027, 'addend': 0},
                                  {'offset': 0x1010, 'info': 1027, 'addend': 0}])

    def test_addend_accumulation_and_reset(self):
        # First group has individual addend deltas; second has no addend.
        result = decode_aps2(stream(3, 0x1000, 2, 11, 8, 1027, 100, -20,
                                   1, 3, 8, 1027))
        self.assertEqual([r['addend'] for r in result], [100, 80, 0])

    def test_grouped_addends(self):
        result = decode_aps2(stream(2, 0, 2, 15, 8, 1027, 12))
        self.assertEqual([r['addend'] for r in result], [12, 24])

    def test_invalid_streams(self):
        for data in [b'', b'APS2\x80', stream(1, 0, 0, 0), stream(1, 0, 2, 0),
                     stream(1, 0, 1, 4), stream(1, 0, 1, 16),
                     stream(0, 0) + b'\0', stream(1, 0, 1, 0, -1, 1027)]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode_aps2(data)


if __name__ == '__main__':
    unittest.main()
