# Scoped storage reset follow-up

The original reconstructed exreset selects every SD/USB disk. A framework snapshot alone cannot constrain that later native operation. This follow-up introduces a separate request containing explicit disk IDs, validates those disks in the native operation, and rejects disappearing framework sessions rather than assuming they ended.

This is still a source experiment. It is not a working ROM, a compiled Android daemon or permission to operate the head unit.

## Native validation

The expanded AIDL experiment preserves all 84 standard transaction IDs and the earlier exreset at 85. The new `exresetPublic(in @utf8InCpp String[] diskIds)` is 86 in both generated Java and C++. Its generated C++ signature accepts `const std::vector<std::string>&`, matching the proposed Binder override.

The new override uses the existing system/root enforcement and VolumeManager lock pattern. Within that lock, the method validates the complete request before the first destroy/create:

- At most 64 nonempty unique disk IDs; an empty list performs no work.
- Every requested disk must still exist, have SD/USB flags, and be neither EMMC nor a stub.
- Each selected disk must have at least one volume. Every volume must currently be public and unmounted. An adoptable flag alone is not evidence of adopted/private content.
- Only selected disks are destroyed/recreated. Unrequested disks are not reset, including new disks with different IDs.

Unlike the recovered legacy loop, this new method checks destroy/create status codes and stops at the first error. That is an intentional new error policy. It provides no rollback if a previous disk was already changed, or destroy succeeded and create failed.

The inspected native VolumeBase API is additionally pinned by hash. Its type/state accessors and Disk's existing ID/volume accessors supply the checks; no firmware executable is transplanted.

## Framework and sessions

The scoped framework variant validates the snapshot as before, deduplicates disk IDs, includes already-unmounted public disks, enforces the same request-count limit before storage calls, and calls exresetPublic instead of exreset. It leaves ordinary volume-ID unmount routing and its permission enforcement intact.

The scoped controller now rejects a missing connection. A new StorageUserConnection helper captures/removes the session and fails if it has disappeared, then invokes the actual end-session operation for that captured object. It does not silently accept the general helper's missing-session path. This can abort reset when asynchronous unmount events removed the session first; it is not proof of a usable runtime sequence. Some volumes may already have unmounted before that abort.

The helper reuses upstream removeSession, including its clearing of the connection's blocked-I/O bookkeeping. Preserving unrelated session entries therefore does not prove that every piece of shared user bookkeeping is unaffected.

## Artifacts and application order

All native files target vold revision `6d20a0078c2bcaa2499dc5d032f337bfe1182d9e`; framework files target frameworks/base revision `94b4c163b7dfe5ce3607f7bb8456f9573f7de57d`.

| Artifact | Apply to |
| --- | --- |
| platform/experiments/vold17/scoped-aidl.patch | Original pinned vold; replaces append-exreset.patch, includes both appended methods |
| platform/experiments/vold17/native-exreset.patch | Original pinned vold native files |
| platform/experiments/vold17/scoped-native.patch | Native tree after native-exreset.patch |
| platform/experiments/vold17/scoped-framework.patch | Original pinned framework; replaces framework-storage.patch |

Do not apply both alternative AIDL patches or both alternative framework patches. Rebuild clients and server together; neither old firmware Binder interfaces nor the earlier single-extension generated classes implement method 86.

## Reproduction and validation

Use the same pinned input files as the earlier recipes, plus model/VolumeBase.h from that vold revision. Generate the scoped AIDL experiment using scripts/experiment_vold_extension.py with `--scoped`; all other arguments are the same as the original experiment, with separate output/report/patch paths.

```sh
python3 scripts/prepare_scoped_vold_patch.py \
  --source-root work/official-vold17 --work-dir work/scoped-vold17 \
  --report evidence/vold17-scoped-native.json \
  --patch platform/experiments/vold17/scoped-native.patch
python3 scripts/prepare_framework_storage_patch.py \
  --source-root work/framework17 --output-root work/framework17-scoped --scoped \
  --report evidence/framework17-scoped-patch.json \
  --patch platform/experiments/vold17/scoped-framework.patch
python3 scripts/check_framework_storage_host.py \
  --source-root work/framework17-scoped --work-dir work/framework17-scoped-host --scoped \
  --report evidence/framework17-scoped-host.json
```

The extracted new C++ method passed 24 fake-disk scenarios: explicit selection/order, complete preflight before any mutation, duplicates/missing/oversized requests, private/mounted/transitional volumes, empty media, EMMC/stub rejection, and destroy/create errors. The extracted scoped Java methods passed 20 fake-framework scenarios, including exact/deduplicated disk-ID forwarding, missing connection/session refusal and early count-limit rejection. Java/C++ AIDL generation preserves existing IDs. All three new patches pass dry-run application against their intended input trees.

Reports are evidence/vold17-scoped-native.json, vold17-scoped-aidl.json, framework17-scoped-patch.json and framework17-scoped-host.json. The default portable suite checks guard regressions and artifact fingerprints. It does not regenerate platform sources or independently rerun the extracted-method harnesses.

## Remaining boundary

Disk IDs are names, not generation tokens. Removal/reinsertion under the same ID can still select different physical media; native public/unmounted checks do not establish continuity with the earlier framework snapshot. Real lock discipline, asynchronous state changes and session end ordering need Android compilation and runtime review. A future transaction protocol needs generation-aware identity and coordinated ownership if continuity is required.

The unchanged old exreset method remains available to privileged callers in this experiment. Only the scoped framework route uses method 86. This does not remove every broad-reset entry point from Android.

Framework handled failures still return normally, and the recovered manager may proceed to sleep after a handled storage error. Successful native validation does not solve that acknowledgement contract. Manager readiness/error handling and a coherent full platform build remain required before device use. No Binder, FUSE, storage, suspend or flashing operation was executed by these host checks.

The subsequent [acknowledgement proposal](storage-sleep-acknowledgement.md) adds a separate boolean storage endpoint and a host-tested coordinator policy that refuses sleep on false. It does not retrofit the existing manager or establish runtime readiness.
