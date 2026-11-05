import unittest
from experiment_vold_extension import append_method, cpp_constants, verify_mappings


class ExtensionChecks(unittest.TestCase):
    def setUp(self):
        self.base = {'reset': 4, 'shutdown': 5}
        self.extended = {**self.base, 'exreset': 6}

    def test_append_before_interface_close(self):
        source = 'interface IVold {\n    void reset();\n}\n'
        result = append_method(source)
        self.assertEqual(result.count('void exreset();'), 1)
        self.assertTrue(result.rstrip().endswith('}'))
        self.assertLess(result.index('void reset();'), result.index('void exreset();'))

    def test_reject_already_extended(self):
        with self.assertRaises(ValueError):
            append_method('interface IVold { void exreset(); }')

    def test_baseline_preserved(self):
        result = verify_mappings(self.base, self.extended, self.base, self.extended)
        self.assertEqual(result['preserved_upstream_transaction_count'], 2)
        self.assertEqual(result['extension_code'], 6)

    def test_reject_shifted_existing_code(self):
        changed = {**self.extended, 'reset': 3}
        with self.assertRaises(ValueError):
            verify_mappings(self.base, changed, self.base, changed)

    def test_reject_language_mismatch(self):
        with self.assertRaises(ValueError):
            verify_mappings(self.base, self.extended, self.base, {**self.extended, 'exreset': 7})

    def test_reject_unexpected_extra_method(self):
        changed = {**self.extended, 'other': 7}
        with self.assertRaises(ValueError):
            verify_mappings(self.base, changed, self.base, changed)

    def test_cpp_constant_offset_and_rejection(self):
        self.assertEqual(cpp_constants('static constexpr uint32_t TRANSACTION_reset = '
                                     '::android::IBinder::FIRST_CALL_TRANSACTION + 3;'), {'reset': 4})
        with self.assertRaises(ValueError):
            cpp_constants('static constexpr uint32_t TRANSACTION_reset = unknown;')


if __name__ == '__main__':
    unittest.main()
