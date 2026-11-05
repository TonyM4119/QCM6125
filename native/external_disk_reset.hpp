#pragma once

namespace hct {
// Experimental source-correlated reconstruction of the reviewed native loop.
// This is not wired into Android/vold or the offline service core. It must not
// be used on a device before the remaining native/platform review is complete.
// DiskRange must hold non-null pointer-like objects with getFlags(), destroy()
// and create(). Caller owns authorization, locking and object lifetime.
template <typename DiskRange>
int experimental_reset_external_disks(const DiskRange& disks) {
  constexpr unsigned sd_or_usb = 0x0c;
  for (const auto& disk : disks) {
    if ((static_cast<unsigned>(disk->getFlags()) & sd_or_usb) == 0) continue;
    disk->destroy();
    disk->create();
  }
  // Matches the reviewed loop's normal return and ignored callee results.
  // Exceptions are not caught here; this is not an error-recovery policy.
  return 0;
}
}  // namespace hct
