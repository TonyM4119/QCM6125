# Resume this project

Updated November 5, 2026. This file preserves context independently of the chat.

## Goal and baseline

Investigate a newer Android port for the HCT/XTRONS QCM6125 head unit while preserving its car functions. Android 17 is the current experimental source target, not a working ROM.

Use the current January 2025 installation and the owner-tested Malaysk reference for compatibility evidence. The November 2022 XTRONS package failed on this unit and must not be used as the porting base. See README.md and docs/firmware-baseline.md.

## Last saved milestone

Commit `1e27641` contains port-artifact consistency checks and the official framework-source access gate. Earlier commits contain a reconstructed external-storage reset loop, an experimental Android 17 IVold extension preserving standard method IDs, and a native source patch. See docs/vold17-native-port.md and platform/experiments/vold17/README.md.

These are isolated source experiments and host tests. No Android image has been built or hardware-tested. No flashing, wiping, bootloader operation, MCU update or device storage operation has been performed.

## Resume work here

November 5 follow-up: added `native/sleep_storage_sequence.hpp` and fake-adapter tests for the manager's sleep/storage ordering and wake cancellation. This is a portable contract model, not Android integration. Both inspected GitHub framework mirror URLs still returned HTTP 404 for the Android 17 StorageManagerService path. See docs/sleep-storage-contract.md for the model's boundaries.

1. Read docs/android-target-gates.md and docs/vold17-native-port.md.
2. Obtain a matching, pinned framework source baseline before making framework patches. On November 5 the active environment policy still excluded android.googlesource.com; the prior notes record a configuration draft, not an applied access change. The inspected GitHub mirror paths had not supplied the matching framework files.
3. Implement and validate the permission-checked `hctall` storage route, boot/daemon readiness, media-provider coordination, and manager sleep-state recheck against that baseline. The observed sequence is in docs/sleep-storage-contract.md. Do not treat a portable model as a compiled Android implementation.
4. Resolve the complete source manifest, legacy vendor/kernel compatibility and build resources before claiming a platform build. The existing filesystem is too small for a full contemporary AOSP checkout and build.

Run `make test` for the existing portable checks. Device testing requires separate authorization.

## If the conversation disappears

Open this repository and ask Codex to read RECOVERY.md and the latest Git log. Inspect `git status --short` for work newer than the commits. The chat is not the sole record of project progress.

On November 5, `git ls-remote origin HEAD refs/heads/main refs/heads/master` confirmed that GitHub HEAD and main both point to `1e27641e6af313994851cbc3e6077b188194898e`, matching the latest local project commit at recovery time. Remote: https://github.com/TonyM4119/QCM6125 . This confirms a remote copy of that committed work, not of later uncommitted files or the conversation. This recovery note was created locally after that check.
