#include "control_policy.hpp"
#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
void check(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
}
int main() {
  auto eq = hct::plan_eq_request(-7);
  check(eq.what == 0 && eq.delay_ms == 10 && eq.arg1 == -7 && !eq.boolean_object,
        "EQ scheduling/clamping boundary changed");
  for (bool value : {false, true}) {
    const auto lud = hct::plan_loudness_request(value);
    check(lud.what == 1 && lud.delay_ms == 10 && lud.arg1 == int(value) && !lud.boolean_object,
          "loudness message shape changed");
    const auto video = hct::plan_video_speed_request(value);
    check(video.what == 2 && video.delay_ms == 50 && video.arg1 == 0 &&
          video.boolean_object == value, "video message payload changed");
    const auto notification = hct::plan_video_speed_notification(value);
    check(notification.topic == "CarEvent" &&
          std::get<std::string>(notification.fields.at("type")) == "handbrake" &&
          std::get<bool>(notification.fields.at("value")) == value,
          "video update invented a speed-valued callback");
  }
  for (auto value : {std::int32_t(-1), std::int32_t(0), std::int32_t(1), std::int32_t(2)}) {
    for (auto dsp : {std::int32_t(0), std::int32_t(1), std::int32_t(15), std::int32_t(31)}) {
      const auto plan = hct::plan_loudness_apply(value, dsp, std::nullopt);
      const std::string expected = dsp == 0 ? (value == 1 ? "av_lud=on" : "av_lud=off") :
                                            (value == 1 ? "av_dsp=1,1,0,0" : "av_dsp=1,0,0,0");
      check(plan.driver_command == expected && plan.setting_key == "key_Lud" &&
            plan.setting_value == value, "loudness routing/default/storage changed");
      check(plan.notification.topic == "CarData" &&
            std::get<std::string>(plan.notification.fields.at("type")) == "LOUND_MODE" &&
            std::get<std::int32_t>(plan.notification.fields.at("value")) == value,
            "loudness callback type or legacy spelling changed");
    }
  }
  check(hct::plan_loudness_apply(1, 15, "4,8").driver_command == "av_dsp=1,1,4,8",
        "stored gain ignored");
  check(hct::plan_loudness_apply(0, 31, "").driver_command == "av_dsp=1,0,",
        "empty gain was treated as missing");
  check(hct::default_eq_index("KGLMMR") == 1 && hct::default_eq_index("KGL1") == 1 &&
        hct::default_eq_index("HCT") == 0 && hct::default_eq_index("kgl1") == 0,
        "customer EQ defaults changed");
  check(hct::default_loudness("KGLMMR") == 1 && hct::default_loudness("KGL1") == 0,
        "EQ and loudness defaults incorrectly unified");

  // Truth table transcribed independently from branch targets in the reference:
  // handbrake=false: always false; setting=0 and brake=true: true;
  // setting=1 and brake=true: requires nonzero speed setting and speed state;
  // every other driving setting: false.
  for (auto driving : {-1, 0, 1, 2}) {
    for (auto speed_setting : {-1, 0, 1, 2}) {
      for (bool brake : {false, true}) {
        for (bool speed : {false, true}) {
          bool expected = false;
          if (brake && driving == 0) expected = true;
          if (brake && driving == 1 && speed_setting != 0) expected = speed;
          check(hct::video_enable_value(driving, speed_setting, brake, speed) == expected,
                "video predicate differs from reviewed branch truth table");
        }
      }
    }
  }
  std::cout << "Deferred control, loudness, defaults and video predicate checks passed; no Android/device I/O.\n";
}
