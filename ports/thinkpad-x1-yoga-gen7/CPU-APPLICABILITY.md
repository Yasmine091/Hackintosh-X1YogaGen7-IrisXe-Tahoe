# CPU compatibility: ThinkPad X1 Yoga Gen 7

Target: Core i7-1265U, Alder Lake-U, 2 P-cores + 8 E-cores, 12 logical processors.

## CPU settings in both Yoga templates

| Setting | Current value | Reason and confidence |
|---|---|---|
| `Kernel -> Emulate -> Cpuid1Data` | `55060A00 00008000 00000000 00000000` | Replaces CPUID leaf 1 EAX with Comet Lake signature `0x000A0655`. OpenCore's Alder Lake recipe uses this EAX replacement. Intel lists the closely related i7-1265UL 2+8 SKU as CPUID `0x906A4`; the Yoga's exact CPUID has not been read from Linux yet. OpenCore's example lists `0x90672`, but this config masks all four EAX bytes, so the replacement does not depend on that source signature. |
| `Kernel -> Emulate -> Cpuid1Mask` | `FFFFFFFF 0000FF00 00000000 00000000` | Applies the EAX spoof and sets only EBX bits 23:16 to `0x80`. The EBX override is the repository's fix for a divide-by-zero in XNU's hybrid-core initialization when `ProvideCurrentCpuInfo` reports 128 logical processors/package but the CPU reports a smaller count. It is proven on the donor i7-1360P, not this exact i7-1265U. Keep it as the current candidate; if a CPU-specific panic occurs, test it as a separate A/B change. |
| `Kernel -> Quirks -> ProvideCurrentCpuInfo` | `true` | OpenCore added Alder Lake support for this quirk in 0.7.7. It is needed for current P/E core information to be passed through to XNU; the Yoga uses OpenCore 1.0.8. |
| `Kernel -> Quirks -> AppleXcpmCfgLock` | `true` | The Yoga's Linux MSR read was `0x74008008`, with bit 15 set, indicating CFG Lock. This quirk stops XNU's XCPM path from writing locked MSR `0xE2`. |
| `Kernel -> Quirks -> AppleCpuPmCfgLock` | `false` | This targets legacy `AppleIntelCPUPowerManagement.kext`, which Apple removed starting in macOS 13. Tahoe's relevant setting here is `AppleXcpmCfgLock`. |
| `AppleXcpmExtraMsrs`, `AppleXcpmForceBoost` | `false` | Neither is an Alder Lake boot requirement. `ForceBoost` forces maximum performance continuously and is inappropriate for this laptop. |
| `cpus=1` | absent | A diagnostic restriction, not a compatibility patch. It hides the multicore path and should not be used as the normal installer configuration. |

The current values match the reference repository's Raptor Lake workaround, including the extra EBX byte. The [OpenCore configuration reference](https://dortania.github.io/docs/latest/Configuration.html) documents the Alder Lake recipe: replace CPUID leaf 1 EAX with `55 06 0A 00` and mask only EAX; `ProvideCurrentCpuInfo` supplies asymmetric-core support. OpenCore added that quirk for Alder Lake in its [0.7.7 changelog](https://github.com/acidanthera/OpenCorePkg/blob/master/Changelog.md). Intel's [12th Gen identification table](https://cdrdv2-public.intel.com/743110/743110_Alder%20Lake%20-PS_Public_Specification%20Update_rev1.1.pdf) lists the related 2+8 i7-1265UL as `906A4`; the precise Yoga CPUID should still be read from Linux `cpuid -1` if needed.

## External Alder Lake comparison and reversible CPU A/B

Research on 2026-10-30 found a Lenovo Yoga 82UT running Tahoe 26.7.1 with reported Iris Xe acceleration. Its CPU is an i7-12700H (8P+8E), so it is not the same CPU topology as this 1265U. Its published EFI uses the documented EAX-only CPUID spoof and `ProvideCurrentCpuInfo`. It also includes `CpuTscSync` with a comment tying it to a non-monotonic-time panic. The `CpuTopologyRebuild` entry is marked enabled while its comment says it is disabled for recovery isolation, so that file is not clean evidence for enabling that plugin here. The author says clean installation is untested and GPU hangs/instability remain. See the [Yoga repository and status](https://github.com/willyyypatootieee/Hackintosh-LenovoYoga-IrisXe-Tahoe), plus its [published EFI config](https://github.com/willyyypatootieee/Hackintosh-LenovoYoga-IrisXe-Tahoe/blob/main/EFI/OC/config.plist).

A Reddit report mentions Tahoe graphics acceleration on a Dell Latitude 7430 with the same i7-1265U and GPU `8086:46A8`, but it does not publish a usable CPU configuration. Treat it as a hardware-feasibility lead, not proof of a specific CPU patch: [report](https://www.reddit.com/r/hackintosh/comments/1xb2okj/macos_tahoe_running_on_raptor_lake_intel_iris_xe/).

For a controlled CPU comparison, `config-recovery-eax-only-ab-template.plist` is a sanitized copy of the recovery template with only `Cpuid1Data[6]` and `Cpuid1Mask[6]` cleared. It removes the unverified `EBX[23:16]=0x80` override while keeping the EAX spoof, `ProvideCurrentCpuInfo`, Yoga ACPI tables, CFG-lock workaround, and all device settings unchanged. It is an experiment, not a known-good replacement. To stage it without writing to a disk or USB, pass it to `tools/build-recovery-efi.py` with `--template` and a new `--output` directory. Keep the active USB config as the control and compare using the same OpenCore version and same Installer entry.

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

Do not change CPU settings just because verbose output ends near `CoreAnalyticsHub`. A prior boot reached Recovery, and the available panic evidence points to `AppleUSBXHCIPCI::getAcpiPort`, not XNU CPU topology. A CPU A/B is available if we specifically want to rule out the donor-only EBX override: back up the active config, use the EAX-only template for one boot with the same Installer entry, and capture the full log/panic. Restore the control after that single comparison if it does not change the result. Do not combine this with USB, ACPI, or graphics changes.
