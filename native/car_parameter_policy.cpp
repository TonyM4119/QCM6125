#include "car_parameter_policy.hpp"

#include <stdexcept>

namespace hct {
namespace {
bool starts_with(std::string_view value, std::string_view prefix) {
  return value.substr(0, prefix.size()) == prefix;
}
ParameterPlan rejected() {
  ParameterPlan result;
  result.local_result = -1;
  return result;
}
ParameterPlan forward(std::string_view command, bool audio) {
  ParameterPlan result;
  result.return_driver_result = true;
  if (audio) result.actions.push_back({ParameterActionKind::audio_parameter, std::string(command)});
  result.actions.push_back({ParameterActionKind::driver_parameter, std::string(command)});
  return result;
}
}  // namespace

ParameterPlan plan_navigation_audio(std::optional<std::string_view> package) {
  ParameterPlan result;
  result.actions.push_back({ParameterActionKind::audio_parameter,
                            "av_gps_package=" + (package ? std::string(*package) : std::string("null"))});
  return result;
}

ParameterPlan plan_car_parameters(std::optional<std::string_view> command, CarParameterState& state) {
  if (!command) return rejected();
  const auto split = command->find('=');
  if (split == std::string_view::npos) return rejected();
  if (!starts_with(*command, "av_")) return forward(*command, false);

  const auto value = command->substr(split + 1);
  if (value.empty()) return rejected();
  if (starts_with(*command, "av_channel_enter=")) {
    state.audio_channel = std::string(value);
    return forward(*command, true);
  }
  if (starts_with(*command, "av_channel_exit=")) {
    if (!state.audio_channel) throw std::logic_error("Audio channel state is null or has the wrong type");
    if (*state.audio_channel == value && *state.audio_channel != "sys") {
      state.audio_channel = "sys";
      return forward("av_channel_enter=sys", true);
    }
    return {};
  }
  if (starts_with(*command, "av_gps_package=")) {
    state.navigation_package = std::string(value);
    return plan_navigation_audio(value);
  }
  return forward(*command, true);
}

ParameterPlan CarParameterPolicy::plan(std::optional<std::string_view> command) {
  return plan_car_parameters(command, state_);
}

}  // namespace hct
