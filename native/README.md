# Experimental MTC transport

This is an original, minimal C++17 implementation of the native parameter transport observed in the November 2022 factory ARM64 library. It is not a ROM, Android service, JNI replacement, or complete CarService implementation. It has only been tested on the host using an injected fake device.

The Linux backend opens `/dev/mtc-car` only when explicitly called. No device-facing command-line program, flashing operation or automatic probe is included. Construction alone performs no I/O. Host tests use FakeDevice, not LinuxDeviceCalls.

The protocol facts and their limits are documented in [native transport findings](../docs/native-transport.md). Command bytes should initially be restricted by a future service to known, reviewed operations. Arbitrary MCU commands have not been validated. There is no claim that a query is side-effect-free merely because it uses the observed query bit.

## Host checks

From the repository root:

```sh
mkdir -p work/tests
c++ -std=c++17 -Wall -Wextra -Werror -pedantic -pthread \
  native/mtc_transport.cpp native/transport_test.cpp -o work/tests/transport_test
./work/tests/transport_test
```

The checks cover request lengths/flags, command and response bytes, ioctl return values, descriptor cleanup on failures, open failure, missing response termination and invalid-input rejection. No actual hardware is accessed.

The transport intentionally clears query buffers, bounds accepted lengths, reports syscall failures and rejects embedded NUL bytes. Those choices differ from the observed factory implementation and need compatibility review. This is not byte-for-byte emulation. It accepts already encoded bytes; a future Java/JNI adapter must account for JNI modified UTF-8 rather than silently assuming ordinary UTF-8 is equivalent.

Use one shared transport instance for synchronization. Multiple instances/processes do not share its mutex. Events/callbacks and serial reads are not implemented. Kernel/driver sources and exact command semantics remain outside this component.
