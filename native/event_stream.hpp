#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace hct {
struct EventFrame {
  std::uint8_t category;
  std::uint8_t subcommand;
  std::vector<std::uint8_t> payload;
};

// Offline receive framing only: no serial/device access and no event semantics.
// Default bound fits the observed service's 4096-byte receive buffer. Oversize
// resynchronization is a deliberate defensive policy, not factory bug emulation.
class EventStreamDecoder {
 public:
  explicit EventStreamDecoder(std::size_t maximum_payload = 4091);
  std::vector<EventFrame> feed(const std::vector<std::uint8_t>& bytes);
  std::size_t buffered_bytes() const { return pending_.size(); }
  std::size_t discarded_bytes() const { return discarded_; }
  std::size_t rejected_headers() const { return rejected_; }

 private:
  void drain(std::vector<EventFrame>& frames);
  const std::size_t maximum_payload_;
  std::vector<std::uint8_t> pending_;
  std::size_t discarded_ = 0;
  std::size_t rejected_ = 0;
};
}  // namespace hct
