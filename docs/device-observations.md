# Owner-provided device observations

These facts were transcribed from the supplied Device Info HW photos. They are app-reported observations, not measurements performed by this project or proof of firmware authenticity. Raw photos are not published in the repository.

| Field | Reported value |
| --- | --- |
| Device / manufacturer label | Doro QCM6125 / Doro |
| Product / build | S10A / S10A_123 |
| Board / platform | trinket |
| Release / API / codename | Android 13 / 33 / Tiramisu |
| Incremental build | eng.hct.20250106.173227 |
| Build date | January 6, 2025, consistent with incremental build |
| Kernel | 4.14.190, #369, January 6, 2025 |
| Build type / tags | userdebug / release-keys |
| Declared security patch | 2022-08-05 |
| SELinux reported mode | Permissive |
| SoC app identification | Snapdragon 665, Qualcomm, 8 cores |
| Architecture | aarch64 / arm64-v8a; 32-bit ARM ABIs also listed |
| GPU app identification | Adreno 610 |
| RAM | 8 GB LPDDR4X |
| Display | 1280x720, 16:9, 60 Hz |
| Logical density | 160 dpi (mdpi) |
| Android-reported RAM total | 7,673 MiB |
| Shared-storage filesystem total | 227.44 GiB, consistent with nominal 256 GB storage |
| Touchscreen label | goodix-ts |
| Wi-Fi label | soc:wcn3990 |

The manufacturer string Doro is a software identity here and does not contradict the XTRONS sales branding. These observations support the HCT trinket/QCM6125 family already identified from the supplied binaries. They do not make Xiaomi ginkgo board files a suitable replacement for HCT board support.

## Firmware identity distinction

Four builds now need to be kept separate:

1. November 2022 XTRONS factory candidate, Android 12/API 31, kernel #48: locally inspected archive; owner confirms this package did not work on the unit. Excluded as a porting base.
2. July 2023 factory firmware, displayed Android 12, kernel #103: earlier owner photos.
3. March 2024 Malaysk reference, Android 13/API 33, kernel #247: locally inspected archive and owner-reported successful prior test.
4. January 2025 build, reported Android 13/API 33, kernel #369: newly supplied Device Info HW photos only.

The owner confirmed that build 4 is currently installed. The photos do not establish which firmware provider supplied it or whether every function works on it. The earlier description of Android 12 as the current installation is superseded by this confirmation. The new build's kernel and incremental identifiers differ from both inspected archives. A matching archive has not yet been supplied or analysed.

## Porting implications

- Later Memory-tab photos report 7,673 MiB RAM and 227.44 GiB shared-storage capacity, consistent with an 8 GB/256 GB unit. The latter is a filesystem capacity, not a physical disk or partition-table measurement. The failed 6+128 package remains a different advertised variant, but capacity differences alone do not establish the reason it failed.
- API 33 is stronger version evidence than a product listing, but the running framework has not been independently inspected. A displayed release/API can be altered by firmware vendors.
- A matching January 2025 archive, if available, would be preferable for analysing the currently working integration; its supplier/stock status is unknown. The 2022 factory candidate is excluded as a base. That would require inspecting the archive, not substituting assumptions from the photos.
- This does not change the recovered 2022 native ABI or validate it against the January 2025 driver. Existing transport tests remain host-only and hardware compatibility remains untested.
- None of these photos establish bootloader unlock state, AVB enforcement, partition sizes, precise peripheral wiring or Android 14+ compatibility. No device modifications are implied or requested.

The Screen-tab physical size/DPI estimates are internally inconsistent, so they are not treated as panel dimensions. Logical density and display mode remain app-reported values.
