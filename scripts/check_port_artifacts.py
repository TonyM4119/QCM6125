"""Check tracked patch/report consistency without firmware or a platform checkout."""
import hashlib
import json
from pathlib import Path

from check_vold_bindings import check as check_bindings
from experiment_vold_extension import EXPECTED_FILES, REVISION
from prepare_vold_native_patch import EXPECTED, extract_method
from prepare_framework_storage_patch import EXPECTED as FRAMEWORK_INPUTS, REVISION as FRAMEWORK_REVISION
from prepare_scoped_vold_patch import METHOD as SCOPED_METHOD, VOLUME_BASE_SHA256
from prepare_storage_ack_patch import INTERFACE_SHA256


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
    framework = json.loads((evidence / 'framework17-storage-patch.json').read_text())
    host = json.loads((evidence / 'framework17-storage-host.json').read_text())
    if framework['source_revision'] != FRAMEWORK_REVISION or framework['input_sha256'] != FRAMEWORK_INPUTS:
        raise ValueError('Framework source pins changed')
    if framework['patch_sha256'] != digest(experiment / 'framework-storage.patch'):
        raise ValueError('Framework patch differs from its report')
    if framework['recipe_sha256'] != digest(root / 'scripts/prepare_framework_storage_patch.py'):
        raise ValueError('Framework patch recipe changed since staging')
    for name, value in host['source_file_sha256'].items():
        if framework['output_sha256'][name] != value:
            raise ValueError('Java host check used a different staged framework file')
    if host['host_recipe_sha256'] != digest(root / 'scripts/check_framework_storage_host.py'):
        raise ValueError('Java host recipe changed since recorded run')
    scoped_native = json.loads((evidence / 'vold17-scoped-native.json').read_text())
    scoped_aidl = json.loads((evidence / 'vold17-scoped-aidl.json').read_text())
    scoped_framework = json.loads((evidence / 'framework17-scoped-patch.json').read_text())
    scoped_host = json.loads((evidence / 'framework17-scoped-host.json').read_text())
    for report, name in [(scoped_native,'scoped-native.patch'), (scoped_aidl,'scoped-aidl.patch'),
                         (scoped_framework,'scoped-framework.patch')]:
        if report['patch_sha256'] != digest(experiment / name):
            raise ValueError('Scoped patch changed: ' + name)
    if scoped_native['input_sha256'] != {**EXPECTED, 'model/VolumeBase.h': VOLUME_BASE_SHA256}:
        raise ValueError('Scoped native inputs changed')
    if scoped_native['base_native_patch_sha256'] != native['patch_sha256']:
        raise ValueError('Scoped native patch has a different base')
    scoped_method = extract_method(SCOPED_METHOD,
        'int VolumeManager::exresetPublic(const std::vector<std::string>& diskIds)')
    if scoped_native['method_sha256'] != hashlib.sha256(scoped_method.encode()).hexdigest():
        raise ValueError('Scoped tested method differs from recipe')
    if scoped_native['recipe_sha256'] != digest(root / 'scripts/prepare_scoped_vold_patch.py'):
        raise ValueError('Scoped native recipe changed')
    if scoped_native['harness_sha256'] != digest(root / 'native/scoped_reset_host_test.cpp'):
        raise ValueError('Scoped native harness changed')
    if scoped_aidl['source_files'] != EXPECTED_FILES or scoped_aidl['source_revision'] != REVISION:
        raise ValueError('Scoped AIDL source pins changed')
    if (scoped_aidl['scoped_extension_code'] != 86 or scoped_aidl['extension_code'] != 85
            or scoped_aidl['preserved_upstream_transaction_count'] != 84):
        raise ValueError('Scoped transaction IDs changed')
    if (scoped_framework['input_sha256'] != FRAMEWORK_INPUTS
            or scoped_framework['source_revision'] != FRAMEWORK_REVISION
            or scoped_framework['scope_mode'] != 'explicit-disk-ids'
            or scoped_framework['recipe_sha256'] != framework['recipe_sha256']):
        raise ValueError('Scoped framework source/recipe changed')
    if scoped_host['host_recipe_sha256'] != host['host_recipe_sha256']:
        raise ValueError('Scoped Java host recipe changed')
    for name, value in scoped_host['source_file_sha256'].items():
        if scoped_framework['output_sha256'][name] != value:
            raise ValueError('Scoped Java host check used different staged files')
    ack = json.loads((evidence / 'framework17-storage-ack.json').read_text())
    ack_host = json.loads((evidence / 'framework17-storage-ack-host.json').read_text())
    if (ack['source_revision'] != FRAMEWORK_REVISION or ack['interface_sha256'] != INTERFACE_SHA256
            or ack['base_framework_patch_sha256'] != scoped_framework['patch_sha256']):
        raise ValueError('Storage acknowledgement source/base patch changed')
    if (ack['ack_transaction_code'] != 101 or ack['preserved_standard_method_count'] != 55):
        raise ValueError('Storage acknowledgement transaction allocation changed')
    if ack['patch_sha256'] != digest(experiment / 'storage-ack.patch'):
        raise ValueError('Storage acknowledgement patch changed')
    if ack['recipe_sha256'] != digest(root / 'scripts/prepare_storage_ack_patch.py'):
        raise ValueError('Storage acknowledgement recipe changed')
    if ack_host['host_recipe_sha256'] != host['host_recipe_sha256']:
        raise ValueError('Storage acknowledgement host recipe changed')
    for name, value in ack_host['source_file_sha256'].items():
        if ack['output_sha256'][name] != value:
            raise ValueError('Storage acknowledgement host check used different files')
    return ('Tracked AIDL/native/framework patches, host-check inputs and storage binding reports agree. '
            'Consistency check only; no platform build or device validation.')


if __name__ == '__main__':
    print(check(Path(__file__).resolve().parents[1]))
