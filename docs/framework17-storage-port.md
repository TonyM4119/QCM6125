# Android 17 framework storage adaptation

Follow-up: [the scoped reset experiment](scoped-storage-reset.md) adds explicit native disk selection and strict missing-session handling. The original patch below is retained as the first proposal; the scoped framework patch is its separate replacement variant. Neither is ready for device use.

The published environment now permits official source reads. The Android 17 r1 frameworks/base tag resolves to `94b4c163b7dfe5ce3607f7bb8456f9573f7de57d`. [Source fingerprints](../evidence/android17-official-source.json) record the small inspected files; this is not a full checkout. The official vold tag resolves to the same `6d20a0078c2bcaa2499dc5d032f337bfe1182d9e` used by the existing experiment. All nine fetched vold files match the pinned hashes, and regeneration produced byte-identical native and AIDL patches.

## Why the old helper cannot be copied directly

The pinned StorageManagerService no longer has `killMediaProvider`. StorageSessionController.onReset unmounts every tracked session and closes user connections. It is broader than an external SD/USB reset.

Killing the process is also not a narrow substitute. StorageUserConnection's service-disconnection path calls resetUserSessions; when sessions remain, that calls StorageManagerInternal.resetUser. The pinned StorageManagerService implementation explicitly queues H_RESET to reset everything. This is a source-level possible path, not an observed device execution.

## Review-only patch

[framework-storage.patch](../platform/experiments/vold17/framework-storage.patch) modifies StorageManagerService and StorageSessionController at that pinned revision. It is an experimental adaptation proposal, not ready for platform integration.

- Keep the existing generated unmount permission enforcement before testing `hctall`. Other IDs retain their existing lookup/unmount path.
- Return before work unless boot and daemon readiness flags are set.
- Clear Binder calling identity for the privileged internal operation and restore it in finally.
- Under the existing volume lock, clone a volume snapshot and validate physical SD/USB volumes before storage calls. Reject non-public volumes and intermediate mount states; skip already-unmounted public volumes.
- For each selected mounted public volume, call vold.unmount, then end that volume's session through a new narrow helper. Preserve unrelated sessions and shared user connections.
- Invoke the existing experimental vold.exreset only after the selected preparation calls return. Handle exceptions through the existing style of fatal logging.

The narrow helper looks up the user connection without removing its session first. It calls removeSessionAndWait directly and propagates its checked failure. This avoids the separate onVolumeRemove step, which removes the entry that removeSessionAndWait needs to obtain. An absent connection remains a no-op, and upstream end-session handling can also return when a session has already disappeared. Neither condition proves teardown completed.

This deliberately differs from legacy MediaProvider termination and supports a narrower proposed scope. Returning after an error does not report failure to the existing manager, whose reviewed handled-error path can continue to sleep. Do not interpret the return as a safe-to-suspend acknowledgement.

## Validation

`scripts/prepare_framework_storage_patch.py` verifies all three inspected storage source hashes before output, checks unique anchors and stages files outside the input tree. The patch passes dry-run application to the original official files. [The patch report](../evidence/framework17-storage-patch.json) records input/output and patch fingerprints.

`scripts/check_framework_storage_host.py` extracts the actual staged unmount entry point and both added methods, compiles those Java methods using fake framework classes, and runs 15 scenarios. These cover permission denial, both readiness gates, normal ID routing, full snapshot rejection before side effects, transition rejection, unmounted/read-only states, vold/session/controller failures, non-external disks and a null disk. The successful case checks that an unrelated session remains. [The host report](../evidence/framework17-storage-host.json) links method, staged-file and harness hashes.

This is not compilation of the actual Android classes or validation of real Binder permission/identity APIs. The fake APIs do not prove target API compatibility. No real FUSE, MediaProvider, vold, storage or power operation occurs. The default `make test` checks recipe source guards and consistency of tracked reports; it does not repeat the Java harness or fetch platform files.

## Reproduce

Fetch the three files listed in the recipe's EXPECTED table from the pinned official revision into SOURCE_ROOT, preserving repository-relative paths. Then run:

```sh
python3 scripts/prepare_framework_storage_patch.py \
  --source-root SOURCE_ROOT --output-root work/framework17-staged \
  --report evidence/framework17-storage-patch.json \
  --patch platform/experiments/vold17/framework-storage.patch
patch --dry-run -p1 -d SOURCE_ROOT \
  -i /workspace/QCM6125/platform/experiments/vold17/framework-storage.patch
python3 scripts/check_framework_storage_host.py \
  --source-root work/framework17-staged --work-dir work/framework17-java-host \
  --report evidence/framework17-storage-host.json
```

The local runtime is OpenJDK 21 with the jdk.compiler module. Its module entry point supplies the compiler even without a javac launcher. All generated classes stay under ignored work/.

## Remaining requirements before integration

The framework snapshot is not a native safety boundary. Existing native exreset still selects every SD/USB disk under its own lock, so a newly inserted/adopted disk or volume transition after the snapshot can invalidate the framework selection. The native interface must constrain and revalidate the intended disk set before a public-only guarantee can be made. The snapshot's rejection of private volumes alone is insufficient.

Real session removal races, asynchronous vold events, concurrent resets, mount/user changes, missing connections, failure reporting and watchdog timeouts also need review. A disappearing session can cause the upstream wait helper to do no work. Some volumes may already have unmounted when a later operation fails; this proposal provides no rollback. Ordinary destroy/create results in the earlier native reconstruction are still ignored.

Next work is coordinated native selection and session-lifecycle handling, followed by compilation against a coherent Android source tree. Source completeness, build disk capacity, vendor/kernel compatibility, service startup and the manager's real sleep routing remain open. No device testing or flashing is authorized by this proposal.
