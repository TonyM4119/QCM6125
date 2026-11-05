#include "eq_policy.hpp"
#include <charconv>
#include <limits>
#include <stdexcept>

namespace hct {
namespace {
std::string join(const IntArray& values) {
  std::string result;
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (i) result += ',';
    result += std::to_string(values[i]);
  }
  return result;
}
std::int32_t signed_bits(std::uint32_t bits) {
  if (bits <= static_cast<std::uint32_t>(std::numeric_limits<std::int32_t>::max()))
    return static_cast<std::int32_t>(bits);
  return -1 - static_cast<std::int32_t>(std::numeric_limits<std::uint32_t>::max() - bits);
}
std::optional<std::int32_t> parse_java_ascii_int(std::string_view text) {
  if (text.empty()) return std::nullopt;
  if (text.front() == '+') {
    text.remove_prefix(1);
    if (text.empty() || text.front() == '+' || text.front() == '-') return std::nullopt;
  }
  std::int32_t value = 0;
  const auto parsed = std::from_chars(text.data(), text.data() + text.size(), value, 10);
  if (parsed.ec != std::errc{} || parsed.ptr != text.data() + text.size()) return std::nullopt;
  return value;
}
}
std::optional<std::string> custom_eq_setting_key(std::int32_t custom_mode) {
  if (custom_mode < 0 || custom_mode > 6) return std::nullopt;
  if (custom_mode == 0) return "KeyCustomEQ";
  return "KeyCustom" + std::to_string(custom_mode) + "EQ";
}
std::optional<std::string> reduce_default_eq_property(std::optional<std::string_view> property) {
  if (!property || property->find(',') == std::string_view::npos) return std::nullopt;
  auto input = *property;
  // Java String.split(",") discards trailing empty elements.
  while (!input.empty() && input.back() == ',') input.remove_suffix(1);
  if (input.empty()) return std::string();
  std::vector<std::string_view> parts;
  std::size_t start = 0;
  for (;;) {
    const auto end = input.find(',', start);
    parts.push_back(input.substr(start, end == std::string_view::npos ? end : end - start));
    if (end == std::string_view::npos) break;
    start = end + 1;
  }
  std::uint32_t sum = 0;
  std::string result;
  for (std::size_t i = 0; i < parts.size(); ++i) {
    const auto value = parse_java_ascii_int(parts[i]);
    if (!value) return std::nullopt;
    sum += static_cast<std::uint32_t>(*value);
    if ((i + 1) % 3 == 0) {
      result += std::to_string(signed_bits(sum) / 3);
      if (i < parts.size() - 1) result += ',';
      sum = 0;
    }
  }
  return result;
}
EqPlan plan_eq_apply(std::int32_t index, std::int32_t dsp_mode,
                     std::optional<std::string_view> custom_setting,
                     std::optional<std::string_view> default_eq_property,
                     const EqPresetTables& presets) {
  if (index < 0 || index > 6) index = 0;
  const bool multi_band = dsp_mode == 15 || dsp_mode == 31;
  std::string coefficients;
  if (index == 0) {
    if (custom_setting) coefficients = std::string(*custom_setting);
    else if (multi_band) coefficients = join(IntArray(static_cast<std::size_t>(dsp_mode), 10));
    else coefficients = reduce_default_eq_property(default_eq_property).value_or("10,10,10");
  } else {
    const auto& table = dsp_mode == 31 ? presets.thirty_one_band :
                        dsp_mode == 15 ? presets.fifteen_band : presets.three_band;
    const auto width = multi_band ? static_cast<std::size_t>(dsp_mode) : std::size_t(3);
    if (table.size() != 6) throw std::invalid_argument("EQ preset row count must be six");
    const auto& row = table.at(static_cast<std::size_t>(index - 1));
    if (row.size() != width) throw std::invalid_argument("EQ preset band count differs from selected path");
    coefficients = join(row);
  }
  return {std::string(multi_band ? "av_dsp=0," : "av_eq=") + coefficients,
          "KeyEQmode", index,
          {"CarData", {{"type", std::string("EQ_MODE")}, {"value", index}}}};
}
}  // namespace hct
