# Sleep, storage reset and the HCT vold interface

Static review of the working manager APK uncovered a dependency beyond car-service Binder methods: HCT changes both StorageManagerService and IVold. The existing portable event mapper records carpower state and CarPower notifications but performs no suspend, unmount or MCU acknowledgement operation.

## Manager-to-storage sequence

MicrontekServer attaches a Handler to `CarEvent,CarPower,KeyDown,CarApp,CarBox,Appinfo`. Its callback dispatcher reads the type string from CarPower and invokes DoCarPower. The power_on, power_off, acc_off and sleep branches have distinct state, delayed-work, Wi-Fi and screen-broadcast behaviour. They must not be reduced to a single Android shutdown call.

The reviewed sleep branch broadcasts SCREEN_OFF and calls MicrontekServiceBase.deviceunMountAndSleep. That helper:

1. Reads the shared carpower string and returns unless it equals sleep.
2. Sends parameter `rpt_media_safemounted=start` through CarManager.
3. Obtains the mount Binder service and calls `IStorageManager.unmount("hctall")`.
4. Sends `rpt_media_safemounted=end` after the handled storage exception path as well as the normal return path.
5. Reads carpower again and returns if it no longer equals sleep.
6. Calls its gotoSleep wrapper, which invokes PowerManager.goToSleep with uptimeMillis.

The second state check matters if a new power event arrives during storage work. These calls are observations of firmware code, not instructions executed by this project. Exception scopes, unreviewed callers and MCU acknowledgement meanings remain integration boundaries.

## Special storage operation

Working StorageManagerService.unmount(String) first enforces MOUNT_UNMOUNT_FILESYSTEMS. It treats the literal hctall specially, invoking resetExDevice instead of resolving it as a normal volume ID. Other strings use the ordinary volume lookup/unmount path.

resetExDevice returns without doing its main work unless boot has completed and the storage daemon is connected. Its reviewed normal path obtains users, calls killMediaProvider and then invokes `mVold.exreset()`. It handles the operation's exception. This is not evidence that every physical volume is unmounted, nor that copying the literal into a newer stock storage API would reproduce the operation.

## Confirmed Java Binder numbering difference

Both the working framework.jar and services.jar contain IVold Stub/Proxy classes. Their recovered 78-entry transaction tables agree. HCT adds exreset at code 4; the selected Android 13 upstream IVold has 77 methods and no exreset.

The upstream interface was passed through the local AIDL Java generator, rather than estimating its codes from text order. Comparing generated constants with both recovered HCT tables found **74 shared methods with different transaction IDs**, plus the HCT-only exreset method:

| Method | Generated upstream Android 13 | Recovered HCT |
| --- | --- | --- |
| setListener | 1 | 1 |
| abortFuse | 2 | 2 |
| monitor | 3 | 3 |
| exreset | Absent | 4 |
| reset | 4 | 5 |
| shutdown | 5 | 6 |

This establishes that the inspected Java interfaces cannot be paired interchangeably by name alone. It does not prove the native working vold server's complete dispatch layout or the Android 17 layout. A complete migration must rebuild/adapt the framework and storage daemon as a consistent interface pair, including the required reset semantics. Merely adding an exreset Java method or changing a transaction number would not implement that operation.

## Native boundary

The working system image contains a 948136-byte ARM64 vold executable. The report records its SHA-256, DT_NEEDED libraries and the presence of an exreset string. No exreset-named ELF symbol was recovered in the inspected symbol tables. These facts identify a native reference; a string is not proof of the function's behaviour or dispatch. The native reset implementation remains unresolved and the old executable is not proposed for transplant into a new Android platform.

## Reproducible evidence

- [Sleep dependency inventory](../evidence/malaysk-sleep-contract.json): source hashes, selected references/constants, both recovered IVold transaction tables, native metadata and upstream source metadata.
- [Generated transaction comparison](../evidence/vold-transaction-comparison.json): upstream source/generated-Java hashes, recovered-table report hash and exact per-method mismatches.
- scripts/recover_sleep_contract.py reads local services.jar, framework.jar and HCTManagerService.apk; optional --vold and --upstream-aidl inputs add the reviewed native/source metadata.
- scripts/compare_vold_transactions.py compares generated Java constants against the recovered tables. Four parser regression checks reject unsupported expressions and duplicate names/codes and verify the FIRST_CALL_TRANSACTION offset.

The upstream comparison source is [Android 13 r1 IVold.aidl](https://github.com/aosp-mirror-neo/platform_system_vold/blob/android-13.0.0_r1/binder/android/os/IVold.aidl), SHA-256 `2faaed2fc685750c410aa0adf2dea65d507f37093ce1daceaa8c2f2261a96150`. Its IVoldListener, IVoldMountCallback and IVoldTaskListener imports were fetched from the same tag into ignored work files. Compiler-only Parcelable forwards declared PersistableBundle and IncrementalFileSystemControlParcel; these are not runtime implementations. Generation used Debian aidl 14.0.0+r75-1 with minimum SDK 33. No generated Java or upstream firmware binary is published here.

No Java compilation, daemon execution, storage operation, suspend, power change or flashing was performed. This comparison establishes an additional porting requirement; it does not make a newer Android ROM bootable.
