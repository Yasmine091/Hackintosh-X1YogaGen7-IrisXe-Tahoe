# Yoga Gen 7 target-side evidence analysis

The user ran the guarded Linux inventory and firmware exporter on the ThinkPad. The evidence was returned on the 64 GB USB and reviewed on the main PC. Its manifest lists 51 files and no missing captures. Raw ACPI and VBT files are not included in this repository.

## GPU and internal display

- Linux identifies Intel GPU 8086:46A8 at 0000:00:02.0, revision 0C, using i915.
- The captured DSDT places GFX0 below \_SB.PC00 with _ADR=0x00020000, consistent with that PCI function. An OpenCore IORegistry path and macOS driver binding have not been tested.
- i915 reports one available slice, six available subslices, 16 available EUs per subslice, and 96 available EUs total. A separate all-zero enabled-SSEU snapshot was taken while the display pipe was active. It is not evidence of fused topology or an absent GPU. Active render topology and L3 bank count remain unresolved.
- The active Linux display is pipe A through DDI/PHY A at 1920×1200, 24 bpp, two eDP lanes, and a 270000 kHz port clock. This is Linux's live state, not proof that Apple's driver can preserve or retrain the Yoga panel.
- PSR is supported by the sink and PSR2 was enabled during capture. DMC firmware i915/adlp_dmc.bin v2.20 loaded in Kubuntu; that does not establish a macOS firmware requirement.
- The VBT export is 9216 bytes, begins with the expected $VBT signature, and its header strings identify ALDERLAKE-P. The active panel/link configuration has not yet been decoded. The VBT is board-specific display configuration; see https://docs.kernel.org/6.13/gpu/i915.html.

The current non-real-TGL hwSetMode() path writes TRANS_DDI_FUNC_CTL_A=0x8A000106, a four-lane assumption documented for the XPS. That conflicts with the Yoga's two-lane Linux state. Treat this as a porting blocker: do not enable the shared path on the Yoga until the register field, call order, and a per-target/reversible setting are traced. The source's DBUF, ABOX, and memory-channel assumptions also remain unverified.

## ACPI paths

The DSDT/SSDT disassembly identifies these target paths and firmware HID mappings:

| Function | ACPI path | Evidence |
|---|---|---|
| Integrated graphics | \_SB.PC00.GFX0 | _ADR=0x00020000, matches PCI 00:02.0 |
| Synaptics touchpad | \_SB.PC00.I2C0.TPD0 | I2C0 at PCI 00:15.0; firmware HID table includes 06CB:CEB3 / SYNA8016, address 0x2C |
| Wacom pen/touch | \_SB.PC00.I2C1.TPL1 | I2C1 at PCI 00:15.1; firmware HID table includes 056A:5308 / WACF2200, address 0x0A |

The devices use PNP0C50. The firmware's _INI and _CRS methods populate HID and GPIO/interrupt resources dynamically, so the exact runtime interrupt mapping still needs careful review. SSDT10 exposes display children DD1F/DD2F and brightness methods; those methods do not prove macOS brightness control.

## Safe next work

1. Decode the VBT blocks that select the internal panel and eDP link configuration; keep the binary private.
2. Trace hwSetMode() and the relevant TRANS_DDI_FUNC_CTL_A bit encoding against the exact patched Tiger Lake driver and NootedGreen call order. Decide whether a Yoga-specific lane setting can be isolated from Dell/Raptor Lake behavior.
3. Resolve the available-versus-enabled topology reporting and identify what the Tiger Lake driver expects before changing EU/L3 overrides.
4. Finish Yoga I2C/GPIO resource analysis and USB port enumeration.
5. Only then generate separate recovery and acceleration configurations. No installer, EFI generation, or internal-disk operation is part of this evidence-analysis step.
