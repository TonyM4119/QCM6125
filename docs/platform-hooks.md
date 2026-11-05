# HCT platform hooks in the working reference

The March 2024 owner-tested services.jar confirms eight selected HCT hook methods across seven framework classes. This extends the earlier factory-candidate observations with evidence from a package that worked on this unit. It does not establish that the January 2025 installation has identical hooks.

[The inventory](../evidence/malaysk-platform-hooks.json) records method signatures, selected references, field accesses and whitelisted strings. scripts/recover_platform_hooks.py also locates direct callers within those seven classes. It is not a complete platform call graph; callers in other classes and native code remain outside the scan.

## Startup and companion package

SystemServer.startOtherServices registers `carservice` using a new CarService after the serial-service startup block. It then registers `mfiservice` using a new MfiService. Local checkpoints are 0x89e..0x8ac and 0x8d2..0x8e2. These are separate Binder services; Mfi is not assumed to be the MCU transport.

The same startup method later calls startMtcManage at 0x26d4. That hook constructs an explicit Intent for package `android.microntek.service`, class `android.microntek.service.ManageService`, and starts it as UserHandle.SYSTEM. A service-layer replacement therefore also needs to account for this APK and its boot lifecycle, not just framework classes. The selected body catches its startup exception. The exact modern service-start placement must be reviewed against a coherent target source tree.

## Task and input contracts

| Hook | Reviewed behaviour | Remaining adaptation |
| --- | --- | --- |
| ActivityManagerService.sendHCTRemoveTask | Broadcast action com.microntek.removetask, string extra class containing the supplied argument | Preserve correct task/process trigger and user identity; do not infer every kill path is covered |
| PhoneWindowManager.sendHctKeyCode | Dispatch KeyDown with type=key and integer value | Map the actual interception branches and media-key ownership |
| PhoneWindowManager.checkHctAuioApp | Scans up to 40 running tasks, checks topActivity package through checkAudioName | Recover the app-selection policy and adapt private task APIs |
| PointerEventDispatcher.sendHctTouchStudy | Emits TouchEvent for action 0/1 when CarTouch is enabled; also implements the touch-study gesture state | Preserve input dispatch, callback state and action timing without guessing panel coordinates |
| Task.HctSendAppinfo | Emits Appinfo with appinfo/extappinfo, package/classname/title strings and integer reboot=0/1 | Find all callers and preserve display/user semantics |

The task hook writes `sys.ship.package` only for display 0. Other displays use the extappinfo type. Its boolean argument is encoded in the field named reboot, but the field name alone does not establish the meaning of every caller.

Within the scanned classes, remove-task notifications are called by forceStopPackage and killBackgroundProcesses. Key hooks are called by interceptKeyBeforeQueueing. Touch-study processing is called by onInputEvent. The Task hook has no direct caller in this limited class set, so its trigger remains unresolved here.

The pointer dispatcher lazily creates a CarManager, reads CarTouch and attaches a Handler to `Appinfo,CarTouch`. Its gesture branch uses five pointers and selected actions, with an integer-seconds threshold `(uptime - downTime) / 1000 > 6`. That is not a precise six-second timer; dispatch requires an eligible input event after the threshold. This review records the behaviour rather than introducing a new gesture implementation.

## Permissions and warnings

PermissionManagerService and AppWarnings both add isHctAppLists helpers that test whether an input string contains a listed entry. The service's checkPermission path includes early grant returns for certain package-prefix/customer/list matches. Its checkUidPermission overload compares its String argument through similar helpers; that argument is the permission name in this overload, so it must not be described as a verified UID-to-package lookup.

AppWarnings calls its helper from showDeprecatedTargetDialogIfNeeded. The permission and warning hooks are distinct behaviours. A future platform integration should identify the concrete permission needs of migrated packages and use the target platform's permission mechanisms. Copying an old broad grant shortcut would neither establish signing/shared-UID compatibility nor implement missing framework APIs. No permission or warning bypass is implemented in this repository.

## Source and validation boundary

These are static binary observations with local control-flow review. No input injection, task operation, broadcast or permission change was performed. The new extractor found all eight selected hooks and twelve direct call sites in the scoped class set. It publishes no complete hook bytecode or disassembly.

The candidate Android 17 full source route remains unresolved. In a follow-up query, neither inspected frameworks/base mirror advertised the exact android-17.0.0_r1 tag. This is a limitation of those mirror queries, not proof that upstream source is unavailable. No patch against a different release is presented as a verified Android 17 integration.

Next integration work must connect the reconstructed car-service contract to actual platform startup, settings/audio/serial adapters and these task/input hooks, while resolving vendor/HAL and source/build gates already documented in [the target assessment](android-target-gates.md).
