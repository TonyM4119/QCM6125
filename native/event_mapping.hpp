#pragma once

#include "event_stream.hpp"
#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <variant>
#include <vector>

namespace hct {
using ByteArray = std::vector<std::uint8_t>;
using IntArray = std::vector<std::int32_t>;
using StringArray = std::vector<std::optional<std::string>>;
using EventValue = std::variant<std::monostate, bool, std::int8_t, std::int32_t,
                                std::string, ByteArray, IntArray, StringArray>;
using EventFields = std::map<std::string, EventValue>;
struct EventNotification { std::string topic; EventFields fields; };
enum class EventDecodeStatus { mapped, unknown, malformed };
struct EventMapping {
  EventDecodeStatus status = EventDecodeStatus::unknown;
  EventFields state_updates;
  std::vector<EventNotification> notifications;
};

// A deliberately limited, side-effect-free mapping. Does not perform Binder,
// camera control, shutdown, UI changes or any other Android platform action.
EventMapping map_event(const EventFrame& frame);
}  // namespace hct
