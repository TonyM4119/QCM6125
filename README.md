# HCT QCM6125 firmware analysis

Offline analysis of XTRONS/HCT QCM6125 head-unit firmware and possible Android porting approaches. **This is research and tooling, not a working ROM or a flashable release.**

Earlier owner photos showed factory Android 12, kernel 4.14.190 (#103, July 2023), MCU `HCTGQ_HCT_V4.04_1`, and VW RZ CAN integration. Newly supplied Device Info HW photos report Android 13/API 33, a January 2025 build, kernel #369, 8 GB LPDDR4X RAM and a 1280x720 display. The owner confirmed these photos show the current installation; its firmware-provider provenance remains unknown; see [device observations](docs/device-observations.md). Two user-supplied firmware packages were inspected: a November 2022 XTRONS Android 12 factory candidate and a March 2024 Android 13 Malaysk Lite reference previously tested successfully on the unit. The owner confirmed the November 2022 XTRONS archive was the package that did not work on this unit. It is excluded as a porting base. Later memory photos report 7,673 MiB RAM and 227.44 GiB shared-storage capacity, consistent with the advertised 8 GB/256 GB variant.

**Baseline correction:** the failed XTRONS archive remains historical analysis evidence only. Prefer the currently working January 2025 installation (matching binaries unavailable) and the previously tested Malaysk archive as compatibility references. The user's preference for a working stock base remains; no compatible stock archive is currently available. The experimental transport originated from the failed archive; a static cross-check now confirms the same parameter ABI in the known-working Malaysk native bridge. Neither this code nor the current January 2025 driver has been hardware-tested by this project.

The key result: car functionality depends on HCT modifications inside the Java framework, system server and native system libraries, as well as kernel drivers and applications. A generic Android image plus copied HCT APKs would omit these dependencies.

- [Dependency findings and evidence](docs/hct-dependencies.md)
- [Porting approaches and next offline milestones](docs/porting-approaches.md)
- [Inspected packages and integrity](docs/firmware-baseline.md)
- [Device details reported in owner photos](docs/device-observations.md)
- [Reproducing the analysis](docs/reproduce.md)
- [Recovered native transport and implementation milestone](docs/native-transport.md)
- [Native ABI cross-check against the working Malaysk reference](docs/working-reference-crosscheck.md)
- [Service messages, callbacks, event stream and audio policy](docs/service-layer.md)
- [Bounded receive decoder and initial event mappings](docs/event-decoder.md)
- [Integrated host core and radio callback extension](docs/offline-service-core.md)
- [Typed HCT state, navigation audio and CarData contract](docs/typed-state-contract.md)
- [Client callback filtering, delivery and attachment lifecycle](docs/callback-delivery.md)
- [Deferred EQ/loudness/video controls, settings and driver routing](docs/control-methods.md)
- [EQ preset recovery, custom coefficients and default conversion](docs/eq-policy.md)
- [Working-reference startup, task, key, touch and permission hooks](docs/platform-hooks.md)
- [Working HCT manager APK, signing relationship and startup chain](docs/manager-service.md)
- [Sleep/storage sequence and incompatible HCT vold transaction numbering](docs/sleep-storage-contract.md)
- [Native external-reset evidence and isolated experimental reconstruction](docs/native-external-reset.md)
- [Native vold dispatch and selected Java/native transaction agreement](docs/native-vold-dispatch.md)
- [Android 17 storage-interface experiment preserving standard transaction IDs](platform/experiments/vold17/README.md)
- [Experimental Android 17 native reset implementation and extracted-method host checks](docs/vold17-native-port.md)
- [Official Android 17 framework storage proposal and Java host checks](docs/framework17-storage-port.md)
- [Scoped native disk validation and strict session reset experiment](docs/scoped-storage-reset.md)
- [Explicit storage acknowledgement and sleep-gating policy](docs/storage-sleep-acknowledgement.md)
- [Experimental Java manager sleep bridge and lifecycle tests](platform/manager/README.md)
- [Sleep-event timestamps and Android power ordering](docs/power-event-order.md)
- [RDS byte arrays and background station results](docs/radio-payloads.md)
- [Working-kernel driver bindings, limits and virtual event framing](docs/working-kernel.md)
- [HCT board/display/touch declarations in compiled device trees](docs/device-tree-findings.md)
- [AIDL declarations and generated Binder contract checks](interfaces/README.md)
- [Android source target, compatibility and build-resource gates](docs/android-target-gates.md)
- [Experimental C++ transport and fake-device host tests](native/README.md)

This repository contains original inspection scripts and derived findings. Firmware archives, proprietary APKs/libraries, decompiled implementations, device identifiers, keys, and raw property dumps are excluded. Public certificate fingerprints in the evidence identify signing relationships; they are not private signing keys.

All work so far was static analysis and local development. An experimental native transport component passes fake-device host tests; it is not an Android-integrated service. No device connection, unlocking, wiping or flashing was performed. No new Android build was produced, and no Android 14+ hardware compatibility has been established.

Run all portable host checks with `make test`. This builds and executes only fake-device or synthetic-input tests and does not access the head unit.
