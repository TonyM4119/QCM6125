#include "mtc_transport.hpp"

#include <array>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <system_error>
#include <sys/ioctl.h>
#include <unistd.h>

namespace hct {
namespace {

void validate(std::string_view command, std::size_t maximum) {
  if (command.empty() || command.size() > maximum ||
      command.find('\0') != std::string_view::npos) {
    throw std::invalid_argument("Invalid MTC command byte length or embedded NUL");
  }
}

class DeviceHandle {
 public:
  explicit DeviceHandle(DeviceCalls& calls) : calls_(calls) {
    fd_ = calls_.open_device("/dev/mtc-car", O_RDWR | O_CLOEXEC);
    if (fd_ < 0) {
      throw std::system_error(errno, std::generic_category(), "open mtc-car");
    }
  }
  ~DeviceHandle() { calls_.close_device(fd_); }
  DeviceHandle(const DeviceHandle&) = delete;
  DeviceHandle& operator=(const DeviceHandle&) = delete;
  int fd() const { return fd_; }

 private:
  DeviceCalls& calls_;
  int fd_;
};

}  // namespace

int LinuxDeviceCalls::open_device(const char* path, int flags) {
  return ::open(path, flags);
}
int LinuxDeviceCalls::control(int fd, unsigned long request, void* argument) {
  return ::ioctl(fd, request, argument);
}
int LinuxDeviceCalls::close_device(int fd) { return ::close(fd); }

int MtcTransport::set_parameters(std::string_view command) {
  // The inspected working kernel accepts text request lengths 1..3071.
  validate(command, maximum_command_bytes);
  std::lock_guard<std::mutex> lock(mutex_);
  DeviceHandle device(calls_);
  std::string bytes(command);
  const int result = calls_.control(device.fd(), bytes.size(), bytes.data());
  if (result < 0) {
    throw std::system_error(errno, std::generic_category(), "MTC set ioctl");
  }
  return result;
}

std::string MtcTransport::get_parameters(std::string_view query) {
  validate(query, maximum_command_bytes);
  std::lock_guard<std::mutex> lock(mutex_);
  DeviceHandle device(calls_);
  std::array<char, query_capacity> buffer{};
  std::memcpy(buffer.data(), query.data(), query.size());
  const auto request = query_flag | static_cast<unsigned long>(query.size());
  if (calls_.control(device.fd(), request, buffer.data()) < 0) {
    throw std::system_error(errno, std::generic_category(), "MTC query ioctl");
  }
  const auto* end = static_cast<const char*>(
      std::memchr(buffer.data(), '\0', buffer.size()));
  if (!end) {
    throw std::runtime_error("MTC query response is not NUL-terminated");
  }
  return std::string(buffer.data(), static_cast<std::size_t>(end - buffer.data()));
}

}  // namespace hct
