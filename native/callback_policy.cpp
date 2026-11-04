#include "callback_policy.hpp"

namespace hct {
std::optional<ClientDelivery> plan_client_delivery(
    std::string_view attached_type, const EventNotification& event,
    bool has_handler, bool has_listener) {
  if (attached_type.find(event.topic) == std::string_view::npos) return std::nullopt;
  if (has_handler) return ClientDelivery{CallbackRoute::handler, -1, event};
  if (has_listener) return ClientDelivery{CallbackRoute::listener, std::nullopt, event};
  return std::nullopt;
}
}  // namespace hct
