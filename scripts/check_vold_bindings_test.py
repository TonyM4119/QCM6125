import copy
import unittest
from check_vold_bindings import check


class BindingChecks(unittest.TestCase):
    def setUp(self):
        self.reference = {'native_vold': {'sha256': 'same'}, 'vold_transaction_tables': [
            {'source_file': 'framework.jar', 'transactions': [{'method': 'exreset', 'code': 4},
                                                             {'method': 'reset', 'code': 5}]},
            {'source_file': 'services.jar', 'transactions': [{'method': 'exreset', 'code': 4},
                                                            {'method': 'reset', 'code': 5}]}]}
        self.native = {'sha256': 'same', 'native_dispatch': {
            'all_targets_are_in_function_bti_entries': True, 'entry_count': 78,
            'reviewed_cases': [{'code': 4, 'trace_labels': ['exreset']},
                               {'code': 5, 'trace_labels': ['reset']},
                               {'code': 2, 'trace_labels': []}]}}

    def test_baseline(self):
        result = check(self.reference, self.native)
        self.assertEqual(len(result['matches']), 4)
        self.assertEqual(result['unlabelled_reviewed_codes'], [2])

    def test_reject_native_code_change(self):
        changed = copy.deepcopy(self.native)
        changed['native_dispatch']['reviewed_cases'][0]['code'] = 3
        with self.assertRaises(ValueError):
            check(self.reference, changed)

    def test_reject_one_java_table_changed(self):
        changed = copy.deepcopy(self.reference)
        changed['vold_transaction_tables'][1]['transactions'][1]['code'] = 4
        with self.assertRaises(ValueError):
            check(changed, self.native)

    def test_reject_wrong_binary(self):
        changed = copy.deepcopy(self.native)
        changed['sha256'] = 'other'
        with self.assertRaises(ValueError):
            check(self.reference, changed)

    def test_reject_ambiguous_label(self):
        changed = copy.deepcopy(self.native)
        changed['native_dispatch']['reviewed_cases'][0]['trace_labels'].append('shutdown')
        with self.assertRaises(ValueError):
            check(self.reference, changed)


if __name__ == '__main__':
    unittest.main()
