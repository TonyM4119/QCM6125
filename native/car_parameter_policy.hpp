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

// Offline policy model recovered from the owner-tested Malaysk service.
// No I/O, Android dependencies, callbacks, persistence, or driver access.
// A future service must serialize this object with its other state operations.
class CarParameterPolicy {
 public:
  ParameterPlan plan(std::optional<std::string_view> command);
  const std::string& audio_channel() const { return audio_channel_; }
  const std::string& navigation_package() const { return navigation_package_; }

 private:
  std::string audio_channel_ = "sys";
  std::string navigation_package_;
};

}  // namespace hct
