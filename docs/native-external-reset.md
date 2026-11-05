# Native external-disk reset follow-up

The working ARM64 vold executable permits a narrower reconstruction of the custom storage reset. This is static analysis of the known hash, not native execution or proof of newer Android compatibility.

## Anchors and confidence

The stripped executable has no recovered exreset-named symbol. It does retain an `exreset` trace string. Its direct code reference belongs to an unwind-described function at 0x57150. A relocated read-only C++ vtable entry points to that function. Nearby entries contain trace labels setListener, monitor, reset and shutdown, in an order consistent with the earlier Java-interface inventory; the abortFuse-position entry has no recovered trace label.

This connects the native trace wrapper to a concrete vtable entry. It still does not prove every BnVold transaction case, Parcel argument or return layout. [The native evidence report](../evidence/working-vold-native.json) records the pointers, unwind bounds and selected instruction checkpoints.

The [native dispatch follow-up](native-vold-dispatch.md) now resolves the 78-entry native switch and traces six selected cases. Five trace-labelled functions agree with both working Java transaction tables, including exreset at code 4. Complete native dispatch and construction/runtime review remain outside that check.

The wrapper calls a UID-checking helper with 1000. That helper reads IPCThreadState.getCallingUid and permits the requested UID or zero, otherwise constructing a Binder exception status. The normal wrapper acquires a mutex, calls the lower routine at 0x93238 and translates its status. Imported mutex, Binder-status and tracing functions were resolved through validated PLT/GOT relocations. This binary's PLT entries are 24 bytes; assuming a 16-byte stride would assign incorrect symbol names.

## Lower reset loop

The 0x93238 function walks a pointer container, reads a flag byte at object offset 0xc0 and tests mask 0x0c. Only matching entries call two routines, at 0x9a2e4 and 0x98b3c, in that order. The loop's normal return is zero; it does not branch on the two returned status values.

The called routines correlate closely with upstream Disk.destroy and Disk.create:

| Observed native behaviour | Upstream correlation |
| --- | --- |
| First routine checks created flag at 0xc4, traverses child entries and clears it | Disk.destroy destroys volumes and clears mCreated |
| First routine uses a listener slot corresponding to the later disk event position | onDiskDestroyed follows other disk listener methods |
| Second routine requires the opposite created-flag state and sets it | Disk.create checks !mCreated and sets mCreated |
| Second routine supplies the flag word to an earlier listener slot | onDiskCreated passes disk flags |
| Second routine takes a separate path for mask 0x60 | Upstream stub flags occupy bits 5 and 6 |

Upstream Android 13 Disk flags identify 0x04 as SD and 0x08 as USB. Thus the observed 0x0c selection is consistent with resetting SD/USB disks. This remains source correlation: no recovered C++ type information names the object field, and it does not establish the actual flags assigned to every disk on this unit.

The selected upstream VolumeManager.reset is broader: it also destroys internal emulated volumes, changes disk lists, updates virtual disks, clears user tracking and aborts FUSE connections. None of those additional operations appears directly in this narrow HCT loop. Callee side effects still require review. Substituting a full stock reset for the custom operation would not preserve the observed algorithm.

The [source fingerprints](../evidence/vold-source-correlation.json) identify the upstream comparison files. They are reference source, not recovered HCT kernel/vold source, and are not presented as an Android 17 checkout.

## Experimental reconstruction

`native/external_disk_reset.hpp` contains an original, isolated reconstruction of the source-correlated loop. It selects pointer-like disk objects with getFlags() & 0x0c, calls destroy then create, and returns zero on normal completion. It deliberately does not introduce a status-return short circuit absent from the binary. Exceptions are not swallowed.

The helper is **not connected to vold, the service core or any device**. Caller authorization, locking, valid object lifetimes, the surrounding Java media-provider/storage sequence and real disk/volume semantics are outside it. It must not be treated as a ready-to-flash storage patch. A platform implementation needs further native-dispatch and target-source review before integration.

The host test uses only fake objects. It checks SD/USB and combined flags, exclusion of nonmatching flags, per-object operation order, ignored ordinary status failures, exception propagation and an empty range. No filesystem, disk, daemon or power function is called.

## Reproducing the static review

scripts/vold_native_evidence.py accepts only the reviewed binary SHA-256 and validates its ARM64 type, function decoding, PLT/GOT matches and selected relocated vtable anchors. It emits short checkpoints and metadata, not the complete executable or function disassembly. It reports 438 validated PLT entries, 505 APS2 relocations and 714 RELR relocation locations.

scripts/android_packed_relocations.py provides the bounded APS2 metadata reader used by the profile. Five regression cases cover signed LEB128 bounds, grouped fields, accumulated/reset addends and invalid/truncated streams. RELR locations are decoded by pyelftools; the reviewed vtable pointer uses RELR, not APS2. These encodings are reported separately rather than applying one interpretation to both.

No ELF relocation was applied, no native executable was run and no storage or sleep request was sent. Native Binder dispatch, operation side effects and integration with the selected newer platform remain unresolved.
