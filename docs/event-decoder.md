# Receive framing and initial event mappings

Implemented from static review of the owner-tested Malaysk `services.jar`, SHA-256 `b3c0f55f7e5830d7213576ee3dad3c910422820b3dbf94c5527cad97120ae6fe`. No real serial bytes or device driver were exercised. The January 2025 installed build remains a separate, uninspected binary reference.

## Stream component

`native/event_stream.*` receives supplied byte vectors and emits frames with category, subcommand and payload. It has no serial/device access. Frame header: FA, category byte, subcommand byte, two-byte little-endian payload length, then payload. Marker bytes within a payload are preserved as data. Split headers and payloads are retained across feeds; multiple frames per feed are supported.

The default maximum payload is 4091 bytes so one complete frame fits the observed 4096-byte receive buffer. Payloads larger than the configured maximum are rejected and the decoder scans forward for a new marker. This is a defensive policy, not emulation of the factory's buffer-reset behaviour. It can lose a genuinely larger frame and can find a false marker inside corrupt data. No unobserved checksum or terminator is invented. Further driver/protocol review is necessary before selecting a hardware-facing overflow policy.

## Initial mapper

`native/event_mapping.*` implements only the 18 category/subcommand pairs below. It returns typed state-update descriptions and callback descriptions. No persistent store, Binder, Android UI action, camera switching or power operation is performed. Unknown pairs are left unknown; short payloads for known fixed fields return malformed without any state update or callback.

| Category / subcommand (hex) | Mapping | Minimum payload |
| --- | --- | --- |
| 1F / 00 | TouchStudy: touch_xy, little-endian x/y | 4 bytes |
| 1F / 01 | TouchStudy: touch_key, unsigned index | 1 byte |
| 1F / 02 | VideoSignal: video_signal, signal and channel | 2 bytes |
| 1F / 03, 04 | CarEvent: touch_down / touch_up | 0 bytes |
| 10 / 14 | CarEvent: mute | 1 byte |
| 10 / 30, 31 | CarEvent and state: dsp_spk_vol / dsp_spk_delay byte arrays | Whole payload, including empty |
| 16 / D3, 4B, 4C | CarEvent and state: aux / handbrake / ipod | 1 byte |
| 16 / 8F | CarEvent and state: unsigned orientation | 1 byte |
| 16 / 43 | CarEvent and state: backview enabled, mode selection | 1 byte |
| 16 / 44 | CarEvent and state: backview disabled, clear mode | 0 bytes |
| 16 / 40, 41, 42, 49 | CarPower and carpower state: power_on / power_off / sleep / acc_off | 0 bytes |

Callbacks include a type String and the observed additional fields. Video signal and mute use byte==1; aux, handbrake and ipod use byte!=0. Video channels map 1..4 to backview/avin/tv/dvr; others use the literal String "null", not a null value. Camera modes 1/6/7 map to backview/frontview/rightview. Other camera modes enable backview state but clear stored mode and omit the callback mode field, matching the reviewed branch.

The mapper's monostate represents clearing the stored nullable camera-mode String; the future Android adapter must map that deliberately. Power events update descriptions only. The original category-16 dispatch path also includes UI status-bar collapsing in a shared tail. That UI effect is not implemented by this mapper. Conditional headlight handling involving isBox, state-reset/wakeup paths and shutdown routines are deliberately not guessed.

## Evidence and limitations

`evidence/malaysk-event-switches.json` records the decoded switch keys and target instruction offsets from cmdProc. Root category values are 10, 11, 12, 13, 15, 16 and 1F in hexadecimal. Mapping names and field semantics were manually traced at those targets; switch keys alone do not establish semantics. This is a subset, not a count of every event supported by the ROM.

Host tests cover every stream split position for a sample frame, concatenation, noise, an embedded FA payload byte, zero-length and 256-byte payloads, malformed header recovery and bounded noise retention. Pipeline tests pass split reads through the decoder into camera state/callback mapping, check little-endian coordinates and Boolean differences, preserve DSP bytes, and reject short/unknown events. Inputs are synthetic, not captured traffic. These checks do not prove the current driver's format or hardware compatibility.

## Host commands

```sh
mkdir -p work/tests
c++ -std=c++17 -Wall -Wextra -Werror -pedantic \
  native/event_stream.cpp native/event_stream_test.cpp -o work/tests/event_stream_test
./work/tests/event_stream_test
c++ -std=c++17 -Wall -Wextra -Werror -pedantic \
  native/event_stream.cpp native/event_mapping.cpp native/event_mapping_test.cpp \
  -o work/tests/event_mapping_test
./work/tests/event_mapping_test
```

Thread synchronization, serial configuration, shared state integration, callback encoding, special projection messages, DSP/audio orchestration and Android build integration remain separate work. Nothing here is installed or flashed.
