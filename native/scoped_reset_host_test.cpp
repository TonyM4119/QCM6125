// Compiles the actual added native method with fake disks/volumes only.
#include <cerrno>
#include <iostream>
#include <list>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

namespace android::vold {
struct VolumeBase {
  enum class Type { kPublic, kPrivate, kEmulated };
  enum class State { kUnmounted, kChecking, kMounted, kMountedReadOnly,
                     kFormatting, kEjecting, kUnmountable, kRemoved, kBadRemoval };
  Type type = Type::kPublic;
  State state = State::kUnmounted;
  Type getType() const { return type; }
  State getState() const { return state; }
};
struct Disk {
  enum Flags { kAdoptable=1, kSd=4, kUsb=8, kEmmc=16 };
  std::string id;
  int flags = kUsb;
  bool stub = false;
  int destroy_status = 0, create_status = 0;
  std::vector<std::shared_ptr<VolumeBase>> volumes;
  std::vector<std::string>* calls;
  const std::string& getId() const { return id; }
  int getFlags() const { return flags; }
  bool isStub() const { return stub; }
  auto getVolumes() const { return volumes; }
  int destroy() { calls->push_back(id+":destroy"); return destroy_status; }
  int create() { calls->push_back(id+":create"); return create_status; }
};
}
struct VolumeManager {
  std::list<std::shared_ptr<android::vold::Disk>> mDisks;
  int exresetPublic(const std::vector<std::string>& diskIds);
};
#include "scoped_reset_method.inc"

int main() {
  using android::vold::Disk;
  using android::vold::VolumeBase;
  std::vector<std::string> calls;
  int scenarios = 0;
  auto disk = [&](const std::string& id) {
    auto d=std::make_shared<Disk>(); d->id=id; d->calls=&calls;
    d->volumes.push_back(std::make_shared<VolumeBase>()); return d;
  };
  auto run = [&](std::list<std::shared_ptr<Disk>> disks, std::vector<std::string> ids,
                 int status, std::vector<std::string> expected={}) {
    VolumeManager vm{disks}; calls.clear();
    if (vm.exresetPublic(ids)!=status || calls!=expected)
      throw std::runtime_error("scoped native selection/order/failure check failed");
    ++scenarios;
  };
  auto a=disk("a"), b=disk("b");
  run({a,b},{"a"},0,{"a:destroy","a:create"});
  run({a,b},{"b","a"},0,{"a:destroy","a:create","b:destroy","b:create"});
  run({a,b},{},0);
  run({a,b},{"a","a"},-EINVAL);
  run({a,b},{""},-EINVAL);
  run({a,b},{"a","missing"},-ENODEV); // No partial mutation of a.
  run({a},std::vector<std::string>(65,"a"),-EINVAL);
  b->volumes[0]->type=VolumeBase::Type::kPrivate;
  run({a,b},{"a","b"},-EINVAL); // Validate every disk before mutating any.
  run({a,b},{"a"},0,{"a:destroy","a:create"}); // Unrequested private media untouched.
  b->volumes[0]->type=VolumeBase::Type::kPublic;
  for (auto state : {VolumeBase::State::kChecking, VolumeBase::State::kMounted,
       VolumeBase::State::kMountedReadOnly, VolumeBase::State::kFormatting,
       VolumeBase::State::kEjecting, VolumeBase::State::kUnmountable,
       VolumeBase::State::kRemoved, VolumeBase::State::kBadRemoval}) {
    b->volumes[0]->state=state; run({a,b},{"a","b"},-EBUSY);
  }
  b->volumes[0]->state=VolumeBase::State::kUnmounted;
  b->volumes.clear(); run({a,b},{"a","b"},-ENODEV);
  b=disk("b"); b->flags=Disk::kEmmc; run({a,b},{"a","b"},-EINVAL);
  b->flags=Disk::kUsb|Disk::kEmmc; run({a,b},{"a","b"},-EINVAL);
  b->flags=Disk::kUsb; b->stub=true; run({a,b},{"a","b"},-EINVAL);
  b->stub=false; b->flags=Disk::kSd|Disk::kUsb|Disk::kAdoptable;
  run({b},{"b"},0,{"b:destroy","b:create"}); // Adoptable flag is not adopted content.
  a->destroy_status=-EIO;
  run({a,b},{"a","b"},-EIO,{"a:destroy"});
  a->destroy_status=0; a->create_status=-EIO;
  run({a,b},{"a","b"},-EIO,{"a:destroy","a:create"});
  std::cout << scenarios << " scoped-reset extracted-method scenarios passed; fake disks only.\n";
}
