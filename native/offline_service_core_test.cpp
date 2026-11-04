#include "offline_service_core.hpp"

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
  hct::OfflineServiceCore core(2);
  check(field<std::string>(core.state_snapshot(), "av_channel") == "sys", "initial channel mismatch");
  check(!core.state_snapshot().count("navi_package"), "invented navigation configuration");
  const auto enter = core.plan_parameter("av_channel_enter=radio");
  check(enter.actions.size() == 2 && enter.return_driver_result, "audio plan missing");
  core.plan_parameter("av_channel_exit=music");
  check(field<std::string>(core.state_snapshot(), "av_channel") == "radio", "stale exit changed shared state");
  core.plan_parameter("av_gps_package=example.navigation");
  check(field<std::string>(core.state_snapshot(), "navi_package") == "example.navigation", "navigation state not integrated");

  const auto partial = core.receive({0xfa, 0x16, 0x43, 1});
  check(partial.frames == 0 && !core.state_snapshot().count("backview"), "partial frame mutated state");
  const auto camera = core.receive({0, 1});
  check(camera.frames == 1 && camera.mapped == 1 &&
        field<bool>(core.state_snapshot(), "backview"), "complete camera frame not applied");

  // Frequency is callback-only; camera state and audio policy remain independent.
  const auto radio = core.receive({0xfa, 0x11, 0x25, 3, 0, 0x7c, 0xa5, 0x01});
  check(radio.mapped == 1 && !core.state_snapshot().count("freq"), "radio invented persistent frequency state");
  auto callbacks = core.drain_notifications();
  check(callbacks.size() == 2 && callbacks[0].topic == "CarEvent" && callbacks[1].topic == "Radio", "callback order mismatch");
  check(field<std::int32_t>(callbacks[1].fields, "value") == 107900000, "frequency lost between decoder and callback");
  check(core.drain_notifications().empty(), "notifications delivered twice");

  auto snapshot = core.state_snapshot();
  snapshot["backview"] = false;
  check(field<bool>(core.state_snapshot(), "backview"), "caller mutated live state snapshot");
  const auto bad = core.receive({0xfa, 0x16, 0x43, 0, 0, 0xfa, 0x16, 0x4a, 1, 0, 1});
  check(bad.malformed == 1 && bad.unknown == 1 && bad.mapped == 0, "unknown/malformed distinction lost");
  check(field<bool>(core.state_snapshot(), "backview") && core.drain_notifications().empty(), "bad event changed state or callbacks");

  const auto overflow = core.receive({0xfa, 0x1f, 3, 0, 0, 0xfa, 0x1f, 4, 0, 0,
                                     0xfa, 0x16, 0x44, 0, 0});
  check(overflow.notifications_dropped == 1 && overflow.mapped == 3, "bounded backlog accounting mismatch");
  callbacks = core.drain_notifications();
  check(callbacks.size() == 2 && field<std::string>(callbacks[0].fields, "type") == "touch_up", "backlog policy/order mismatch");
  check(!field<bool>(core.state_snapshot(), "backview") &&
        std::holds_alternative<std::monostate>(core.state_snapshot().at("backview_mode")), "latest camera state lost on backlog overflow");
  check(field<std::string>(core.state_snapshot(), "av_channel") == "radio", "serial event unexpectedly changed audio selection");
  core.plan_parameter("av_channel_exit=radio");
  check(field<std::string>(core.state_snapshot(), "av_channel") == "sys", "audio exit state not synchronized");
  std::cout << "Offline service integration scenarios passed; no device, Android service or external callback accessed.\n";
}
