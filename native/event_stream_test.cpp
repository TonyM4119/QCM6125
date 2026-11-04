#include "event_stream.hpp"

#include <iostream>
#include <stdexcept>

namespace {
void check(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
}  // namespace

int main() {
  // Marker within payload must not split a frame; length is little-endian.
  const std::vector<std::uint8_t> frame{0xfa, 0x10, 0x41, 2, 0, 0x55, 0xfa};
  for (std::size_t split = 0; split <= frame.size(); ++split) {
    hct::EventStreamDecoder decoder;
    auto output = decoder.feed({frame.begin(), frame.begin() + split});
    auto tail = decoder.feed({frame.begin() + split, frame.end()});
    output.insert(output.end(), tail.begin(), tail.end());
    check(output.size() == 1, "fragmented frame lost or duplicated");
    check(output[0].category == 0x10 && output[0].subcommand == 0x41, "header changed");
    check(output[0].payload == std::vector<std::uint8_t>({0x55, 0xfa}), "payload changed");
    check(decoder.buffered_bytes() == 0, "complete frame retained");
  }

  hct::EventStreamDecoder decoder;
  auto empty = decoder.feed({0, 1, 2, 0xfa, 0x11});
  check(empty.empty() && decoder.buffered_bytes() == 2, "partial header not retained");
  auto two = decoder.feed({0x22, 0, 0, 0xfa, 0x33, 0x44, 1, 0, 0x77});
  check(two.size() == 2 && two[0].payload.empty() && two[1].payload[0] == 0x77,
        "concatenated or zero-payload frame failed");
  check(decoder.discarded_bytes() == 3, "noise accounting failed");

  std::vector<std::uint8_t> large{0xfa, 1, 2, 0, 1}; // 256 payload bytes.
  large.resize(261, 0x66);
  auto large_output = decoder.feed(large);
  check(large_output.size() == 1 && large_output[0].payload.size() == 256,
        "two-byte little-endian length failed");

  hct::EventStreamDecoder bounded(2);
  auto recovered = bounded.feed({0xfa, 1, 2, 3, 0, 0xfa, 3, 4, 1, 0, 0x88});
  check(bounded.rejected_headers() == 1, "oversized header not rejected");
  check(recovered.size() == 1 && recovered[0].payload[0] == 0x88, "resynchronization failed");
  check(bounded.buffered_bytes() == 0, "resynchronized bytes retained");
  for (int i = 0; i < 10000; ++i) bounded.feed({0x22});
  check(bounded.buffered_bytes() == 0, "noise causes unbounded retention");

  bool invalid = false;
  try { hct::EventStreamDecoder unsupported(65536); }
  catch (const std::invalid_argument&) { invalid = true; }
  check(invalid, "unsupported wire length allowed");
  std::cout << "Synthetic stream fragmentation, framing and bound checks passed; no hardware accessed.\n";
}
