"""Synthetic container/bounds checks; creates no bootable firmware or device I/O."""
import struct
import unittest

from pyfdt.pyfdt import Fdt, FdtNode, FdtPropertyStrings
from device_tree_profile import base_profiles, boot_dtb, overlay_entries, profile


def tree_blob():
    tree = Fdt()
    root = FdtNode('/')
    root.append(FdtPropertyStrings('compatible', ['test,board']))
    tree.add_rootnode(root)
    return tree.to_dtb()


def boot_fixture(blob):
    header = bytearray(4096)
    header[:8] = b'ANDROID!'
    for offset, value in [(8, 4096), (36, 4096), (40, 2), (1644, 1660), (1648, len(blob))]:
        struct.pack_into('<I', header, offset, value)
    return bytes(header) + b'\xa5' * 4096 + blob


def overlay_fixture(blob):
    size = 64 + len(blob)
    return (struct.pack('>8I', 0xd7b7ab1e, size, 32, 32, 1, 32, 4096, 0) +
            struct.pack('>8I', len(blob), 64, 17, 2, 0, 0, 0, 0) + blob)


class ProfileChecks(unittest.TestCase):
    def test_valid_boot_layout(self):
        blob = tree_blob()
        extracted, layout = boot_dtb(boot_fixture(blob))
        self.assertEqual(extracted, blob)
        self.assertEqual(layout['dtb_offset'], 8192)
        self.assertEqual(profile(extracted)['root']['compatible'], ['test,board'])

    def test_truncated_boot_dtb_rejected(self):
        with self.assertRaises(ValueError):
            boot_dtb(boot_fixture(tree_blob())[:-1])

    def test_unreviewed_header_rejected(self):
        data = bytearray(boot_fixture(tree_blob()))
        struct.pack_into('<I', data, 40, 4)
        with self.assertRaises(ValueError):
            boot_dtb(data)

    def test_valid_overlay_entry(self):
        blob = tree_blob()
        entries = overlay_entries(overlay_fixture(blob))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0], blob)
        self.assertEqual(entries[0][1]['id'], 17)

    def test_overlay_out_of_bounds_rejected(self):
        data = bytearray(overlay_fixture(tree_blob()))
        struct.pack_into('>I', data, 36, len(data))
        with self.assertRaises(ValueError):
            overlay_entries(data)

    def test_concatenated_base_trees_preserved(self):
        blob = tree_blob()
        profiles = base_profiles(blob + blob)
        self.assertEqual(len(profiles), 2)
        self.assertEqual(profiles[1]['offset'], len(blob))
        with self.assertRaises(ValueError):
            base_profiles(blob + b'not-a-tree')

    def test_invalid_fdt_length_rejected(self):
        data = bytearray(tree_blob())
        struct.pack_into('>I', data, 4, len(data) + 100)
        with self.assertRaises(ValueError):
            profile(data)


if __name__ == '__main__':
    unittest.main()
