# Android 17 storage-interface experiment

This directory contains **source experiments**, not a complete validated vold/platform integration. Nothing here is an installable update. The initial interface-only experiment is append-exreset.patch; the follow-up native-exreset.patch adds an experimental implementation. Coordinated regeneration/rebuilding and framework adaptation are still required.

The patch applies to platform/system/vold at revision `6d20a0078c2bcaa2499dc5d032f337bfe1182d9e`, from the inspected android-17.0.0_r1 mirror tag. It appends exreset after the existing method declarations, preserving every standard method's transaction ID.

Local Java and C++ AIDL generation found:

| Check | Result |
| --- | --- |
| Existing upstream methods | 84 |
| Existing IDs preserved | All 84 |
| Experimental exreset code | 85 |
| Java/C++ generated code tables | Match |
| Native implementation | Experimental follow-up patch; extracted method host-tested with fake disks |
| Android 17 daemon/platform build | Not performed |

This deliberately does **not** retain the old HCT exreset code 4. The original working daemon is incompatible with the experimental interface; it must not be paired with the generated clients. The old Java storage routing also needs adaptation against the real target framework. The existing isolated external-disk helper is a source-correlated prototype, not an installed daemon implementation.

## Reproduce

Obtain IVold.aidl, IVoldListener.aidl, IVoldMountCallback.aidl and IVoldTaskListener.aidl from [the pinned source directory](https://github.com/aosp-mirror-neo/platform_system_vold/tree/6d20a0078c2bcaa2499dc5d032f337bfe1182d9e/binder/android/os), placing them under SOURCE_ROOT/android/os. The script verifies the hashes of all four inputs and writes experiments outside that input tree.

Run scripts/experiment_vold_extension.py with --source-root, --work-dir, --aidl, --compiler-label, --report and --patch. The local result is [the experiment report](../../../evidence/vold17-extension-experiment.json). The compiler used here was Debian aidl 14.0.0+r75-1 with minimum SDK 33; generated Java/C++ was not compiled. Compiler-only Parcelable forwards supply type declarations, not runtime classes. These checks do not establish behaviour of the Android 17 platform compiler or runtime.

The script creates baseline and extended Java/C++ output in the ignored work directory, compares all method codes and emits the small patch. Seven synthetic regression checks cover appending and rejection of renumbering, language mismatches, unexpected methods and unsupported constants.

## Native follow-up

native-exreset.patch modifies four files at the same pinned revision. It adds VolumeManager::exreset and the matching VoldNativeService declaration/wrapper. The wrapper uses the existing ENFORCE_SYSTEM_OR_ROOT, ACQUIRE_LOCK and status translation pattern. The volume-manager method selects SD/USB flags and calls destroy/create in the recovered order without the broader stock reset operations.

Apply append-exreset.patch and native-exreset.patch together in a separate source checkout for review. The second patch alone leaves the generated interface without the method. No Android build has verified the pair yet.

scripts/prepare_vold_native_patch.py verifies the five pinned native reference files, stages the proposed changes outside that input tree, emits the patch and extracts the actual new method into an ignored host-test include. It compiles that method with fake Disk/VolumeManager scaffolding using native/vold_method_host_test.cpp and runs only that host harness. The real Android translation units, Binder wrapper and daemon are not compiled or executed. [The native-patch report](../../../evidence/vold17-native-patch.json) records inputs, outputs, patch/body/harness hashes and the host result.

The default make test also runs scripts/check_port_artifacts.py without needing firmware or a platform checkout. It checks tracked patch hashes, the native method additions against the recorded tested-body hash, the harness fingerprint and the source/report links for the storage transaction comparisons. This catches stale or mismatched review artifacts; it does not repeat code generation or independently establish runtime compatibility.

See [the native source-port review](../../../docs/vold17-native-port.md) for the implementation boundary and remaining framework work.

Remaining work includes Android compilation and review of permission/locking/error semantics, framework sleep/storage routing, all affected consumers, complete source/build availability and runtime validation under separately authorized device testing. No firmware, storage, power or flashing command is included in this experiment.

## Framework follow-up

The newer [scoped reset follow-up](../../../docs/scoped-storage-reset.md) adds transaction 86 with explicit native disk IDs and strict missing-session handling. Its scoped AIDL/framework patches replace their earlier alternatives; scoped-native.patch applies after native-exreset.patch. Read that document for the exact application order and remaining generation/session/manager limitations.

`storage-ack.patch` then applies after scoped-framework.patch and adds a permission-checked boolean IStorageManager endpoint at code 101, preserving all 55 existing storage IDs. It requires a replacement manager to consume the result. See [acknowledgement before sleep](../../../docs/storage-sleep-acknowledgement.md).

`framework-storage.patch` is a separate review-only proposal against frameworks/base revision `94b4c163b7dfe5ce3607f7bb8456f9573f7de57d`, obtained from the official Android 17 r1 tag. It introduces permission-checked hctall routing and narrow public-volume session handling. It does not reproduce legacy MediaProvider termination. Fifteen extracted-method Java scenarios pass with fake framework objects; full Android classes were not compiled. Native disk selection and session races still prevent a public-only safety guarantee. Do not treat the three patches as a validated platform integration. See [the framework review](../../../docs/framework17-storage-port.md) for reproduction and known gaps.
