# Typed HCT state and notification contract

The offline core now models boolean, signed byte, signed 32-bit integer, string, byte-array, integer-array and nullable-string-array state. The owner-tested March 2024 service uses the matching Bundle methods, guarded by a lock. Missing or mismatched primitive values return false/zero; reference getters return null. Null reference values and empty arrays/strings remain distinct. A stored null still occupies a key in the snapshot.

The original interface spellings `putByteArraryState`, `putIntArraryState`, `putStringArraryState` and `putDataChanage` remain in the reconstructed AIDL. The C++ model uses readable snake-case method names; it is not itself a Binder implementation.

## Shared state and navigation audio

Direct state writes and parameter commands use one state map. This matters when an app writes `av_channel` directly: a subsequent matching exit must see that channel and plan a return to `sys`. A separate cached channel would silently diverge. A null or wrongly typed channel causes the host exit planner to throw a logic error; this represents an invalid service state, not a recreation of the Java exception type. Explicit channel entry can restore a string value.

`putStringState("navi_package", value)` also calls AudioManager with `av_gps_package=` followed by the value. Java string concatenation turns null into the literal `null`; an empty direct string produces a parameter ending in `=`. In contrast, the `setParameters` entry rejects an empty value. The model returns these audio actions without executing them. There is no driver ioctl in this navigation branch.

Ordinary typed writes do not produce callbacks. `putDataChanage(type, value)` produces a `CarData` notification containing the two nullable strings and does not update the shared state map. The offline implementation queues that description with its existing bounded queue policy.

## Evidence and validation

`scripts/recover_state_contract.py` extracts selected method references and constants from a local services.jar. [The reviewed inventory](../evidence/malaysk-state-contract.json) identifies its source by SHA-256. References establish which methods occur; the behavioural interpretation above also uses local instruction/control-flow review. An inventory alone does not prove branch ordering or runtime success.

`make test` includes state-contract scenarios covering typed defaults, wrong-type reads, null versus empty values, signed bytes, array copies, direct-write/parameter consistency, navigation audio actions and CarData notifications. Inputs are synthetic. No Android service, audio API or device is accessed.

## Remaining differences

The host API requires non-null keys and copies arrays on retrieval. It does not reproduce Java in-process array aliasing, nullable Bundle keys, Android string encoding/Parcel behaviour, permission enforcement, global static-state lifetime or exception details. Each core instance has its own state. Binder declarations have been checked separately with Java code generation, but there is no deployed Binder adapter or newer Android ROM yet.
