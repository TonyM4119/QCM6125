# HCT dependency findings

**Compatibility correction:** the owner confirmed that the November 2022 XTRONS archive did not work on this exact unit. It is not an approved porting base. Analysis derived from it remains evidence about that package only; a follow-up static cross-check confirms the recovered parameter ABI in the known-working Malaysk native bridge. The replacement transport remains untested on any real driver, and the January 2025 native implementation has not been inspected. The failure symptoms and cause are unknown.

Inspected November 4, 2026. Evidence comes from the supplied November 2022 factory candidate and March 2024 Malaysk reference. Observations establish what these packages contain, not runtime behaviour on an untested build.

## Main control path

```mermaid
flowchart TD
    A[HCT radio / CAN / Bluetooth / wheel / camera apps] --> B[android.microntek.CarManager]
    B --> C[Binder service: carservice]
    C --> D[com.android.server.microntek.CarService]
    D --> E[HCT JNI in libandroid_servers.so]
    E --> F[/dev/mtc-car and factory kernel drivers]
    G[Camera JNI: libcvbs_jni.so] --> H[/dev/mtc-cvbs]
    G --> F
    I[SystemServer and input / task / permission hooks] --> D
```

DEX definitions show 33 classes under `android.microntek` in factory `framework.jar`, including CarManager, HCTApi, ICarService, callback classes and Mfi interfaces. Factory `services.jar` defines 22 classes under `com.android.server.microntek`, including CarService, MfiService and HCT command definitions.

Disassembly of CarManager's constructor shows a lookup through `ServiceManager.getService("carservice")`, followed by `ICarService.Stub.asInterface`. Its getParameters/setParameters methods call the Binder interface. These are actual instruction observations, rather than conclusions from strings alone.

CarService declares native_getParameters and native_setParameters. The ELF symbol table of factory `libandroid_servers.so` exports JNI registration functions for both CarService and MfiService; its strings include `/dev/mtc-car`. Combined with `init.hct.rc` and the Java native declarations, this establishes the factory native bridge. Follow-up work recovered the narrow parameter ioctl ABI and confirmed it in the owner-tested Malaysk native library; see [the cross-check](working-reference-crosscheck.md). Driver internals, command semantics and event transport are still unresolved.

## Application dependencies

| App | Package | Observed framework references | Additional constraint |
| --- | --- | --- | --- |
| HCTRadio | com.microntek.radio | CarManager attach/detach, state, parameter getters/setters | Overlay/audio/settings permissions |
| HCTCanBus | android.microntek.canbus | CarManager, byte-array state, callbacks, EQ controls | Requests android.uid.system and SERIAL_PORT |
| HCTBlueToothManager | android.microntek.mtcser | CarManager and HCTApi.setSoftApBAND | Requests android.uid.system; target SDK 22 |
| HCTWheelStudy | com.hct.wheelstudy | CarManager attach/detach and parameter commands | System settings integration |
| HCTBackView | com.microntek.backview | CarManager state and parameter commands | Native CVBS path and window behaviour also need checking |
| HCTFactorySettings | com.hct.factory | Factory configuration UI | Requests android.uid.system and custom HCT_FACTORY permission |

These are DEX method references and manifest facts, not a complete runtime call graph. A referenced method can exist in unreachable code. Runtime tests would still be necessary to establish which paths a particular peripheral uses.

The CAN, Bluetooth manager and factory-settings APK certificates match the certificate in factory `framework-res.apk`. A rebuilt platform must deliberately handle signing and shared UID compatibility. No factory private signing key was found or assumed. Possible development strategies include a consistent development signing identity across rebuilt/migrated shared-UID packages, with a separately considered data migration plan. Copying a factory shared-UID package into a differently signed platform is not a complete solution.

The CAN app targets SDK 31; the Bluetooth manager targets SDK 22 despite a minimum SDK declaration of 31. Such legacy declarations may encounter newer installation and behaviour restrictions. Inclusion in a custom image and privileged placement alone do not establish compatibility.

## Framework changes extend beyond CarService

Factory services.jar defines these HCT-specific methods outside the Microntek service package:

- SystemServer.startMtcManage
- ActivityManagerService.sendHCTRemoveTask and ProcessRecord.sendHCTRemoveTask
- PermissionManagerService.isHctAppLists and AppWarnings.isHctAppLists
- PointerEventDispatcher.sendHctTouchStudy
- PhoneWindowManager.checkHctAuioApp and PhoneWindowManager.sendHctKeyCode
- Task.HctSendAppinfo

SystemServer.startMtcManage contains an explicit request to start `android.microntek.service.ManageService` in package `android.microntek.service`. The package is another integration dependency; the full service startup order has not been reconstructed. The method names indicate where adaptation is needed, but do not prove complete hook semantics.

HCTApi also exposes task/window/process helpers, implying reliance on private platform APIs. Porting a CarManager facade alone would leave these framework behaviours unresolved.

## Native and init dependencies

Factory `libcvbs_jni.so` exports JNI entry points for `com.microntek.cvbs.JniUtil` (open, close and surface/frame methods), and contains `/dev/mtc-cvbs` and `/dev/mtc-car` strings. Its DT_NEEDED list includes private platform libraries such as libandroidfw, libui, libhwui, libmedia and libgui. It therefore cannot be assumed to work unchanged with a newer framework simply because it is ARM64.

Factory `libandroid_servers.so` also links `android.hardware.mtc.mfi@1.0.so`. The vendor partition supplies MTC Mfi interface/implementation libraries and a service; the exact peripheral role and exercised paths require further analysis. Mfi should not be assumed to be the MCU transport just from its name.

`init.hct.rc` sets ownership/modes for mtc-car, mtc-av, mtc-dab, mtc-cvbs and serial interfaces. It defines property-triggered HCT services, projection startup scripts, and an optional external Bluetooth process using `/dev/ttyHS2`. This suggests that working head-unit Bluetooth may involve paths beyond Android's normal Bluetooth stack. The file also includes properties for reverse-camera and GNSS-related services.

Both supplied packages request SELinux permissive mode in their boot cmdlines. A future enforcing build would need deliberate policies for these services and devices; copying file permissions is insufficient. The analysis does not recommend disabling platform security to conceal missing integration.

## What the Android 13 reference tells us

The selected core interfaces CarManager, ICarService, ICarManageCallback and IMfiService contain 69 defined method signatures in each framework. All 66 signatures remaining after excluding the three compiler-generated CarManager accessors are shared. Follow-up extraction also found matching transaction constants across five HCT Stub classes (40 constants). This is encouraging evidence for a stable app-facing interface. It does **not** prove Parcel-layout equivalence, implementation identity or hardware behaviour on another build. See [the transport follow-up](native-transport.md) for details.

The CarService and MfiService families remain present in the Android 13 reference. Some service implementation methods differ. The native libandroid_servers and CVBS JNI binaries differ in size and SHA-256 between releases. We cannot infer whether HCT or Malaysk made those changes, but these files are not byte-for-byte copies of the Android 12 versions.

The practical implication is to preserve the interface contract while adapting its implementation to the target Android framework, rather than transplanting an entire old framework or native system library.

## Limits

No device execution, input tracing, ioctl tracing, signing-key recovery, firmware modification or boot testing was performed. No claim is made that every relevant dependency was discovered. The factory candidate is not the exact July 2023 installed build, and that mismatch remains relevant to peripheral validation.
