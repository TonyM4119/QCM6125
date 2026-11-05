# EQ, loudness and video control methods

This review uses the owner-tested March 2024 Malaysk service. The currently installed January 2025 implementation remains unavailable. No setting, audio command or device operation was executed.

## Deferred setters

The public setters remove pending Handler messages of the same kind before posting their replacement:

| API | Message what | Payload | Delay |
| --- | --- | --- | --- |
| setEqIdx(index) | 0 | arg1 = supplied integer | 10 ms |
| setLud(enabled) | 1 | arg1 = 0 or 1 | 10 ms |
| setVideoOverSpeed(value) | 2 | obj = boxed Boolean | 50 ms |

These are separate message kinds; a new EQ request does not cancel a pending loudness request. The EQ setter itself does not clamp the supplied index. Its private handler target setEQ later normalizes values outside 0..6 to zero.

`native/deferred_controls.*` supplies a bounded, deterministic host queue for these three kinds. The caller supplies monotonic milliseconds and explicitly drains due work. Equal deadlines preserve insertion order. Pending work of a matching kind is removed even if overdue but not yet dispatched. This models a stalled dispatcher without assuming it has run. Backwards times and arithmetic overflow are rejected without changing the pending requests. The queue owns no thread and is not thread-safe; an adapter must serialize its use. It never applies the returned messages.

`native/control_policy.*` describes the individual messages. The video handler updates isVideoOverSpeed and emits `CarEvent` with type `handbrake` and a **boolean value containing the current handbrake state**, rather than the new speed flag. The model returns the notification description separately; it does not update the integrated core's speed state.

## Settings and loudness

The service's getInt/putInt wrappers use Settings.System, which is separate from the in-memory Bundle exposed by typed state methods. A compatible adapter must not merge those stores.

| Read | Setting | Default |
| --- | --- | --- |
| getEqIdx | KeyEQmode | 1 for customer sub KGLMMR or KGL1; otherwise 0 |
| getLud | key_Lud | 1 for KGLMMR only; otherwise 0 |
| getVideoEnable input | DrivingVideoEN | 0 |
| getVideoEnable input | DrivingVideoOverSpeed | 0 |

The customer sub property is `ro.product.customer.sub`, with fallback HCT. The different EQ/loudness defaults are intentional observations, not a typo to normalize.

The private setLUD handler target constructs one native parameter command:

| DSP mode | Input value exactly 1 | Other input value |
| --- | --- | --- |
| 0 | av_lud=on | av_lud=off |
| Nonzero | av_dsp=1,1,GAIN | av_dsp=1,0,GAIN |

GAIN is the Settings.System string KeyLudGain. Only null selects `0,0`; an empty string stays empty. The public boolean setter normally supplies 0/1, but the private routine retains the supplied integer when persisting key_Lud and broadcasting CarData with type `LOUND_MODE` and an **integer** value. That original spelling and value type differ from the string-valued putDataChanage API.

Ordering is native command, setting write, then callback. The native return value and Settings.System.putInt boolean result are not used to skip later steps in the reviewed normal path. Exceptions can interrupt that path; the pure plan does not claim transactional behaviour. These commands call native_setParameters directly, not the public audio-arbitration method.

## Video predicate

Literal getVideoEnable result, with B = stored boolean handbrake, D = DrivingVideoEN, S = DrivingVideoOverSpeed and O = isVideoOverSpeed:

`B && (D == 0 || (D == 1 && S != 0 && O))`

Nonzero S includes negative values. Other D values yield false. This records the original predicate; it does not interpret physical handbrake polarity, alter restrictions or establish which window/camera consumers use the result. Settings names alone are insufficient to infer that meaning.

## EQ remains a separate integration task

The private setEQ selects custom settings KeyCustomEQ/KeyCustom1EQ through KeyCustom6EQ using KeyCTmode, uses preset/default arrays and has separate DSP paths including modes 15 and 31. It sends av_eq= or av_dsp=0, commands, persists KeyEQmode and emits integer-valued CarData/EQ_MODE. The initial control milestone did not implement this path. The [EQ follow-up](eq-policy.md) now provides its offline selection/conversion model and recovered preset data; actual Android/driver integration is still outstanding.

getParameters delegates to the native query under mLock. The previously recovered ioctl transport remains separate; a pure query plan cannot validate the response meanings or the current installed driver's behaviour.

## Evidence and checks

[The control inventory](../evidence/malaysk-control-contract.json) records the source SHA-256, selected method bytecode hashes, method references and whitelisted constants with byte offsets. Reproduce it using scripts/recover_control_contract.py and the local services.jar. It contains no full disassembly or binary payload. Branch and ordering interpretations above also rely on local control-flow review; the inventory alone does not prove them.

getVideoEnable branch checkpoints are 0x30/0x34/0x38/0x3c/0x40/0x48, with true at 0x4e and false at 0x52. setLUD selects DSP at 0x0c, compares the value to 1, writes the setting at 0xb2 and dispatches at 0xe2. The public setters call removeMessages before sendMessageDelayed.

`make test` includes control payload/default/loudness/video cases and fake-time replacement, boundaries, ordering and error-preservation cases. No Android timing, driver, persistence or hardware compatibility has been tested. The remaining platform adapter must supply actual settings, Handler scheduling, Binder lifecycle and driver/audio connections.
