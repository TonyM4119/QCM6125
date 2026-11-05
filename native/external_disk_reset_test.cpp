#include "external_disk_reset.hpp"
#include <iostream>
#include <list>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
void check(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
struct FakeDisk {
  unsigned flags;
  std::string name;
  std::vector<std::string>* calls;
  int destroy_result = 0;
  bool throw_on_destroy = false;
  unsigned getFlags() const { return flags; }
  int destroy() {
    calls->push_back(name + ":destroy");
    if (throw_on_destroy) throw std::runtime_error("synthetic destroy exception");
    return destroy_result;
  }
  int create() { calls->push_back(name + ":create"); return -7; }
};
}
int main() {
  std::vector<std::string> calls;
  std::list<std::shared_ptr<FakeDisk>> disks;
  for (const auto& item : std::vector<std::pair<unsigned, std::string>>{
           {0, "none"}, {1, "adoptable"}, {2, "primary"}, {4, "sd"},
           {8, "usb"}, {12, "both"}, {16, "emmc"}, {32, "stub"}, {9, "adoptable_usb"}}) {
    disks.push_back(std::make_shared<FakeDisk>(FakeDisk{item.first, item.second, &calls}));
  }
  check(hct::experimental_reset_external_disks(disks) == 0, "normal reset return changed");
  check(calls == std::vector<std::string>{"sd:destroy", "sd:create", "usb:destroy", "usb:create",
                                         "both:destroy", "both:create", "adoptable_usb:destroy",
                                         "adoptable_usb:create"},
        "flag selection, per-disk order or duplicate operation changed");
  calls.clear();
  auto failing = std::make_shared<FakeDisk>(FakeDisk{8, "failure", &calls, -5});
  check(hct::experimental_reset_external_disks(std::vector<std::shared_ptr<FakeDisk>>{failing}) == 0 &&
        calls == std::vector<std::string>{"failure:destroy", "failure:create"},
        "reconstruction invented a return-code short circuit");
  calls.clear();
  failing->throw_on_destroy = true;
  bool threw = false;
  try { hct::experimental_reset_external_disks(std::vector<std::shared_ptr<FakeDisk>>{failing}); }
  catch (const std::runtime_error&) { threw = true; }
  check(threw && calls == std::vector<std::string>{"failure:destroy"},
        "synthetic exception was swallowed or create ran after throw");
  check(hct::experimental_reset_external_disks(std::vector<std::shared_ptr<FakeDisk>>{}) == 0,
        "empty disk range changed normal result");
  std::cout << "Experimental external-reset selection/order checks passed; fake disks only.\n";
}
