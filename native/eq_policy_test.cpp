#include "eq_policy.hpp"
#include "eq_reference.hpp"
#include <iostream>
#include <stdexcept>
#include <algorithm>

namespace {
void check(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
}
int main() {
  const auto tables = reference_eq_tables();
  check(hct::custom_eq_setting_key(0) == "KeyCustomEQ" &&
        hct::custom_eq_setting_key(6) == "KeyCustom6EQ" &&
        !hct::custom_eq_setting_key(-1) && !hct::custom_eq_setting_key(7),
        "custom-mode settings selection changed");
  check(!hct::reduce_default_eq_property(std::nullopt) &&
        !hct::reduce_default_eq_property("") && !hct::reduce_default_eq_property("10"),
        "missing/comma-free property did not fall back");
  check(hct::reduce_default_eq_property("9,12,15,3,6,9,0,0,0") == "12,6,0",
        "nine-band reduction changed");
  check(hct::reduce_default_eq_property("-1,-1,0,+3,0,0") == "0,1",
        "Java signed division or plus-sign parsing changed");
  check(hct::reduce_default_eq_property("1,2,3,") == "2" &&
        hct::reduce_default_eq_property("1,2,3,4") == "2," &&
        hct::reduce_default_eq_property("1,2") == "" &&
        hct::reduce_default_eq_property(",,,") == "",
        "Java splitting/incomplete-group behaviour changed");
  check(!hct::reduce_default_eq_property("1,,3") &&
        !hct::reduce_default_eq_property("1, 2,3") &&
        !hct::reduce_default_eq_property("1,2147483648,3") &&
        !hct::reduce_default_eq_property("1,+-2,3"), "invalid property accepted");
  check(hct::reduce_default_eq_property("2147483647,2147483647,2147483647") == "715827881",
        "Java int accumulation wraparound changed");

  auto plan = hct::plan_eq_apply(1, 0, std::nullopt, std::nullopt, tables);
  check(plan.driver_command == "av_eq=18,8,18" && plan.setting_key == "KeyEQmode" &&
        plan.setting_value == 1 && plan.notification.topic == "CarData" &&
        std::get<std::string>(plan.notification.fields.at("type")) == "EQ_MODE" &&
        std::get<std::int32_t>(plan.notification.fields.at("value")) == 1,
        "reviewed first preset or persistence/callback shape changed");
  check(hct::plan_eq_apply(6, 9, std::nullopt, std::nullopt, tables).driver_command == "av_eq=8,16,8",
        "non-15/31 DSP path did not use three-band preset");
  for (auto dsp : {0, 15, 31}) {
    for (auto index : {-1, 0, 7}) {
      const auto custom = hct::plan_eq_apply(index, dsp, "2,4,6", "9,9,9", tables);
      check(custom.setting_value == 0 && custom.driver_command ==
            (dsp == 0 ? "av_eq=2,4,6" : "av_dsp=0,2,4,6"),
            "index normalization or stored custom string precedence changed");
    }
    const auto empty = hct::plan_eq_apply(0, dsp, "", std::nullopt, tables);
    check(empty.driver_command == (dsp == 0 ? "av_eq=" : "av_dsp=0,"),
          "empty stored custom EQ was treated as null");
    for (int index = 1; index <= 6; ++index) {
      const auto preset = hct::plan_eq_apply(index, dsp, "ignored", "ignored", tables);
      const auto expected_commas = dsp == 0 ? 2 : dsp; // DSP prefix includes a comma.
      check(std::count(preset.driver_command.begin(), preset.driver_command.end(), ',') == expected_commas,
            "preset selected wrong band count");
    }
  }
  check(hct::plan_eq_apply(0, 0, std::nullopt, "3,6,9,12,15,18", tables).driver_command == "av_eq=6,15",
        "property reduction was not used by three-band path");
  check(hct::plan_eq_apply(0, 0, std::nullopt, "bad,property", tables).driver_command == "av_eq=10,10,10",
        "malformed property did not select flat default");
  const auto flat15 = hct::plan_eq_apply(0, 15, std::nullopt, "bad,property", tables);
  check(flat15.driver_command == "av_dsp=0,10,10,10,10,10,10,10,10,10,10,10,10,10,10,10",
        "15-band flat default/property isolation changed");
  auto damaged = tables;
  damaged.thirty_one_band[0].pop_back();
  bool rejected = false;
  try { hct::plan_eq_apply(1, 31, std::nullopt, std::nullopt, damaged); }
  catch (const std::invalid_argument&) { rejected = true; }
  check(rejected, "wrong preset width was silently used");
  std::cout << "EQ preset routing, custom/default selection and Java numeric edge checks passed; no device I/O.\n";
}
