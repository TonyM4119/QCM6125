#pragma once

#include "event_mapping.hpp"
#include <string_view>

namespace hct {
struct DeferredControl {
  std::int32_t what;
  std::int32_t delay_ms;
  std::int32_t arg1;
  std::optional<bool> boolean_object;
  // The Android setter first removes pending messages with this same what.
};
DeferredControl plan_eq_request(std::int32_t index);
DeferredControl plan_loudness_request(bool enabled);
DeferredControl plan_video_speed_request(bool over_speed);

struct LoudnessPlan {
  std::string driver_command;
  std::string setting_key;
  std::int32_t setting_value;
  EventNotification notification;
};
// Models the private setLUD handler target, not the delayed public setter.
LoudnessPlan plan_loudness_apply(std::int32_t value, std::int32_t dsp_mode,
                                 std::optional<std::string_view> gain);
std::int32_t default_eq_index(std::string_view customer_sub);
std::int32_t default_loudness(std::string_view customer_sub);
// Literal predicate from getVideoEnable. These inputs are raw stored values;
// no assumption is made about the physical polarity of the handbrake signal.
bool video_enable_value(std::int32_t driving_video_setting,
                        std::int32_t over_speed_setting,
                        bool handbrake_state, bool over_speed_state);
EventNotification plan_video_speed_notification(bool handbrake_state);
}  // namespace hct
