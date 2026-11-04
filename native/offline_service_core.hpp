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

 private:
  const std::size_t notification_limit_;
  mutable std::mutex mutex_;
  CarParameterPolicy parameter_policy_;
  EventStreamDecoder decoder_;
  EventFields state_;
  std::vector<EventNotification> notifications_;
};
}  // namespace hct
