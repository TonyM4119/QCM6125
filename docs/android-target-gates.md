# Android source target and build gates

Checked November 4, 2026. This records source and resource observations, not an Android build or proof that this device can run a given release.

## Candidate source release

The broader `aosp-mirror-neo` GitHub mirror advertises `android-17.0.0_r1` for the manifest, build, hardware/interfaces, libvintf and system/bpf projects checked. This is the highest numbered release tag observed in the queried build mirror. It supersedes the earlier limited mirror's Android 16-only result. This is a candidate for the owner's latest-Android objective, not a claim that every source project is currently obtainable through this mirror or that no newer release exists elsewhere.

Observed peeled revisions:

| Project | android-17.0.0_r1 revision |
| --- | --- |
| platform/manifest | 5bc9a7ce1cd78dd53613bbfd0ebf506e1e4adb0f |
| platform/build | 5ce6f787337d0223710bf7d4a16dbe6d2a35f777 |
| platform/hardware/interfaces | 0162af698935100a590b7359581ac8b1b80693e5 |
| platform/system/libvintf | df89ad736e14ac375f61d50fa543ae7cd746a140 |
| platform/system/bpf | d68a263039127dc709114802395e57537a02babf |

The manifest's default revision is refs/tags/android-17.0.0_r1. Its listed projects include packages/modules/Connectivity. The inspected Connectivity mirror did not advertise Android 16/17 tags, and cloning its Android 17 tag failed. Some guessed raw source URLs also returned 404. These observations limit this mirror route; they do not prove that upstream source is unavailable. A coherent checkout must resolve all manifest revisions before a target build is claimed.

Follow-up: the vold mirror does provide the Android 17 tag, peeled revision `6d20a0078c2bcaa2499dc5d032f337bfe1182d9e`. Four pinned Binder-interface files were fetched and used in an [isolated Java/C++ code-generation experiment](../platform/experiments/vold17/README.md). Its appended reset method preserves all 84 standard transaction IDs. This is progress within one source project, not resolution of the complete manifest. The inspected frameworks/base SystemServer path still returned 404 at the Android 17 tag; no platform build is claimed.

Sources inspected:

- [Release manifest](https://github.com/aosp-mirror-neo/platform_manifest/blob/5bc9a7ce1cd78dd53613bbfd0ebf506e1e4adb0f/default.xml)
- [Hardware compatibility matrix build definitions](https://github.com/aosp-mirror-neo/platform_hardware_interfaces/blob/0162af698935100a590b7359581ac8b1b80693e5/compatibility_matrices/Android.bp)
- [BPF loader](https://github.com/aosp-mirror-neo/platform_system_bpf/blob/d68a263039127dc709114802395e57537a02babf/loader/Loader.cpp)

## Official framework source access

At the next framework-integration checkpoint, the managed environment's enforced restricted HTTP policy did not include android.googlesource.com. The selected GitHub framework mirrors still did not expose the requested Android 17 revision. A configuration draft was saved to add only android.googlesource.com to the custom host list while preserving the three Dropbox hosts and existing package-manager preset. The save did not apply the policy; the environment workflow requires user review and publication.

That access is intended for small, pinned official source reads to establish a matching framework baseline. It does not authorize a disk-filling full source sync, resolve the build-storage limit or prove that the requested source tag is available upstream. Once access is active, the actual official revisions and file contents must be checked before preparing framework patches.

## Vendor/kernel compatibility gate

Both available firmware archives declare vendor FCM target level 5 and kernel target level 5, alongside an Android 11 vendor base and Linux 4.14.190. The current January 2025 installation's vendor manifest is unavailable, so its level must not be assumed from the photos.

In the inspected Android 17 hardware/interfaces source, SYSTEM_MATRIX_DEPS_A17 lists levels 7, 8, 202404, 202504, 202604 and the device matrix. It does not include level 5. The old compatibility_matrix.5.xml path is absent at the checked tag. The level-7 module lists android13 kernel config families 5.10 and 5.15; the level-8 module lists 5.15 and 6.1. These facts establish that the original legacy baseline is outside the inspected default compatibility sets. They are not a universal statement that every upgraded device must replace its kernel solely because its Android version changes.

Retaining the known-working vendor/kernel therefore needs a real legacy compatibility project: restore/adapt the relevant matrix requirements and confirm all actual HAL, linker, kernel and framework expectations. Raising a manifest number, restoring only an empty XML file or bypassing checks would not implement the missing support. Replacing the kernel would instead require the HCT board/device trees and car-specific drivers, which have not been obtained.

The Android 17 BPF loader source has per-program/map kernel version gates; this inspection did not establish a single universal minimum kernel version from those files. The networking module and actual required programs still need review. Existing CONFIG_BPF/CONFIG_CGROUP_BPF flags alone are insufficient to establish newer networking compatibility.

## Build resource gate

The current workspace has a 63 GiB filesystem with about 41 GiB free. It has about 33 GiB RAM. These resources are adequate for the current static analysis and host C++ tests, but the disk is not suitable for a full contemporary AOSP checkout plus build outputs. A practical build workspace should provide approximately 400 GB free disk, preferably more for multiple builds/caches. This is a planning requirement, not a measured exact size for a completed checkout.

No full source sync or Android build was started, and no disk-filling sync is proposed on the present filesystem. Before that stage, provide a larger Linux build workspace and a source route that resolves the selected manifest. The board configuration, integration code and legacy compatibility work must then be developed and reviewed; larger disk space alone will not produce a working ROM.

## Concrete build-stage sequence

1. Keep the failed XTRONS package excluded. Preserve the current installation and use the owner-tested Malaysk binaries as the available working reference.
2. Resolve a coherent source snapshot for the candidate release in a sufficiently large workspace.
3. Audit actual vendor manifest/HAL/linker requirements against that snapshot and implement the legacy compatibility changes rather than disguising incompatibilities.
4. Build the portable service components against Android interfaces, add Binder/serial/audio adapters and board configuration, and validate the resulting system offline.
5. Consider device tests only under separate future authorization. No bootloader, MCU or firmware update is part of current work.
