#include "offline_service_core.hpp"

#include <stdexcept>
#include <utility>

namespace hct {
OfflineServiceCore::OfflineServiceCore(std::size_t notification_limit)
    : notification_limit_(notification_limit) {
  if (notification_limit == 0) throw std::invalid_argument("Notification limit must be positive");
  state_["av_channel"] = parameter_policy_.audio_channel();
}

ParameterPlan OfflineServiceCore::plan_parameter(std::optional<std::string_view> command) {
  std::lock_guard<std::mutex> lock(mutex_);
  const auto old_navigation = parameter_policy_.navigation_package();
  auto plan = parameter_policy_.plan(command);
  state_["av_channel"] = parameter_policy_.audio_channel();
  if (old_navigation != parameter_policy_.navigation_package()) {
    state_["navi_package"] = parameter_policy_.navigation_package();
  }
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
      if (notifications_.size() == notification_limit_) {
        notifications_.erase(notifications_.begin());
        ++report.notifications_dropped;
      }
      notifications_.push_back(std::move(notification));
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
}  // namespace hct
