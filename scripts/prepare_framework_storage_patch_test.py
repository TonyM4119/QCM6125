"""Verify that unreviewed source/output layouts fail before staging anything."""
from pathlib import Path
import tempfile
import unittest

from prepare_framework_storage_patch import SERVICE, prepare


class SourceGuards(unittest.TestCase):
    def test_unreviewed_source_creates_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input'
            path = source / SERVICE
            path.parent.mkdir(parents=True)
            path.write_text('unreviewed Java')
            output = Path(directory) / 'output'
            with self.assertRaisesRegex(ValueError, 'Unreviewed framework input'):
                prepare(source, output)
            self.assertFalse(output.exists())
            self.assertEqual(path.read_text(), 'unreviewed Java')

    def test_overlapping_output_rejected_before_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source, output in [(root, root), (root, root / 'out'), (root / 'in', root)]:
                with self.subTest(source=source, output=output):
                    with self.assertRaisesRegex(ValueError, 'must not overlap'):
                        prepare(source, output)


if __name__ == '__main__':
    unittest.main()
