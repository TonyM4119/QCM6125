// Scaffolding only: compiles the method extracted from the experimental patch.
// No Android headers or real disk objects are used here.
#include <iostream>
#include <list>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace android::vold {
struct Disk {
  enum Flags { kSd = 1 << 2, kUsb = 1 << 3 };
  int flags;
  std::string name;
  std::vector<std::string>* calls;
  int destroy_result = 0;
  int getFlags() const { return flags; }
  int destroy() { calls->push_back(name + ":destroy"); return destroy_result; }
  int create() { calls->push_back(name + ":create"); return -7; }
};
}  // namespace android::vold
struct VolumeManager {
  std::list<std::shared_ptr<android::vold::Disk>> mDisks;
  int exreset();
};
#include "vold_exreset_method.inc"

int main() {
  VolumeManager manager;
  std::vector<std::string> calls;
  for (const auto& item : std::vector<std::pair<int, std::string>>{
           {0, "none"}, {1, "adoptable"}, {2, "primary"}, {4, "sd"},
           {8, "usb"}, {12, "both"}, {16, "emmc"}, {32, "stub"}, {9, "adoptable_usb"}}) {
    manager.mDisks.push_back(std::make_shared<android::vold::Disk>(
        android::vold::Disk{item.first, item.second, &calls}));
  }
  if (manager.exreset() != 0 || calls != std::vector<std::string>{
      "sd:destroy", "sd:create", "usb:destroy", "usb:create", "both:destroy", "both:create",
      "adoptable_usb:destroy", "adoptable_usb:create"})
    throw std::runtime_error("patched method changed selection, order or normal return");
  calls.clear();
  manager.mDisks.clear();
  manager.mDisks.push_back(std::make_shared<android::vold::Disk>(
      android::vold::Disk{8, "failed_status", &calls, -5}));
  if (manager.exreset() != 0 || calls != std::vector<std::string>{
      "failed_status:destroy", "failed_status:create"})
    throw std::runtime_error("patched method introduced a status-code short circuit");
  calls.clear();
  manager.mDisks.clear();
  if (manager.exreset() != 0 || !calls.empty())
    throw std::runtime_error("empty-range behaviour changed");
  std::cout << "Patched VolumeManager::exreset method passed fake-disk selection/order/status checks.\n";
}
