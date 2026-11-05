#pragma once

#include "event_mapping.hpp"
#include <string_view>

namespace hct {
struct EqPresetTables {
  std::vector<IntArray> three_band;
  std::vector<IntArray> fifteen_band;
  std::vector<IntArray> thirty_one_band;
};
struct EqPlan {
  std::string driver_command;
  std::string setting_key;
  std::int32_t setting_value;
  EventNotification notification;
};
std::optional<std::string> custom_eq_setting_key(std::int32_t custom_mode);
// ASCII subset of the Java property parser. Invalid numeric input returns null;
// sum wraparound, division toward zero and Java trailing-empty splitting apply.
std::optional<std::string> reduce_default_eq_property(std::optional<std::string_view> property);
EqPlan plan_eq_apply(std::int32_t index, std::int32_t dsp_mode,
                     std::optional<std::string_view> custom_setting,
                     std::optional<std::string_view> default_eq_property,
                     const EqPresetTables& presets);
}  // namespace hct
