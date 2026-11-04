"""Regression checks using generated Java as a local fixture, never Android I/O."""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from check_binder_contract import verify


class ContractChecks(unittest.TestCase):
    generated = None
    reference = None

    def test_reference_matches(self):
        self.assertEqual(len(verify(self.generated, self.reference)), 27)

    def reject_mutation(self, kind):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'generated'
            shutil.copytree(self.generated, root)
            if kind == 'callback_flags':
                path = root / 'android/microntek/ICarManageCallback.java'
                source = path.read_text()
                self.assertIn('android.os.IBinder.FLAG_ONEWAY', source)
                source = source.replace('android.os.IBinder.FLAG_ONEWAY', '0')
            else:
                path = root / 'android/microntek/ICarService.java'
                source = path.read_text()
                if kind == 'transaction_number':
                    source, count = re.subn(
                        r'(TRANSACTION_setParameters\s*=\s*\(android\.os\.IBinder\.FIRST_CALL_TRANSACTION\s*\+\s*)16',
                        r'\g<1>99', source)
                    self.assertEqual(count, 1)
                else:
                    self.assertIn('_data.writeString(', source)
                    source = source.replace('_data.writeString(', '_data.writeByte(', 1)
            path.write_text(source)
            with self.assertRaises(ValueError):
                verify(root, self.reference)

    def test_wrong_callback_direction_rejected(self):
        self.reject_mutation('callback_flags')

    def test_wrong_transaction_number_rejected(self):
        self.reject_mutation('transaction_number')

    def test_wrong_request_operation_rejected(self):
        self.reject_mutation('request_operation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    ContractChecks.generated = args.generated
    ContractChecks.reference = json.loads(args.reference.read_text())
    unittest.main(argv=['check_binder_contract_test'])
