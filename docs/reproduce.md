# Reproducing the static analysis

Supply firmware you are authorized to inspect locally. This repository intentionally does not redistribute firmware or provide a flashing workflow.

1. Verify the original download against the archive hashes in firmware-baseline.md.
2. Extract the actual OTA update.zip. These RAR files contain stored ZIPs, and some readers select an embedded ZIP instead of the RAR container. Force RAR5 mode with a compatible archive reader when inventorying outer entries.
3. Validate OTA ZIP CRCs and payload_properties.txt hashes. Decode payload.bin with an appropriate A/B payload extractor and compare every reconstructed partition's SHA-256 with its manifest entry.
4. Extract the system partition into a local ignored directory such as `work/factory/system`. A system-as-root image may contain another `system/` subdirectory; use the directory containing framework/, app/ and priv-app/ as the input below.
5. Run the original table-reading tool (Python standard library only):

```sh
python3 scripts/dex_inventory.py work/factory/system work/factory/dex-tables
python3 scripts/hct_summary.py work/factory/dex-tables work/factory/hct-summary.json
```

The first tool reads DEX string/type/method/class tables without executing the APK or JAR. It reports ZIP entry CRC status and supports reading a modified entry with a stale CRC. It does not treat a mismatching CRC as successful validation. Its raw local JSON includes arbitrary firmware strings and must stay in work/; publish only reviewed scoped summaries. Duplicate basenames in a scan are rejected so results are not silently overwritten.

The second tool scopes the output to Microntek framework definitions, native declarations, and app references, and records source CRC status. Method references establish static dependencies, not execution or a complete call graph. Compiler-generated accessor differences should be separated from meaningful API changes when comparing builds.

APK manifests and certificate relationships were independently inspected with Androguard 4.1.4. Native ELF exports and DT_NEEDED entries were inspected using readelf; relevant device paths were checked using strings and factory init configuration. Firmware executables were not run.

Selected Java instruction paths were inspected with Androguard after omitting the hidden-API metadata map entry in an **in-memory analysis copy** and recomputing that copy's DEX checksums. This worked around Androguard rejecting a hidden-API domain flag. The original files and partition images were not changed. Full decompiled or disassembled implementations are not included in this repository.

The tools expect ordinary unpacked APK/JAR files containing classes*.dex; they do not reconstruct missing DEX from optimized-only OAT/VDEX files, validate the update signing trust chain, or prove boot compatibility. Bounds/malformed-input hardening is limited; use a resource-limited environment for untrusted files.

The optional service Proxy check uses the dependencies in requirements-analysis.txt:

```sh
python3 scripts/recover_proxy_wire.py \
  work/malaysk/system/framework/framework.jar \
  work/malaysk/proxy-wire.json
```

Its output is restricted to the two selected HCT Proxy classes, method signatures, constant transaction arguments and Parcel method names. It preserves original CRC results and uses the same in-memory hidden-API workaround. It does not infer server permissions, callback Bundle schemas or message equivalence on a different Android release.
