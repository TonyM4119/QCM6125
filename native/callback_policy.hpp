#pragma once

#include "event_mapping.hpp"
#include <optional>
#include <string_view>

namespace hct {
enum class CallbackRoute { handler, listener };
struct ClientDelivery {
  CallbackRoute route;
  // Populated only for Handler delivery: Message.what = -1.
  std::optional<std::int32_t> message_what;
  // Handler Message.obj / listener event name, and the supplied Bundle fields.
  EventNotification event;
};

// Pure model of CarManager$1.onStatusChanged for non-null ASCII event/type
// strings and a non-null Bundle. No Handler, listener or Binder is invoked.
std::optional<ClientDelivery> plan_client_delivery(
    std::string_view attached_type, const EventNotification& event,
    bool has_handler, bool has_listener);
}  // namespace hct
