#include "event_stream.hpp"

#include <algorithm>
#include <stdexcept>

namespace hct {
EventStreamDecoder::EventStreamDecoder(std::size_t maximum_payload)
    : maximum_payload_(maximum_payload) {
  if (maximum_payload > 65535) throw std::invalid_argument("Payload limit exceeds wire field");
  pending_.reserve(maximum_payload + 5);
}

std::vector<EventFrame> EventStreamDecoder::feed(const std::vector<std::uint8_t>& bytes) {
  std::vector<EventFrame> frames;
  for (const auto byte : bytes) {
    pending_.push_back(byte);
    drain(frames);
  }
  return frames;
}

void EventStreamDecoder::drain(std::vector<EventFrame>& frames) {
  while (!pending_.empty()) {
    const auto marker = std::find(pending_.begin(), pending_.end(), 0xfa);
    discarded_ += static_cast<std::size_t>(marker - pending_.begin());
    pending_.erase(pending_.begin(), marker);
    if (pending_.size() < 5) return;
    const auto length = static_cast<std::size_t>(pending_[3]) |
                        (static_cast<std::size_t>(pending_[4]) << 8);
    if (length > maximum_payload_) {
      ++rejected_;
      ++discarded_;
      pending_.erase(pending_.begin());
      continue;
    }
    if (pending_.size() < length + 5) return;
    frames.push_back({pending_[1], pending_[2],
                      std::vector<std::uint8_t>(pending_.begin() + 5,
                                               pending_.begin() + 5 + length)});
    pending_.erase(pending_.begin(), pending_.begin() + 5 + length);
  }
}
}  // namespace hct
