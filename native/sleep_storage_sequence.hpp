#pragma once

namespace hct {
// Portable model of the reviewed manager sequence, not an Android adapter.
// The adapter must map only the reviewed handled storage failures to
// handled_failure. Unexpected exceptions propagate and stop this sequence.
enum class StoragePreparation { completed, handled_failure };
enum class SleepPreparation { skipped, cancelled, requested, storage_failed };

// Caller provides serialized invocation. Power reads must observe current state.
// Storage completion does not prove disks are safe or that suspend succeeded.
template <typename Adapter>
SleepPreparation experimental_prepare_sleep(Adapter& adapter) {
  if (!adapter.is_sleep()) return SleepPreparation::skipped;
  adapter.report_media_safe_mounted("start");
  // Both normal completion and handled storage failure continue to the end
  // report and fresh state check, matching the recovered manager behaviour.
  const StoragePreparation storage = adapter.unmount_hctall();
  (void)storage;
  adapter.report_media_safe_mounted("end");
  if (!adapter.is_sleep()) return SleepPreparation::cancelled;
  adapter.request_sleep();
  return SleepPreparation::requested;
}

// New coordinator policy, not a reconstruction of legacy manager error handling.
// Adapter must use the explicit boolean preparation API, never infer success from
// void unmount returning. MCU reporting is deliberately outside this model.
template <typename Adapter>
SleepPreparation experimental_prepare_acknowledged_sleep(Adapter& adapter) {
  if (!adapter.is_sleep()) return SleepPreparation::skipped;
  const bool prepared = adapter.prepare_external_storage();
  if (!adapter.is_sleep()) return SleepPreparation::cancelled;
  if (!prepared) return SleepPreparation::storage_failed;
  adapter.request_sleep();
  return SleepPreparation::requested;
}
}  // namespace hct
