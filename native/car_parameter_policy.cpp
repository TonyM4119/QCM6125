#include "car_parameter_policy.hpp"

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

ParameterPlan CarParameterPolicy::plan(std::optional<std::string_view> command) {
  if (!command) return rejected();
  const auto split = command->find('=');
  if (split == std::string_view::npos) return rejected();
  if (!starts_with(*command, "av_")) return forward(*command, false);

  const auto value = command->substr(split + 1);
  if (value.empty()) return rejected();
  if (starts_with(*command, "av_channel_enter=")) {
    audio_channel_ = std::string(value);
    return forward(*command, true);
  }
  if (starts_with(*command, "av_channel_exit=")) {
    if (audio_channel_ == value && audio_channel_ != "sys") {
      audio_channel_ = "sys";
      return forward("av_channel_enter=sys", true);
    }
    return {};
  }
  if (starts_with(*command, "av_gps_package=")) {
    navigation_package_ = std::string(value);
    return {};
  }
  return forward(*command, true);
}

}  // namespace hct
