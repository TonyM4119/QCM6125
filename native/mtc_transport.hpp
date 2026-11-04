#pragma once

#include <mutex>
#include <string>
#include <string_view>

namespace hct {

// Injectable calls keep host tests entirely separate from head-unit hardware.
class DeviceCalls {
 public:
  virtual ~DeviceCalls() = default;
  virtual int open_device(const char* path, int flags) = 0;
  virtual int control(int fd, unsigned long request, void* argument) = 0;
  virtual int close_device(int fd) = 0;
};

class LinuxDeviceCalls final : public DeviceCalls {
 public:
  int open_device(const char* path, int flags) override;
  int control(int fd, unsigned long request, void* argument) override;
  int close_device(int fd) override;
};

// Experimental transport, not a replacement for CarService or its DSP logic.
// Callers supply command bytes; this layer performs no Java string conversion.
// Use one shared instance to serialize access. No device access occurs until a
// caller explicitly invokes set_parameters() or get_parameters().
class MtcTransport {
 public:
  static constexpr unsigned long query_flag = 0x10000;
  static constexpr std::size_t query_capacity = 0xc00;

  explicit MtcTransport(DeviceCalls& calls) : calls_(calls) {}
  int set_parameters(std::string_view command);
  std::string get_parameters(std::string_view query);

 private:
  DeviceCalls& calls_;
  std::mutex mutex_;
};

}  // namespace hct
