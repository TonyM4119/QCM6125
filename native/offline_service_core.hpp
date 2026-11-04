#pragma once

#include "car_parameter_policy.hpp"
#include "event_mapping.hpp"
#include <mutex>

namespace hct {
struct ReceiveReport {
  std::size_t frames = 0;
  std::size_t mapped = 0;
  std::size_t unknown = 0;
  std::size_t malformed = 0;
  std::size_t notifications_dropped = 0;
};

// Host model integrating recovered pieces. This is NOT an Android/Binder
// service. It never executes its parameter plans or invokes external callbacks.
class OfflineServiceCore {
 public:
  explicit OfflineServiceCore(std::size_t notification_limit = 256);
  ParameterPlan plan_parameter(std::optional<std::string_view> command);
  ReceiveReport receive(const std::vector<std::uint8_t>& bytes);
  EventFields state_snapshot() const;
  std::vector<EventNotification> drain_notifications();
  void put_boolean_state(std::string key, bool value);
  void put_byte_state(std::string key, std::int8_t value);
  void put_int_state(std::string key, std::int32_t value);
  ParameterPlan put_string_state(std::string key, std::optional<std::string> value);
  void put_byte_array_state(std::string key, std::optional<ByteArray> value);
  void put_int_array_state(std::string key, std::optional<IntArray> value);
  void put_string_array_state(std::string key, std::optional<StringArray> value);
  bool get_boolean_state(const std::string& key) const;
  std::int8_t get_byte_state(const std::string& key) const;
  std::int32_t get_int_state(const std::string& key) const;
  std::optional<std::string> get_string_state(const std::string& key) const;
  std::optional<ByteArray> get_byte_array_state(const std::string& key) const;
  std::optional<IntArray> get_int_array_state(const std::string& key) const;
  std::optional<StringArray> get_string_array_state(const std::string& key) const;
  std::size_t notify_data_change(std::optional<std::string> type, std::optional<std::string> value);

 private:
  const std::size_t notification_limit_;
  mutable std::mutex mutex_;
  EventStreamDecoder decoder_;
  EventFields state_;
  std::vector<EventNotification> notifications_;
  void write_state(std::string key, EventValue value);
  bool enqueue_notification(EventNotification notification); // Caller holds mutex_.
  template <typename T>
  std::optional<T> read_state(const std::string& key) const {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto item = state_.find(key);
    if (item != state_.end()) {
      if (const auto* value = std::get_if<T>(&item->second)) return *value;
    }
    return std::nullopt;
  }
};
}  // namespace hct
