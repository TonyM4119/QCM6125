#include "car_parameter_policy.hpp"

#include <iostream>
#include <stdexcept>

namespace {
void check(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
void check_forward(const hct::ParameterPlan& plan, const char* expected, bool audio) {
  check(plan.return_driver_result, "driver return value must be preserved");
  check(plan.actions.size() == (audio ? 2u : 1u), "unexpected action count");
  if (audio) {
    check(plan.actions[0].kind == hct::ParameterActionKind::audio_parameter, "audio action must come first");
    check(plan.actions[0].command == expected, "wrong audio command");
  }
  check(plan.actions.back().kind == hct::ParameterActionKind::driver_parameter, "missing driver action");
  check(plan.actions.back().command == expected, "wrong driver command");
}
void check_local(const hct::ParameterPlan& plan, int result) {
  check(plan.actions.empty(), "local branch must not send hardware/audio commands");
  check(!plan.return_driver_result && plan.local_result == result, "wrong local result");
}
}  // namespace

int main() {
  hct::CarParameterPolicy policy;
  check(policy.audio_channel() == "sys", "wrong initial channel");
  check_local(policy.plan(std::nullopt), -1);
  check_local(policy.plan("malformed"), -1);
  check_local(policy.plan("av_channel_enter="), -1);
  check(policy.audio_channel() == "sys", "invalid request changed channel");

  check_forward(policy.plan("av_channel_enter=radio"), "av_channel_enter=radio", true);
  check(policy.audio_channel() == "radio", "radio was not selected");
  // A stale exit from another app must not interrupt the active radio channel.
  check_local(policy.plan("av_channel_exit=music"), 0);
  check(policy.audio_channel() == "radio", "inactive exit disturbed audio");
  check_local(policy.plan("av_gps_package=example.navigation"), 0);
  check(policy.navigation_package() == "example.navigation", "navigation state not retained");
  check(policy.audio_channel() == "radio", "navigation configuration disturbed audio");

  check_forward(policy.plan("av_channel_exit=radio"), "av_channel_enter=sys", true);
  check(policy.audio_channel() == "sys", "active exit did not restore system audio");
  check_local(policy.plan("av_channel_exit=sys"), 0);
  check_forward(policy.plan("test_key="), "test_key=", false);
  check_forward(policy.plan("av_test=value=with_equals"), "av_test=value=with_equals", true);
  std::cout << "Audio-channel policy scenarios passed; no Android or hardware accessed.\n";
}
