# Yoga Gen 7 target-side evidence analysis

The user ran the guarded Linux inventory and firmware exporter on the ThinkPad. The evidence was returned on the 64 GB USB and reviewed on the main PC. Its manifest lists 51 files and no missing captures. Raw ACPI and VBT files are not included in this repository.

## GPU and internal display

- Linux identifies Intel GPU 8086:46A8 at 0000:00:02.0, revision 0C, using i915.
- The captured DSDT places GFX0 below \_SB.PC00 with _ADR=0x00020000, consistent with that PCI function. An OpenCore IORegistry path and macOS driver binding have not been tested.
- i915 reports one available slice, six available subslices, 16 available EUs per subslice, and 96 available EUs total. A separate all-zero enabled-SSEU snapshot was taken while the display pipe was active. It is not evidence of fused topology or an absent GPU. Active render topology and L3 bank count remain unresolved.
- The active Linux display is pipe A through DDI/PHY A at 1920×1200, 24 bpp, two eDP lanes, and a 270000 kHz port clock. This is Linux's live state, not proof that Apple's driver can preserve or retrain the Yoga panel.
- PSR is supported by the sink and PSR2 was enabled during capture. DMC firmware i915/adlp_dmc.bin v2.20 loaded in Kubuntu; that does not establish a macOS firmware requirement.
- The VBT export is 9216 bytes, with VBT header version 100 and BDB version 251; its header strings identify ALDERLAKE-P. The 16-entry LFP data table (BDB block 42) contains a generic 1920×1200 timing at panel index 9 (154 MHz pixel clock), but that entry has no AUO PnP ID. The LFP options block sets primary `panel_type=255` (EDID-based selection); neither named PnP entry matches the panel EDID `AUO / D291`. Therefore the dump does not establish that index 9 was selected, nor that its timing is the live panel timing. The eDP block's fast-link fields do not provide a reliable target lane/rate setting. VBT is board-specific display configuration; see [Linux i915 VBT documentation](https://docs.kernel.org/6.13/gpu/i915.html) and the [Linux VBT definitions](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_vbt_defs.h).

