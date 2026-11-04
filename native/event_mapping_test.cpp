#include "event_mapping.hpp"
#include <iostream>
#include <stdexcept>

namespace {
void check(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
template <typename T>
const T& field(const hct::EventFields& fields, const char* key) {
  return std::get<T>(fields.at(key));
}
}  // namespace

int main() {
  // Full pipeline: two serial reads -> frames -> callback/state descriptions.
  hct::EventStreamDecoder stream;
  check(stream.feed({0xfa, 0x16, 0x43, 1}).empty(), "partial event was emitted");
  auto frames = stream.feed({0, 6, 0xfa, 0x16, 0x44, 0, 0});
  check(frames.size() == 2, "pipeline frame count");
  const auto on = hct::map_event(frames[0]);
  const auto off = hct::map_event(frames[1]);
  check(field<bool>(on.state_updates, "backview"), "camera state not enabled");
  check(field<std::string>(on.state_updates, "backview_mode") == "frontview", "camera mode changed");
  check(on.notifications[0].topic == "CarEvent", "camera callback topic changed");
  check(!field<bool>(off.state_updates, "backview"), "camera state not disabled");
  check(std::holds_alternative<std::monostate>(off.state_updates.at("backview_mode")), "stale camera mode retained");
  check(!off.notifications[0].fields.count("mode"), "off callback unexpectedly contains mode");

  const auto touch = hct::map_event({0x1f, 0, {0x34, 0x12, 0x78, 0x56}});
  check(field<std::int32_t>(touch.notifications[0].fields, "x") == 0x1234, "touch x endian mismatch");
  check(field<std::int32_t>(touch.notifications[0].fields, "y") == 0x5678, "touch y endian mismatch");
  check(touch.state_updates.empty(), "touch invented persistent state");
  const auto video = hct::map_event({0x1f, 2, {2, 0xff}});
  check(!field<bool>(video.notifications[0].fields, "signal"), "video must test equality to one");
  check(field<std::string>(video.notifications[0].fields, "channel") == "null", "unknown video channel mapping");
  check(field<bool>(hct::map_event({0x16, 0x4b, {0xff}}).state_updates, "handbrake"), "state must test nonzero");
  const auto dsp = hct::map_event({0x10, 0x30, {1, 0xfa, 3}});
  check(field<std::vector<std::uint8_t>>(dsp.state_updates, "dsp_spk_vol") ==
        std::vector<std::uint8_t>({1, 0xfa, 3}), "DSP bytes changed");
  const auto power = hct::map_event({0x16, 0x42, {}});
  check(power.notifications[0].topic == "CarPower" &&
        field<std::string>(power.state_updates, "carpower") == "sleep", "power notification mismatch");

  const auto frequency = hct::map_event({0x11, 0x25, {0x7c, 0xa5, 0x01}});
  check(frequency.notifications[0].topic == "Radio" &&
        field<std::int32_t>(frequency.notifications[0].fields, "value") == 107900000,
        "radio frequency byte order or unit scaling changed");
  check(frequency.state_updates.empty(), "radio callback invented shared state");
  const auto wrapped_frequency = hct::map_event({0x11, 0x25, {0xff, 0xff, 0xff}});
  check(field<std::int32_t>(wrapped_frequency.notifications[0].fields, "value") == -402654184,
        "Java int overflow semantics changed");
  const auto traffic = hct::map_event({0x11, 0x31, {}});
  check(std::holds_alternative<std::int32_t>(traffic.notifications[0].fields.at("value")) &&
        field<std::int32_t>(traffic.notifications[0].fields, "value") == 1,
        "traffic announcement must remain int, not bool");
  const auto seek = hct::map_event({0x11, 0x35, {0xfe}});
  check(field<std::int32_t>(seek.notifications[0].fields, "strength") == 254 &&
        !seek.notifications[0].fields.count("value"), "seek callback schema mismatch");
  check(field<std::int32_t>(hct::map_event({0x11, 0x28, {0xab, 0xcd}}).notifications[0].fields, "value") == 0xcdab,
        "radio programme identifier endian mismatch");

  for (const auto& frame : std::vector<hct::EventFrame>{{0x16, 0x43, {}}, {0x16, 0x4b, {}},
                                                      {0x1f, 0, {1, 2, 3}}, {0x1f, 2, {1}},
                                                      {0x11, 0x25, {0x7c, 0xa5}}, {0x11, 0x28, {1}},
                                                      {0x11, 0x21, {}}}) {
    const auto bad = hct::map_event(frame);
    check(bad.status == hct::EventDecodeStatus::malformed && bad.notifications.empty() &&
          bad.state_updates.empty(), "truncated event produced state or callback");
  }
  const auto unknown = hct::map_event({0x16, 0x4a, {1}}); // Conditional isBox path deliberately omitted.
  check(unknown.status == hct::EventDecodeStatus::unknown && unknown.state_updates.empty(),
        "unimplemented event guessed");
  std::cout << "Event pipeline, typed field and malformed-input checks passed; no hardware accessed.\n";
}
