# Working-reference kernel driver findings

Static analysis of the March 2024 owner-tested Malaysk kernel (#247, Linux 4.14.190). The currently installed January 2025 kernel (#369) has not been obtained or inspected. Original kernel-image SHA-256: `57714b0fdbbb366e8b42059370a5474a7ef6efb6cd468a8b84089af5ddcc3f46`.

## Recovered symbol index and address checks

vmlinux-to-elf 1.4.0 recovered an AArch64 analysis ELF containing about 120,000 symbol entries from the embedded kallsyms data. This ELF is an analysis artifact, not original source, a boot image or an original debug build. It is retained only in ignored work/ and is not redistributed.

The recovery tool guessed base address ffffff8008080000 and warned that its offsets looked absolute. The guess was not accepted blindly: linux_banner and the mtc_dev_register export-name anchor both map to the expected bytes in the original image. Relative relocation addends independently link car_misc_device's name to "mtc-car", its operations to car_fops, and the ioctl slot to car_ioctl. Pointer fields in the raw image are zero before relocation; reading those zeroes as complete pointer values would have been incorrect.

The evidence tool reads R_AARCH64_RELATIVE records without executing or applying the kernel. The file-operation offsets are for the reviewed kernel structure/layout and must not be assumed valid for arbitrary kernels. Anchor or binding failures cause rejection.

## Command and response limits

The linked car_ioctl handler masks the ordinary text request length to 16 bits, subtracts 1, compares it unsigned with 0xBFE and rejects values above that threshold. Valid ordinary request lengths are therefore **1..3071 bytes**, for both setters and queries. The handler terminates the copied input and locates the last '=' with strrchr before dispatching into mtc_ioctl. It tests request bit 16 to distinguish query from setter.

The query response is a separate buffer/path. The inspected copy guard allows at most **0xF00 / 3840 bytes including the NUL terminator**. That differs from the legacy JNI query-copy object-size hint of 0xC00. The prototype now keeps input bounded at 3071 and allocates a 3840-byte response buffer, rather than treating the JNI input-copy bound as the driver's maximum response-copy size. No claim is made that typical responses reach this maximum or that the current January 2025 driver has identical limits.

The earlier prototype's 65535-byte setter allowance came from the request flag layout, before kernel inspection. It has been replaced with the actual inspected text-path bound. Tests reject 3072-byte requests before opening even a fake device, accept 3071-byte requests, accept a 3839-byte response plus terminator, and reject unterminated replies. Fake-device transport checks and address/undefined-behaviour sanitizer checks pass. No actual ioctl was issued.

The native transport passes command bytes unchanged, preserving the driver's last-delimiter interpretation. Java audio policy separately inspects the first '='; these layers must not be merged into an invented normalized key/value protocol. Error, length and buffer initialization behaviour in the prototype remain deliberately defensive rather than exact emulation of all legacy bugs.

## Kernel confirmation of virtual event framing

The recovered virtual-serial driver has driver/dev names ttyV. Its vs_send_func builds a buffer of payload length + 5, writes FA, category and subcommand into bytes 0..2, and the little-endian payload length into bytes 3..4. It then copies payload bytes and passes them through uart_insert_char and tty_flip_buffer_push.

This independently supports the frame layout already recovered from the Java parser and connects it to the ttyV event path. This is a kernel-created virtual stream format, not proof of the physical MCU UART protocol, its checksums or current-device timing.

Other recovered names include car/AV ioctl handlers, MTC wake/sleep helpers, virtual-serial send routines and a camera probe. Symbol names and machine code do not restore the original driver source, device-tree source labels, includes, build dependencies or a newer-kernel port. No replacement kernel has been built.

## Reproduction

Optional dependencies are listed separately in requirements-kernel-analysis.txt, alongside the ordinary ELF/Capstone analysis dependencies. If the Python environment expects a missing C compiler while building minilzo, select an installed compiler such as CC=gcc during dependency installation.

```sh
vmlinux-to-elf work/reference/kernel.bin work/reference/recovered-kernel.elf
python3 scripts/kernel_driver_evidence.py work/reference/kernel.bin \
  work/reference/recovered-kernel.elf work/reference/kernel-driver-evidence.json
```

Reviewed metadata and short instruction windows are in evidence/working-kernel-driver.json. No kernel binary, recovered ELF or complete driver disassembly is committed. The analysis tool deliberately targets the reviewed symbol/structure/instruction shapes and rejects unsupported layouts rather than guessing.
