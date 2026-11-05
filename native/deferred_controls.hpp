#pragma once

#include "control_policy.hpp"
#include <cstdint>
#include <vector>

namespace hct {
// Deterministic host queue for the three reviewed Handler message kinds.
// Caller supplies monotonic milliseconds and explicitly chooses dispatch times.
// No clock, thread, Android Handler, setting write or driver operation is used.
class DeferredControls {
 public:
  void request_eq(std::int32_t index, std::uint64_t now_ms);
  void request_loudness(bool enabled, std::uint64_t now_ms);
  void request_video_speed(bool over_speed, std::uint64_t now_ms);
  std::vector<DeferredControl> take_due(std::uint64_t now_ms);
  std::size_t pending_count() const { return pending_.size(); }

 private:
  struct Pending { DeferredControl message; std::uint64_t due_ms; };
  std::vector<Pending> pending_;
  std::uint64_t last_time_ = 0;
  void schedule(DeferredControl message, std::uint64_t now_ms);
  void check_time(std::uint64_t now_ms) const;
};
}  // namespace hct
