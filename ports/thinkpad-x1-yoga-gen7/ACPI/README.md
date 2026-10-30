# Yoga ACPI tables

These AML/ASL files are derived from the ThinkPad X1 Yoga Gen 7 ACPI capture. The raw DSDT/MADT and manifest remain private and are not tracked here.

The captured DSDT declares `PR00`–`PR63` as `Device` objects with `_HID=ACPI0007` and UIDs 0–63. The static APIC/MADT capture has 12 enabled processor entries, UIDs 0–11; higher entries are disabled or absent. This matches the i7-1265U's 12 logical processors.

| Table | Purpose | SHA-256 |
|---|---|---|
| `SSDT-CPU-STA.aml` | Hides `PR12`–`PR63` only when macOS reports `_OSI("Darwin")`; leaves UIDs 0–11 available and returns the original present status to other operating systems. | `ed4a1a63cbbbc963bb6c84fad8bca43f0924f9584d4b3805dae662a6b4317d68` |
| `SSDT-PLUG-ALT.aml` | Provides the Alder Lake `Processor()` compatibility objects and plugin-type property for macOS. It is based on the OpenCore `SSDT-PLUG-ALT` sample. | `64331ae5c240031fd00f73ab31e1116cd4f6128c0fb6eb5788e801b1f23a2b18` |
| `SSDT-RTCAWAC.aml` | Sets the RTC status flag for Darwin. It is not a CPU table. | `665933431fb49e3bf9097207f4ebf9da213cd60f36bc6e5d04d61edb30f87d89` |

## Validation and limits

- All three AML tables came from the live Yoga USB inspected on 2026-10-30; they differ from same-named Dell repository AML files.
- iASL 20251212 decompiled the tables and compiled the sources back byte-identically. `SSDT-PLUG-ALT` emits expected legacy `Processor()` warnings, with zero compile errors.
- The tables are enabled in the Yoga Recovery and post-install templates and included by the Recovery builder. This configuration reached macOS Recovery on the target once, according to the user's report.
- The CPU tables have not been proven to cause or fix the repeated Installer restart. The raw MADT disabled entries can explain `LocalApicId=255 Disabled` log lines; that text alone is not a boot error.
- The Recovery and post-install config templates also delete only the captured Lenovo `SSDT` `ProjSsdt` (OEM table ID `ProjSsdt`, length 4731). Its direct reference to conditional `\_SB.PC00.XHCI.RHUB.HS01` produced `AE_NOT_FOUND` in an earlier boot; the error was absent from a later user-reported boot. This targeted deletion is intended to omit that faulty table. OpenCore applies ACPI table deletion regardless of which OS is selected in its picker, so it can affect Kubuntu when booted through OpenCore. It does not modify the firmware table or Kubuntu's EFI.
- The deleted table is the Yoga firmware's table, not a Dell table. The deletion has not been shown to cause or fix the later installer restart.
- Do not use these on another laptop without auditing its ACPI namespace and MADT. Do not edit the captured firmware tables in place.
