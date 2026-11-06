"""Source/output guards for the scoped native proposal; no platform or device I/O."""
from pathlib import Path
import tempfile
import unittest
from prepare_scoped_vold_patch import scoped_prepare


class SourceGuards(unittest.TestCase):
    def test_wrong_volume_api_fails_without_output_or_compiler(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / 'source', root / 'output'
            (source / 'model').mkdir(parents=True)
            (source / 'model/VolumeBase.h').write_text('unreviewed API')
            with self.assertRaisesRegex(ValueError, 'Unreviewed VolumeBase API'):
                scoped_prepare(source, output, Path('missing-compiler'), root)
            self.assertFalse(output.exists())

    def test_overlapping_paths_fail_before_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source, output in [(root,root), (root,root/'out'), (root/'in',root)]:
                with self.subTest(source=source,output=output):
                    with self.assertRaisesRegex(ValueError,'must not overlap'):
                        scoped_prepare(source, output, Path('missing-compiler'), root)


if __name__ == '__main__':
    unittest.main()
