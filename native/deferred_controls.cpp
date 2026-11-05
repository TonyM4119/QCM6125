#include "deferred_controls.hpp"
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace hct {
void DeferredControls::check_time(std::uint64_t now_ms) const {
  if (now_ms < last_time_) throw std::invalid_argument("Host control clock moved backwards");
}
void DeferredControls::schedule(DeferredControl message, std::uint64_t now_ms) {
  check_time(now_ms);
  const auto delay = static_cast<std::uint64_t>(message.delay_ms);
  if (now_ms > std::numeric_limits<std::uint64_t>::max() - delay)
    throw std::overflow_error("Host control due time overflow");
  // Allocation happens before removing an existing message, so allocation
  // failure does not silently cancel it. There are at most three pending kinds.
  auto updated = pending_;
  updated.erase(std::remove_if(updated.begin(), updated.end(), [&](const Pending& entry) {
    return entry.message.what == message.what;
  }), updated.end());
  updated.push_back({message, now_ms + delay});
  std::stable_sort(updated.begin(), updated.end(), [](const Pending& a, const Pending& b) {
    return a.due_ms < b.due_ms;
  });
  pending_.swap(updated);
  last_time_ = now_ms;
}
void DeferredControls::request_eq(std::int32_t index, std::uint64_t now_ms) {
  schedule(plan_eq_request(index), now_ms);
}
void DeferredControls::request_loudness(bool enabled, std::uint64_t now_ms) {
  schedule(plan_loudness_request(enabled), now_ms);
}
void DeferredControls::request_video_speed(bool over_speed, std::uint64_t now_ms) {
  schedule(plan_video_speed_request(over_speed), now_ms);
}
std::vector<DeferredControl> DeferredControls::take_due(std::uint64_t now_ms) {
  check_time(now_ms);
  std::vector<DeferredControl> result;
  for (const auto& entry : pending_) {
    if (entry.due_ms > now_ms) break;
    result.push_back(entry.message);
  }
  pending_.erase(pending_.begin(), pending_.begin() + result.size());
  last_time_ = now_ms;
  return result;
}
}  // namespace hct
