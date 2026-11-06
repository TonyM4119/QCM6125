#include "sleep_storage_sequence.hpp"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
void check(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
struct Adapter {
  bool sleeping = true;
  bool wake_during_storage = false;
  bool unexpected_failure = false;
  hct::StoragePreparation storage = hct::StoragePreparation::completed;
  std::vector<std::string> calls;
  bool is_sleep() { calls.push_back("state"); return sleeping; }
  void report_media_safe_mounted(const char* value) { calls.push_back(value); }
  hct::StoragePreparation unmount_hctall() {
    calls.push_back("hctall");
    if (unexpected_failure) throw std::runtime_error("unexpected adapter failure");
    if (wake_during_storage) sleeping = false;
    return storage;
  }
  void request_sleep() { calls.push_back("sleep"); }
  bool prepare_external_storage() {
    calls.push_back("prepare");
    if (unexpected_failure) throw std::runtime_error("unexpected preparation failure");
    if (wake_during_storage) sleeping = false;
    return storage == hct::StoragePreparation::completed;
  }
};
}

int main() {
  for (auto storage : {hct::StoragePreparation::completed,
                       hct::StoragePreparation::handled_failure}) {
    Adapter normal;
    normal.storage = storage;
    check(hct::experimental_prepare_sleep(normal) == hct::SleepPreparation::requested,
          "normal/handled storage result changed sleep request");
    check(normal.calls == std::vector<std::string>{"state", "start", "hctall", "end", "state", "sleep"},
          "manager call ordering changed");
    Adapter waking;
    waking.storage = storage;
    waking.wake_during_storage = true;
    check(hct::experimental_prepare_sleep(waking) == hct::SleepPreparation::cancelled,
          "wake during storage did not cancel sleep");
    check(waking.calls == std::vector<std::string>{"state", "start", "hctall", "end", "state"},
          "wake cancellation lost report or requested sleep");
  }
  Adapter awake;
  awake.sleeping = false;
  check(hct::experimental_prepare_sleep(awake) == hct::SleepPreparation::skipped &&
        awake.calls == std::vector<std::string>{"state"}, "awake state performed work");
  Adapter broken;
  broken.unexpected_failure = true;
  bool threw = false;
  try { hct::experimental_prepare_sleep(broken); }
  catch (const std::runtime_error&) { threw = true; }
  check(threw && broken.calls == std::vector<std::string>{"state", "start", "hctall"},
        "unexpected failure was treated as a handled storage exception");
  for (bool prepared : {false, true}) {
    Adapter ack;
    ack.storage = prepared ? hct::StoragePreparation::completed : hct::StoragePreparation::handled_failure;
    check(hct::experimental_prepare_acknowledged_sleep(ack) ==
          (prepared ? hct::SleepPreparation::requested : hct::SleepPreparation::storage_failed),
          "acknowledged policy slept after failure or blocked successful preparation");
    check(ack.calls == (prepared ? std::vector<std::string>{"state","prepare","state","sleep"}
                                : std::vector<std::string>{"state","prepare","state"}),
          "acknowledged call order changed");
    ack.calls.clear(); ack.wake_during_storage=true;
    check(hct::experimental_prepare_acknowledged_sleep(ack) == hct::SleepPreparation::cancelled &&
          ack.calls == std::vector<std::string>{"state","prepare","state"},
          "wake did not cancel acknowledged sleep");
  }
  Adapter ack_awake; ack_awake.sleeping=false;
  check(hct::experimental_prepare_acknowledged_sleep(ack_awake) == hct::SleepPreparation::skipped &&
        ack_awake.calls == std::vector<std::string>{"state"}, "awake acknowledged policy did work");
  Adapter ack_broken; ack_broken.unexpected_failure=true; threw=false;
  try { hct::experimental_prepare_acknowledged_sleep(ack_broken); }
  catch (const std::runtime_error&) { threw=true; }
  check(threw && ack_broken.calls == std::vector<std::string>{"state","prepare"},
        "unexpected acknowledged preparation failure requested sleep");
  std::cout << "Sleep preparation ordering and wake cancellation passed; fake adapters only.\n";
}
