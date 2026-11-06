"""Fail before generation on an unreviewed interface or overlapping output tree."""
from pathlib import Path
import tempfile
import unittest
from prepare_storage_ack_patch import INTERFACE, prepare_ack


class AckGuards(unittest.TestCase):
    def test_wrong_interface_fails_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';output=root/'output'
            path=source/INTERFACE;path.parent.mkdir(parents=True)
            path.write_text('unreviewed storage interface')
            with self.assertRaisesRegex(ValueError,'Unreviewed storage Binder interface'):
                prepare_ack(source,output,Path('missing-aidl'))
            self.assertFalse(output.exists())

    def test_overlapping_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for source,output in [(root,root),(root,root/'out'),(root/'in',root)]:
                with self.subTest(source=source,output=output):
                    with self.assertRaisesRegex(ValueError,'must not overlap'):
                        prepare_ack(source,output,Path('missing-aidl'))


if __name__ == '__main__':
    unittest.main()
