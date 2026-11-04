# HCT QCM6125 firmware analysis

Offline analysis of XTRONS/HCT QCM6125 head-unit firmware and possible Android porting approaches. **This is research and tooling, not a working ROM or a flashable release.**

The owner's installed factory build reports Android 12, kernel 4.14.190 (#103, July 2023), MCU `HCTGQ_HCT_V4.04_1`, and VW RZ CAN integration. Two user-supplied firmware packages were inspected: a November 2022 XTRONS Android 12 factory candidate and a March 2024 Android 13 Malaysk Lite reference previously tested successfully on the unit. The older factory candidate is labeled 6 GB/128 GB; exact compatibility with the owner's advertised 8 GB/256 GB variant remains unverified.

The key result: car functionality depends on HCT modifications inside the Java framework, system server and native system libraries, as well as kernel drivers and applications. A generic Android image plus copied HCT APKs would omit these dependencies.

- [Dependency findings and evidence](docs/hct-dependencies.md)
- [Porting approaches and next offline milestones](docs/porting-approaches.md)
- [Inspected packages and integrity](docs/firmware-baseline.md)
- [Reproducing the analysis](docs/reproduce.md)
- [Recovered native transport and implementation milestone](docs/native-transport.md)
- [Experimental C++ transport and fake-device host tests](native/README.md)

This repository contains original inspection scripts and derived findings. Firmware archives, proprietary APKs/libraries, decompiled implementations, device identifiers, keys, and raw property dumps are excluded. Public certificate fingerprints in the evidence identify signing relationships; they are not private signing keys.

All work so far was static analysis and local development. An experimental native transport component passes fake-device host tests; it is not an Android-integrated service. No device connection, unlocking, wiping or flashing was performed. No new Android build was produced, and no Android 14+ hardware compatibility has been established.
