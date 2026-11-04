# Compiled device-tree declarations

Read-only comparison of boot/dtbo images from the owner-tested Malaysk reference and the owner-reported failed XTRONS package. The failed package remains excluded as a porting base. No overlays were applied, no DTS/DTB was changed and no device was accessed.

## Containers and shared identifiers

Both boot images use header version 2 and 4096-byte pages. Their declared DTB sections contain two concatenated FDT blobs, not just one. The first contains the board declarations; the 173-byte second blob has no whitelisted model/compatible/board-ID fields and is not interpreted further here. The profiler preserves both entries rather than silently discarding the latter.

| Item | Working Malaysk reference | Failed XTRONS reference |
| --- | --- | --- |
| Boot DTB section size | 317468 bytes | 316402 bytes |
| First FDT size | 317295 bytes | 316229 bytes |
| Additional FDT size | 173 bytes | 173 bytes |
| DTBO entries | One, id/revision/custom fields all zero | Same |
| Overlay blob size | 143543 bytes | 113580 bytes |
| Model label | Qualcomm Technologies, Inc. TRINKET IOT IDP SoC | Same |
| Compatible | qcom,trinket-iot | Same |
| qcom,msm-id | 467, 0 | Same |
| qcom,board-id | 0, 0 | Same |

These are generic compiled board identifiers, not an exact XTRONS product code or proof that either firmware fits a different unit. The supplied package's RAM/storage label and these IDs cannot establish why it failed.

## HCT interfaces and display path

The overlay declares MTC init, car, virtual-serial, HDMI, camera, DVD and radio nodes, including compatible strings mtc,car, mtc,vs, mtc,radio and mtc-camera. It also declares an ICN6202 node with compatible hct,icn6202 and a panel named "HCT lvds video mode dsi panel". The display label dsi_td4330_truly_vid_display is consistent with the owner's app photo. Those labels exist in both archive overlays.

The working overlay declares 62 panel timing nodes; the failed overlay declares 40. Both already include multiple 1280x720/60 Hz timing declarations. The working overlay adds timing@40 through timing@61, including another 1280x720 timing. This does not reveal which mode the current unit selected, whether timing details beyond width/height/refresh differ, or whether mode selection contributed to the failure. It is not a reason to transplant the failed overlay.

## Touch and camera declarations

Both overlays declare Goodix and FocalTech touchscreen alternatives. The working overlay additionally declares Himax and Jadard alternatives. The owner's app reports goodix-ts; the existence of other nodes does not establish that those controllers are fitted or active. Even an absent status property or a locally enabled node is insufficient without the applied tree, parent status and runtime probing.

The working mtc-init node additionally names mtc,camera_rst and mtc,camera_pwr. Both have similar bridge/display/radio control-property names. GPIO-related cells in these unmerged overlays contain unresolved phandle markers; they are not direct wiring instructions. Controller resolution, flags, overlay fixups and runtime board configuration would need review before using them in a reconstructed device tree.

## Porting implications

The known-working reference's boot/kernel/vendor configuration should stay together during further analysis. A related Xiaomi SoC tree does not provide these HCT bindings and peripherals automatically. Compiled device-tree data can help reconstruct configuration, but it does not supply original driver source or establish newer-kernel compatibility.

No failure diagnosis or new compatibility claim is inferred from this comparison. Bootloader fixups, runtime-selected display profiles, persist/calibration data, driver implementations and the January 2025 installed images remain outside this static comparison.

## Reproduction and checks

With pyfdt 0.3 installed:

```sh
python3 scripts/device_tree_profile.py --boot work/reference/boot.img \
  --dtbo work/reference/dtbo.img --label working_reference \
  --output work/reference/device-tree-profile.json
python3 scripts/device_tree_profile_test.py
```

The profiler supports the reviewed boot-v2/DTBO-v0 layouts, validates container bounds, retains concatenated base blobs and publishes only whitelisted property values. Synthetic tests cover valid extraction, unsupported/truncated headers, overlay bounds, concatenation and invalid FDT sizes. The real source images were also parsed. Reports are evidence/working-device-tree-profile.json and evidence/failed-device-tree-profile.json. Raw trees and full DTS output remain local and ignored.
