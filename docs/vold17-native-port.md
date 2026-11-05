# Experimental native storage implementation against Android 17

The pinned Android 17 vold source is sufficient to prepare a concrete native adaptation of the recovered external-reset loop. This is one source component; no Android daemon or platform image has been built.

## Proposed source changes

[native-exreset.patch](../platform/experiments/vold17/native-exreset.patch) targets vold revision `6d20a0078c2bcaa2499dc5d032f337bfe1182d9e` and changes four files:

| File | Change |
| --- | --- |
| VolumeManager.h | Declare the external-reset method separately from stock reset |
| VolumeManager.cpp | Select Disk SD/USB flags and perform per-disk destroy/create |
| VoldNativeService.h | Declare the matching Binder method override |
| VoldNativeService.cpp | Use existing system/root authorization, volume-manager lock and status translation |

The patch uses named Disk flags from the selected source rather than inventing new disk categories. It does not clear users, alter disk lists, reset internal emulated volumes or invoke the broader stock reset. The normal return is zero and ordinary destroy/create return values are ignored, preserving the reviewed HCT loop behaviour. That is a compatibility choice, not proof that every downstream failure is harmless or recoverable.

The authorization/locking wrapper follows the same upstream pattern as its existing reset method and is consistent with the recovered HCT native wrapper. Real target compilation and runtime review of that wrapper remain outstanding.

## Interface pairing

The native patch depends on [the appended AIDL method](../platform/experiments/vold17/append-exreset.patch). The interface experiment produces code 85 for exreset and preserves all 84 standard Android 17 method IDs in both Java and C++ generation. The old working HCT binary uses code 4 and is incompatible with this experimental interface. All relevant generated clients and the daemon must be rebuilt together.

No native binary is copied from the old firmware into the proposed target. The source patches reconstruct the reviewed operation against the newer component APIs.

## What was tested

scripts/prepare_vold_native_patch.py checks the hashes of VolumeManager.cpp/.h, VoldNativeService.cpp/.h and model/Disk.h from the pinned source. It requires unique patch anchors, writes a separate staged source tree and emits a reviewable diff. The original reference files remain unchanged.

The script then extracts the actual added VolumeManager::exreset body from the staged file and compiles it in a host harness with fake disk objects and a global VolumeManager scaffold. Tests cover flag selection, combined flags without duplicate calls, per-disk operation order, empty lists and continued creation after an ordinary destroy error result. These checks exercise the body included in the patch, rather than a separately maintained copy of that algorithm.

This is **not** compilation of the real Android translation unit or daemon. Platform headers, class layout, Binder implementation, actual disk objects, event callbacks, SELinux and real device effects are outside the harness. The real authorization/locking macros are not executed by this fake-object test.

Five additional regression cases check unique anchors, method extraction and refusal of unreviewed source before any compiler/output operation. [The report](../evidence/vold17-native-patch.json) records source/output hashes, patch/body/harness hashes and host-test output. Both patches also pass dry-run application against their original source contexts.

## Remaining integration boundary

The framework must still implement the permission-checked hctall routing, media-provider coordination, boot/daemon readiness and the manager's sleep-state recheck. The inspected Android 17 frameworks/base mirror path remains unavailable, so no patch against an unrelated framework release is substituted here. Full source/build, vendor/kernel compatibility and real runtime validation remain open.

The two source patches are a concrete porting proposal for review, not a complete working ROM or authorization to test storage/suspend on the head unit. No flashing or device operation occurred.
