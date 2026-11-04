#include "event_mapping.hpp"

#include <algorithm>

namespace hct {
namespace {
EventMapping notification(const std::string& topic, const std::string& type) {
  EventMapping result;
  result.status = EventDecodeStatus::mapped;
  result.notifications.push_back({topic, {{"type", type}}});
  return result;
}
EventMapping malformed() {
  EventMapping result;
  result.status = EventDecodeStatus::malformed;
  return result;
}
std::int32_t little16(const std::vector<std::uint8_t>& bytes, std::size_t offset) {
  return bytes[offset] | (static_cast<std::int32_t>(bytes[offset + 1]) << 8);
}
std::int32_t radio_frequency(const std::vector<std::uint8_t>& bytes) {
  const std::uint32_t units = bytes[0] | (static_cast<std::uint32_t>(bytes[1]) << 8) |
                              (static_cast<std::uint32_t>(bytes[2]) << 16);
  // Java's int multiplication wraps; avoid C++ signed-overflow undefined behaviour.
  const std::uint32_t wrapped = units * 1000u;
  std::int64_t value = wrapped;
  if (value > 2147483647LL) value -= 4294967296LL;
  return static_cast<std::int32_t>(value);
}
EventMapping boolean_state(const EventFrame& frame, const std::string& key) {
  if (frame.payload.empty()) return malformed();
  auto result = notification("CarEvent", key);
  const bool value = frame.payload[0] != 0;
  result.state_updates[key] = value;
  result.notifications[0].fields["value"] = value;
  return result;
}
}  // namespace

EventMapping map_event(const EventFrame& frame) {
  const auto& payload = frame.payload;
  if (frame.category == 0x11) {
    const char* type = nullptr;
    switch (frame.subcommand) {
      case 0x20: type = "seek_end"; break;
      case 0x22: type = "seek_end_auto"; break;
      case 0x33: type = "seek_start"; break;
      case 0x34: type = "seek_start_auto"; break;
      case 0x40: type = "bg_seek_refresh"; break;
      case 0x42: type = "bg_seek_end"; break;
      case 0x31: case 0x32: {
        auto result = notification("Radio", "ta");
        result.notifications[0].fields["value"] = std::int32_t(frame.subcommand == 0x31 ? 1 : 0);
        return result;
      }
      case 0x21: case 0x35: {
        if (payload.empty()) return malformed();
        auto result = notification("Radio", frame.subcommand == 0x21 ? "seek_found" : "seek_found_auto");
        result.notifications[0].fields["strength"] = static_cast<std::int32_t>(payload[0]);
        return result;
      }
      case 0x24: case 0x27: case 0x29: {
        if (payload.empty()) return malformed();
        const char* name = frame.subcommand == 0x24 ? "tp" : frame.subcommand == 0x27 ? "pty" : "stereo";
        auto result = notification("Radio", name);
        result.notifications[0].fields["value"] = static_cast<std::int32_t>(payload[0]);
        return result;
      }
      case 0x28: {
        if (payload.size() < 2) return malformed();
        auto result = notification("Radio", "pi");
        result.notifications[0].fields["value"] = little16(payload, 0);
        return result;
      }
      case 0x25: {
        if (payload.size() < 3) return malformed();
        auto result = notification("Radio", "freq");
        result.notifications[0].fields["value"] = radio_frequency(payload);
        return result;
      }
      case 0x23: case 0x26: {
        auto result = notification("Radio", frame.subcommand == 0x23 ? "rt" : "psn");
        // The reference keeps bytes up to the first NUL; it does not transcode
        // this helper's byte-array result to a Java String.
        const auto end = std::find(payload.begin(), payload.end(), 0);
        result.notifications[0].fields["value"] = std::vector<std::uint8_t>(payload.begin(), end);
        return result;
      }
      case 0x41: {
        if (payload.size() < 4 || payload.size() == 5) return malformed();
        auto result = notification("Radio", "bg_seek_found");
        auto& fields = result.notifications[0].fields;
        fields["freq"] = radio_frequency(payload);
        fields["db"] = static_cast<std::int32_t>(payload[3]);
        fields["pi"] = payload.size() > 4 ? little16(payload, 4) : std::int32_t(0);
        fields["psn"] = std::monostate{};
        if (payload.size() > 6) {
          std::size_t count = 0;
          while (count < 8 && 6 + count < payload.size() && payload[6 + count] != 0) ++count;
          // A short field is accepted only when it has an explicit NUL, as in
          // the reviewed helper; otherwise it would read beyond this frame.
          if (count < 8 && 6 + count == payload.size()) return malformed();
          fields["psn"] = std::vector<std::uint8_t>(payload.begin() + 6, payload.begin() + 6 + count);
        }
        fields["pty"] = std::int32_t(0);
        fields["tp"] = std::int32_t(0);
        fields["ta"] = std::int32_t(0);
        return result;
      }
      default: return {};
    }
    return notification("Radio", type);
  }
  if (frame.category == 0x1f) {
    switch (frame.subcommand) {
      case 0: {
        if (payload.size() < 4) return malformed();
        auto result = notification("TouchStudy", "touch_xy");
        result.notifications[0].fields["x"] = little16(payload, 0);
        result.notifications[0].fields["y"] = little16(payload, 2);
        return result;
      }
      case 1: {
        if (payload.empty()) return malformed();
        auto result = notification("TouchStudy", "touch_key");
        result.notifications[0].fields["index"] = static_cast<std::int32_t>(payload[0]);
        return result;
      }
      case 2: {
        if (payload.size() < 2) return malformed();
        auto result = notification("VideoSignal", "video_signal");
        const char* channels[] = {"null", "backview", "avin", "tv", "dvr"};
        result.notifications[0].fields["channel"] =
            std::string(channels[payload[1] <= 4 ? payload[1] : 0]);
        result.notifications[0].fields["signal"] = payload[0] == 1;
        return result;
      }
      case 3: return notification("CarEvent", "touch_down");
      case 4: return notification("CarEvent", "touch_up");
      default: return {};
    }
  }
  if (frame.category == 0x10) {
    if (frame.subcommand == 0x14) {
      if (payload.empty()) return malformed();
      auto result = notification("CarEvent", "mute");
      result.notifications[0].fields["value"] = payload[0] == 1;
      return result;
    }
    if (frame.subcommand == 0x30 || frame.subcommand == 0x31) {
      const std::string key = frame.subcommand == 0x30 ? "dsp_spk_vol" : "dsp_spk_delay";
      auto result = notification("CarEvent", key);
      result.state_updates[key] = payload;
      result.notifications[0].fields["value"] = payload;
      return result;
    }
    return {};
  }
  if (frame.category != 0x16) return {};
  switch (frame.subcommand) {
    case 0xd3: return boolean_state(frame, "aux");
    case 0x4b: return boolean_state(frame, "handbrake");
    case 0x4c: return boolean_state(frame, "ipod");
    case 0x8f: {
      if (payload.empty()) return malformed();
      auto result = notification("CarEvent", "orientation");
      const auto value = static_cast<std::int32_t>(payload[0]);
      result.state_updates["orientation"] = value;
      result.notifications[0].fields["value"] = value;
      return result;
    }
    case 0x43: {
      if (payload.empty()) return malformed();
      auto result = notification("CarEvent", "backview");
      result.state_updates["backview"] = true;
      result.notifications[0].fields["value"] = true;
      std::string mode;
      if (payload[0] == 1) mode = "backview";
      else if (payload[0] == 6) mode = "frontview";
      else if (payload[0] == 7) mode = "rightview";
      if (mode.empty()) result.state_updates["backview_mode"] = std::monostate{};
      else {
        result.state_updates["backview_mode"] = mode;
        result.notifications[0].fields["mode"] = mode;
      }
      return result;
    }
    case 0x44: {
      auto result = notification("CarEvent", "backview");
      result.state_updates["backview"] = false;
      result.state_updates["backview_mode"] = std::monostate{};
      result.notifications[0].fields["value"] = false;
      return result;
    }
    case 0x40: case 0x41: case 0x42: case 0x49: {
      const std::string type = frame.subcommand == 0x40 ? "power_on" :
          frame.subcommand == 0x41 ? "power_off" :
          frame.subcommand == 0x42 ? "sleep" : "acc_off";
      auto result = notification("CarPower", type);
      result.state_updates["carpower"] = type;
      return result;
    }
    default: return {};
  }
}
}  // namespace hct
