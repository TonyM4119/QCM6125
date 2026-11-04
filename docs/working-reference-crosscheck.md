# Known-working Malaysk native reference cross-check

The owner reports previously testing the supplied Malaysk package successfully on this unit. This work inspected that package offline; it did not repeat the on-device test or execute firmware code.

The failed November 2022 XTRONS archive remains excluded as a porting base. Its native findings were compared with the March 2024 Malaysk ARM64 `libandroid_servers.so`, SHA-256 `19a34faff5bde74a3b1eeeaa6f48ee31ed087d5c4cc549459b925ab01e91e01e`.

## Native interface result

| Detail | Failed XTRONS reference | Known-working Malaysk reference |
| --- | --- | --- |
| Set JNI function address | 0xb94c8 | 0x923e0 |
| Get JNI function address | 0xb9590 | 0x924a8 |
| Set signature | (Ljava/lang/String;)I | Same |
| Get signature | (Ljava/lang/String;)Ljava/lang/String; | Same |
| Device opened | /dev/mtc-car | Same |
| Open access flags | 2 / O_RDWR | Same |
| Command encoding at JNI boundary | GetStringUTFChars, byte length from strlen | Same |
| Setter request | Byte length | Same |
| Getter request | Byte length OR 0x10000 | Same |
| Checked query-copy capacity | 0xc00 / 3072 bytes | Same |
| Success cleanup | close descriptor, release JNI string | Same |

Addresses are virtual addresses in the respective ELF, not portable runtime constants. In the Malaysk binary the device-path string is at 0x29243, the setter ioctl call is at 0x92444, and the getter ioctl call is at 0x92534. Before the query call, `orr w1, w23, #0x10000` provides the flag. The preceding checked-copy sequence sets w3 to 0xc00. The registration table ties these functions to the Java native names and signatures.

These observations support the prototype's basic native request encoding using a working firmware reference. They do not establish that the complete native libraries or drivers are identical. They do not explain the failed XTRONS update or make its board configuration usable on this unit.

## Tool correction and checks

The first tool version assumed every AArch64 PLT entry was 16 bytes. The Malaysk binary uses 24-byte entries, so that assumption produced no named calls despite locating the JNI methods correctly. The tool now decodes each target stub's GOT load and resolves it through the relocation records, rather than deriving names from a fixed stride.

Both files were reprocessed. The expected open, strlen, ioctl and close calls were resolved for both methods in both libraries, along with the checked copy and query-flag instruction in each getter. The reviewed outputs are `evidence/factory-car-jni.json` and `evidence/malaysk-car-jni.json`. No firmware executables, complete disassembly or library bytes are published.

## Implementation status and next boundary

The C++ transport already uses the matching byte-length/query-flag convention. No transport-code changes were required by this cross-check. Its prior fake-device and sanitizer checks remain host evidence only. Its defensive length, buffer and error handling intentionally differ from the firmware implementation, as documented in native/README.md.

Later [kernel inspection](working-kernel.md) established the actual driver-side input and response-copy bounds and tightened the prototype accordingly. The paragraph above records the earlier JNI-only comparison, not the current complete limit evidence.

The current January 2025 build is still a separate, unavailable binary reference. Its kernel driver ABI has not been inspected or exercised. The next work is to verify Binder parcel/callback behaviour and map the service's state/event and audio arbitration paths using the known-working package, then implement those behaviours against a selected Android source target. A transport match alone does not make a working ROM, establish Android 14+ compatibility, or remove the need for eventual separately authorized hardware validation.
