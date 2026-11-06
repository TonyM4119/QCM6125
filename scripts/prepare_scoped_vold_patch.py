"""Prepare a separate scoped-reset patch on top of the existing native experiment."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

from prepare_vold_native_patch import EXPECTED, REVISION, extract_method, prepare, replace_once

VOLUME_BASE_SHA256 = '186837e1dafb9d78c878f0a27b9129a6ccc4256849fa2db1a7047e2d36b61cab'
METHOD = '''int VolumeManager::exresetPublic(const std::vector<std::string>& diskIds) {
    using android::vold::Disk;
    using android::vold::VolumeBase;
    if (diskIds.size() > 64) return -EINVAL;
    std::unordered_set<std::string> wanted;
    for (const auto& id : diskIds) {
        if (id.empty() || !wanted.insert(id).second) return -EINVAL;
    }
    std::vector<std::shared_ptr<Disk>> selected;
    // Caller holds the VolumeManager lock across validation and mutation.
    // Validate the entire request before the first destructive operation.
    for (const auto& disk : mDisks) {
        if (wanted.count(disk->getId()) == 0) continue;
        const int flags = disk->getFlags();
        if ((flags & (Disk::Flags::kSd | Disk::Flags::kUsb)) == 0 ||
                (flags & Disk::Flags::kEmmc) != 0 || disk->isStub()) return -EINVAL;
        const auto volumes = disk->getVolumes();
        if (volumes.empty()) return -ENODEV;
        for (const auto& volume : volumes) {
            if (volume->getType() != VolumeBase::Type::kPublic) return -EINVAL;
            if (volume->getState() != VolumeBase::State::kUnmounted) return -EBUSY;
        }
        selected.push_back(disk);
    }
    if (selected.size() != wanted.size()) return -ENODEV;
    for (const auto& disk : selected) {
        int status = disk->destroy();
        if (status != 0) return status;
        status = disk->create();
        if (status != 0) return status;
    }
    return 0;
}

'''
WRAPPER = '''binder::Status VoldNativeService::exresetPublic(const std::vector<std::string>& diskIds) {
    ENFORCE_SYSTEM_OR_ROOT;
    ACQUIRE_LOCK;

    return translate(VolumeManager::Instance()->exresetPublic(diskIds));
}

'''


def scoped_prepare(source_root, work_dir, cxx, root):
    source_root, work_dir = source_root.resolve(), work_dir.resolve()
    if (source_root == work_dir or source_root in work_dir.parents
            or work_dir in source_root.parents):
        raise ValueError('Source and output must not overlap')
    if hashlib.sha256((source_root / 'model/VolumeBase.h').read_bytes()).hexdigest() != VOLUME_BASE_SHA256:
        raise ValueError('Unreviewed VolumeBase API')
    # Bootstrap stages the already reviewed exreset implementation and checks it.
    _, base_patch = prepare(source_root, work_dir / 'bootstrap', cxx, root / 'native/vold_method_host_test.cpp')
    base = work_dir / 'bootstrap/source'
    original = {name: (base / name).read_text() for name in EXPECTED}
    updated = dict(original)
    updated['VolumeManager.h'] = replace_once(original['VolumeManager.h'], '    int exreset();',
        '    int exreset();\n    int exresetPublic(const std::vector<std::string>& diskIds);')
    updated['VoldNativeService.h'] = replace_once(original['VoldNativeService.h'],
        '    binder::Status exreset() override;',
        '    binder::Status exreset() override;\n'
        '    binder::Status exresetPublic(const std::vector<std::string>& diskIds) override;')
    anchor = 'int VolumeManager::exreset() {'
    updated['VolumeManager.cpp'] = replace_once(original['VolumeManager.cpp'], anchor, METHOD + anchor)
    updated['VolumeManager.cpp'] = replace_once(updated['VolumeManager.cpp'], '#include <array>',
        '#include <array>\n#include <unordered_set>')
    anchor = 'binder::Status VoldNativeService::exreset() {'
    updated['VoldNativeService.cpp'] = replace_once(original['VoldNativeService.cpp'], anchor, WRAPPER + anchor)
    patch = ''
    for name in updated:
        destination = work_dir / 'source' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(updated[name])
        patch += ''.join(difflib.unified_diff(original[name].splitlines(keepends=True),
            updated[name].splitlines(keepends=True), fromfile='a/' + name, tofile='b/' + name))
    method = extract_method(updated['VolumeManager.cpp'],
                            'int VolumeManager::exresetPublic(const std::vector<std::string>& diskIds)')
    (work_dir / 'scoped_reset_method.inc').write_text(method)
    executable = work_dir / 'scoped_reset_host'
    harness = root / 'native/scoped_reset_host_test.cpp'
    subprocess.run([str(cxx), '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pedantic',
                    '-I' + str(work_dir), str(harness), '-o', str(executable)],
                   check=True, capture_output=True, text=True)
    run = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
    return {'source_revision': REVISION, 'input_sha256': {**EXPECTED, 'model/VolumeBase.h': VOLUME_BASE_SHA256},
            'recipe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'base_native_patch_sha256': hashlib.sha256(base_patch.encode()).hexdigest(),
            'patch_sha256': hashlib.sha256(patch.encode()).hexdigest(),
            'method_sha256': hashlib.sha256(method.encode()).hexdigest(),
            'harness_sha256': hashlib.sha256(harness.read_bytes()).hexdigest(),
            'host_output': run.stdout.strip(),
            'limits': ['Extracted method with fake disks/volumes only; not a compiled Android daemon.',
                       'Binder authorization and actual lock macros not exercised.',
                       'Disk IDs are not generation tokens; reused IDs remain an identity race.',
                       'Failure after mutation can leave partial progress; no rollback.',
                       'No physical media, FUSE, sleep, flashing or hardware operations.']}, patch


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--cxx', default='c++', type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--patch', required=True, type=Path)
    args = parser.parse_args()
    report, patch = scoped_prepare(args.source_root, args.work_dir, args.cxx,
                                  Path(__file__).resolve().parents[1])
    for path in (args.report, args.patch):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    args.patch.write_text(patch)
    print(report['host_output'])
