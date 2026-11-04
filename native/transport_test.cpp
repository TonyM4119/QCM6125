#include "mtc_transport.hpp"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <stdexcept>
#include <system_error>

namespace {
void check(bool value, const char* message) {
  if (!value) throw std::runtime_error(message);
}

class FakeDevice final : public hct::DeviceCalls {
 public:
  bool fail_open = false;
  bool fail_control = false;
  bool unterminated = false;
  int opens = 0;
  int closes = 0;
  unsigned long expected_request = 0;
  std::string expected_input;
  std::string response = "factory-test-response";

  int open_device(const char* path, int flags) override {
    ++opens;
    check(std::string(path) == "/dev/mtc-car", "wrong device path");
    check((flags & O_ACCMODE) == O_RDWR, "wrong access mode");
    check(flags & O_CLOEXEC, "missing close-on-exec");
    if (fail_open) { errno = EACCES; return -1; }
    return 73;
  }
  int control(int fd, unsigned long request, void* data) override {
    check(fd == 73, "wrong fd");
    check(request == expected_request, "wrong request encoding");
    check(std::string(static_cast<char*>(data)) == expected_input, "wrong command bytes");
    if (fail_control) { errno = EIO; return -1; }
    if (request & hct::MtcTransport::query_flag) {
      if (unterminated) {
        std::memset(data, 'x', hct::MtcTransport::query_capacity);
      } else {
        std::memcpy(data, response.c_str(), response.size() + 1);
      }
    }
    return 7;
  }
  int close_device(int fd) override {
    check(fd == 73, "wrong close fd");
    ++closes;
    return 0;
  }
};

template <typename Error, typename Function>
void expect_error(Function function) {
  bool raised = false;
  try { function(); } catch (const Error&) { raised = true; }
  check(raised, "expected error was not raised");
}
}  // namespace

int main() {
  FakeDevice calls;
  hct::MtcTransport transport(calls);
  calls.expected_input = "test_key=test_value";
  calls.expected_request = calls.expected_input.size();
  check(transport.set_parameters(calls.expected_input) == 7, "lost ioctl return");
  check(calls.opens == 1 && calls.closes == 1, "setter handle leak");

  calls.expected_input = "test_key=";
  calls.expected_request = hct::MtcTransport::query_flag | calls.expected_input.size();
  check(transport.get_parameters(calls.expected_input) == calls.response, "wrong query response");
  check(calls.opens == 2 && calls.closes == 2, "getter handle leak");

  calls.fail_control = true;
  expect_error<std::system_error>([&] { transport.get_parameters(calls.expected_input); });
  check(calls.closes == 3, "handle leak on ioctl error");
  calls.expected_request = calls.expected_input.size();
  expect_error<std::system_error>([&] { transport.set_parameters(calls.expected_input); });
  check(calls.closes == 4, "setter handle leak on ioctl error");
  calls.fail_control = false;

  calls.fail_open = true;
  expect_error<std::system_error>([&] { transport.get_parameters(calls.expected_input); });
  check(calls.closes == 4, "closed invalid handle");
  calls.fail_open = false;

  calls.expected_request = hct::MtcTransport::query_flag | calls.expected_input.size();
  calls.unterminated = true;
  expect_error<std::runtime_error>([&] { transport.get_parameters(calls.expected_input); });
  check(calls.closes == 5, "handle leak on invalid response");

  const int before = calls.opens;
  expect_error<std::invalid_argument>([&] { transport.get_parameters(""); });
  expect_error<std::invalid_argument>([&] { transport.get_parameters(std::string(3072, 'x')); });
  expect_error<std::invalid_argument>([&] { transport.set_parameters(std::string(65536, 'x')); });
  expect_error<std::invalid_argument>([&] { transport.set_parameters(std::string("a\0b", 3)); });
  check(calls.opens == before, "invalid input reached driver");
  std::cout << "All fake-device transport checks passed; no hardware accessed.\n";
}
