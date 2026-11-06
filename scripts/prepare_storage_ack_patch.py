"""Add an explicit storage-preparation acknowledgement to the scoped framework proposal."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess

from compare_vold_transactions import generated_constants
from prepare_framework_storage_patch import SERVICE, REVISION, prepare
from prepare_vold_native_patch import replace_once

INTERFACE = 'core/java/android/os/storage/IStorageManager.aidl'
INTERFACE_SHA256 = '01c230e09901621cae04f437331b5a60d47c7a09c5cc335a5d32f5d246a0b6c4'
ENTRY = '''    @android.annotation.EnforcePermission(android.Manifest.permission.MOUNT_UNMOUNT_FILESYSTEMS)
    @Override
    public boolean prepareHctExternalDisksForSleep() {
        super.prepareHctExternalDisksForSleep_enforcePermission();
        return resetHctExternalDisks();
    }

'''


def prepare_ack(source_root, work_dir, aidl):
    source_root, work_dir = source_root.resolve(), work_dir.resolve()
    if source_root == work_dir or source_root in work_dir.parents or work_dir in source_root.parents:
        raise ValueError('Source and output must not overlap')
    raw = (source_root / INTERFACE).read_bytes()
    if hashlib.sha256(raw).hexdigest() != INTERFACE_SHA256:
        raise ValueError('Unreviewed storage Binder interface')
    original_aidl = raw.decode()
    offsets = [int(n) for n in re.findall(r'=\s*(\d+)\s*;', original_aidl)]
    if not offsets or max(offsets) != 99:
        raise ValueError('Unexpected explicit storage transaction allocation')
    base_report, _ = prepare(source_root, work_dir / 'source', scoped=True)
    original_service = (work_dir / 'source' / SERVICE).read_text()
    service = replace_once(original_service, '    private void resetHctExternalDisks() {',
                           '    private boolean resetHctExternalDisks() {')
    service = replace_once(service, '        if (!mBootCompleted || !mDaemonConnected) return;',
                          '        if (!mBootCompleted || !mDaemonConnected) return false;')
    anchor = '            mVold.exresetPublic(diskIds.toArray(new String[0]));'
    service = replace_once(service, anchor, anchor + '\n            return true;')
    anchor = '            // A return here is not an acknowledgement that disks are safe.\n            Slog.wtf(TAG, e);'
    service = replace_once(service, anchor,
        '            // Failure is exposed only through the new boolean endpoint.\n'
        '            Slog.wtf(TAG, e);\n            return false;')
    anchor = ('    @android.annotation.EnforcePermission(android.Manifest.permission.MOUNT_UNMOUNT_FILESYSTEMS)\n'
              '    @Override\n    public void unmount(String volId) {')
    service = replace_once(service, anchor, ENTRY + anchor)
    at = original_aidl.rfind('}')
    extended_aidl = original_aidl[:at] + (
        '\n    // Experimental acknowledgement for a replacement HCT sleep coordinator.\n'
        '    @EnforcePermission("MOUNT_UNMOUNT_FILESYSTEMS")\n'
        '    boolean prepareHctExternalDisksForSleep() = 100;\n') + original_aidl[at:]
    patch = ''
    for name, before, after in [(SERVICE,original_service,service),
                                (INTERFACE,original_aidl,extended_aidl)]:
        p = work_dir / 'source' / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(after)
        patch += ''.join(difflib.unified_diff(before.splitlines(keepends=True),
            after.splitlines(keepends=True), fromfile='a/'+name,tofile='b/'+name))
    # Compiler-only declarations preserve each imported type's interface/parcelable kind.
    interfaces = {'IPackageMoveObserver','IVoldTaskListener','IStorageEventListener',
                  'IStorageShutdownObserver','IObbActionListener'}
    forwards = ''
    for name in re.findall(r'^import ([\w.]+);',original_aidl,re.M):
        kind = 'interface' if name.rsplit('.',1)[1] in interfaces else 'parcelable'
        forwards += kind + ' ' + name + ';\n'
    types = work_dir / 'compiler-types.aidl'
    types.write_text(forwards)
    maps, fingerprints = {}, {}
    for variant, content in [('baseline',original_aidl),('ack',extended_aidl)]:
        input_path = work_dir / variant / INTERFACE
        input_path.parent.mkdir(parents=True,exist_ok=True)
        input_path.write_text(content)
        output = work_dir / variant / 'java'
        subprocess.run([str(aidl),'--lang=java','--min_sdk_version=33','--omit_invocation',
                        '-I'+str(work_dir/variant/'core/java'),
                        '-p'+str(types),'-o'+str(output),str(input_path)],
                       check=True,capture_output=True,text=True)
        generated = output / 'android/os/storage/IStorageManager.java'
        java = generated.read_text()
        maps[variant] = generated_constants(java)
        fingerprints[variant] = hashlib.sha256(generated.read_bytes()).hexdigest()
        if variant == 'ack' and ('protected void prepareHctExternalDisksForSleep_enforcePermission()'
                                  not in java):
            raise ValueError('Generated permission helper missing')
    old, new = maps['baseline'], maps['ack']
    if (new.keys() - old.keys() != {'prepareHctExternalDisksForSleep'}
            or any(new.get(name)!=code for name,code in old.items())
            or new['prepareHctExternalDisksForSleep'] != 101):
        raise ValueError('Storage Binder transaction allocation changed')
    return {'source_revision':REVISION,'interface_sha256':INTERFACE_SHA256,
            'base_framework_patch_sha256':base_report['patch_sha256'],
            'recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'patch_sha256':hashlib.sha256(patch.encode()).hexdigest(),
            'preserved_standard_method_count':len(old),'ack_transaction_code':101,
            'generated_java_sha256':fingerprints,
            'compiler_forwards_sha256':hashlib.sha256(forwards.encode()).hexdigest(),
            'output_sha256':{name:hashlib.sha256((work_dir/'source'/name).read_bytes()).hexdigest()
                             for name in [*base_report['output_sha256'],INTERFACE]},
            'limits':['AIDL generation with compiler-only type forwards; no full Android compilation.',
                      'Boolean success is not a lease across later mount or power changes.',
                      'Legacy unmount callers still ignore the boolean result.',
                      'Replacement manager integration and sleep gating remain unimplemented.',
                      'No native IMountService client wrapper for the new Java-only method.',
                      'No Binder, FUSE, storage, sleep or device operation executed.']},patch


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',required=True,type=Path)
    parser.add_argument('--work-dir',required=True,type=Path)
    parser.add_argument('--aidl',required=True,type=Path)
    parser.add_argument('--report',required=True,type=Path)
    parser.add_argument('--patch',required=True,type=Path)
    args=parser.parse_args()
    report,patch=prepare_ack(args.source_root,args.work_dir,args.aidl)
    for path in [args.report,args.patch]: path.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n');args.patch.write_text(patch)
    print(str(report['preserved_standard_method_count'])+' standard storage Binder IDs preserved; ack code 101.')
