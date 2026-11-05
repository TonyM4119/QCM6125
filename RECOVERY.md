# Resume this project

Updated November 5, 2026. This file preserves context independently of the chat.

## Goal and baseline

Investigate a newer Android port for the HCT/XTRONS QCM6125 head unit while preserving its car functions. Android 17 is the current experimental source target, not a working ROM.

Use the current January 2025 installation and the owner-tested Malaysk reference for compatibility evidence. The November 2022 XTRONS package failed on this unit and must not be used as the porting base. See README.md and docs/firmware-baseline.md.

## Last saved milestone

Commit `1e27641` contains port-artifact consistency checks and the official framework-source access gate. Earlier commits contain a reconstructed external-storage reset loop, an experimental Android 17 IVold extension preserving standard method IDs, and a native source patch. See docs/vold17-native-port.md and platform/experiments/vold17/README.md.

These are isolated source experiments and host tests. No Android image has been built or hardware-tested. No flashing, wiping, bootloader operation, MCU update or device storage operation has been performed.

## Resume work here

Latest November 5 checkpoint: official source access is active after user publication. Framework Android 17 r1 is pinned to `94b4c163b7dfe5ce3607f7bb8456f9573f7de57d`; official vold inputs reproduce the old patches unchanged. A review-only framework patch and extracted-Java host harness are documented in docs/framework17-storage-port.md. Fifteen fake-framework scenarios pass. Read its remaining requirements first: native exreset still selects all SD/USB disks, so snapshot validation is not a safety gate. Next work is native disk-set validation and real session-lifecycle/concurrency coordination, not device deployment.

Earlier November 5 checkpoint: added `native/sleep_storage_sequence.hpp` and fake-adapter tests for the manager's sleep/storage ordering and wake cancellation. This is a portable contract model, not Android integration. Both inspected GitHub framework mirror URLs returned HTTP 404; the later official-source route above supersedes that blocker. See docs/sleep-storage-contract.md for the model's boundaries.

1. Read docs/android-target-gates.md and docs/vold17-native-port.md.
2. The matching framework source baseline is now pinned from the official host; the earlier mirror/access blocker is resolved for small source reads. Preserve source hashes when preparing further patches.
3. Implement and validate the permission-checked `hctall` storage route, boot/daemon readiness, media-provider coordination, and manager sleep-state recheck against that baseline. The observed sequence is in docs/sleep-storage-contract.md. Do not treat a portable model as a compiled Android implementation.
4. Resolve the complete source manifest, legacy vendor/kernel compatibility and build resources before claiming a platform build. The existing filesystem is too small for a full contemporary AOSP checkout and build.

Run `make test` for the existing portable checks. Device testing requires separate authorization.

## If the conversation disappears

Open this repository and ask Codex to read RECOVERY.md and the latest Git log. Inspect `git status --short` for work newer than the commits. The chat is not the sole record of project progress.

On November 5, `git ls-remote origin HEAD refs/heads/main refs/heads/master` confirmed that GitHub HEAD and main both point to `1e27641e6af313994851cbc3e6077b188194898e`, matching the latest local project commit at recovery time. Remote: https://github.com/TonyM4119/QCM6125 . This confirms a remote copy of that committed work, not of later uncommitted files or the conversation. This recovery note was created locally after that check.
