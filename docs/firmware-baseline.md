# Inspected firmware

| Item | Factory candidate | Malaysk Lite reference |
| --- | --- | --- |
| Filename identity | XTRONS IQ/IQP 6+128 Android 12, OTA 20221115 | Malay Mod Lite 1.0 QCM6125 MCU MTCH Android 13 |
| OTA target | QCM6125 / S10A_123 | QCM6125 / S10A_123 |
| Framework | Android 12 / API 31 | Android 13 / API 33 |
| Vendor | Android 11 / API 30 | Android 11 / API 30 |
| Kernel | 4.14.190 #48, November 2022 | 4.14.190 #247, March 2024 |
| System / vendor declared patches | 2021-10-05 / 2021-09-05 | 2022-08-05 / 2021-09-05 |
| OTA type | Full virtual A/B, dynamic partitions | Full virtual A/B, dynamic partitions |
| Reconstructed partition checks | 10/10 SHA-256 match | 11/11 SHA-256 match |

Factory original RAR SHA-256: `c5e9462302eb05f2a620d8befea18426f10eed66547b3380b6dafc0683f23f97`.

Factory OTA ZIP SHA-256: `7ddb3bdfe90ba4c523bd40c7627e66d3583938356d83291869201d8a484f39d9`.

Malaysk original RAR SHA-256: `5156399c1ddc6783aea19c10c29b555bc6fef508ec773eab99b77369aaf7f597`.

Both OTA ZIPs pass their ZIP CRC checks; payload hashes match payload_properties.txt. Factory framework.jar passes its internal ZIP CRC check. Malaysk framework.jar has an internal classes.dex CRC mismatch even though its containing system partition matches the manifest hash. The original modified entry was read for static table comparison; the mismatch is not represented as successful ZIP validation.

Both payloads include boot, dtbo, product, recovery, system, system_ext, vbmeta, vbmeta_system, vendor and xbl. Malaysk additionally includes devcfg. xbl is a Qualcomm bootloader component; these are not merely app updates. No separately named MCU update appears in either payload partition list. These observations do not exclude MCU resources somewhere inside a filesystem.

The user reports that Malaysk was previously tested on the actual unit with all functions working; it is not the current installation. The current photographed installation is July 2023 factory firmware (#103). The older supplied factory candidate is therefore a reference, not an exact backup of the installed version. No additional live-device verification was performed.
