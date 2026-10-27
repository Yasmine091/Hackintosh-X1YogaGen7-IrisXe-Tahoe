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

## Safe next work

1. Determine how Linux selected the active panel despite the VBT's EDID-based primary type and missing AUO PnP match; capture the live firmware panel type if it can be obtained safely. Keep the VBT binary private.
2. Trace `hwSetMode()` and the relevant `TRANS_DDI_FUNC_CTL_A` field against the exact patched Tiger Lake driver and NootedGreen call order. Remove the contradictory source comment and design a Yoga-specific, reversible path that preserves or correctly programs the observed two-lane state before any hardware test.
3. Resolve the available-versus-enabled topology reporting and identify what the Tiger Lake driver expects before changing EU/L3 overrides.
4. Finish Yoga I2C/GPIO resource analysis and USB port enumeration.
5. Only then generate separate recovery and acceleration configurations. No installer, EFI generation, or internal-disk operation is part of this evidence-analysis step.
