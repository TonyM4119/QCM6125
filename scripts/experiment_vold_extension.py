"""Generate an isolated Android 17 IVold extension experiment; no platform/device build."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from compare_vold_transactions import generated_constants

REVISION = '6d20a0078c2bcaa2499dc5d032f337bfe1182d9e'
EXPECTED_FILES = {
    'IVold.aidl': '8e81eac438a1b468c7bccf1d3cd49b0a824ea454b87544475bf1bd4da5fcf1f6',
    'IVoldListener.aidl': '0e5410fd8f0dae3f5dcfaa480e9c775937266d0149976af763e264e0c4c43e85',
    'IVoldMountCallback.aidl': '0eb6fe4e00132338c5b65e67c32f00dab8a76974324f5bd0981dbe7f13ab74d9',
    'IVoldTaskListener.aidl': '38329ac1b6e51232213cd5713952f11a600004cd21a5bf68a20f9a64a5842cb5',
}
FORWARDS = ('parcelable android.os.PersistableBundle cpp_header "binder/PersistableBundle.h";\n'
            'parcelable android.os.incremental.IncrementalFileSystemControlParcel '
            'cpp_header "android/os/incremental/IncrementalFileSystemControlParcel.h";\n')


def append_method(source):
    if re.search(r'\bexreset\s*\(', source) or not source.rstrip().endswith('}'):
        raise ValueError('Expected unextended interface ending in a closing brace')
    at = source.rfind('}')
    return source[:at] + ('\n    // Experimental HCT external-disk reset; native implementation required.\n'
                         '    void exreset();\n') + source[at:]


def cpp_constants(source):
    declarations = re.findall(r'static constexpr uint32_t TRANSACTION_(\w+)\s*=\s*([^;]+);', source)
    if not declarations:
        raise ValueError('No generated C++ transaction constants')
    result = {}
    for name, expression in declarations:
        match = re.fullmatch(r'::android::IBinder::FIRST_CALL_TRANSACTION \+ (\d+)', expression.strip())
        if not match or name in result:
            raise ValueError('Unsupported/duplicate C++ constant')
        result[name] = int(match[1]) + 1
    if len(set(result.values())) != len(result):
        raise ValueError('Duplicate C++ transaction codes')
    return result


def verify_mappings(baseline_java, extension_java, baseline_cpp, extension_cpp):
    if not baseline_java or 'exreset' in baseline_java or baseline_java != baseline_cpp:
        raise ValueError('Invalid or inconsistent baseline')
    if extension_java != extension_cpp:
        raise ValueError('Java/C++ extension codes differ')
    if extension_java.keys() - baseline_java.keys() != {'exreset'}:
        raise ValueError('Unexpected extension method set')
    if any(extension_java.get(name) != code for name, code in baseline_java.items()):
        raise ValueError('Existing upstream transaction was removed or renumbered')
    if extension_java['exreset'] != max(baseline_java.values()) + 1:
        raise ValueError('Extension is not appended after existing codes')
    return {'upstream_method_count': len(baseline_java), 'extended_method_count': len(extension_java),
            'preserved_upstream_transaction_count': len(baseline_java),
            'extension_code': extension_java['exreset'], 'java_cpp_codes_match': True}


def experiment(source_root, work_dir, aidl, compiler_label):
    source_root, work_dir = source_root.resolve(), work_dir.resolve()
    if work_dir == source_root or source_root in work_dir.parents:
        raise ValueError('Experiment outputs must stay outside the input source tree')
    files = {}
    for name, expected in EXPECTED_FILES.items():
        raw = (source_root / 'android/os' / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Pinned source differs: ' + name)
        files[name] = raw
    original = files['IVold.aidl'].decode()
    patched = append_method(original)
    work_dir.mkdir(parents=True, exist_ok=True)
    forwards = work_dir / 'compiler-types.aidl'
    forwards.write_text(FORWARDS)
    aidl_path = Path(shutil.which(str(aidl)) or str(aidl)).resolve()
    mappings, generated_hashes = {}, {}
    for variant in ('baseline', 'extended'):
        root = work_dir / variant
        include = root / 'source'
        package = include / 'android/os'
        package.mkdir(parents=True, exist_ok=True)
        for name, raw in files.items():
            (package / name).write_bytes(patched.encode() if variant == 'extended' and name == 'IVold.aidl' else raw)
        for language in ('java', 'cpp'):
            output, headers = root / language, root / 'headers'
            command = [str(aidl_path), '--lang=' + language, '--min_sdk_version=33', '--omit_invocation',
                       '-I' + str(include), '-p' + str(forwards), '-o' + str(output)]
            if language == 'cpp':
                command.append('-h' + str(headers))
            command.append(str(package / 'IVold.aidl'))
            subprocess.run(command, check=True, capture_output=True, text=True)
            generated = output / 'android/os/IVold.java' if language == 'java' else headers / 'android/os/BnVold.h'
            raw = generated.read_bytes()
            mappings[(variant, language)] = (generated_constants if language == 'java' else cpp_constants)(raw.decode())
            generated_hashes[variant + '_' + language] = hashlib.sha256(raw).hexdigest()
    checks = verify_mappings(mappings['baseline', 'java'], mappings['extended', 'java'],
                             mappings['baseline', 'cpp'], mappings['extended', 'cpp'])
    if checks['upstream_method_count'] != 84:
        raise ValueError('Unexpected Android 17 source method count')
    patch = ''.join(difflib.unified_diff(original.splitlines(keepends=True), patched.splitlines(keepends=True),
                                       fromfile='a/binder/android/os/IVold.aidl',
                                       tofile='b/binder/android/os/IVold.aidl'))
    result = {'check_kind': 'Isolated Java/C++ AIDL generation and transaction preservation experiment',
              'source_revision': REVISION, 'source_tag': 'android-17.0.0_r1',
              'source_files': EXPECTED_FILES, 'compiler_label': compiler_label,
              'compiler_sha256': hashlib.sha256(aidl_path.read_bytes()).hexdigest(),
              'compiler_forward_declarations_sha256': hashlib.sha256(FORWARDS.encode()).hexdigest(),
              'extended_aidl_sha256': hashlib.sha256(patched.encode()).hexdigest(),
              'patch_sha256': hashlib.sha256(patch.encode()).hexdigest(),
              'generated_file_sha256': generated_hashes, **checks,
              'limits': ['Code generation only using the named local compiler; no Android 17 platform compilation.',
                         'Compiler-only Parcelable forwards are not runtime implementations.',
                         'No native service implementation, framework routing or complete Parcel compatibility check.',
                         'Extended code 85 differs from old HCT code 4; all affected clients/servers must be rebuilt consistently.',
                         'Input source files unchanged; no device, Binder, storage or flashing operation.']}
    return result, patch


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--aidl', required=True, type=Path)
    parser.add_argument('--compiler-label', required=True)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--patch', required=True, type=Path)
    args = parser.parse_args()
    report, patch = experiment(args.source_root, args.work_dir, args.aidl, args.compiler_label)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.patch.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    args.patch.write_text(patch)
