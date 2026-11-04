# HCT callback delivery boundary

The owner-tested March 2024 reference separates service broadcast from client filtering. `CarService.dispatchCallback` uses RemoteCallbackList, calls each non-null callback and catches RemoteException around each call. `dispatchMessage` enters that broadcast path under mLock. The service receives no subscription string when registering a callback.

`CarManager$1.onStatusChanged` performs the client-side filter with `mType.contains(eventName)`. The match is case-sensitive and has no token-boundary check. Thus `RadioExtended` accepts `Radio`. An empty event name matches an empty non-null type string. Replacing this with equality or a set of parsed tokens would alter behaviour.

After a match, a non-null Handler takes precedence. The code obtains a Message with `what = -1`, assigns the event name to `obj`, sets the supplied Bundle and calls sendMessage. If there is no Handler but there is a listener, it calls the listener's onStatusChanged. A Handler-path exception does not trigger listener fallback. Neither path's success is established by the offline model.

## Attachment lifecycle

The two attach overloads accept a Handler or listener plus a type string. Both refuse attachment if either target is already present, or the new target/type is null. They store the target/type before requesting callback registration. The reviewed exception path does not undo those assignments, so registration failure is not equivalent to a clean unattached state. Empty non-null type strings are not explicitly rejected.

Detach requests unregistration when a target exists, then clears both targets even after the handled registration-service exception. It does not clear mType in the reviewed method. A future adapter must also support Binder death handling through the platform callback mechanism; a vector of C++ function pointers would not provide that lifecycle.

## Offline implementation and evidence

`native/callback_policy.*` models only non-null ASCII type/event strings, a non-null field map, and the target-selection decision. It returns a detached delivery description; it invokes no callback, Handler, Binder or device. Presence flags make precedence explicit, including the defensive case of both targets being present. Ordinary attach calls prevent that case.

The tests check combined subscriptions, substring/case/empty-name behaviour, absent targets, Handler precedence, message shape, listener routing and delivery from the existing CarData queue. The pure planner has no registration, exception, ordering, thread-affinity or backpressure model. C++ byte strings are not a general replacement for Java UTF-16 matching, and copied field maps do not reproduce same-process Bundle aliasing.

The source references are the CarService methods in services.jar SHA-256 `b3c0f55f7e5830d7213576ee3dad3c910422820b3dbf94c5527cad97120ae6fe` and CarManager/CarManager$1 in the framework.jar identified by the existing proxy-wire evidence. Local instruction review found these checkpoints:

| Method | Byte offset | Reviewed operation |
| --- | --- | --- |
| CarService.dispatchCallback | 0x06 / 0x2a / 0x48 | beginBroadcast / onStatusChanged / finishBroadcast |
| CarService.dispatchMessage | 0x06 | dispatchCallback |
| CarManager.attach (both overloads) | 0x18 / 0x1c / 0x28 | store target / store type / registerCallback |
| CarManager.detach | 0x18 / 0x24 / 0x28 | unregisterCallback / clear Handler / clear listener |
| CarManager$1.onStatusChanged | 0x0c | String.contains |
| CarManager$1.onStatusChanged | 0x34 / 0x3e / 0x42 / 0x54 | what=-1 / obj / setData / sendMessage |
| CarManager$1.onStatusChanged | 0x7e | listener onStatusChanged |

These are derived observations from the known-working package, not runtime verification of the installed January 2025 build. Callback Parcel flags were independently checked against generated AIDL; see [the service-layer report](service-layer.md).
