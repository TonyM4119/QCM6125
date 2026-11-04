#include "offline_service_core.hpp"

#include <stdexcept>
#include <utility>

namespace hct {
namespace {
std::optional<std::string> string_value(const EventFields& state, const std::string& key) {
  const auto item = state.find(key);
  if (item != state.end()) {
    if (const auto* value = std::get_if<std::string>(&item->second)) return *value;
  }
  return std::nullopt;
}
template <typename T>
EventValue nullable_value(std::optional<T> value) {
  if (value) return std::move(*value);
  return std::monostate{};
}
}  // namespace

OfflineServiceCore::OfflineServiceCore(std::size_t notification_limit)
    : notification_limit_(notification_limit) {
  if (notification_limit == 0) throw std::invalid_argument("Notification limit must be positive");
  state_["av_channel"] = std::string("sys");
}

ParameterPlan OfflineServiceCore::plan_parameter(std::optional<std::string_view> command) {
  std::lock_guard<std::mutex> lock(mutex_);
  CarParameterState parameters{string_value(state_, "av_channel"), string_value(state_, "navi_package")};
  const auto before = parameters;
  auto plan = plan_car_parameters(command, parameters);
  if (parameters.audio_channel != before.audio_channel) state_["av_channel"] = nullable_value(parameters.audio_channel);
  if (parameters.navigation_package != before.navigation_package) state_["navi_package"] = nullable_value(parameters.navigation_package);
  return plan;
}

ReceiveReport OfflineServiceCore::receive(const std::vector<std::uint8_t>& bytes) {
  std::lock_guard<std::mutex> lock(mutex_);
  ReceiveReport report;
  auto frames = decoder_.feed(bytes);
  report.frames = frames.size();
  for (const auto& frame : frames) {
    auto mapping = map_event(frame);
    if (mapping.status == EventDecodeStatus::malformed) {
      ++report.malformed;
      continue;
    }
    if (mapping.status == EventDecodeStatus::unknown) {
      ++report.unknown;
      continue;
    }
    ++report.mapped;
    for (auto& [key, value] : mapping.state_updates) state_[key] = std::move(value);
    for (auto& notification : mapping.notifications) {
      report.notifications_dropped += enqueue_notification(std::move(notification));
    }
  }
  return report;
}

EventFields OfflineServiceCore::state_snapshot() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return state_;
}

std::vector<EventNotification> OfflineServiceCore::drain_notifications() {
  std::lock_guard<std::mutex> lock(mutex_);
  std::vector<EventNotification> result;
  result.swap(notifications_);
  return result;
}

bool OfflineServiceCore::enqueue_notification(EventNotification notification) {
  const bool dropped = notifications_.size() == notification_limit_;
  if (dropped) notifications_.erase(notifications_.begin());
  notifications_.push_back(std::move(notification));
  return dropped;
}

void OfflineServiceCore::write_state(std::string key, EventValue value) {
  std::lock_guard<std::mutex> lock(mutex_);
  state_[std::move(key)] = std::move(value);
}
void OfflineServiceCore::put_boolean_state(std::string key, bool value) { write_state(std::move(key), value); }
void OfflineServiceCore::put_byte_state(std::string key, std::int8_t value) { write_state(std::move(key), value); }
void OfflineServiceCore::put_int_state(std::string key, std::int32_t value) { write_state(std::move(key), value); }
ParameterPlan OfflineServiceCore::put_string_state(std::string key, std::optional<std::string> value) {
  std::lock_guard<std::mutex> lock(mutex_);
  state_[key] = nullable_value(value);
  if (key == "navi_package") {
    return plan_navigation_audio(value ? std::optional<std::string_view>(*value) : std::nullopt);
  }
  return {};
}
void OfflineServiceCore::put_byte_array_state(std::string key, std::optional<ByteArray> value) {
  write_state(std::move(key), nullable_value(std::move(value)));
}
void OfflineServiceCore::put_int_array_state(std::string key, std::optional<IntArray> value) {
  write_state(std::move(key), nullable_value(std::move(value)));
}
void OfflineServiceCore::put_string_array_state(std::string key, std::optional<StringArray> value) {
  write_state(std::move(key), nullable_value(std::move(value)));
}
bool OfflineServiceCore::get_boolean_state(const std::string& key) const { return read_state<bool>(key).value_or(false); }
std::int8_t OfflineServiceCore::get_byte_state(const std::string& key) const { return read_state<std::int8_t>(key).value_or(0); }
std::int32_t OfflineServiceCore::get_int_state(const std::string& key) const { return read_state<std::int32_t>(key).value_or(0); }
std::optional<std::string> OfflineServiceCore::get_string_state(const std::string& key) const { return read_state<std::string>(key); }
std::optional<ByteArray> OfflineServiceCore::get_byte_array_state(const std::string& key) const { return read_state<ByteArray>(key); }
std::optional<IntArray> OfflineServiceCore::get_int_array_state(const std::string& key) const { return read_state<IntArray>(key); }
std::optional<StringArray> OfflineServiceCore::get_string_array_state(const std::string& key) const { return read_state<StringArray>(key); }
std::size_t OfflineServiceCore::notify_data_change(std::optional<std::string> type, std::optional<std::string> value) {
  std::lock_guard<std::mutex> lock(mutex_);
  return enqueue_notification({"CarData", {{"type", nullable_value(std::move(type))},
                                          {"value", nullable_value(std::move(value))}}});
}
}  // namespace hct
