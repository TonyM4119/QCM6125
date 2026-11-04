#include "callback_policy.hpp"
#include "offline_service_core.hpp"

#include <iostream>
#include <stdexcept>

namespace {
void check(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
}

int main() {
  hct::EventNotification radio{"Radio", {{"type", std::string("seek_end")}}};
  check(!hct::plan_client_delivery("CarData", radio, true, true), "unmatched event delivered");
  check(!hct::plan_client_delivery("radio", radio, true, true), "case-sensitive filter changed");
  check(!hct::plan_client_delivery("", radio, true, true), "empty subscription matched named event");
  check(!hct::plan_client_delivery("Radio", radio, false, false), "delivery invented absent target");
  const auto handler = hct::plan_client_delivery("CarData,Radio,VideoSignal", radio, true, true);
  check(handler && handler->route == hct::CallbackRoute::handler && handler->message_what == -1,
        "Handler precedence or Message.what changed");
  check(handler->event.topic == "Radio" && handler->event.fields == radio.fields,
        "Handler event name or Bundle fields changed");
  const auto listener = hct::plan_client_delivery("Radio", radio, false, true);
  check(listener && listener->route == hct::CallbackRoute::listener && !listener->message_what,
        "listener fallback changed");
  check(hct::plan_client_delivery("RadioExtended", radio, false, true).has_value(),
        "substring match was incorrectly replaced with exact token matching");
  hct::EventNotification empty{"", {}};
  check(hct::plan_client_delivery("", empty, true, false).has_value(),
        "Java contains(empty) behaviour changed");

  hct::OfflineServiceCore core;
  core.notify_data_change(std::string("volume"), std::string("12"));
  auto queued = core.drain_notifications();
  auto planned = hct::plan_client_delivery("CarData", queued.at(0), true, false);
  queued[0].fields["value"] = std::string("99");
  check(planned && std::get<std::string>(planned->event.fields.at("value")) == "12",
        "planned delivery exposed mutable source fields");
  check(core.drain_notifications().empty(), "client delivery requeued service notification");
  std::cout << "Callback filtering, target precedence and delivery-shape checks passed; no Binder/Android I/O.\n";
}
