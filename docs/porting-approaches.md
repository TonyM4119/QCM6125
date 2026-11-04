# Porting approaches

The objective is newer Android while retaining the known-working HCT car functions. The owner confirmed that the November 2022 XTRONS archive did not work on this unit. It is excluded as a porting base and retained only for historical analysis. The current January 2025 installation and previously tested Malaysk archive are the working compatibility references. The current installation has no matching archive available, and the preference for a working stock base remains.

| Approach | What it preserves | Work and limits | Assessment |
| --- | --- | --- | --- |
| Customize factory Android 12 | Existing HCT framework, native integration and drivers | App/UI/script changes; cannot supply a newer Android API simply by changing properties | Most tractable customization path, but does not meet latest-Android objective |
| Generic system image with existing kernel/vendor | Many Qualcomm vendor components and kernel drivers | Loses HCT framework/service hooks unless reconstructed; boot alone does not establish car functionality | Useful only as an experimental compatibility probe, not a complete head-unit port |
| Build newer AOSP with adapted HCT compatibility layer | Potentially preserves the app-facing CarManager/Binder contract and original driver baseline | Reimplement or adapt services, JNI, init, permissions, signing, camera integration and input/task hooks; check target vendor/kernel compatibility | Most defensible route toward the requested newer Android, but substantial engineering remains |
| Isolate driver access in a small native service | Can preserve driver protocol while avoiding wholesale transplantation of an old libandroid_servers | Requires protocol reconstruction, IPC design, service permission checks and framework integration | Promising architecture within the AOSP route, not yet implemented or proven |
| Replace the kernel using a Xiaomi ginkgo tree | Related Qualcomm SoC support | Missing HCT board device trees, MCU/car/CVBS drivers, audio wiring and peripherals | Not a drop-in kernel source for this unit |
| Find a newer HCT release for the same board | Potentially retains vendor-supported integration | Must verify actual SDK/framework, board and peripheral match; version labels alone are insufficient | Strong candidate if a verified matching release is found; none established here |

A framework-only upgrade can retain an older vendor partition in some Treble configurations. This archive alone does not demonstrate compatibility with Android 14, 15, 16 or a later source release. Candidate-specific VINTF/FCM, VNDK/linker, kernel/eBPF, graphics, audio, AVB and partition-layout checks are necessary. Launch-device requirements should not automatically be applied as if every upgraded device must ship a new kernel, but neither should an old kernel be assumed compatible.

## Recommended offline milestones

1. **Interface inventory:** preserve complete HCT API signatures and identify app consumers. This repository establishes the core map and tools to extend it.
2. **Protocol recovery:** the first native parameter ABI and a host-tested transport implementation are now documented in [the transport milestone](native-transport.md). Continue with event decoding, Java command construction, audio arbitration and callback dispatch. Record uncertainty instead of inventing packet formats.
3. **Platform integration map:** identify call sites and semantics for SystemServer startup, key dispatch, sleep/wake, process management, task/window and permission hooks. Enumerate custom resources and settings expected by the APKs.
4. **Target selection and static compatibility:** a broader mirror now exposes the Android 17 r1 manifest and selected project revisions. The legacy vendor FCM 5 is absent from its default framework matrix set; see [source-target gates](android-target-gates.md). Resolve a coherent checkout and the actual vendor/kernel gaps before proposing a target build. The earlier limited mirror's Android 16-only result is superseded.
5. **Implement a small compatible service layer:** preserve the observed app-facing API and Binder transaction contract, rebuild against the selected platform, and isolate hardware-native code where practical. Reuse original vendor blobs only where their ABI contracts remain supported.
6. **Build and offline review:** assemble an experimental image only after meaningful implementations exist, validate dependencies, signatures, layouts and update metadata, and clearly label it untested. Creating placeholder device-tree files is not a completed port.

The no-flashing constraint remains in force. Hardware validation would be a separate future decision, not an implied next action. None of these milestones requires another screenshot right now. A working port cannot ultimately be established from static analysis alone.

## Gate before further hardware-specific implementation

The native parameter ABI has now been statically cross-checked against the known-working Malaysk bridge; see [the cross-check](working-reference-crosscheck.md). Framework behaviour, events and actual driver compatibility still require investigation before extending the implementation. Matching Java signatures and Binder constants do not validate the failed package's kernel, device trees, peripherals or native driver ABI. Do not transplant its boot, vendor, dtbo, bootloader or board-specific configuration into a proposed build. The failure mode is unknown; do not infer that RAM/storage capacity caused it.
