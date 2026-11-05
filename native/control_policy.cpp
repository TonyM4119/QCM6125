#include "control_policy.hpp"

namespace hct {
DeferredControl plan_eq_request(std::int32_t index) { return {0, 10, index, std::nullopt}; }
DeferredControl plan_loudness_request(bool enabled) { return {1, 10, enabled ? 1 : 0, std::nullopt}; }
DeferredControl plan_video_speed_request(bool over_speed) { return {2, 50, 0, over_speed}; }

LoudnessPlan plan_loudness_apply(std::int32_t value, std::int32_t dsp_mode,
                                 std::optional<std::string_view> gain) {
  const bool enabled = value == 1;
  const std::string command = dsp_mode == 0
      ? std::string(enabled ? "av_lud=on" : "av_lud=off")
      : std::string(enabled ? "av_dsp=1,1," : "av_dsp=1,0,") +
          std::string(gain.value_or("0,0"));
  return {command, "key_Lud", value,
          {"CarData", {{"type", std::string("LOUND_MODE")}, {"value", value}}}};
}
std::int32_t default_eq_index(std::string_view customer_sub) {
  return customer_sub == "KGLMMR" || customer_sub == "KGL1" ? 1 : 0;
}
std::int32_t default_loudness(std::string_view customer_sub) {
  return customer_sub == "KGLMMR" ? 1 : 0;
}
bool video_enable_value(std::int32_t driving_video_setting,
                        std::int32_t over_speed_setting,
                        bool handbrake_state, bool over_speed_state) {
  return handbrake_state &&
      (driving_video_setting == 0 ||
       (driving_video_setting == 1 && over_speed_setting != 0 && over_speed_state));
}
EventNotification plan_video_speed_notification(bool handbrake_state) {
  return {"CarEvent", {{"type", std::string("handbrake")}, {"value", handbrake_state}}};
}
}  // namespace hct
