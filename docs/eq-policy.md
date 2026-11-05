# EQ coefficient selection and conversion

`native/eq_policy.*` models the private setEQ handler target from the owner-tested March 2024 service. It returns a driver command, a Settings.System write description and a CarData notification. It executes none of them. The public setter's separate delayed replacement behaviour is documented in [control methods](control-methods.md).

## Selection rules

Indices outside 0..6 normalize to zero at apply time. Index zero is custom/default; indices 1..6 choose the six stored preset rows. DSP modes 15 and 31 use 15 and 31 coefficients respectively, with prefix `av_dsp=0,`. Every other mode takes the reviewed three-coefficient path with prefix `av_eq=`. The presence of other arrays in MTCData does not mean this particular routine selects them.

For index zero, KeyCTmode 0 selects KeyCustomEQ and 1..6 select KeyCustom1EQ through KeyCustom6EQ. Other custom modes select no stored string. The helper exposes that key selection; the caller must supply the corresponding setting value. A non-null stored string is used unchanged, including an empty string and regardless of its coefficient count. This reproduces the observed selection, not validation of whether that command would be accepted by hardware.

Missing custom data defaults to all 10s for the 15/31-band paths. For the three-coefficient path, the service first attempts getDefEq9modeString using property `ro.product.keycustomeq9`. If that returns null, it uses `10,10,10`.

## Property reduction

The reviewed helper requires a comma, uses Java String.split(","), parses signed 32-bit integers, accumulates each group of three and emits its arithmetic average. Java int sums wrap and division truncates toward zero. There is no exact-nine-elements validation. Incomplete final groups do not emit an average, but a previous group can leave a trailing comma; input `1,2,3,4` returns `2,`. A string containing only commas returns an empty string, which is distinct from null and prevents the flat-default fallback. Trailing empty split elements are discarded. Parse errors return null.

The host helper implements ASCII numeric input, including signs, whitespace rejection, numeric bounds and explicit wraparound without C++ signed-overflow undefined behaviour. It does not claim compatibility with Java's acceptance of non-ASCII decimal digits. That remains an adapter boundary if such property values ever need support.

## Presets and evidence

[Recovered numeric tables](../evidence/malaysk-eq-tables.json) contain only the three arrays actually referenced by the reviewed setEQ branches: music_stytle_data, music_stytle_data15 and music_stytle_data31. The original field spelling is retained. Each has six rows. Values stay in their original order and scale; no conversion to dB or frequency labels is inferred.

scripts/recover_eq_tables.py statically follows the narrow observed MTCData initializer instruction set: constants, array allocation/fill, row assignment and static field assignment. It rejects unsupported operations, missing tables and wrong dimensions. It does not execute the initializer. It reports the original framework.jar ZIP CRC discrepancy and uses an in-memory hidden-API analysis copy, leaving the firmware untouched. It does not publish the initializer bytecode or full disassembly.

The host policy takes preset tables as an explicit input. The default test build uses scripts/eq_test_fixture.py to generate an ignored C++ fixture from the reviewed JSON, avoiding separately maintained copies of the coefficient values. A real platform adapter must provide the correctly sourced tables and live settings/property inputs.

After command construction, the normal service path calls native_setParameters, persists KeyEQmode using the normalized index, then broadcasts CarData with type `EQ_MODE` and an integer value. It does not call the public audio-arbitration method. The model returns those descriptions without simulating external success, exceptions or rollback.

## Validation and limits

`make test` checks known three-band rows, all six preset indices across the three paths, coefficient counts, invalid-index normalization, custom/default precedence, empty/null differences, property parsing and overflow, and rejection of a damaged supplied row. These are host checks against reviewed binary facts. They do not establish installed-firmware identity, driver acceptance, audible results or Android runtime compatibility. No setting or physical audio output was changed.
