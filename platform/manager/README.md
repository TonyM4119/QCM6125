# Experimental manager sleep bridge

This directory contains the first Java manager component for the Android 17 port proposal. It consumes CarPower callbacks, obtains the explicit storage acknowledgement and calls PowerManager only after a successful result and fresh power-state reads. It is a source library, not a complete HCT manager replacement or an installable app.

## Components

`HctSleepCoordinator` implements the asynchronous state machine using injected storage/power ports and an executor. It keeps one preparation in flight. A power transition invalidates the current generation immediately; wake followed by another sleep requires a fresh preparation. Repeated identical states are coalesced. Failure does not automatically loop/retry. Unknown states invalidate preparation instead of assuming sleep.

`AndroidHctSleepBridge` supplies the Android ports:

- Registers the reconstructed ICarManageCallback with the injected ICarService, listens only for CarPower, and reads its type field. Malformed or missing data invalidates pending work.
- Reads getStringState("carpower") before and after storage preparation.
- Calls the patched IStorageManager.prepareHctExternalDisksForSleep boolean method.
- Requests PowerManager.goToSleep using the uptime captured when the sleep state was first observed, never wall-clock or preparation-completion time. Duplicate sleep callbacks do not refresh it; a new sleep after wake gets a new time.
- Links both service binders to death handling. Disconnect/close invalidates late acknowledgements immediately, even if a remote call is still blocked.
- Cleans up callbacks and death links on the worker. Registration/start/close are idempotent; partial setup failures are cleaned up best-effort.

The caller supplies a background Handler. A main-looper Handler is rejected. The bridge never owns or stops that looper. Keep it alive until queued cleanup completes; stopping it first can prevent remote callback cleanup, although the coordinator remains closed. There is no automatic service rediscovery or reconnection; a service owner must construct a new bridge after reconnecting.

Startup reads are guarded against callbacks arriving during the read, so a stale initial value does not overwrite a newer event. No Binder or storage operation is performed while the coordinator holds its state lock.

## Build and integration

The root Android.bp defines the optional `hct-sleep-bridge-experimental` Java library with the two source classes and reconstructed car-service AIDL. It excludes test-support and tests. The library is not installable and has no boot hook. Soong has not evaluated it in a full checkout.

It requires the matching scoped vold/framework patches and storage-ack.patch from platform/experiments/vold17. The generated IStorageManager must include the permission-checked boolean method. Callers need real live car/storage services, DEVICE_POWER and MOUNT_UNMOUNT_FILESYSTEMS privileges, a background looper, and deliberate platform startup wiring. This repository's portable car core does not yet register that live car Binder service.

Only one manager should own sleep. Leaving the original manager's unconditional/handled-error sleep path running alongside this bridge would bypass its acknowledgement gate. No original APK has been patched, disabled or replaced here. The bridge does not implement the original manager's Bluetooth/CAN/application startup, wake behavior, windows, audio, or MCU media-report protocol.

The proposed integration is to construct the bridge with those dependencies, call start after service readiness, and close it before retiring the worker/services. That is an integration contract, not a command to run it on the head unit.

## Host validation

Run `make test-manager` or:

```sh
python3 scripts/check_sleep_manager.py --report work/sleep-manager-host.json
```

The script compiles the actual Java sources with test-only Android API shapes, then runs 21 coordinator and 20 bridge scenarios. One coordinator test uses a real executor thread and latches to exercise wake/new-sleep while preparation is blocked; it verifies preparation does not overlap and the old acknowledgement is not reused. Bridge tests exercise startup/callback state handling, Binder death, partial registration cleanup, false/error acknowledgements, invalid data, worker rejection and uptime selection. See docs/power-event-order.md for the pinned source review behind event-time preservation.

The test-support directory is not a runtime framework implementation and must not be included in an Android image. These checks do not establish Binder transport behavior, permissions, PowerManager behavior or actual Android API compatibility. The host JDK compiler uses source/target 17 with host platform classes because this runtime lacks the release-17 API archive. This is not a --release 17 baseline check or a Soong/Android build.

The tracked evidence/sleep-manager-host.json report records sources, test API shapes, build descriptor, test recipe and outputs. The default portable suite checks these fingerprints for staleness; the separate test-manager target actually compiles and runs the manager tests.

## Remaining boundary

Close/wake cancels work at coordinator checks, not an already running remote storage operation. There is no remote-call timeout or rollback. The final power-state/generation check is not atomic with the subsequent PowerManager Binder call; a wake/close in that gap can race a sleep request. REQUESTED means the call returned, not that the device actually suspended.

The acknowledgement is not a storage lease. Native disk IDs still lack generation identity, mounts can change later, session ordering needs Android-level validation, and the MCU acknowledgement meaning remains unresolved. These limitations, platform compatibility, actual manager replacement and a coherent build must be addressed before device use. No real Binder, storage, power, flashing or hardware operation was executed by the host tests.
