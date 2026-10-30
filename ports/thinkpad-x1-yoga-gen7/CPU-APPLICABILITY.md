# CPU compatibility: ThinkPad X1 Yoga Gen 7

Target: Core i7-1265U, Alder Lake-U, 2 P-cores + 8 E-cores, 12 logical processors.

## CPU settings in both Yoga templates

| Setting | Current value | Reason and confidence |
|---|---|---|
| `Kernel -> Emulate -> Cpuid1Data` | `55060A00 00008000 00000000 00000000` | Replaces CPUID leaf 1 EAX with Comet Lake signature `0x000A0655`. OpenCore's Alder Lake recipe uses this EAX replacement. Intel lists the closely related i7-1265UL 2+8 SKU as CPUID `0x906A4`; the Yoga's exact CPUID has not been read from Linux yet. OpenCore's example lists `0x90672`, but this config masks all four EAX bytes, so the replacement does not depend on that source signature. |
| `Kernel -> Emulate -> Cpuid1Mask` | `FFFFFFFF 0000FF00 00000000 00000000` | Applies the EAX spoof and sets EBX[23:16] to `0x80`. This workaround was confirmed on the donor i7-1360P and independently on a ThinkPad X1 Carbon Gen 11 i7-1355U with the same 2P+8E / 12-thread topology. The Carbon report says the setting transfers unchanged and all 12 threads work. That is strong same-topology evidence, though not an exact Yoga i7-1265U test. Keep it enabled unless a CPU-specific failure points here. |
| `Kernel -> Quirks -> ProvideCurrentCpuInfo` | `true` | OpenCore added Alder Lake support for this quirk in 0.7.7. It is needed for current P/E core information to be passed through to XNU; the Yoga uses OpenCore 1.0.8. |
| `Kernel -> Quirks -> AppleXcpmCfgLock` | `true` | The Yoga's Linux MSR read was `0x74008008`, with bit 15 set, indicating CFG Lock. This quirk stops XNU's XCPM path from writing locked MSR `0xE2`. |
| `Kernel -> Quirks -> AppleCpuPmCfgLock` | `false` | This targets legacy `AppleIntelCPUPowerManagement.kext`, which Apple removed starting in macOS 13. Tahoe's relevant setting here is `AppleXcpmCfgLock`. |
| `AppleXcpmExtraMsrs`, `AppleXcpmForceBoost` | `false` | Neither is an Alder Lake boot requirement. `ForceBoost` forces maximum performance continuously and is inappropriate for this laptop. |
| `cpus=1` | absent | A diagnostic restriction, not a compatibility patch. It hides the multicore path and should not be used as the normal installer configuration. |

OpenCore's [official configuration reference](https://raw.githubusercontent.com/acidanthera/OpenCorePkg/master/Docs/Configuration.pdf) gives the Alder Lake-to-Comet Lake EAX spoof `55 06 0A 00`, masks EAX, and documents `ProvideCurrentCpuInfo` as adding asymmetric SMP support for Intel Alder Lake.

## Closest tested ThinkPad CPU evidence

The closest CPU-topology comparison found is the [ThinkPad X1 Carbon Gen 11 Tahoe port](https://github.com/dssoftx/Hackintosh-X1Carbon-G11-IrisXe-Tahoe). It uses an i7-1355U (Raptor Lake-U), also 2P+8E / 12 threads. Its published [stage-1 EFI config](https://github.com/dssoftx/Hackintosh-X1Carbon-G11-IrisXe-Tahoe/blob/main/dist/EFI-stage1/OC/config.plist) has the same CPUID EAX spoof and EBX[23:16]=0x80, `ProvideCurrentCpuInfo=true`, `AppleXcpmCfgLock=true`, and `AppleXcpmExtraMsrs=false`. Its [port changelog](https://github.com/dssoftx/Hackintosh-X1Carbon-G11-IrisXe-Tahoe/blob/main/CHANGELOG-X1C.md) reports all 12 threads working and explicitly says the EBX=128 workaround transfers to the 2P+8E CPU. The Carbon's stage-1 config also uses `SetupVirtualMap=true`; the current Yoga USB already has that setting.

This is not an exact Alder Lake i7-1265U test, but it is stronger evidence for retaining the EBX byte than the Dell-only evidence available before. The current Yoga USB's CPU and boot settings now match that working 2P+8E ThinkPad pattern. Do not switch to the EAX-only test profile for the next installer attempt.

A separate ThinkPad Yoga 82UT report uses an i7-12700H (8P+8E), so its topology is different. A community report mentions Tahoe graphics acceleration on a Dell Latitude 7430 with the same i7-1265U and GPU `8086:46A8`, but it does not publish a CPU config. Treat both as secondary evidence, not direct configuration proof.

`config-recovery-eax-only-ab-template.plist` remains available as a diagnostic if a captured CPU-topology panic specifically implicates the EBX workaround. It is not the current recommendation. `CpuTopologyRebuild` and `CpuTscSync` remain out: there is no Yoga panic matching either plugin's purpose.

## Yoga-specific ACPI CPU tables

The private Yoga ACPI capture—not the Dell's DSDT—was used to produce the three AML files in `ACPI/`. See [ACPI/README.md](ACPI/README.md) for source, hashes and static validation.

- `SSDT-PLUG-ALT.aml` supplies the Alder Lake compatibility `Processor()` objects and the Darwin `plugin-type=1` property. This matches the modern `ACPI0007` device style in the Yoga DSDT and the upstream [OpenCore `SSDT-PLUG-ALT` sample](https://github.com/acidanthera/OpenCorePkg/blob/master/Docs/AcpiSamples/Source/SSDT-PLUG-ALT.dsl).
- `SSDT-CPU-STA.aml` hides the unused Yoga firmware CPU placeholders `PR12`–`PR63` only for Darwin. It does not disable the 12 enabled processors.
- The Yoga MADT has 12 enabled processor entries, UIDs 0–11. The disabled `LocalApicId=255` messages for placeholder IDs are expected from the captured firmware table; by themselves they are not evidence of a CPU hang.

These tables compile and round-trip through iASL, and the Recovery UI was reached once with the Yoga CPU tables loaded. That establishes a viable boot path, not reliable power management. No CPU-specific panic has been established as the cause of the repeated installer restart.

## Optional items and non-fixes

- `CpuTopologyRebuild` is an optional Lilu plugin for presenting hybrid P/E topology differently to macOS. Its maintainer describes the performance effect as uncertain and lists possible verbose-boot failures. It is not required to install; defer it until a stable install and a specific scheduling goal: [project README](https://github.com/b00t0x/CpuTopologyRebuild).
- `CpuTscSync` is not a generic Alder Lake boot requirement. Consider it only if the Yoga produces a matching TSC/non-monotonic-time panic.
- `CPUFriend` and CPUFriendDataProvider are power-profile tools, not generic Alder Lake boot patches. Do not use a Dell/XPS profile on this Yoga.
- Do not copy the donor XPS PL1/PL2, HWP/EPP, or thermal settings without measurements from the Yoga.

## Evidence-based next CPU test

The current live USB has the Alder Lake EAX spoof, EBX[23:16]=0x80, `ProvideCurrentCpuInfo=true`, and `AppleXcpmCfgLock=true`; it reached the Recovery UI on this Yoga. Its CPUID settings also match the tested 2P+8E ThinkPad X1 Carbon Gen 11 stage-1 configuration. The saved Yoga panic instead faults in `AppleUSBXHCIPCI::getAcpiPort`, and no newer panic log is present. Keep the CPU settings unchanged while diagnosing the repeated Installer restart.