The captured live Linux state reports DDI/PHY A, two eDP lanes, a 270 MHz port clock, and 24 bpp. Upstream Linux defines `TRANS_DDI_PORT_WIDTH` in bits 3:1 as `lane_count - 1`; therefore `0x8A000106` encodes four lanes. Its mode field is separate (`TRANS_DDI_MODE_SELECT` in bits 26:24). See [Linux i915 register definitions](https://kernel.googlesource.com/pub/scm/linux/kernel/git/netdev/net-next/+/daaeec235e46b45a0dbd4facfb275cc43022028d/drivers/gpu/drm/i915/display/intel_display_regs.h).

Reachability matters: `hwInitializeCState()` is routed for the TGL framebuffer and writes `0x8A000106` plus fixed timing/panel values unless `-ngreenkeepefi` is set and pipe A is already enabled. `computeLaneCount()` and `setupOptimalLaneCount()` are also routed; for non-TGL CPUs they read `DDI_BUF_CTL_A` and only raise Apple's chosen lane count when the current hardware count is larger. In contrast, the custom `Gen11::hwSetMode()` and `Gen11::allocateDisplayResources()` bodies have no active route request in this checkout; their direct writes are not currently reachable through those hooks. The `kPatchHwRegsNeedUpdateBypass` byte patch is in the `kextG11FB` ICL-fallback load branch, while the documented `-ngreentglwithgfx` setup selects the TGL framebuffer branch. Do not attribute that ICL patch to the normal TGL path. The TGL branch routes `Gen11::hwRegsNeedUpdate()`, which adjusts some pending CRTC fields on non-TGL CPUs and then calls Apple's original implementation. Its exact branch behavior and resulting register values remain unverified against the loaded TGL framebuffer binary. The captured i915 report gives the live lane count but not raw `TRANS_DDI_FUNC_CTL_A`, `TRANS_DDI_FUNC_CTL_EDP`, or `DDI_BUF_CTL_A` values. The source comments claiming `0x8A000106` is two-lane conflict with Linux's field definitions. Do not enable the generic graphics path for Yoga until the active modeset path and its register state are reconciled.

## ACPI paths

The DSDT/SSDT disassembly identifies these target paths and firmware HID mappings:

| Function | ACPI path | Evidence |
|---|---|---|
| Integrated graphics | \_SB.PC00.GFX0 | _ADR=0x00020000, matches PCI 00:02.0 |
| Synaptics touchpad | \_SB.PC00.I2C0.TPD0 | I2C0 at PCI 00:15.0; firmware HID table includes 06CB:CEB3 / SYNA8016, address 0x2C |
| Wacom pen/touch | \_SB.PC00.I2C1.TPL1 | I2C1 at PCI 00:15.1; firmware HID table includes 056A:5308 / WACF2200, address 0x0A |

The devices use PNP0C50. The firmware's _INI and _CRS methods populate HID and GPIO/interrupt resources dynamically, so the exact runtime interrupt mapping still needs careful review. SSDT10 exposes display children DD1F/DD2F and brightness methods; those methods do not prove macOS brightness control.

## USB paths (Linux observations; OpenCore map pending)

Two user-run captures on the Yoga observed a 480 Mbit/s path and a 5000 Mbit/s path on each physical connector. The 5000 Mbit/s probe used a Western Digital storage device (`1058:25A2`); this proves the negotiated rate for that device/cable, not the maximum port rate.

| User label | USB 2 observation | 5 Gbit/s observation |
|---|---|---|
| USB-A-LEFT | bus 3, `3-9`, PCI `0000:00:14.0` | bus 4, `4-1`, PCI `0000:00:14.0` |
| USB-A-RIGHT | bus 3, `3-7`, PCI `0000:00:14.0` | bus 4, `4-2`, PCI `0000:00:14.0` |
| USB-C-LEFT-BOTTOM | bus 3, `3-1`, PCI `0000:00:14.0` | bus 2, `2-1`, PCI `0000:00:0d.0` |
| USB-C-LEFT-TOP-CHARGING | bus 3, `3-3`, PCI `0000:00:14.0` | bus 2, `2-3`, PCI `0000:00:0d.0` |

The user separately confirms both USB-C ports charge the laptop. A follow-up test with the same Western Digital device found the same 5 Gbit/s route in both plug orientations: top port `2-3`, bottom port `2-1`, both through PCI `0000:00:0d.0`. This orientation result is specific to the tested device, cable, and link. The built-in Bluetooth, fingerprint reader, and Intel USB Bridge appeared at `3-10`, `3-6`, and `3-8` respectively, each at 12 Mbit/s. These Linux paths are evidence for a later map, not an OpenCore USB map. The appearance of USB-C traffic through PCI `0000:00:0d.0` does not establish Thunderbolt/USB4 PCIe topology; that remains uncaptured.

## Safe next work

1. Determine how Linux selected the active panel despite the VBT's EDID-based primary type and missing AUO PnP match; capture the live firmware panel type if it can be obtained safely. Keep the VBT binary private.
2. Resolve which transcoder/register Apple will use for the Yoga eDP link and how the TGL branch's original mode-setting logic behaves after `Gen11::hwRegsNeedUpdate()` edits CRTC parameters. The `JE→JMP` patch is scoped to the ICL fallback, not the documented TGL setup. `-ngreenkeepefi` only skips the initial fixed timing block when pipe A is active; it does not by itself establish what Apple's TGL modesetting will write. Keep the generic path out of any Yoga EFI until a Yoga-specific, reversible path is justified.
3. Resolve the available-versus-enabled topology reporting and identify what the Tiger Lake driver expects before changing EU/L3 overrides.
4. Finish Yoga I2C/GPIO resource analysis; derive the OpenCore USB map from the captured paths and inspect Thunderbolt separately.
5. Only then generate separate recovery and acceleration configurations. No installer, EFI generation, or internal-disk operation is part of this evidence-analysis step.
