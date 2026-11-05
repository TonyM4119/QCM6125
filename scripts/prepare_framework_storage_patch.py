"""Stage a review-only Android 17 public-external storage adaptation; no device I/O."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

from prepare_vold_native_patch import replace_once

REVISION = '94b4c163b7dfe5ce3607f7bb8456f9573f7de57d'
SERVICE = 'services/core/java/com/android/server/StorageManagerService.java'
CONTROLLER = 'services/core/java/com/android/server/storage/StorageSessionController.java'
CONNECTION = 'services/core/java/com/android/server/storage/StorageUserConnection.java'
EXPECTED = {
    SERVICE: '4b274514605d62962712a6ee729cbc5676c7b49897353e59ab910aec857aacb1',
    CONTROLLER: '05d0f2db32ca635e2a096ec11515e0bf201fb1869d6ead07e060aa893ed6c836',
    CONNECTION: '56ad1318a997930a608c75b4e20fccc72117060577c79853f43d1ec10ffe7d21',
}

RESET = '''    /**
     * Experimental public SD/USB preparation. Not a replacement for a full reset.
     * Snapshot validation does not serialize hotplug, user or mount transitions.
     */
    private void resetHctExternalDisks() {
        if (!mBootCompleted || !mDaemonConnected) return;

        final long token = Binder.clearCallingIdentity();
        try {
            final List<ImmutableVolumeInfo> external = new ArrayList<>();
            synchronized (mLock) {
                // Validate the complete snapshot before the first storage operation.
                for (int i = 0; i < mVolumes.size(); i++) {
                    final ImmutableVolumeInfo vol =
                            mVolumes.valueAt(i).getClonedImmutableVolumeInfo();
                    final DiskInfo disk = vol.getDisk();
                    if (disk == null || (!disk.isSd() && !disk.isUsb())) continue;
                    if (vol.getType() != VolumeInfo.TYPE_PUBLIC) {
                        throw new IllegalStateException(
                                "HCT experimental reset supports public SD/USB only");
                    }
                    if (vol.getState() == VolumeInfo.STATE_UNMOUNTED) continue;
                    if (vol.getState() != VolumeInfo.STATE_MOUNTED
                            && vol.getState() != VolumeInfo.STATE_MOUNTED_READ_ONLY) {
                        throw new IllegalStateException("External volume is transitioning");
                    }
                    external.add(vol);
                }
            }
            for (ImmutableVolumeInfo vol : external) {
                // End the corresponding session only after vold unmount returns.
                mVold.unmount(vol.getId());
                mStorageSessionController.endHctExternalSession(vol);
            }
            mVold.exreset();
        } catch (Exception e) {
            // Matches the reviewed manager-facing handled storage failure path.
            // A return here is not an acknowledgement that disks are safe.
            Slog.wtf(TAG, e);
        } finally {
            Binder.restoreCallingIdentity(token);
        }
    }

'''

END_SESSION = '''    /**
     * Review-only narrow reset helper. Does not kill MediaProvider, close the
     * shared user connection, or reset unrelated sessions. Caller unmounts first.
     */
    public void endHctExternalSession(ImmutableVolumeInfo vol)
            throws ExternalStorageServiceException {
        if (!shouldHandle(vol)) {
            throw new ExternalStorageServiceException("Storage controller is resetting");
        }
        final int userId = getConnectionUserIdForVolume(vol);
        final StorageUserConnection connection;
        synchronized (mLock) {
            connection = mConnections.get(userId);
        }
        if (connection != null) {
            // Do not call onVolumeRemove first: it removes the session before
            // removeSessionAndWait can obtain the session to end.
            connection.removeSessionAndWait(vol.getId());
        }
    }

'''


def prepare(source_root, output_root):
    source_root, output_root = source_root.resolve(), output_root.resolve()
    if (output_root == source_root or source_root in output_root.parents
            or output_root in source_root.parents):
        raise ValueError('Source and output trees must not overlap')
    original = {}
    for name, expected in EXPECTED.items():
        raw = (source_root / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Unreviewed framework input: ' + name)
        original[name] = raw.decode()
    updated = dict(original)
    anchor = ('        super.unmount_enforcePermission();\n\n'
              '        final WatchedVolumeInfo vol = findVolumeByIdOrThrow(volId);')
    updated[SERVICE] = replace_once(original[SERVICE], anchor,
        '        super.unmount_enforcePermission();\n\n'
        '        if ("hctall".equals(volId)) {\n'
        '            resetHctExternalDisks();\n'
        '            return;\n'
        '        }\n\n'
        '        final WatchedVolumeInfo vol = findVolumeByIdOrThrow(volId);')
    anchor = '    private void unmount(ImmutableVolumeInfo vol) {'
    updated[SERVICE] = replace_once(updated[SERVICE], anchor, RESET + anchor)
    anchor = '    private void initExternalStorageServiceComponent() throws ExternalStorageServiceException {'
    updated[CONTROLLER] = replace_once(original[CONTROLLER], anchor, END_SESSION + anchor)
    patch = ''.join(''.join(difflib.unified_diff(
        original[name].splitlines(keepends=True), updated[name].splitlines(keepends=True),
        fromfile='a/' + name, tofile='b/' + name)) for name in sorted(updated))
    # Validate all inputs and patch anchors before creating any output.
    for name, source in updated.items():
        path = output_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    return {
        'check_kind': 'Pinned framework staging and review patch only; Java not compiled',
        'source_revision': REVISION, 'source_tag': 'android-17.0.0_r1',
        'source_url': 'https://android.googlesource.com/platform/frameworks/base/+/' + REVISION,
        'recipe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'input_sha256': EXPECTED,
        'output_sha256': {name: hashlib.sha256(s.encode()).hexdigest() for name, s in updated.items()},
        'patch_sha256': hashlib.sha256(patch.encode()).hexdigest(),
        'limits': [
            'Not compiled against Android; no Binder, FUSE, daemon or device execution.',
            'Requires both existing vold17 patches and rebuilt clients/daemon.',
            'Public-only snapshot validation differs from legacy media-provider termination.',
            'Snapshot does not prevent hotplug, mount, daemon or user races before native reset.',
            'Native exreset still selects all SD/USB disks; snapshot is not a native safety gate.',
            'Missing sessions and vold/session teardown races need Android runtime validation.',
            'Handled failure returns normally; manager continuation is not proof of safe storage.',
            'Not ready for platform integration or device tests.'],
    }, patch


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--patch', type=Path, required=True)
    args = parser.parse_args()
    report, patch = prepare(args.source_root, args.output_root)
    for path in (args.report, args.patch):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    args.patch.write_text(patch)
