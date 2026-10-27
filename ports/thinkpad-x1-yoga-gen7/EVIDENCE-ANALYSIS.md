# Yoga Gen 7 target-side evidence analysis

The user ran the guarded Linux inventory and firmware exporter on the ThinkPad. The evidence was returned on the 64 GB USB and reviewed on the main PC. Its manifest lists 51 files and no missing captures. Raw ACPI and VBT files are not included in this repository.

## GPU and internal display

- Linux identifies Intel GPU 8086:46A8 at 0000:00:02.0, revision 0C, using i915.
- The captured DSDT places GFX0 below \_SB.PC00 with _ADR=0x00020000, consistent with that PCI function. An OpenCore IORegistry path and macOS driver binding have not been tested.
- i915 reports one available slice, six available subslices, 16 available EUs per subslice, and 96 available EUs total. A separate all-zero enabled-SSEU snapshot was taken while the display pipe was active. It is not evidence of fused topology or an absent GPU. Active render topology and L3 bank count remain unresolved.
- The active Linux display is pipe A through DDI/PHY A at 1920×1200, 24 bpp, two eDP lanes, and a 270000 kHz port clock. This is Linux's live state, not proof that Apple's driver can preserve or retrain the Yoga panel.
- PSR is supported by the sink and PSR2 was enabled during capture. DMC firmware i915/adlp_dmc.bin v2.20 loaded in Kubuntu; that does not establish a macOS firmware requirement.
- The VBT export is 9216 bytes, with VBT header version 100 and BDB version 251; its header strings identify ALDERLAKE-P. The 16-entry LFP data table (BDB block 42) contains a generic 1920×1200 timing at panel index 9 (154 MHz pixel clock), but that entry has no AUO PnP ID. The LFP options block sets primary `panel_type=255` (EDID-based selection); neither named PnP entry matches the panel EDID `AUO / D291`. Therefore the dump does not establish that index 9 was selected, nor that its timing is the live panel timing. The eDP block's fast-link fields do not provide a reliable target lane/rate setting. VBT is board-specific display configuration; see [Linux i915 VBT documentation](https://docs.kernel.org/6.13/gpu/i915.html) and the [Linux VBT definitions](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_vbt_defs.h).

The captured live Linux state is stronger evidence for this boot: i915 reports DDI/PHY A, two eDP lanes, a 270 MHz port clock, and 24 bpp. The register field definitions in upstream Linux encode lane width in bits 3:1: `0x8A000106` has width code 3 (four lanes), while the two-lane code is 1. NootedGreen's `hwSetMode()` writes `0x8A000106` on the non-real-TGL path, so that Dell/Raptor Lake assumption conflicts with the Yoga's live two-lane state. A separate comment in `kern_gen11.cpp` labels this same value as two lanes; the register encoding shows that comment is wrong. Treat the write and its call order as a porting blocker; do not enable the shared path on the Yoga until a reversible per-target path is designed and validated. The source's DBUF, ABOX, and memory-channel assumptions also remain unverified.

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

The user separately confirms both USB-C ports charge the laptop. USB-C plug orientation was not recorded. The built-in Bluetooth, fingerprint reader, and Intel USB Bridge appeared at `3-10`, `3-6`, and `3-8` respectively, each at 12 Mbit/s. These Linux paths are evidence for a later map, not an OpenCore USB map. The appearance of USB-C traffic through PCI `0000:00:0d.0` does not establish Thunderbolt/USB4 PCIe topology; that remains uncaptured.

## Safe next work

1. Determine how Linux selected the active panel despite the VBT's EDID-based primary type and missing AUO PnP match; capture the live firmware panel type if it can be obtained safely. Keep the VBT binary private.
2. Trace `setupOptimalLaneCount()`, register staging, and `hwSetMode()` against the exact patched Tiger Lake driver and NootedGreen call order. In this source revision, `-ngreenkeepefi` gates one display-register staging block, but `hwSetMode()` still separately writes `0x8A000106` on every non-real-TGL path. Do not treat that boot argument as a Yoga two-lane safeguard; design a Yoga-specific, reversible path and capture the Yoga's pre-macOS register state before any hardware test.
3. Resolve the available-versus-enabled topology reporting and identify what the Tiger Lake driver expects before changing EU/L3 overrides.
4. Finish Yoga I2C/GPIO resource analysis; verify whether USB-C orientation changes any captured path, derive the OpenCore USB map, and inspect Thunderbolt separately.
5. Only then generate separate recovery and acceleration configurations. No installer, EFI generation, or internal-disk operation is part of this evidence-analysis step.
