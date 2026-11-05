"""Check that transaction extraction rejects misleading generated constants."""
import unittest
from compare_vold_transactions import generated_constants


class ConstantChecks(unittest.TestCase):
    def test_first_call_offset(self):
        self.assertEqual(generated_constants('static final int TRANSACTION_reset = '
                         '(android.os.IBinder.FIRST_CALL_TRANSACTION + 3);'), {'reset': 4})

    def test_reject_unparsed_expression(self):
        with self.assertRaises(ValueError):
            generated_constants('static final int TRANSACTION_reset = unknown;')

    def test_reject_duplicate_name(self):
        line = 'static final int TRANSACTION_reset = (android.os.IBinder.FIRST_CALL_TRANSACTION + 3);'
        with self.assertRaises(ValueError):
            generated_constants(line + line)

    def test_reject_duplicate_code(self):
        with self.assertRaises(ValueError):
            generated_constants('static final int TRANSACTION_reset = '
                                '(android.os.IBinder.FIRST_CALL_TRANSACTION + 3);'
                                'static final int TRANSACTION_shutdown = '
                                '(android.os.IBinder.FIRST_CALL_TRANSACTION + 3);')


if __name__ == '__main__':
    unittest.main()
