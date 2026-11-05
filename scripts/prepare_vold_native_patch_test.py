from pathlib import Path
import tempfile
import unittest
from prepare_vold_native_patch import extract_method, prepare, replace_once


class PatchChecks(unittest.TestCase):
    def test_unique_anchor(self):
        self.assertEqual(replace_once('before reset after', 'reset', 'exreset'), 'before exreset after')

    def test_reject_missing_or_ambiguous_anchor(self):
        for source in ['missing', 'reset reset']:
            with self.subTest(source=source), self.assertRaises(ValueError):
                replace_once(source, 'reset', 'exreset')

    def test_nested_method_extraction(self):
        source = 'before\nint X::method() { if (true) { return 0; } return 1; }\nafter'
        self.assertEqual(extract_method(source, 'int X::method()'),
                         'int X::method() { if (true) { return 0; } return 1; }\n')

    def test_reject_incomplete_or_ambiguous_method(self):
        for source in ['int X::method() {', 'int X::method() {} int X::method() {}']:
            with self.subTest(source=source), self.assertRaises(ValueError):
                extract_method(source, 'int X::method()')

    def test_wrong_source_fails_before_compilation_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'input'
            source.mkdir()
            (source / 'VolumeManager.cpp').write_text('unreviewed source')
            output = root / 'output'
            with self.assertRaises(ValueError):
                prepare(source, output, Path('nonexistent-compiler'), root / 'nonexistent-harness')
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
