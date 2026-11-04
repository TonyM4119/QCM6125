#pragma once

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace hct {

enum class ParameterActionKind { audio_parameter, driver_parameter };
struct ParameterAction {
  ParameterActionKind kind;
  std::string command;
};
struct ParameterPlan {
  // When forwarding to the driver, the adapter must return its result instead.
  int local_result = 0;
  bool return_driver_result = false;
  std::vector<ParameterAction> actions;
};

struct CarParameterState {
  std::optional<std::string> audio_channel = "sys";
  std::optional<std::string> navigation_package;
};

ParameterPlan plan_car_parameters(std::optional<std::string_view> command, CarParameterState& state);
ParameterPlan plan_navigation_audio(std::optional<std::string_view> package);

// Offline policy model recovered from the owner-tested Malaysk service.
// No I/O, Android dependencies, callbacks, persistence, or driver access.
// A future service must serialize this object with its other state operations.
class CarParameterPolicy {
 public:
  ParameterPlan plan(std::optional<std::string_view> command);
  const std::string& audio_channel() const { return state_.audio_channel.value(); }
  const std::string& navigation_package() const {
    return state_.navigation_package ? *state_.navigation_package : empty_navigation_;
  }

 private:
  CarParameterState state_;
  std::string empty_navigation_;
};

}  // namespace hct
