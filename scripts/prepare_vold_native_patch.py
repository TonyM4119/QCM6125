"""Prepare and host-check an experimental native reset patch against pinned Android 17 files."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

REVISION = '6d20a0078c2bcaa2499dc5d032f337bfe1182d9e'
EXPECTED = {
    'VolumeManager.cpp': '35526fed10321312f8180d0d380a2cadef38c0dd9720a438253058dcd387d8e8',
    'VolumeManager.h': 'e682e153f0b6c47196729683082cd646a7e54678ba0835eef9944e834f2ad72d',
    'VoldNativeService.cpp': '6481fce1ef520fdda7a9b17f514d9a427292336f5372c6f283dac9ca5e36587f',
    'VoldNativeService.h': '2bbee5a6cd1994ebb788c95eb664081b50bfd431a3692f78293f445ef436cf59',
    'model/Disk.h': 'adfd37b4f31cfb5896e60bad635e0c42637d47fcfa80f7f08606c0e614e887c1',
}
METHOD = '''int VolumeManager::exreset() {
    constexpr int kExternalMask = android::vold::Disk::Flags::kSd |
                                  android::vold::Disk::Flags::kUsb;
    for (const auto& disk : mDisks) {
        if ((disk->getFlags() & kExternalMask) == 0) continue;
        disk->destroy();
        disk->create();
    }
    return 0;
}

'''
WRAPPER = '''binder::Status VoldNativeService::exreset() {
    ENFORCE_SYSTEM_OR_ROOT;
    ACQUIRE_LOCK;

    return translate(VolumeManager::Instance()->exreset());
}

'''


def replace_once(source, anchor, replacement):
    if source.count(anchor) != 1:
        raise ValueError('Patch anchor absent or ambiguous')
    return source.replace(anchor, replacement, 1)


def extract_method(source, signature):
    if source.count(signature) != 1:
        raise ValueError('Method signature absent or ambiguous')
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    for at in range(opening + 1, len(source)):
        depth += (source[at] == '{') - (source[at] == '}')
        if depth == 0:
            return source[start:at + 1] + '\n'
    raise ValueError('Method braces are incomplete')


def prepare(source_root, work_dir, cxx, harness_path):
    source_root, work_dir = source_root.resolve(), work_dir.resolve()
    if work_dir == source_root or source_root in work_dir.parents:
        raise ValueError('Output must remain outside the input source tree')
    original = {}
    for name, expected in EXPECTED.items():
        raw = (source_root / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Pinned native source differs: ' + name)
        original[name] = raw.decode()
    updated = dict(original)
    updated['VolumeManager.h'] = replace_once(original['VolumeManager.h'], '    int reset();',
        '    int reset();\n    /* Reset external SD/USB disks for HCT sleep preparation. */\n    int exreset();')
    anchor = '// Can be called twice (sequentially) during shutdown. should be safe for that.\nint VolumeManager::shutdown() {'
    updated['VolumeManager.cpp'] = replace_once(original['VolumeManager.cpp'], anchor, METHOD + anchor)
    updated['VoldNativeService.h'] = replace_once(original['VoldNativeService.h'], '    binder::Status reset();',
        '    binder::Status reset();\n    binder::Status exreset() override;')
    anchor = 'binder::Status VoldNativeService::shutdown() {'
    updated['VoldNativeService.cpp'] = replace_once(original['VoldNativeService.cpp'], anchor, WRAPPER + anchor)
    patch = ''
    for name in sorted(updated):
        destination = work_dir / 'source' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(updated[name])
        if updated[name] != original[name]:
            patch += ''.join(difflib.unified_diff(original[name].splitlines(keepends=True),
                                                 updated[name].splitlines(keepends=True),
                                                 fromfile='a/' + name, tofile='b/' + name))
    method = extract_method(updated['VolumeManager.cpp'], 'int VolumeManager::exreset()')
    method_path = work_dir / 'vold_exreset_method.inc'
    method_path.write_text(method)
    compiler = Path(shutil.which(str(cxx)) or str(cxx)).resolve()
    executable = work_dir / 'native_method_host_test'
    subprocess.run([str(compiler), '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pedantic',
                    '-I' + str(work_dir), str(harness_path.resolve()), '-o', str(executable)],
                   check=True, capture_output=True, text=True)
    test = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
    return {'check_kind': 'Pinned native patch and extracted-method host test with fake disk objects',
            'source_revision': REVISION, 'input_sha256': EXPECTED,
            'output_sha256': {name: hashlib.sha256(text.encode()).hexdigest() for name, text in updated.items()},
            'patch_sha256': hashlib.sha256(patch.encode()).hexdigest(),
            'extracted_method_sha256': hashlib.sha256(method.encode()).hexdigest(),
            'host_harness_sha256': hashlib.sha256(harness_path.read_bytes()).hexdigest(),
            'host_compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
            'host_test_output': test.stdout.strip(),
            'limits': ['Actual patched method body compiled in a fake-object harness only.',
                       'Full VoldNativeService/VolumeManager translation units and Android 17 daemon not compiled.',
                       'Requires the separate appended AIDL method and regeneration/rebuilding of affected components.',
                       'Framework storage/sleep routing, native side effects and runtime validation remain incomplete.',
                       'No firmware executable, physical disk, Binder, sleep or flashing operation executed.']}, patch


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--cxx', default='c++', type=Path)
    parser.add_argument('--harness', default=Path(__file__).resolve().parents[1] / 'native/vold_method_host_test.cpp', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--patch', required=True, type=Path)
    args = parser.parse_args()
    report, patch = prepare(args.source_root, args.work_dir, args.cxx, args.harness)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.patch.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    args.patch.write_text(patch)
