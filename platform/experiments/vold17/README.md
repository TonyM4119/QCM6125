# Android 17 storage-interface experiment

This directory contains an **interface-only experiment**, not a complete or buildable vold integration patch. Appending the method requires a real native implementation and coordinated regeneration/rebuilding of the affected Java/C++ components. Nothing here is an installable update.

The patch applies to platform/system/vold at revision `6d20a0078c2bcaa2499dc5d032f337bfe1182d9e`, from the inspected android-17.0.0_r1 mirror tag. It appends exreset after the existing method declarations, preserving every standard method's transaction ID.

Local Java and C++ AIDL generation found:

| Check | Result |
| --- | --- |
| Existing upstream methods | 84 |
| Existing IDs preserved | All 84 |
| Experimental exreset code | 85 |
| Java/C++ generated code tables | Match |
| Native implementation or Android 17 platform build | Not performed |

This deliberately does **not** retain the old HCT exreset code 4. The original working daemon is incompatible with the experimental interface; it must not be paired with the generated clients. The old Java storage routing also needs adaptation against the real target framework. The existing isolated external-disk helper is a source-correlated prototype, not an installed daemon implementation.

## Reproduce

Obtain IVold.aidl, IVoldListener.aidl, IVoldMountCallback.aidl and IVoldTaskListener.aidl from [the pinned source directory](https://github.com/aosp-mirror-neo/platform_system_vold/tree/6d20a0078c2bcaa2499dc5d032f337bfe1182d9e/binder/android/os), placing them under SOURCE_ROOT/android/os. The script verifies the hashes of all four inputs and writes experiments outside that input tree.

Run scripts/experiment_vold_extension.py with --source-root, --work-dir, --aidl, --compiler-label, --report and --patch. The local result is [the experiment report](../../../evidence/vold17-extension-experiment.json). The compiler used here was Debian aidl 14.0.0+r75-1 with minimum SDK 33; generated Java/C++ was not compiled. Compiler-only Parcelable forwards supply type declarations, not runtime classes. These checks do not establish behaviour of the Android 17 platform compiler or runtime.

The script creates baseline and extended Java/C++ output in the ignored work directory, compares all method codes and emits the small patch. Seven synthetic regression checks cover appending and rejection of renumbering, language mismatches, unexpected methods and unsupported constants.

Remaining work includes the native implementation, correct permission/locking/error semantics, framework sleep/storage routing, all affected consumers, complete source/build availability and runtime validation under separately authorized device testing. No firmware, storage, power or flashing command is included in this experiment.
