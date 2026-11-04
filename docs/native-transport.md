# Factory native transport reconstruction

**Compatibility correction:** the owner confirmed that the November 2022 XTRONS archive did not work on this exact unit. It is not an approved porting base. Analysis derived from it remains evidence about that package only; the experimental native transport has not yet been validated against a known-working driver/native implementation. The failure symptoms and cause are unknown.

Recovered offline from ARM64 factory `libandroid_servers.so`, SHA-256 `815a2fab3a26d6dbbf79d10240add486a78b285f9f8c37250870dc965b1a077e`. Addresses below are ELF virtual addresses for this exact binary, not offsets or addresses valid on every firmware release.

## JNI bindings

The exported CarService registration function is at `0xb9014`. Its instructions pass a two-entry table at `0xd2570` to JNI RegisterNatives. The table entries identify:

| Java native | Signature | Native function | Table entry |
| --- | --- | --- | --- |
| native_setParameters | (Ljava/lang/String;)I | 0xb94c8 | 0xd2570 |
| native_getParameters | (Ljava/lang/String;)Ljava/lang/String; | 0xb9590 | 0xd2588 |

This ties the recovered functions to the Java declarations; they were not selected solely because they contain an interesting device-path string.

## Observed driver ABI

Both functions open `/dev/mtc-car` with flag value 2 (O_RDWR). JNI string handling uses GetStringUTFChars / ReleaseStringUTFChars; lengths therefore count modified-UTF-8 bytes, not Java characters.

| Operation | ioctl request | Argument | Result handling in factory |
| --- | --- | --- | --- |
| Set | strlen(command bytes) | Pointer to command bytes | ioctl result returned as Java int; descriptor closed |
| Get | 0x10000 OR strlen(query bytes) | Mutable buffer, with query bytes copied into it | Descriptor closed; buffer converted with NewStringUTF |

Selected instruction evidence:

- Setter calls strlen at `0xb951c`, moves the length to x1 and command pointer to x2, then calls ioctl at `0xb952c`.
- Getter prepares a checked copy with destination capacity `0xc00` (3072 bytes), combines the byte length with `0x10000` at `0xb9610`, and calls ioctl at `0xb961c`.
- Both functions use the `/dev/mtc-car` string at `0x3b2d6`.

This ABI uses a length-plus-flag request; it should not be replaced with an invented conventional _IOW/_IOR structure. The native getter does not check the ioctl return before converting the buffer to Java. Its buffer reuse/termination assumptions have not been established from driver source. Neither the request flag nor names prove that every query has no hardware side effects.

## Java service semantics must also be preserved

The Java CarService serializes getParameters/setParameters through mLock. setParameters rejects null strings and strings without '='. It does more than pass bytes to the native function:

- It maintains application audio-channel state for av_channel_enter/exit commands.
- For some av_ commands it also calls AudioManager.setParameters.
- Exiting the active non-system audio channel can restore the system channel before issuing a native command.
- av_gps_package updates navigation-package state through a separate branch.

Consequently, exposing only the native ioctl transport will not preserve audio arbitration. A compatible service needs the state machine, audio HAL interaction, callbacks and policy hooks as well as the driver ABI.

## Implementation milestone

`native/mtc_transport.*` implements the narrow transport with injected syscalls and a Linux backend. Fake-device host checks pass. It deliberately improves bounds/error handling and uses per-query initialized storage; those differences are documented and have not been validated against a head unit. The code is not installed anywhere and has not accessed hardware.

This establishes a small component that can later sit behind an Android service. Still missing: complete Binder parcel-layout verification, Java API/service adaptation, driver event decoding, command semantics, audio/DSP orchestration, camera integration, input and sleep/wake behaviour, SELinux/build configuration, and an Android target build. No claim of newer-Android compatibility follows from host tests.

## Binder constants milestone

Static TRANSACTION_ fields were recovered from five HCT Stub classes in both packages. All 40 method-to-number mappings match: 26 for ICarService, one for ICarManageCallback, ten for IMfiService, one for IMfiCallback and two for IMfiListener. For example, ICarService setParameters is transaction 17 and getParameters is 18; registerCallback/unregisterCallback are 15/16.

The factory's spelling of names such as putByteArraryState and putDataChanage is retained in the evidence. These are interface names, not corrected English. The derived tables are in `evidence/factory-binder-constants.json` and `evidence/malaysk-binder-constants.json`. This is stronger evidence of interface stability than Java signatures alone, but still does not verify Parcel encodings, one-way flags, permission checks or runtime equivalence.

To reproduce the constants extraction with Androguard 4.1.4 installed:

```sh
python3 scripts/recover_binder_constants.py \
  work/factory/system/framework/framework.jar \
  work/factory/binder-constants.json
```

The tool records original ZIP CRC statuses separately from the in-memory hidden-API workaround. The known stale CRC in the modified Malaysk classes.dex remains reported as a mismatch; it is not silently treated as valid.

## Reproduction

With locally extracted factory files and the optional Python dependencies installed:

```sh
python3 scripts/recover_car_jni.py \
  work/factory/system/lib64/libandroid_servers.so \
  work/factory/car-jni.json
```

The tool reads ELF tables and disassembles selected instruction windows. It never dlopens or executes the input. `evidence/factory-car-jni.json` records the reviewed address/call-site evidence. It assumes a conventional AArch64 PLT and a JNI table with directly readable pointer addends, as present in this package; other builds may need different relocation handling.
