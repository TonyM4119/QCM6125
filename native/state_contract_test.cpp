#include "offline_service_core.hpp"

#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
void check(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
void check_audio_only(const hct::ParameterPlan& plan, const std::string& command) {
  check(plan.local_result == 0 && !plan.return_driver_result && plan.actions.size() == 1,
        "string-state audio plan shape changed");
  check(plan.actions[0].kind == hct::ParameterActionKind::audio_parameter &&
        plan.actions[0].command == command, "string-state audio command changed");
}
}  // namespace

int main() {
  hct::OfflineServiceCore core;
  check(!core.get_boolean_state("missing") && core.get_byte_state("missing") == 0 &&
        core.get_int_state("missing") == 0, "missing primitive defaults changed");
  check(!core.get_string_state("missing") && !core.get_byte_array_state("missing") &&
        !core.get_int_array_state("missing") && !core.get_string_array_state("missing"),
        "missing reference defaults changed");

  core.put_byte_state("typed", std::int8_t(-7));
  check(core.get_byte_state("typed") == -7 && core.get_int_state("typed") == 0 &&
        !core.get_boolean_state("typed"), "byte was coerced to another primitive");
  core.put_int_state("typed", 1);
  check(core.get_int_state("typed") == 1 && !core.get_boolean_state("typed") &&
        core.get_byte_state("typed") == 0, "int was coerced to another primitive");
  core.put_boolean_state("typed", true);
  check(core.get_boolean_state("typed") && core.get_int_state("typed") == 0 &&
        !core.get_string_state("typed"), "bool was coerced to another type");
  check(core.put_string_state("typed", std::string("true")).actions.empty(), "ordinary string write invented audio action");
  check(core.get_string_state("typed") == std::optional<std::string>("true") &&
        !core.get_boolean_state("typed"), "string was coerced to bool");
  core.put_string_state("typed", std::nullopt);
  check(!core.get_string_state("typed") && core.state_snapshot().count("typed"), "nullable string did not preserve stored key");

  const hct::ByteArray bytes{0, 0xff, 0xfa};
  const hct::IntArray integers{std::numeric_limits<std::int32_t>::min(), 0,
                              std::numeric_limits<std::int32_t>::max()};
  const hct::StringArray strings{std::string("alpha"), std::nullopt, std::string()};
  core.put_byte_array_state("bytes", bytes);
  core.put_int_array_state("integers", integers);
  core.put_string_array_state("strings", strings);
  check(core.get_byte_array_state("bytes").value() == bytes &&
        core.get_int_array_state("integers").value() == integers &&
        core.get_string_array_state("strings").value() == strings, "array type/content roundtrip failed");
  check(!core.get_int_array_state("bytes"), "array element type was coerced");
  auto detached = core.get_byte_array_state("bytes").value();
  detached[0] = 42;
  check(core.get_byte_array_state("bytes")->at(0) == 0, "getter exposed mutable live array");
  core.put_byte_array_state("bytes", std::nullopt);
  check(!core.get_byte_array_state("bytes"), "null byte array changed to empty");
  core.put_byte_array_state("bytes", hct::ByteArray{});
  check(core.get_byte_array_state("bytes") && core.get_byte_array_state("bytes")->empty(), "empty byte array changed to null");

  core.put_string_state("av_channel", std::string("music"));
  const auto exit = core.plan_parameter("av_channel_exit=music");
  check(exit.return_driver_result && exit.actions.size() == 2 &&
        core.get_string_state("av_channel").value() == "sys", "audio policy ignored direct shared-state write");
  core.put_int_state("av_channel", 9);
  bool invalid_channel = false;
  try { core.plan_parameter("av_channel_exit=music"); }
  catch (const std::logic_error&) { invalid_channel = true; }
  check(invalid_channel && core.get_int_state("av_channel") == 9,
        "invalid channel type was silently coerced or replaced");
  core.plan_parameter("av_channel_enter=radio");
  check(core.get_string_state("av_channel").value() == "radio", "explicit enter did not repair channel state");

  core.plan_parameter("av_gps_package=first.navigation");
  check_audio_only(core.put_string_state("navi_package", std::string("second.navigation")),
                   "av_gps_package=second.navigation");
  check_audio_only(core.plan_parameter("av_gps_package=first.navigation"), "av_gps_package=first.navigation");
  check(core.get_string_state("navi_package").value() == "first.navigation", "stale private navigation cache overrode shared state");
  check_audio_only(core.put_string_state("navi_package", std::nullopt), "av_gps_package=null");
  check(!core.get_string_state("navi_package"), "null navigation string lost");
  check_audio_only(core.put_string_state("navi_package", std::string()), "av_gps_package=");
  const auto rejected = core.plan_parameter("av_gps_package=");
  check(rejected.local_result == -1 && rejected.actions.empty() &&
        core.get_string_state("navi_package")->empty(), "direct empty string and empty parameter command confused");
  check(core.get_string_state("av_channel").value() == "radio", "navigation state switched audio channel");
  check(core.drain_notifications().empty(), "state writes invented Binder callbacks");

  check(core.notify_data_change(std::string("volume"), std::string("12")) == 0, "unexpected notification drop");
  auto notifications = core.drain_notifications();
  check(notifications.size() == 1 && notifications[0].topic == "CarData" &&
        std::get<std::string>(notifications[0].fields.at("type")) == "volume" &&
        std::get<std::string>(notifications[0].fields.at("value")) == "12", "CarData callback shape changed");
  check(!core.state_snapshot().count("volume"), "CarData notification invented stored state");
  core.notify_data_change(std::nullopt, std::nullopt);
  notifications = core.drain_notifications();
  check(std::holds_alternative<std::monostate>(notifications[0].fields.at("type")) &&
        std::holds_alternative<std::monostate>(notifications[0].fields.at("value")), "nullable CarData Strings changed");
  std::cout << "Typed state, shared policy and CarData scenarios passed; no Android/device I/O.\n";
}
