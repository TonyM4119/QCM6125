#include "deferred_controls.hpp"
#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
void check(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
}
int main() {
  hct::DeferredControls queue;
  queue.request_eq(2, 100);
  queue.request_loudness(true, 100);
  queue.request_video_speed(true, 100);
  check(queue.pending_count() == 3 && queue.take_due(109).empty(), "control ran too early");
  queue.request_eq(6, 109); // Replace only EQ, due now at 119.
  auto due = queue.take_due(110);
  check(due.size() == 1 && due[0].what == 1 && due[0].arg1 == 1,
        "EQ replacement cancelled unrelated loudness message");
  check(queue.take_due(118).empty(), "replacement kept obsolete due time");
  due = queue.take_due(119);
  check(due.size() == 1 && due[0].what == 0 && due[0].arg1 == 6,
        "superseded EQ message was delivered");
  queue.request_video_speed(false, 149);
  check(queue.take_due(150).empty(), "replaced video status ran at obsolete deadline");
  due = queue.take_due(199);
  check(due.size() == 1 && due[0].what == 2 && due[0].boolean_object == false,
        "video status coalescing lost false object value");
  check(queue.take_due(199).empty() && queue.pending_count() == 0,
        "drained controls delivered twice");

  queue.request_loudness(false, 200);
  queue.request_eq(-9, 200);
  due = queue.take_due(210);
  check(due.size() == 2 && due[0].what == 1 && due[1].what == 0 && due[1].arg1 == -9,
        "equal-deadline insertion order or raw EQ request changed");
  bool backwards = false;
  try { queue.request_eq(0, 209); } catch (const std::invalid_argument&) { backwards = true; }
  check(backwards && queue.pending_count() == 0, "backwards time mutated queue");

  queue.request_loudness(true, 220);
  bool overflow = false;
  try { queue.request_loudness(false, std::numeric_limits<std::uint64_t>::max()); }
  catch (const std::overflow_error&) { overflow = true; }
  check(overflow && queue.pending_count() == 1, "overflow cancelled pending request");
  due = queue.take_due(230);
  check(due.size() == 1 && due[0].arg1 == 1, "failed schedule changed time or prior value");

  // A stalled fake dispatcher need not run overdue work before cancellation.
  queue.request_eq(1, 300);
  queue.request_eq(4, 400);
  check(queue.take_due(409).empty(), "cancelled overdue message survived");
  due = queue.take_due(410);
  check(due.size() == 1 && due[0].arg1 == 4, "latest EQ request was not retained");
  std::cout << "Deferred replacement, timing boundaries and queue ordering checks passed; fake time only.\n";
}
