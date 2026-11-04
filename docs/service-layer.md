# Working-reference service layer

This analysis uses the owner-tested March 2024 Malaysk package, not the failed XTRONS package. No device or firmware executables were run. The January 2025 installed build remains a separate, unavailable binary reference.

## Binder directions and Parcel operations

All 26 ICarService proxy methods use transaction flag 0, a reply Parcel and readException: they are synchronous. Requests start with interface token `android.microntek.ICarService`. Transaction numbers agree with the earlier Stub constants.

ICarManageCallback uses transaction 1 with flag 1 (one-way), a null reply Parcel and no readException. Its request writes token `android.microntek.ICarManageCallback`, an event-name String and a typed Bundle. Making callbacks synchronous would change the contract.

| Call | Code | Request after interface token | Reply after exception marker |
| --- | --- | --- | --- |
| setParameters | 17 | String | int |
| getParameters | 18 | String | String |
| registerCallback / unregisterCallback | 15 / 16 | Strong interface reference | No payload |
| getBooleanState | 8 | String | Boolean |
| getByteArrayState | 12 | String | Byte array |
| dispatchMessage | 20 | String, typed Bundle | No payload |
| onStatusChanged callback | 1 | String, typed Bundle | No reply: one-way |

`evidence/malaysk-proxy-wire.json` records all selected signatures, Parcel operations, codes and flags. `scripts/recover_proxy_wire.py` uses narrow straight-line constant propagation and rejects unresolved transact codes/flags. It is not a general control-flow analyser. Bundle schemas, server enforcement and target-platform compatibility need separate review.

## Callback distribution

CarService uses RemoteCallbackList to register non-null interfaces and broadcast named events with Bundles. dispatchMessage forwards through that path under mLock. Binder callback lifecycle and death handling need to remain supported.

CarManager filters callbacks on the client using the attached type String's `contains(eventName)` result. It then sends a Handler message with what=-1, obj=eventName and the Bundle, or calls the listener's onStatusChanged. This is not an exact server-side topic subscription: changing it to equality would alter clients attaching several event names in one String.

The [callback delivery review](callback-delivery.md) records attachment lifecycle, target precedence and instruction checkpoints. A pure host planner now tests the client filtering and delivery shape without invoking Android or Binder.

## Separate serial event stream

initComm obtains Android SerialManager and opens `/dev/ttyV2` at 38400 baud, allocating a 4096-byte ByteBuffer and starting a reader. Successful reads feed DataProc, which accumulates bytes, finds frames, calls cmdProc and retains the unconsumed tail. This stream is separate from parameter-command ioctls.

HctUtil.getFramePos/getInt2 indicate this frame shape at the Java layer:

| Offset | Meaning |
| --- | --- |
| 0 | Marker 0xFA (Java signed byte -6) |
| 1 | Command/category |
| 2 | Subcommand |
| 3..4 | Little-endian payload length |
| 5 onward | Payload |

The computed total is payload length + 5. The helper searches for the marker and waits for enough bytes; no checksum comparison is visible in that helper. This does not establish that upstream drivers/MCU transport lack checksums. Overflow and resynchronization require further review: the two-byte length can exceed the service's 4096-byte buffer.

cmdProc updates state and emits topics including CarEvent, VideoSignal, TouchStudy and CarBox. Observed handling includes video/reverse-camera signals, touch events and DSP state. A full category/subcommand-to-Bundle map remains to be reconstructed; these labels do not identify the raw MCU protocol or prove the current driver's compatibility.

## Additional projection-audio transaction

CarService.onTransact recognizes 4735828 (`0x484354`) outside the normal 1..26 table. The observed branch reads two raw ints, updates `carboxaudio` and `audio_session_id`, broadcasts CarBox with type="audio", value and value2, then calls the superclass onTransact.

Generating only the standard AIDL interface would omit this path. Caller identity, framing and full return behaviour require further investigation before reproducing it. This repository does not implement the special transaction.

## Audio-channel policy model

Original portable code in `native/car_parameter_policy.*` models the observed setParameters branches. It performs no I/O and produces an ordered action plan for a future Android/driver adapter:

- Null commands or strings without '=' return -1 locally.
- Non-av_ commands produce only a driver action.
- av_ commands require a non-empty value after the first '='.
- av_channel_enter updates channel state, then plans audio-system and driver actions.
- Exiting an inactive channel sends neither action. Exiting the active non-system channel restores sys through av_channel_enter=sys. Exiting sys is a no-op.
- av_gps_package changes navigation-package state and plans an audio-system configuration update through putStringState; it does not issue a driver ioctl.
- Other av_ commands plan audio-system then driver actions.

When forwarding to the driver, the eventual service must return its result. The model starts with sys and updates state before the adapter executes the plan; it does not roll back driver failures. The observed Android service skips AudioManager calls if the manager is unavailable and still calls the native driver; the future adapter must account for that.

Typed state storage, persistence, callbacks, permissions, synchronization and Android adapters remain unimplemented. This is a narrow model, not a full service. Java string encoding and the transport's separate NUL/length checks also remain adapter concerns.

Correction from helper-level review: the original host model treated av_gps_package as having no audio side effect. The concrete service calls putStringState("navi_package", value), whose conditional branch calls AudioManager.setParameters("av_gps_package=" + value). That indirect effect is now included and regression-tested. It does not switch the selected audio channel or issue a native ioctl. The host model still produces plans only; no AudioManager operation was executed.

## Checks and remaining boundaries

Host policy tests cover stale exits not interrupting active audio, active exits restoring system audio, navigation configuration not changing channels, invalid-input rejection and ordered forwarding. No hardware or Android system is accessed. The extractor recovered 27 proxy methods and their transaction numbers were checked against earlier Stub constants.

Next: server-side Parcel enforcement, exact Bundle schemas, frame decoding and typed-state updates, audio HAL expectations and input/power/window hooks. Android source-target selection/build integration and hardware validation remain outstanding. No replacement ROM was assembled or flashed.

Follow-up: the reconstructed [AIDL declarations](../interfaces/README.md) pass Java generation with a local AIDL compiler. All 27 generated proxy/Stub methods match the recovered signatures, numbers, Parcel operation sequences and callback flags, including per-case no-extra-data checks. The report is evidence/binder-contract-check.json. This is code-generation/static verification, not a compiled Java service or runtime Android test. Bundle schemas and concrete CarService overrides remain outside that check.
