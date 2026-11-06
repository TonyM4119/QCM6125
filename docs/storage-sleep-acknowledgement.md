# Explicit acknowledgement before sleep

The recovered manager can continue to goToSleep after handled storage errors. A void unmount return cannot distinguish success, a readiness skip or a logged reset failure. This follow-up proposes a separate boolean Binder endpoint and a coordinator policy that requires its success before requesting sleep.

This is an experimental framework/interface patch plus host policy tests. No replacement manager is implemented or installed, and no actual Android power operation is performed.

## Framework endpoint

`IStorageManager.prepareHctExternalDisksForSleep()` is appended with explicit offset 100, yielding Binder transaction 101. Code generation against the original pinned interface confirms all 55 existing method IDs remain unchanged. The interface file is pinned at SHA-256 `01c230e09901621cae04f437331b5a60d47c7a09c5cc335a5d32f5d246a0b6c4` from frameworks/base revision `94b4c163b7dfe5ce3607f7bb8456f9573f7de57d`.

The endpoint has the same MOUNT_UNMOUNT_FILESYSTEMS permission as unmount and invokes the generated permission helper before preparation. The existing scoped preparation helper now returns:

| Outcome | Result |
| --- | --- |
| Boot or daemon not ready | false, without storage work |
| Snapshot/count validation failure | false |
| Unmount, session, or native reset exception | false, with identity restored |
| All scoped preparation calls return normally | true |
| Permission denied | SecurityException before preparation |

The legacy unmount("hctall") route remains and ignores this result, preserving the existing caller-facing contract. Therefore the patch alone does not fix the original manager. A replacement coordinator must explicitly call the boolean endpoint; it must not infer success from void unmount, log output or the media-report end marker.

The IStorageManager source warns that native IMountService definitions must track interface changes. This experiment adds a Java-only extension and preserves all existing numbers; it does not implement a native client wrapper for method 101. Any native consumer of the new method would require that additional implementation and validation.

## Coordinator policy

`native/sleep_storage_sequence.hpp` retains the original sequence model and adds `experimental_prepare_acknowledged_sleep` as a distinct proposed policy:

1. Return immediately unless current carpower is sleep.
2. Obtain an explicit boolean preparation result.
3. Read current carpower again and cancel if it changed.
4. Return storage_failed on false; request sleep only on true.

Unexpected adapter exceptions propagate without a sleep request. Six fake-adapter cases cover success/failure, wake during either outcome, an initially awake state and an unexpected preparation error. This helper does not send MCU media parameters: the meaning of those reports is not established well enough to invent a new failure protocol. A real adapter must define that part separately.

## Artifacts and reproduction

`platform/experiments/vold17/storage-ack.patch` applies **after scoped-framework.patch**, against the same framework revision. The scoped vold AIDL/native patches remain required. Do not apply this directly to an unmodified framework or mix it with the earlier broad-reset framework variant.

The recipe requires the three pinned storage Java files and the additional IStorageManager.aidl at its repository-relative path. It verifies the interface fingerprint, stages the scoped base, adds the acknowledgement endpoint, generates both baseline/extended Java and verifies their IDs. Compiler-only forwards preserve imported interface/parcelable kinds; they are not Android implementations.

```sh
LD_LIBRARY_PATH=/workspace/QCM6125/work/tooling/aidl-root/usr/lib/x86_64-linux-gnu/android \
python3 scripts/prepare_storage_ack_patch.py \
  --source-root work/framework17 --work-dir work/framework17-ack \
  --aidl /workspace/QCM6125/work/tooling/aidl-root/usr/bin/aidl \
  --report evidence/framework17-storage-ack.json \
  --patch platform/experiments/vold17/storage-ack.patch
python3 scripts/check_framework_storage_host.py \
  --source-root work/framework17-ack/source --work-dir work/framework17-ack-host \
  --scoped --ack --report evidence/framework17-storage-ack-host.json
```

Thirty extracted-Java scenarios pass with fake framework objects: the prior scoped cases plus acknowledgement permission enforcement, both readiness gates, private media refusal, missing connection/session, session/unmount errors, native reset failure and success. The patch passes dry-run application to its scoped base. Full portable checks include the new C++ coordinator policy, source guards and artifact consistency.

## Remaining implementation boundary

No actual Binder call or Android translation unit was compiled. Generated type forwards and mock Java API shapes do not establish platform compatibility. Native disk-generation identity, concurrent mounts/resets, real session ordering, timeout/watchdog handling and partial failure recovery remain unresolved.

A successful boolean is a completed call result, not a lease preventing subsequent mount or power changes. The final power-state read is not atomic with a sleep request. The endpoint permits an empty disk set to succeed; it does not prove every storage consumer is quiescent. A real replacement manager, signed/permissioned integration, MCU protocol and Android-level tests are still required before this can govern sleep on the device.
