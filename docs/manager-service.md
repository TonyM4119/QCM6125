# Working HCT manager APK dependency

The explicit startup target in SystemServer is supplied by `system/priv-app/HCTManagerService/HCTManagerService.apk` in the owner-tested March 2024 system image. The APK was extracted locally for static inspection only. It was not installed, launched or modified, and it is not included in this repository.

[The profile](../evidence/malaysk-manager-apk.json) records the APK and platform-resource hashes, manifest components/permissions, selected startup references and external HCT calls. scripts/profile_manager_apk.py reproduces it from local files.

## Identity and platform dependencies

The package is `android.microntek.service`, with declared minimum and target SDK 33 and sharedUserId `android.uid.system`. Its parsed signing-certificate set matches framework-res.apk extracted from the same working image. This identifies a signing relationship in that archive; certificate parsing here is not a complete APK signature-verification result and supplies no private signing key.

The manifest declares ManageService, MicrontekServer and MicrontekTimeUpdateServer, plus a boot-completed receiver. All four are explicitly exported in this reference. Their exact manifest attributes and action names are in the profile. The APK requests 35 permissions, including settings, audio, task/process, device-power and location-related permissions. Requests alone do not establish what is granted or which paths run.

The app contains its own helper classes under android.microntek as well as external references to CarManager, HCTApi and MfiManager. The scan found 22 unique external HCT method signatures. All have direct matching definitions in the working framework DEX inventory. This is a static signature check, not verification of access, class-loader resolution or behaviour. The profile includes the source inventory hash.

In particular, this manager needs HCTApi dual-screen/window-policy helpers and Mfi listener APIs beyond the reconstructed ICarService interface. A replacement CarService alone cannot satisfy those dependencies.

## Startup chain

ManageService.onCreate calls helper routines for these startup attempts in order:

1. MicrontekServer in the same APK.
2. HCT Bluetooth service.
3. Optional original-Bluetooth audio-routing service.
4. CAN bus service.
5. Box service.
6. Navigation-bar service.
7. LED visualizer service.

The helpers contain configuration/package checks; a call to the helper does not prove the target starts on this unit. The extracted references identify these concrete component dependencies:

| Helper | Component reference |
| --- | --- |
| StartCarService | android.microntek.service.MicrontekServer |
| StartBTService | android.microntek.mtcser.BlueToothService |
| StartOrgBTService | android.microntek.passthrough.OrgBlueToothService |
| StartCanBusService | android.microntek.canbus.CanBusServer |
| StartBoxService | android.microntek.box.BoxServer |
| startNaviBarService | com.microntek.NavigationBar.service.EventService |
| StartLedSettingService | com.microntek.ledsettings.VisualizerService |

The method also posts an ASR runnable after 10000 ms and attaches a CarManager Handler for Appinfo. Subsequent runnable retries, callback handling and the full MicrontekServer lifecycle remain separate analysis tasks.

The same onCreate includes settings/lock/debugging operations, including a hidden LockPatternUtils.clearLock call and a StartAdbOn helper. They were inspected as code references, not executed or copied into a new platform. A modern adapter must deliberately account for these behaviours and changed private APIs rather than assuming the old APK is portable unchanged.

## Porting implications

Preserve the observed component/action contracts while adapting service startup and the actual privileges they require. The old shared system UID and matching platform certificate do not carry over automatically to a differently signed AOSP image. Existing signing/data-migration constraints still apply. The profile does not propose disabling permission checks or changing live settings.

The next dependency boundaries are the manager's event/state initialization, its Mfi and window-policy usage, and the remaining APKs in its startup chain. No claim is made that these subsystems work on newer Android merely because the framework method signatures match.
