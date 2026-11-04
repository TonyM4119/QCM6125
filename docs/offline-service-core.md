# Integrated offline service core and radio callbacks

`native/offline_service_core.*` connects framing, event mapping and parameter policy into one host model. It has no device, Binder or Android service connection. It never executes a parameter plan or invokes an external callback.

## Integration behaviour

- receive accepts supplied byte chunks. Mapped frames update in-memory state and append callback descriptions. Unknown and malformed frames are counted separately and do not change state.
- state_snapshot returns a detached copy; nullable camera-mode clearing uses monostate.
- plan_parameter returns the ordered audio/driver plan without executing it and reflects its audio/navigation state in the snapshot.
- drain_notifications transfers queued descriptions once, in order. A default backlog limit of 256 drops the oldest description on overflow, retains current state and reports the drop count.
- Public operations are mutex-protected; no external callback executes under the lock.

The bounded queue is a host-model policy, not a reconstruction of Android Binder/RemoteCallbackList scheduling. This model does not expose all typed ICarService state methods, persist settings, register Binder callbacks or perform Android permission checks. Nor does it roll back state after future adapter failures. It is not an Android service replacement or ROM build.

## Additional radio mappings

Working Malaysk cmdProc category 0x11 provides these additional mappings. All emit Radio notifications; the reviewed branches do not write shared service state.

| Subcommand (hex) | Callback type | Fields / payload interpretation |
| --- | --- | --- |
| 20 | seek_end | None |
| 21 | seek_found | strength: unsigned byte |
| 22 | seek_end_auto | None |
| 24 | tp | value: unsigned byte, retained as int |
| 25 | freq | value: 3-byte little-endian integer multiplied by 1000 |
| 27 | pty | value: unsigned byte |
| 28 | pi | value: 2-byte little-endian integer |
| 29 | stereo | value: unsigned byte, retained as int |
| 31 / 32 | ta | value: int 1 / 0, no payload needed |
| 33 / 34 | seek_start / seek_start_auto | None |
| 35 | seek_found_auto | strength: unsigned byte |
| 40 / 42 | bg_seek_refresh / bg_seek_end | None |

These 15 pairs extend the original 18 to 33 implemented pairs. RDS conversion, background-search result structures and other unimplemented commands remain unknown. Existing switch-target evidence includes these subcommands.

Follow-up: [RDS bytes and background-search results](radio-payloads.md) add three verified receive mappings, bringing the current total to 36. The statement above describes the earlier implementation milestone; unimplemented formats still remain unknown.

Frequency scaling preserves Java int wraparound using unsigned multiplication and explicit signed conversion, avoiding C++ signed-overflow undefined behaviour. Tests encode 107900 as 7C A5 01 and expect 107900000, plus a boundary wraparound case. No frequency command is sent to hardware; these are received callback descriptions.

## Validation

`make test` builds and runs the portable suites. New scenarios check split camera frames, ordered camera/radio callbacks, frequency units, independent audio state, detached snapshots, bounded backlog and malformed/unknown input isolation. All input is synthetic; these tests do not establish January 2025 driver or hardware compatibility.

Next Android-facing work includes compiled Binder declarations and Parcel checks, the actual service/state adapter, and serial/audio wiring. Larger build infrastructure remains necessary for full platform compilation, not these host tests.
