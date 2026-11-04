# RDS bytes and background search results

This extends the earlier radio mappings using the same owner-tested Malaysk services.jar. It is an offline receive-data model; no tuner command or hardware operation is performed.

## Byte-array text semantics

The HctUtil.getAsciiByteArray helper scans until the requested count or the first zero byte, then returns a byte-array prefix. It does not decode a Java String or transcode high-bit characters. Consequently category 11/subcommands 23 (rt) and 26 (psn), all hexadecimal, emit Radio callbacks with their prefix bytes in value. Empty payloads become empty arrays.

A different helper named getAsciiString decodes GB2312. Its existence does not justify applying that decoding to the byte-array radio fields. TV/DAB text-list handling is still outside the implemented mapper.

## Background station result

Category 11/subcommand 41 emits Radio, type=bg_seek_found:

| Field | Payload offset | Interpretation |
| --- | --- | --- |
| freq | 0..2 | Little-endian three-byte integer multiplied by 1000 |
| db | 3 | Unsigned byte, stored as int |
| pi | 4..5, when length exceeds 4 | Little-endian two-byte integer; otherwise int 0 |
| psn | 6 onward, when length exceeds 6 | Up to eight bytes, stopping at NUL; otherwise null byte array |
| pty, tp, ta | Not read here | Each explicitly int 0 |

The callback uses named freq/db/pi/psn fields, not a generic value field. Null PSN differs from an explicitly present empty array. The model represents null by monostate; a future adapter must interpret it as a nullable byte array in this schema, rather than assuming every monostate is a nullable String.

At least four payload bytes are needed. A five-byte payload truncates PI and is rejected. If a PSN field is present, it must either contain a terminator within the available frame bytes or provide the full eight-byte field. These checks enforce per-frame bounds. The original helper receives a larger serial accumulation buffer and can inspect beyond a malformed frame's declared payload; the model deliberately does not reproduce that behaviour or consume bytes from another frame.

These three pairs bring the mapper to 36 implemented category/subcommand pairs. Other formats remain unknown. This does not cover all radio firmware behaviour or establish compatibility with the currently installed January 2025 driver.

## Checks

Host tests preserve a high-bit RDS byte, truncate at NUL, retain empty arrays, verify background frequency units/strength, distinguish absent and empty station names, accept a full eight-byte name and reject truncated results. Existing Java-int frequency wraparound checks remain in place. All input is synthetic, and the five portable test programs pass through make test. No Android callback or real driver is exercised.
