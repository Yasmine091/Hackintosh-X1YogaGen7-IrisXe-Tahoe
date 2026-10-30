# Yoga Gen 7 target-side evidence analysis

The user ran the guarded Linux inventory and firmware exporter on the ThinkPad. The evidence was returned on the 64 GB USB and reviewed on the main PC. Its manifest lists 51 files and no missing captures. Raw ACPI and VBT files are not included in this repository.

## GPU and internal display

- Linux identifies Intel GPU 8086:46A8 at 0000:00:02.0, revision 0C, using i915.
- The captured DSDT places GFX0 below \_SB.PC00 with _ADR=0x00020000, consistent with that PCI function. An OpenCore IORegistry path and macOS driver binding have not been tested.
- i915 reports one available slice, six available subslices, 16 available EUs per subslice, and 96 available EUs total. A separate all-zero enabled-SSEU snapshot was taken while the display pipe was active. Upstream i915 (v6.16-rc1) prints “Available” from its device-info topology, then computes “Enabled” separately by reading slice/subslice/EU power-gating acknowledgement registers under runtime power management. The zero snapshot is therefore a live power-state sample, not fused-topology evidence or proof of an absent GPU; an active display pipe alone does not prove render EUs were enabled at that instant. See [i915 SSEU status implementation](https://codebrowser.dev/linux/linux/drivers/gpu/drm/i915/gt/intel_sseu_debugfs.c.html). Active render topology and L3 bank count remain unresolved.
- The active Linux display is pipe A through DDI/PHY A at 1920×1200, 24 bpp, two eDP lanes, and a 270000 kHz port clock. This is Linux's live state, not proof that Apple's driver can preserve or retrain the Yoga panel.
- PSR is supported by the sink and PSR2 was enabled during capture. DMC firmware i915/adlp_dmc.bin v2.20 loaded in Kubuntu; that does not establish a macOS firmware requirement.
- The VBT export is 9216 bytes, with VBT header version 100 and BDB version 251; its header strings identify ALDERLAKE-P. The 16-entry LFP data table (BDB block 42) contains a generic 1920×1200 timing at panel index 9 (154 MHz pixel clock), but that entry has no AUO PnP ID. The LFP options block sets primary `panel_type=255` (EDID-based selection); neither named PnP entry matches the panel EDID `AUO / D291`. Therefore the dump does not establish that index 9 was selected, nor that its timing is the live panel timing. The eDP block's fast-link fields do not provide a reliable target lane/rate setting. VBT is board-specific display configuration; see [Linux i915 VBT documentation](https://docs.kernel.org/6.13/gpu/i915.html) and the [Linux VBT definitions](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_vbt_defs.h).

The captured live Linux state reports DDI/PHY A, two eDP lanes, a 270 MHz port clock, and 24 bpp. Upstream Linux defines `TRANS_DDI_PORT_WIDTH` in bits 3:1 as `lane_count - 1`; therefore `0x8A000106` encodes four lanes. Its mode field is separate (`TRANS_DDI_MODE_SELECT` in bits 26:24). See [Linux i915 register definitions](https://kernel.googlesource.com/pub/scm/linux/kernel/git/netdev/net-next/+/daaeec235e46b45a0dbd4facfb275cc43022028d/drivers/gpu/drm/i915/display/intel_display_regs.h).

Reachability matters: `hwInitializeCState()` is routed for the TGL framebuffer. Only its `ngreen-dmc=adlp` branch contains the fixed `0x8A000106` Transcoder A value and timing/PPS block; `-ngreenkeepefi` skips that block only when `PIPE_CONF_A` (`0x70008`) bit 31 is set. The argument does not skip the branch's earlier ADL-P DMC, DC-state, power-well, and display-context/TC register writes. `computeLaneCount()` and `setupOptimalLaneCount()` are also routed; for non-TGL CPUs they read `DDI_BUF_CTL_A` and only raise Apple's chosen lane count when the current hardware count is larger. In contrast, the custom `Gen11::hwSetMode()` and `Gen11::allocateDisplayResources()` bodies have no active route request in this checkout; their direct writes are not currently reachable through those hooks. The `kPatchHwRegsNeedUpdateBypass` byte patch is in the `kextG11FB` ICL-fallback load branch, while the documented `-ngreentglwithgfx` setup selects the TGL framebuffer branch. Do not attribute that ICL patch to the normal TGL path. The matching pinned TGL framebuffer binary has now been statically traced; results and limits are below. The captured i915 report gives the live lane count but not raw `TRANS_DDI_FUNC_CTL_A`, `TRANS_DDI_FUNC_CTL_EDP`, or `DDI_BUF_CTL_A` values. The source comments claiming `0x8A000106` is two-lane conflict with Linux's field definitions. Do not enable the generic graphics path for Yoga until the target register state and the fixed initialization writes are reconciled.

### Static trace of the pinned TGL framebuffer binary

The user supplied output from the NootedGreen checkout at commit `95f81898be65cb9f7b3d370ca78054be4cc8a62` (`V212 add`). The selected file is `sle_Internal/le/AppleIntelTGLGraphicsFramebuffer.kext/Contents/MacOS/AppleIntelTGLGraphicsFramebuffer`, a Mach-O x86_64 kext binary with SHA-256 `285ee7a9c3d6c9a9647013f44fb40f312b1cb42879974ef0542544cf049442b5`. Embedded source strings identify Apple GPUDriversIntel 16.0.32. The binary itself is not included in this repository.

Symbol lookup and bounded disassembly with `llvm-nm`/`llvm-objdump` found:

- `AppleIntelBaseController::hwSetMode(...)` at `0x74c1e`. It calls `SetupParams(...)` at `0x74f3d`, then Apple's `hwRegsNeedUpdate(...)` at `0x75028`.
- `AppleIntelBaseController::hwRegsNeedUpdate(...)` at `0x732dc`. When the path is already active, it calls `paramsFbCompare(...)` at `0x7342c`; an inactive path or the driver's force-modeset sysctl instead requests a full modeset. Further clock, mode-validation, colorimetry and pipe-seam checks can also affect the result.
- `AppleIntelBaseController::paramsFbCompare(...)` at `0x736b8` compares CRTC fields including `TRANS_DDI_FUNC_CTL` at offset `+0x4` and `TRANS_CONF` at `+0x2c`, and logs changes to both. These offsets match `src/NootedGreen/AppleIntelParams.hpp`.

This confirms the active TGL hook's scope: `Gen11::hwRegsNeedUpdate()` clears bit 16 in the pending `TRANS_DDI_FUNC_CTL`, replaces pending `TRANS_CONF` with a read of `0x70008`, and then calls Apple's original `hwRegsNeedUpdate()`. It does not bypass that method or write `TRANS_DDI_FUNC_CTL_A` itself. The custom `Gen11::hwSetMode()` body that writes `0x8A000106` is still not routed by the TGL route table. The fixed Transcoder A timing/PPS block is instead inside `hwInitializeCState()`'s `ngreen-dmc=adlp` branch and is skipped only when `-ngreenkeepefi` is present and `PIPE_CONF_A` bit 31 is set. That skip does not suppress the branch's other ADL-P firmware and MMIO writes.

The tracked Dell `EFI/OC/config.plist` currently selects `ngreen-dmc=adlp` and `-ngreenkeepefi`. This describes that Dell experiment, not a validated Yoga setup. The saved Yoga `i915_display_info` text confirms Linux had pipe A enabled at 1920×1200 on two lanes; it is not a raw MMIO register capture and does not establish what the firmware pipe state would be when macOS runs. The user reports `intel_reg` is not installed on the Yoga; do not install it just for this snapshot.

This is static analysis of the pinned binary, not a Yoga hardware test. It establishes neither the live Yoga register contents nor which comparison triggers on that machine, whether macOS will preserve or retrain eDP, or whether the panel and Metal will work. The mismatch is material: Linux reports a two-lane Yoga eDP link, while `0x8A000106` encodes four lanes under the Intel DDI width field. Do not infer that the Yoga should be forced to four lanes.

## ACPI paths

The DSDT/SSDT disassembly identifies these target paths and firmware HID mappings:

| Function | ACPI path | Evidence |
|---|---|---|
| Integrated graphics | \_SB.PC00.GFX0 | _ADR=0x00020000, matches PCI 00:02.0 |
| Synaptics touchpad | \_SB.PC00.I2C0.TPD0 | I2C0 at PCI 00:15.0; firmware HID table includes 06CB:CEB3 / SYNA8016, address 0x2C |
| Wacom pen/touch | \_SB.PC00.I2C1.TPL1 | I2C1 at PCI 00:15.1; firmware HID table includes 056A:5308 / WACF2200, address 0x0A |

The devices use PNP0C50. The firmware's _INI and _CRS methods populate HID and GPIO/interrupt resources dynamically, so the exact runtime interrupt mapping still needs careful review. SSDT10 exposes display children DD1F/DD2F and brightness methods; those methods do not prove macOS brightness control.

## USB paths and captured OpenCore map

Two user-run captures on the Yoga observed a 480 Mbit/s path and a 5000 Mbit/s path on each physical connector. The 5000 Mbit/s probe used a Western Digital storage device (`1058:25A2`); this proves the negotiated rate for that device/cable, not the maximum port rate.

| User label | USB 2 observation | 5 Gbit/s observation |
|---|---|---|
| USB-A-LEFT | bus 3, `3-9`, PCI `0000:00:14.0` | bus 4, `4-1`, PCI `0000:00:14.0` |
| USB-A-RIGHT | bus 3, `3-7`, PCI `0000:00:14.0` | bus 4, `4-2`, PCI `0000:00:14.0` |
| USB-C-LEFT-BOTTOM | bus 3, `3-1`, PCI `0000:00:14.0` | bus 2, `2-1`, PCI `0000:00:0d.0` |
| USB-C-LEFT-TOP-CHARGING | bus 3, `3-3`, PCI `0000:00:14.0` | bus 2, `2-3`, PCI `0000:00:0d.0` |

The user separately confirms both USB-C ports charge the laptop. A follow-up test with the same Western Digital device found the same 5 Gbit/s route in both plug orientations: top port `2-3`, bottom port `2-1`, both through PCI `0000:00:0d.0`. This orientation result is specific to the tested device, cable, and link. The built-in Bluetooth, fingerprint reader, and Intel USB Bridge appeared at `3-10`, `3-6`, and `3-8` respectively, each at 12 Mbit/s. These observed paths have been converted into `Kexts/UTBMap.kext`, with entries for PCH XHCI `8086:51ED` (USB-A, USB-C USB2, fingerprint reader, Intel bridge, and Bluetooth) and Thunderbolt XHCI `8086:461E` (the two USB-C SuperSpeed paths). This map is based on Linux enumeration and has not been validated by macOS. USB-C traffic through PCI `0000:00:0d.0` does not establish Thunderbolt/USB4 PCIe tunneling topology; that remains uncaptured.

## Captured kernel panic: XHCI ACPI-port lookup

The USB contained four `panic-*.txt` files, but they are byte-for-byte copies of one panic report (same SHA-256), not four distinct failures. The report shows a null page fault (`CR2=0`) in `AppleUSBXHCIPCI::getAcpiPort`, called from `AppleUSBXHCIPCI::createPort` and `AppleUSBXHCI::createPorts`. It is direct evidence of an early Apple XHCI/ACPI port-creation crash; it does not identify which of the two XHCI controllers caused it and does not implicate CPU topology. Its recorded boot arguments include the old `debug=0x14e` and `cpus=1` values, so it does not describe the current USB config, whose boot arguments omit both. The latest OpenCore trace on the USB is from Oct 29 at 21:38 and ends at `EXITBS:START`, the handoff to macOS; there is no later kernel panic report to establish whether the current XHCI A/B changed the crash.

The current Recovery config has `ApplePanic=True`, `USBToolBox` and the mapped Yoga `UTBMap` enabled, and `XHCI-unsupported` disabled. The [USBToolBox documentation](https://github.com/USBToolBox/kext#configuration) describes `-utbacpioff` as disabling its removal of RHUB from the ACPI plane. A separate recovery template, `config-recovery-utbacpioff-template.plist`, adds only this boot argument. It keeps the captured port map and all kext settings unchanged, to test whether retaining the ACPI RHUB avoids the null ACPI-port lookup. The resulting local EFI passed OpenCore 1.0.8 `ocvalidate`; this is static validation only, and the USB has not been modified or boot-tested with this argument.

## Safe next work

1. Determine how Linux selected the active panel despite the VBT's EDID-based primary type and missing AUO PnP match; capture the live firmware panel type if it can be obtained safely. Keep the VBT binary private.
2. Raw register values remain optional follow-up evidence: `intel_reg` is absent on the Yoga, while the already-captured i915 report establishes the active Linux lane count. Do not install a tool just for this. If a reviewed read-only capture method becomes available later, collect `TRANS_DDI_FUNC_CTL_A` (`0x60400`), `DDI_BUF_CTL_A` (`0x64000`), `TRANS_DDI_FUNC_CTL_EDP` (`0x6f400`), and `PIPE_CONF_A` (`0x70008`). Keep the generic path out of any Yoga EFI until a Yoga-specific, reversible path is justified. `-ngreenkeepefi` skips only the Transcoder A timing/PPS block in the `ngreen-dmc=adlp` branch when pipe A is active; it does not suppress that branch's other writes or establish what Apple's later TGL modesetting will do.
3. Resolve the available-versus-enabled topology reporting and identify what the Tiger Lake driver expects before changing EU/L3 overrides.
4. Validate the captured USB map in macOS; finish Yoga I2C/GPIO resource analysis and inspect Thunderbolt separately.
5. Only then generate separate recovery and acceleration configurations. No installer, EFI generation, or internal-disk operation is part of this evidence-analysis step.

For item 2, if `intel_reg` is already installed on Kubuntu, the narrow capture command is `sudo intel_reg read 0x60400 0x64000 0x6f400 0x70008`. This uses the tool's `read` operation only; do not substitute `write` or a broad `dump`. The tool documentation notes that some register reads can hang a GPU or machine, so do not install anything or proceed if the tool reports an unsupported device or register. See the [intel_reg manual](https://manpages.debian.org/trixie/intel-gpu-tools/intel_reg.1.en.html).
