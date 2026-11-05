# Native vold dispatch and Java-interface cross-check

This follow-up statically traces the working native storage daemon's transaction switch. It does not send Binder requests or execute any firmware code.

## Dispatch switch

The unwind-described function at 0xd3268 subtracts 1 from the supplied code, compares the unsigned result against 77 and selects a 16-bit jump-table entry. The table is at 0x1a53c, with targets computed as `0xd32c0 + entry * 4`. This yields 78 targets; each resolves to a BTI entry inside the reviewed function. This verifies switch bounds and target placement, not the meaning of every transaction.

Six selected cases were traced to their vtable loads and shared invocation tails. The primary vtable address point, 0xdd7f0, is inferred from the previously anchored setListener slot and its load offset. Each selected target pointer has a RELR relocation and an unwind-described function. No complete object-construction proof is claimed.

| Native code | Case address | Vtable offset | Target trace label |
| --- | --- | --- | --- |
| 1 | 0xd32c0 | 0x20 | setListener |
| 2 | 0xd3dc0 | 0x28 | No trace label recovered |
| 3 | 0xd3de8 | 0x30 | monitor |
| 4 | 0xd3e10 | 0x38 | exreset |
| 5 | 0xd3e38 | 0x40 | reset |
| 6 | 0xd3e60 | 0x48 | shutdown |

Code 4 therefore selects the reviewed pointer at 0xdd828, whose target is the exreset trace wrapper at 0x57150. Code 5 selects the following pointer, whose target carries the reset trace label. This supports the historical HCT numbering already recovered from Java, rather than treating a native string alone as evidence of dispatch.

## Parameterless reset call and reply

The code-4 block checks the interface through Parcel.checkInterface, then loads the vtable target and branches to the shared tail at 0xd56c0. The reviewed block reads no additional argument. The tail invokes the selected function through x9 and writes its Binder Status to the reply Parcel using Status.writeToParcel. The selected block/tail contain no enforceNoDataAvail call; the report does not invent one from the separately checked Java HCT car-service interface.

The initial code-1 case has a different argument path, so its detailed Parcel semantics are not inferred from code 4. No claim is made that all 78 native cases have matching argument layouts, error handling or reply behaviour.

## Cross-source check

scripts/vold_native_evidence.py now emits the switch, selected cases, resolved pointers and short shared-tail checkpoints in [the native report](../evidence/working-vold-native.json). It remains restricted to the exact reviewed vold SHA-256 and validates the known instruction shape before interpreting the table.

scripts/check_vold_bindings.py compares each unambiguous native trace label with the method codes in both recovered working Java tables. The input binary hashes must agree. Five labelled cases produce ten matching Java/native name-and-code bindings; the unlabelled code-2 case is explicitly excluded from name validation. Both the source and native report hashes are retained in [the binding report](../evidence/vold-native-java-bindings.json).

Five regression checks cover the consistent baseline, a changed native code, one changed Java table, a different input binary hash and an ambiguous native label. They use synthetic metadata only and are included in make test.

## Consequence for the port

The earlier mismatch with generated upstream Android 13 is now supported by selected native dispatch evidence as well as Java constants. A newer platform must provide a consistent framework/daemon pair and preserve the external-reset operation; pairing components solely by method names would miss the numbering change.

The historical HCT numbers need not be imposed on every newly generated upstream interface if the relevant native and Java clients are rebuilt together. The remaining design task is to choose a target-source integration that implements the operation while keeping that pair consistent. This report does not provide an Android 17 interface, a complete native ABI audit or a bootable image.

A subsequent [Android 17 interface-only experiment](../platform/experiments/vold17/README.md) appends exreset without renumbering any of 84 standard methods. It supplies a reviewable interface patch and generation checks, but no native service implementation or platform image.

No Binder, mount/unmount, sleep, power or flashing operation was performed.
