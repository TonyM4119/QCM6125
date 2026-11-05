"""Check tracked patch/report consistency without firmware or a platform checkout."""
import hashlib
import json
from pathlib import Path

from check_vold_bindings import check as check_bindings
from experiment_vold_extension import EXPECTED_FILES, REVISION
from prepare_vold_native_patch import EXPECTED, extract_method


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root):
    evidence = root / 'evidence'
    experiment = root / 'platform/experiments/vold17'
    extension = json.loads((evidence / 'vold17-extension-experiment.json').read_text())
    native = json.loads((evidence / 'vold17-native-patch.json').read_text())
    if extension['source_revision'] != REVISION or native['source_revision'] != REVISION:
        raise ValueError('Source revisions differ from the pinned experiment')
    if extension['source_files'] != EXPECTED_FILES or native['input_sha256'] != EXPECTED:
        raise ValueError('Recorded source fingerprints differ from recipe inputs')
    if extension['patch_sha256'] != digest(experiment / 'append-exreset.patch'):
        raise ValueError('AIDL patch differs from its report')
    native_patch = experiment / 'native-exreset.patch'
    if native['patch_sha256'] != digest(native_patch):
        raise ValueError('Native patch differs from its report')
    if native['host_harness_sha256'] != digest(root / 'native/vold_method_host_test.cpp'):
        raise ValueError('Host harness changed since the recorded method test')
    # All lines of this added method are additions in the VolumeManager.cpp hunk.
    additions, current_file = [], None
    for line in native_patch.read_text().splitlines(keepends=True):
        if line.startswith('+++ b/'):
            current_file = line[6:].strip()
        elif current_file == 'VolumeManager.cpp' and line.startswith('+'):
            additions.append(line[1:])
    method = extract_method(''.join(additions), 'int VolumeManager::exreset()')
    if native['extracted_method_sha256'] != hashlib.sha256(method.encode()).hexdigest():
        raise ValueError('Tested method does not match the native patch additions')

    reference_path = evidence / 'malaysk-sleep-contract.json'
    native_path = evidence / 'working-vold-native.json'
    bindings = json.loads((evidence / 'vold-native-java-bindings.json').read_text())
    if bindings['reference_sha256'] != digest(reference_path) or bindings['native_report_sha256'] != digest(native_path):
        raise ValueError('Binding report inputs changed')
    recomputed = check_bindings(json.loads(reference_path.read_text()), json.loads(native_path.read_text()))
    for key, value in recomputed.items():
        if bindings[key] != value:
            raise ValueError('Stored binding result differs: ' + key)
    upstream = json.loads((evidence / 'vold-transaction-comparison.json').read_text())
    if upstream['reference_sha256'] != digest(reference_path):
        raise ValueError('Upstream transaction comparison references stale recovered data')
    return ('Tracked AIDL/native patches, tested-method body, harness and storage binding reports agree. '
            'Consistency check only; no platform build or device validation.')


if __name__ == '__main__':
    print(check(Path(__file__).resolve().parents[1]))
