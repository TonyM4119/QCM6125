# Reconstructed HCT Binder declarations

The two AIDL files under android/microntek declare the observed 26 ICarService methods and one one-way callback. Method names, types and declaration order preserve the owner-tested Malaysk interface; misspellings are intentional. They are original interface declarations reconstructed from the inspected contract, not decompiled implementations.

`test-support/framework-types.aidl` is a compiler-only declaration that Android already supplies Bundle. It is not an implementation and must not replace Android's framework class in a platform build.

## Local code-generation check

With an appropriate AIDL compiler available:

```sh
python3 scripts/check_binder_contract.py --aidl /path/to/aidl \
  --reference evidence/malaysk-proxy-wire.json \
  --report work/binder-contract-check.json
```

The checked run used Debian aidl 14.0.0+r75-1, generating Java with minimum SDK 33. Generated sources stay under ignored work/. They were not compiled to bytecode or executed. No Android 17 build, runtime Binder exchange or hardware test is implied.

The check compares all 27 generated proxy methods and Stub cases with separately recovered firmware evidence:

- Java signatures and interface descriptor Strings;
- transaction numbers, synchronous flags and null-reply one-way callback;
- ordered request writes and reply reads;
- Stub request reads, reply writes and no-extra-data checks.

The generated operations match this reference. The parser intentionally handles the tested compiler's conventional Java output and rejects differences; other compiler versions may require parser maintenance. This static comparison is not a general Java proof, and matching operation names cannot prove all value provenance or Bundle schemas.

These declarations alone do not create/register a service, implement state or audio behaviour, add HCTApi/CarManager, expose hardware devices, reproduce the custom 0x484354 transaction, or establish signing/permissions. Those require Android integration. Do not install the generated classes into the currently running unit.
